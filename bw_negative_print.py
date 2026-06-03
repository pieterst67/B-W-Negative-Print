#!/usr/bin/env python3
import argparse
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image


PAPER_GRADE_SETTINGS = {
    "off": {
        "k": None,
        "highlight_rolloff_knee": 0.00,
        "highlight_rolloff_strength": 0.0,
    },
    "1": {
        "k": 3.0,
        "highlight_rolloff_knee": 0.06,
        "highlight_rolloff_strength": 0.7,
    },
    "2": {
        "k": 5.0,
        "highlight_rolloff_knee": 0.10,
        "highlight_rolloff_strength": 1.0,
    },
    "3": {
        "k": 7.5,
        "highlight_rolloff_knee": 0.14,
        "highlight_rolloff_strength": 1.35,
    },
}


def sigmoid01(x: np.ndarray, k: float) -> np.ndarray:
    s = 1.0 / (1.0 + np.exp(-k * (x - 0.5)))
    s0 = 1.0 / (1.0 + np.exp(k * 0.5))
    s1 = 1.0 / (1.0 + np.exp(-k * 0.5))
    return (s - s0) / (s1 - s0)


def apply_highlight_rolloff(x: np.ndarray, knee: float, strength: float) -> np.ndarray:
    if knee <= 0.0 or strength <= 0.0:
        return x

    y = x.copy()
    mask = x < knee
    y[mask] = knee * np.exp((x[mask] - knee) / (knee * strength))
    return y


def apply_paper_curve(x: np.ndarray, paper_grade: str) -> np.ndarray:
    k = PAPER_GRADE_SETTINGS[paper_grade]["k"]

    if k is None:
        return x

    return sigmoid01(x, k)


def copy_metadata(input_path: Path, output_path: Path) -> None:
    if shutil.which("exiftool") is None:
        print("WARNING: exiftool not found; metadata was not copied.")
        return

    subprocess.run(
        [
            "exiftool",
            "-overwrite_original",
            "-TagsFromFile",
            str(input_path),
            "-all:all",
            "-icc_profile:all=",
            str(output_path),
        ],
        check=True,
    )


def convert_negative_simple(
    input_path: Path,
    output_path: Path,
    base_percentile: float = 99.9,
    low_percentile: float = 0.5,
    high_percentile: float = 99.7,
    shadow_margin: float = 0.03,
    highlight_margin: float = 0.10,
    print_exposure_stops: float = 0.0,
    paper_grade: str = "2",
    highlight_rolloff_knee: float | None = None,
    highlight_rolloff_strength: float | None = None,
    print_dmax: float = 2.0,
    output_gamma: float = 2.2,
    output_margin: int = 8,
    copy_exif: bool = True,
    compression: str = "raw",
) -> None:
    img = Image.open(input_path)
    arr = np.asarray(img)

    if arr.ndim != 2:
        raise ValueError("Input must be a grayscale TIFF.")

    if not np.issubdtype(arr.dtype, np.integer):
        raise ValueError("Input must contain integer pixel data.")

    maxv = float(np.iinfo(arr.dtype).max)

    t = arr.astype(np.float32) / maxv
    t = np.maximum(t, 1e-6)

    t_base = float(np.percentile(t, base_percentile))
    t_base = max(t_base, 1e-6)

    d_neg = np.log10(t_base / t)
    d_neg = np.maximum(d_neg, 0.0)

    d_lo = float(np.percentile(d_neg, low_percentile))
    d_hi = float(np.percentile(d_neg, high_percentile))

    if d_hi <= d_lo + 1e-6:
        raise ValueError("Density range too small.")

    density_span = d_hi - d_lo
    d_lo_m = d_lo - shadow_margin * density_span
    d_hi_m = d_hi + highlight_margin * density_span

    exposure_shift = print_exposure_stops * np.log10(2.0)
    x = (d_hi_m - d_neg + exposure_shift) / (d_hi_m - d_lo_m)

    settings = PAPER_GRADE_SETTINGS[paper_grade]

    if highlight_rolloff_knee is None:
        highlight_rolloff_knee = settings["highlight_rolloff_knee"]

    if highlight_rolloff_strength is None:
        highlight_rolloff_strength = settings["highlight_rolloff_strength"]

    x = apply_highlight_rolloff(
        x,
        knee=highlight_rolloff_knee,
        strength=highlight_rolloff_strength,
    )

    x = np.clip(x, 0.0, 1.0)

    x = apply_paper_curve(x, paper_grade)
    x = np.clip(x, 0.0, 1.0)

    d_print = x * print_dmax

    y = 10.0 ** (-d_print)

    y_black = 10.0 ** (-print_dmax)
    y = (y - y_black) / (1.0 - y_black)

    m = output_margin / 65535.0
    y = np.clip(y, m, 1.0 - m)

    out = y ** (1.0 / output_gamma)

    out16 = (out * 65535.0 + 0.5).astype(np.uint16)
    dpi = img.info.get("dpi", (300, 300))

    output_path.parent.mkdir(parents=True, exist_ok=True)

    save_kwargs = {
        "format": "TIFF",
        "dpi": dpi,
    }

    if compression:
        save_kwargs["compression"] = compression

    Image.fromarray(out16, mode="I;16").save(output_path, **save_kwargs)

    if copy_exif:
        copy_metadata(input_path, output_path)


def find_input_files(input_dir: Path, patterns: list[str], recursive: bool) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()

    for pattern in patterns:
        iterator = input_dir.rglob(pattern) if recursive else input_dir.glob(pattern)
        for path in iterator:
            if path.is_file():
                resolved = path.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    files.append(path)

    return sorted(files)


def convert_with_args(src: Path, dst: Path, args: argparse.Namespace) -> None:
    convert_negative_simple(
        input_path=src,
        output_path=dst,
        base_percentile=args.base_percentile,
        low_percentile=args.low_percentile,
        high_percentile=args.high_percentile,
        shadow_margin=args.shadow_margin,
        highlight_margin=args.highlight_margin,
        print_exposure_stops=args.print_exposure_stops,
        paper_grade=args.paper_grade,
        highlight_rolloff_knee=args.highlight_rolloff_knee,
        highlight_rolloff_strength=args.highlight_rolloff_strength,
        print_dmax=args.print_dmax,
        output_gamma=args.output_gamma,
        output_margin=args.output_margin,
        copy_exif=not args.no_metadata,
        compression=args.compression,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Density/log B&W negative inversion with optional paper curve, grade-aware highlight roll-off and batch processing."
    )

    parser.add_argument("input", help="Input TIFF file or input directory.")
    parser.add_argument("output", help="Output TIFF file or output directory.")

    parser.add_argument("--base-percentile", type=float, default=99.9)
    parser.add_argument("--low-percentile", type=float, default=0.5)
    parser.add_argument("--high-percentile", type=float, default=99.7)

    parser.add_argument("--shadow-margin", type=float, default=0.03)
    parser.add_argument("--highlight-margin", type=float, default=0.10)

    parser.add_argument(
        "--print-exposure-stops",
        type=float,
        default=0.0,
        help="Darkroom-style print exposure. Positive values darken the print; negative values lighten it.",
    )
    parser.add_argument("--paper-grade", choices=["off", "1", "2", "3"], default="2")

    parser.add_argument("--highlight-rolloff-knee", type=float, default=None)
    parser.add_argument("--highlight-rolloff-strength", type=float, default=None)

    parser.add_argument("--print-dmax", type=float, default=2.0)
    parser.add_argument("--output-gamma", type=float, default=2.2)
    parser.add_argument("--output-margin", type=int, default=8)

    parser.add_argument("--compression", default="raw")
    parser.add_argument("--no-metadata", action="store_true")

    parser.add_argument(
        "--pattern",
        action="append",
        default=None,
        help="Input file pattern. Can be repeated. Default: *.tif, *.tiff, *.TIF, *.TIFF",
    )
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--suffix", default="_converted")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--stop-on-error", action="store_true")

    args = parser.parse_args()

    input_path = Path(args.input).expanduser()
    output_path = Path(args.output).expanduser()

    if input_path.is_dir():
        patterns = args.pattern or ["*.tif", "*.tiff", "*.TIF", "*.TIFF"]
        output_path.mkdir(parents=True, exist_ok=True)

        files = find_input_files(input_path, patterns, args.recursive)

        if not files:
            raise SystemExit("No input TIFF files found.")

        done = 0
        skipped = 0
        failed = 0

        for src in files:
            rel = src.relative_to(input_path) if args.recursive else Path(src.name)
            dst = output_path / rel.parent / f"{rel.stem}{args.suffix}.tif"

            if src.resolve() == dst.resolve():
                print(f"SKIP same input/output: {src}")
                skipped += 1
                continue

            if dst.exists() and not args.overwrite:
                print(f"SKIP exists: {dst}")
                skipped += 1
                continue

            try:
                print(f"PROCESS {src} -> {dst}")
                convert_with_args(src, dst, args)
                done += 1
            except Exception as exc:
                failed += 1
                print(f"ERROR {src}: {exc}")
                if args.stop_on_error:
                    raise

        print()
        print(f"Done: {done}, skipped: {skipped}, failed: {failed}")

        if failed:
            raise SystemExit(1)

    else:
        if output_path.is_dir():
            dst = output_path / f"{input_path.stem}{args.suffix}.tif"
        elif output_path.suffix:
            dst = output_path
        else:
            output_path.mkdir(parents=True, exist_ok=True)
            dst = output_path / f"{input_path.stem}{args.suffix}.tif"

        if dst.exists() and not args.overwrite:
            raise SystemExit(f"Output exists. Use --overwrite to replace: {dst}")

        print(f"PROCESS {input_path} -> {dst}")
        convert_with_args(input_path, dst, args)


if __name__ == "__main__":
    main()

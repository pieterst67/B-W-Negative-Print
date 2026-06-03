# B&W Negative Print

A Python tool for converting linear black-and-white negative scans into positive, print-like TIFF files.

The script is intended as a technical starting point for scanned B&W negatives. It performs inversion in photographic density/log space rather than using a simple `1 - pixel` inversion.

## Features

* Converts linear positive scans of B&W negatives to positive TIFF files
* Uses density/log-domain inversion
* Optional paper/emulsion contrast curves: `off`, `1`, `2`, `3`
* Grade-aware highlight roll-off
* Darkroom-style print exposure adjustment in stops
* Highlight and shadow margin controls
* Batch processing for folders
* Optional recursive folder processing
* Custom output suffix, such as `_inverted`
* Preserves DPI metadata
* Optionally copies EXIF/TIFF metadata with ExifTool
* Saves 16-bit grayscale TIFF output

## Concept

The script assumes that the input scan is a linear positive scan of a B&W negative.

Processing order:

```text
linear scan transmittance
→ convert transmittance to negative density
→ invert in density/log space
→ apply highlight roll-off
→ apply optional paper/emulsion curve
→ convert simulated print density to luminance
→ encode to Gamma 2.2
→ save 16-bit TIFF
```

This follows the photographic principle that film and paper response are better described using density and log exposure than by simple pixel subtraction.

Reference:

https://www.kodak.com/content/products-brochures/Film/Basic-Photographic-Sensitometry-Workbook.pdf

## Requirements

* Python 3
* NumPy
* Pillow
* Optional: ExifTool for metadata copying

Python virtual environments:

https://docs.python.org/3/library/venv.html

NumPy:

https://numpy.org/

Pillow:

https://pillow.readthedocs.io/

ExifTool:

https://exiftool.org/

## Installation on macOS

Create and activate a virtual environment:

```bash
python3 -m venv ~/Documents/negscan-env
source ~/Documents/negscan-env/bin/activate
```

Install Python dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install numpy pillow
```

Optional metadata support:

```bash
brew install exiftool
```

Save the script somewhere outside the virtual environment, for example:

```text
~/Documents/negscan-tools/bw_negative_print.py
```

## Basic Usage

Single file:

```bash
python ~/Documents/negscan-tools/bw_negative_print.py input.tif output.tif
```

Single file with output folder:

```bash
python ~/Documents/negscan-tools/bw_negative_print.py input.tif ~/Pictures/converted
```

This produces:

```text
input_inverted.tif
```

## Batch Processing

Process all TIFF files in a folder:

```bash
python ~/Documents/negscan-tools/bw_negative_print.py \
  ~/Pictures/Negatives/raw \
  ~/Pictures/Negatives/converted
```

Process recursively:

```bash
python ~/Documents/negscan-tools/bw_negative_print.py \
  ~/Pictures/Negatives/raw \
  ~/Pictures/Negatives/converted \
  --recursive
```

Overwrite existing output files:

```bash
python ~/Documents/negscan-tools/bw_negative_print.py \
  ~/Pictures/Negatives/raw \
  ~/Pictures/Negatives/converted \
  --overwrite
```

Use a custom filename suffix:

```bash
python ~/Documents/negscan-tools/bw_negative_print.py \
  ~/Pictures/Negatives/raw \
  ~/Pictures/Negatives/converted \
  --suffix _grade2
```

Example result:

```text
raw0006.tif → raw0006_grade2.tif
```

## Paper Grade

The paper grade controls the optional paper/emulsion curve.

```bash
--paper-grade off
--paper-grade 1
--paper-grade 2
--paper-grade 3
```

Suggested use:

```bash
python bw_negative_print.py input.tif output.tif --paper-grade 2
```

Meaning:

```text
off     density/log inversion only
grade 1 softer contrast
grade 2 normal contrast
grade 3 harder contrast
```

## Print Exposure

The print exposure parameter simulates darkroom enlarger exposure.

```bash
--print-exposure-stops 0.3
```

Positive values darken the print:

```bash
--print-exposure-stops 0.5
```

Negative values lighten the print:

```bash
--print-exposure-stops -0.5
```

This behavior is intentional: in darkroom printing, more paper exposure makes the print darker.

## Test Strip Example

Generate digital equivalents of darkroom test strips:

```bash
python bw_negative_print.py raw0006.tif raw0006_m05.tif --paper-grade 2 --print-exposure-stops -0.5
python bw_negative_print.py raw0006.tif raw0006_000.tif --paper-grade 2 --print-exposure-stops 0
python bw_negative_print.py raw0006.tif raw0006_p05.tif --paper-grade 2 --print-exposure-stops 0.5
```

## Highlight Protection

The script has two highlight-related controls.

### Highlight Margin

```bash
--highlight-margin 0.10
```

This expands the dense-negative highlight endpoint before normalization. It reduces the chance that dense negative areas are mapped directly to paper white.

Higher values preserve more highlight detail but may make highlights flatter.

Typical values:

```text
0.05  mild protection
0.10  normal protection
0.20  strong protection
```

### Highlight Roll-off

```bash
--highlight-rolloff-knee 0.10
--highlight-rolloff-strength 1.0
```

The roll-off compresses highlights smoothly before clipping. This is intended to avoid hard highlight cutoff and to approximate the toe behavior of photographic paper.

If these parameters are not supplied, the script uses grade-aware defaults.

Suggested defaults:

```text
paper-grade off  no roll-off
paper-grade 1    mild roll-off
paper-grade 2    normal roll-off
paper-grade 3    stronger roll-off
```

Manual example:

```bash
python bw_negative_print.py input.tif output.tif \
  --paper-grade 3 \
  --highlight-rolloff-knee 0.18 \
  --highlight-rolloff-strength 1.6
```

## Shadow Protection

```bash
--shadow-margin 0.03
```

This expands the thin-negative shadow endpoint before normalization. It can help avoid shadow clipping.

Typical values:

```text
0.02  mild
0.03  normal
0.05  strong
```

## Density Range Percentiles

The script estimates the useful negative density range using percentiles.

```bash
--low-percentile 0.5
--high-percentile 99.7
```

For difficult negatives, increasing `--high-percentile` can help preserve dense-negative highlight detail:

```bash
--high-percentile 99.99
```

or:

```bash
--high-percentile 100
```

Using `100` uses the actual maximum density value, which may be sensitive to dust, scratches or scan defects.

## Print Dmax

```bash
--print-dmax 2.0
```

Controls the simulated maximum print density.

Lower values produce a flatter print:

```bash
--print-dmax 1.8
```

Higher values produce deeper blacks and stronger contrast:

```bash
--print-dmax 2.2
```

## Output Gamma

The output is gamma encoded, defaulting to Gamma 2.2:

```bash
--output-gamma 2.2
```

When opening the result in Photoshop, assign:

```text
Gray Gamma 2.2
```

The script does not currently embed the output ICC profile.

## Output Margin

```bash
--output-margin 8
```

Prevents exact digital black and white values in the output TIFF.

For less endpoint protection:

```bash
--output-margin 1
```

For more endpoint protection:

```bash
--output-margin 16
```

## Metadata

By default, the script attempts to copy metadata using ExifTool and removes the source ICC profile from the output.

This is intentional because the input is a linear negative scan while the output is a Gamma 2.2 positive image.

Disable metadata copying:

```bash
--no-metadata
```

## Compression

Default:

```bash
--compression raw
```

This saves uncompressed TIFF data.

Other TIFF compression modes may work depending on Pillow and the installed TIFF support, for example:

```bash
--compression tiff_lzw
```

or:

```bash
--compression tiff_adobe_deflate
```

TIFF support in Pillow:

https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html

## Recommended Starting Commands

Normal grade 2 conversion:

```bash
python bw_negative_print.py input.tif output.tif \
  --paper-grade 2
```

More highlight-safe conversion:

```bash
python bw_negative_print.py input.tif output.tif \
  --paper-grade 2 \
  --high-percentile 99.99 \
  --highlight-margin 0.15
```

Softer print:

```bash
python bw_negative_print.py input.tif output.tif \
  --paper-grade 1 \
  --print-dmax 1.8
```

Harder print with stronger highlight roll-off:

```bash
python bw_negative_print.py input.tif output.tif \
  --paper-grade 3 \
  --highlight-rolloff-knee 0.16 \
  --highlight-rolloff-strength 1.5
```

Batch conversion:

```bash
python bw_negative_print.py ~/Pictures/Negatives/raw ~/Pictures/Negatives/converted \
  --paper-grade 2 \
  --suffix _inverted
```

## Important Notes

The input should be:

```text
linear
positive scan of the negative
16-bit grayscale TIFF
without automatic scanner tonal correction
```

The script is not intended for already inverted positives.

The script is not an exact emulation of a specific photographic paper, developer or enlarger. Exact paper emulation would require measured film and paper characteristic curves.

The output is intended as a technically consistent starting point for further editing, spotting, dodging, burning, sharpening and printing.

## Limitations

* No dust removal
* No local dodging or burning
* No automatic cropping
* No embedded output ICC profile
* Paper grades are approximations
* Highlight roll-off is an approximation, not a measured paper curve
* Scanner clipping cannot be recovered

## License

MIT License:

https://opensource.org/license/mit


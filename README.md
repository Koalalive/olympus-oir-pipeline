# olympus-oir-pipeline

Convert **Olympus/Evident `.oir`** confocal microscopy files to **OME-TIFF**,
fix channel metadata, render RGB merges, and view multi-channel stacks.

Pure Python. No Java, no Fiji required for conversion.

## Why

`.oir` is a closed binary container from FluoView / cellSens. The original
tooling around this workflow used a compiled Java helper (`Oir2Ome`) whose source
was never kept. This repo replaces it with `oirfile` (BSD-3, pure Python) so the
whole chain is reproducible and modifiable.

## Install

```bash
pip install -r requirements.txt
```

## Quick start

```bash
# 1. Look at what's inside (shape, dtype, channels, companion files)
python scripts/convert_oir.py /path/to/oir --info

# 2. Optional: describe your channels
cp scripts/channels.cfg.example scripts/channels.cfg
#    edit: 0|name=DAPI|color=0000FF|ex=405|em=470

# 3. Convert everything to OME-TIFF
python scripts/convert_oir.py /path/to/oir -o ome --cfg scripts/channels.cfg

# 4. Inspect / relabel / compress
python scripts/ome_channels.py info ome/
python scripts/ome_channels.py set ome/ --ch "1 name=CD31:color=FF0000"
python scripts/ome_channels.py compress ome/ --compress lzw

# 5. Render or view
python scripts/make_rgb.py ome/ merge_rgb/
python scripts/napari_channels.py ome/1-2.ome.tif
```

On Windows you can also double-click `scripts/convert.bat`,
`scripts/napari_channels.bat`, `scripts/open_in_fiji.bat`.

## Output

| Stage | Output |
|---|---|
| `convert_oir.py` | `ome/<name>.ome.tif` — uint16, CYX, zlib, physical pixel size |
| `make_rgb.py` | `merge_rgb/<name>_merge.png` + `_merge.tif` — 8-bit RGB |
| `ome_channels.py render` | one PNG preview with per-channel window/gamma |

## Verified behaviour

On real 4096×4096, 2-channel, 12-bit OIR files:

- read + write to zlib OME-TIFF: **~0.4 s** per 68 MB file
- output ~27 MB (≈40% of raw)
- OME-XML carries `PhysicalSizeX/Y` from `coord_scales` (e.g. 0.0777 µm/px)

## Gotchas

- OIR metadata can list **more channels than pixel planes** — map by order.
- `_000N.oir` files are usually **separate acquisitions**, not chunks
  (Bio-Formats companions are `basename_00001`, no extension).
- Truncated `.oir` loses its trailing index → partial/blank planes without error.
- `.oir` is read-only; this project never writes it.

## License

MIT

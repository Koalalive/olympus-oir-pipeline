---
name: olympus-oir-pipeline
description: Use when working with Olympus/Evident .oir confocal microscopy files on Windows - converting OIR/POIR/MPOIR to OME-TIFF, inspecting or correcting channel names/colors/excitation-emission in OME metadata, rendering multi-channel RGB composites, or opening multi-channel stacks in napari or Fiji. Triggers - .oir, OIR, cellSens, FluoView, FV1000, FV3000, confocal raw data, OME-TIFF channel LUT, merge RGB.
---

# Olympus OIR Pipeline

## Overview

`.oir` is Olympus/Evident FluoView / cellSens raw data: one binary container
(`OLYMPUSRAWFORMAT` magic + pixel blocks + a block index at the **end** of file).
Read it with **oirfile** (pure Python, BSD-3, no JVM) or **Bio-Formats**.
**Never write `.oir`** — always export to OME-TIFF.

## When to Use

- Convert `.oir` / `.poir` / `.mpoir` to OME-TIFF
- Fix channel names, colors, Ex/Em, pinhole in the OME-XML
- Build an 8-bit RGB merge preview
- Open multi-channel stacks with correct per-channel LUTs
- NOT for other formats — use Bio-Formats directly for those

## Quick Reference

| Task | Command |
|---|---|
| Inspect metadata | `python scripts/convert_oir.py DIR --info` |
| Convert folder | `python scripts/convert_oir.py DIR -o ome --cfg scripts/channels.cfg` |
| Channel report | `python scripts/ome_channels.py info ome/` |
| Relabel channels | `python scripts/ome_channels.py set ome/ --ch "0 name=DAPI:color=0000FF:ex=405:em=470"` |
| Compress only | `python scripts/ome_channels.py compress ome/ --compress lzw` |
| RGB merge | `python scripts/make_rgb.py ome/ merge_rgb/` |
| napari view | `python scripts/napari_channels.py ome/1-2.ome.tif` |
| Fiji view | `scripts/open_in_fiji.bat <image>` |

## Workflow

1. `pip install -r requirements.txt`
2. `convert_oir.py DIR --info` — confirm shape, dtype, bits, channels
3. Copy `scripts/channels.cfg.example` to `scripts/channels.cfg`, set names/colors
4. `convert_oir.py DIR` — writes OME-TIFF (zlib, ~40% of raw size)
5. `ome_channels.py info ome/` — check per-channel saturation flags
6. Render (`make_rgb.py`) or open (`napari_channels.bat` / `open_in_fiji.bat`)

## Critical Rules

- **Never modify `.oir`.** Read-only; export, never round-trip.
- **Channel/plane mismatch is normal.** OIR metadata may list more channels than
  pixel planes (e.g. 3 entries, 2 planes; one is often a transmitted-light or
  stale entry). Map planes **by order**; verify with `--info` before labelling.
- **`_000N.oir` are usually NOT chunks.** Bio-Formats groups companions only as
  `basename_00001` (5 digits, **no extension**). Check `companion_files`; if
  empty, convert each file separately — do not concatenate.
- **`.oir` > 1 GB** may need companion chunks in the same folder.
- **Truncated `.oir`** loses its end-of-file index. Both readers may return
  partial/zero-filled planes without failing — always compare `--info` dims
  against cellSens.

## Scripts

| File | Purpose |
|---|---|
| `convert_oir.py` | OIR -> OME-TIFF (oirfile; replaces the Java `Oir2Ome`) |
| `ome_channels.py` | `info` / `set` / `compress` / `render` for OME-TIFF |
| `make_rgb.py` | multi-channel -> 8-bit RGB PNG/TIFF merge |
| `napari_channels.py` | napari viewer, one layer per channel |
| `open_merge.ijm` | ImageJ macro for composite view + auto contrast |
| `channels.cfg.example` | per-channel name/color/ex/em template |
| `*.bat` | Windows double-click wrappers (use `pythonw` for GUI) |

## Windows Notes

- Disc-copied folder names may contain **Cyrillic homoglyphs** (e.g. `Usb Drіve`
  where `і` is U+0456, not ASCII `i`). Pass paths via variables or drag-and-drop;
  never retype them.
- Encoding: `.bat` files here are ASCII-only to avoid GBK/UTF-8 confusion.
- Pixel size comes from `coord_scales` (µm). If absent, OME has no physical size
  and downstream area/thickness measurements will be wrong.

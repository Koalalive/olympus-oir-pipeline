#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
convert_oir.py -- Olympus/Evident .oir -> OME-TIFF (pure Python, no Java).

Replaces the original Java `Oir2Ome` tool (which shipped only as .class files
with no source). Uses `oirfile` (BSD-3, pure Python) to read OIR/POIR/MPOIR and
`tifffile` to write OME-TIFF with channel names, colors and wavelengths taken
from an optional channels.cfg.

Usage
  python convert_oir.py <path>                  convert every .oir in a folder
  python convert_oir.py <path> --info           print metadata only, no output
  python convert_oir.py <file.oir> -o out/      convert one file into out/
  python convert_oir.py <path> --cfg channels.cfg --compress lzw

channels.cfg format (one channel per line, '#' comments allowed)
  0|name=DAPI|color=0000FF|ex=405|em=470
  1|name=CD31|color=FF0000|ex=561|em=620

Notes
  * ex/em/pinhole are *acquisition metadata labels*. Changing them only changes
    tags, never the pixels.
  * Files > 1 GB in OIR may be split into companion chunks; oirfile handles
    multifile OIR when all chunks sit in the same folder.
"""

import argparse
import glob
import os
import sys

import numpy as np
import tifffile
from oirfile import OirFile

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# ----------------------------------------------------------------- config
def parse_cfg(path):
    """Parse channels.cfg -> {channel_index: {key: value}}."""
    cfg = {}
    if not path or not os.path.exists(path):
        return cfg
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if not parts or not parts[0].isdigit():
                continue
            spec = {}
            for kv in parts[1:]:
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    spec[k.strip().lower()] = v.strip()
            cfg[int(parts[0])] = spec
    return cfg


def hex_to_ome_color(h):
    """'#RRGGBB' / 'RRGGBB' -> signed 32-bit int as OME expects."""
    v = h.lstrip("#")
    if len(v) == 8:
        v = v[2:]
    if len(v) != 6:
        raise ValueError("color must be RRGGBB, got: %s" % h)
    rgba = (int(v[0:2], 16) << 24) | (int(v[2:4], 16) << 16) | (int(v[4:6], 16) << 8) | 0xFF
    return rgba - (1 << 32) if rgba >= (1 << 31) else rgba


# ----------------------------------------------------------------- oir read
def load_oir(path):
    """Return (array CYX, channel dicts, coord_scales, meta)."""
    with OirFile(path, memmap=True) as o:
        arr = o.asarray()
        if arr.ndim == 2:
            arr = arr[None, ...]
        n = arr.shape[0]

        chans = []
        src = list(getattr(o, "channels", []) or [])
        for i in range(n):
            c = src[i] if i < len(src) else None
            chans.append({
                "name": getattr(c, "name", None) or ("C%d" % i),
                "ex": getattr(c, "start_wavelength", None),
                "em": getattr(c, "end_wavelength", None),
            })

        scales = dict(getattr(o, "coord_scales", {}) or {})
        meta = {
            "dims": tuple(getattr(o, "dims", ())),
            "dtype": str(arr.dtype),
            "bits": getattr(o, "bitspersample", None),
            "color": getattr(o, "colortype", None),
            "producer": getattr(o, "producer", None),
            "datetime": getattr(o, "datetime", None),
            "companions": tuple(getattr(o, "companion_files", ()) or ()),
            "units": getattr(o, "coord_units", None),
        }
    return arr, chans, scales, meta


def apply_cfg(chans, cfg):
    """Overlay channels.cfg onto discovered channels."""
    for i, spec in cfg.items():
        if i >= len(chans):
            print("  ! cfg channel %d out of range (%d channels)" % (i, len(chans)))
            continue
        if "name" in spec:
            chans[i]["name"] = spec["name"]
        if "color" in spec:
            chans[i]["color"] = spec["color"]
        for key in ("ex", "em"):
            if key in spec:
                chans[i][key] = spec[key]
    return chans


def build_ome_meta(chans, scales):
    names, colors, exs, ems = [], [], [], []
    fallback = ["0000FF", "FF0000", "00FF00", "FF00FF", "00FFFF", "FFFF00"]
    for i, c in enumerate(chans):
        names.append(c.get("name") or ("C%d" % i))
        colors.append(hex_to_ome_color(c.get("color") or fallback[i % len(fallback)]))
        if c.get("ex") not in (None, ""):
            exs.append(float(c["ex"]))
        if c.get("em") not in (None, ""):
            ems.append(float(c["em"]))

    meta = {"axes": "CYX", "Channel": {"Name": names, "Color": colors}}
    sx = scales.get("X") or scales.get("x")
    sy = scales.get("Y") or scales.get("y")
    unit = "µm"
    if sx:
        meta["PhysicalSizeX"] = float(sx)
        meta["PhysicalSizeXUnit"] = unit
    if sy:
        meta["PhysicalSizeY"] = float(sy)
        meta["PhysicalSizeYUnit"] = unit
    # Only write wavelengths when EVERY channel has a value. Padding a partial
    # list would fabricate metadata for channels whose OIR entry is empty.
    if exs and len(exs) == len(chans):
        meta["Channel"]["ExcitationWavelength"] = exs
    elif exs:
        print("  note: partial Ex/Em (%d/%d channels), omitted to avoid false metadata"
              % (len(exs), len(chans)))
    if ems and len(ems) == len(chans):
        meta["Channel"]["EmissionWavelength"] = ems
    return meta


# ----------------------------------------------------------------- commands
def cmd_info(path):
    files = expand(path)
    if not files:
        print("no .oir found under %s" % path)
        return
    for p in files:
        try:
            arr, chans, scales, meta = load_oir(p)
            print()
            print("=" * 78)
            print(os.path.basename(p), "  (%.1f MB)" % (os.path.getsize(p) / 1e6))
            print("  dims=%s shape=%s dtype=%s bits=%s color=%s" % (
                meta["dims"], arr.shape, meta["dtype"], meta["bits"], meta["color"]))
            print("  producer=%s  datetime=%s" % (meta["producer"], meta["datetime"]))
            print("  scales=%s  companions=%s" % (
                {k: round(float(v), 4) for k, v in scales.items()}, meta["companions"]))
            for i, c in enumerate(chans):
                print("  ch%d  name=%-10s ex=%s em=%s" % (
                    i, c["name"], c.get("ex"), c.get("em")))
        except Exception as e:  # noqa: BLE001
            print("%s  ERROR %s: %s" % (os.path.basename(p), type(e).__name__, e))


def cmd_convert(path, outdir, cfg, compress, skip_existing):
    files = expand(path)
    if not files:
        print("no .oir found under %s" % path)
        return 1
    if outdir is None:
        outdir = os.path.join(os.path.dirname(os.path.abspath(files[0])), "ome")
    os.makedirs(outdir, exist_ok=True)

    ok = fail = 0
    for p in files:
        base = os.path.splitext(os.path.basename(p))[0]
        out = os.path.join(outdir, base + ".ome.tif")
        if skip_existing and os.path.exists(out):
            print("[skip] %s (exists)" % base)
            continue
        try:
            arr, chans, scales, meta = load_oir(p)
            chans = apply_cfg(chans, cfg)
            ome_meta = build_ome_meta(chans, scales)
            tifffile.imwrite(
                out, arr,
                ome=True,
                metadata=ome_meta,
                compression=compress,
                photometric="minisblack",
            )
            size = os.path.getsize(out) / 1e6
            print("[ok] %-24s %s  %.1f MB  ch=%d" % (
                base, arr.shape, size, arr.shape[0]))
            ok += 1
        except Exception as e:  # noqa: BLE001
            print("[FAIL] %-24s %s: %s" % (base, type(e).__name__, e))
            fail += 1

    print("\ndone: %d ok, %d failed -> %s" % (ok, fail, outdir))
    return 0 if fail == 0 else 2


# ----------------------------------------------------------------- helpers
def expand(path):
    if os.path.isdir(path):
        found = []
        for pattern in ("*.oir", "*.OIR", "*.poir", "*.POIR"):
            found.extend(glob.glob(os.path.join(path, pattern)))
        return sorted(set(found))
    return [path]


def main():
    ap = argparse.ArgumentParser(description="Convert Olympus .oir to OME-TIFF (pure Python).")
    ap.add_argument("path", help="a folder containing .oir files, or a single .oir")
    ap.add_argument("--info", action="store_true", help="print metadata only, do not convert")
    ap.add_argument("-o", "--out-dir", default=None, help="output folder (default: <src>/ome)")
    ap.add_argument("--cfg", default=None, help="channels.cfg path")
    ap.add_argument("--compress", default="zlib", choices=["zlib", "lzw", "deflate", "none"])
    ap.add_argument("--skip-existing", action="store_true")
    a = ap.parse_args()

    if a.info:
        cmd_info(a.path)
        return 0
    cfg = parse_cfg(a.cfg)
    comp = None if a.compress == "none" else a.compress
    return cmd_convert(a.path, a.out_dir, cfg, comp, a.skip_existing)


if __name__ == "__main__":
    sys.exit(main())

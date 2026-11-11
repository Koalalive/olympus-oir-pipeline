#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
把多通道 OME-TIFF 渲染成带颜色的合成图（8-bit RGB）。

- 16-bit OME-TIFF 原件不动，仍是无损主数据
- 每个通道用自己的颜色（读 OME-XML 里的 Channel Color，缺失则按顺序回退）
- 每个通道的显示区间按 0.5-99.8% 分位自动确定
- 输出 PNG（任何看图软件都能看）和 8-bit RGB TIFF

用法:
    python make_rgb.py <ome目录> [输出目录]
"""

import glob
import os
import re
import sys

import numpy as np
import tifffile
from PIL import Image

FALLBACK = [(0, 0, 255), (255, 0, 0), (0, 255, 0), (255, 0, 255), (0, 255, 255), (255, 255, 0)]


def read(path):
    with tifffile.TiffFile(path) as tf:
        arr = tf.series[0].asarray()
        desc = tf.pages[0].description or ""
    if arr.ndim == 2:
        arr = arr[None]
    return arr, desc


def parse(desc, n):
    names, colors = [], []
    for m in re.finditer(r"<Channel\b[^>]*>", desc):
        tag = m.group(0)
        nm = re.search(r'Name="([^"]*)"', tag)
        names.append(nm.group(1) if nm else "C%d" % (len(names) + 1))
        co = re.search(r'Color="(-?\d+)"', tag)
        if co:
            v = int(co.group(1)) & 0xFFFFFFFF
            colors.append(((v >> 24) & 255, (v >> 16) & 255, (v >> 8) & 255))
        else:
            colors.append(FALLBACK[len(colors) % len(FALLBACK)])
    while len(names) < n:
        names.append("C%d" % (len(names) + 1))
        colors.append(FALLBACK[len(colors) % len(FALLBACK)])
    return names[:n], colors[:n]


def render(arr, colors, gamma=1.0):
    h, w = arr.shape[1], arr.shape[2]
    rgb = np.zeros((h, w, 3), np.float32)
    info = []
    for i in range(arr.shape[0]):
        a = arr[i].astype(np.float32)
        lo, hi = np.percentile(a, (0.5, 99.8))
        hi = max(float(hi), float(lo) + 1.0)
        v = np.clip((a - lo) / (hi - lo), 0.0, 1.0) ** gamma
        c = np.array(colors[i], np.float32) / 255.0
        rgb += v[..., None] * c[None, None, :]
        info.append((lo, hi))
    return (np.clip(rgb, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8), info


def main(src, dst):
    os.makedirs(dst, exist_ok=True)
    files = sorted(glob.glob(os.path.join(src, "*.ome.tif")))
    print("found %d file(s)\n" % len(files))
    print("%-18s %-28s %-24s %s" % ("file", "channels", "colors(#hex)", "window(lo-hi)"))
    for p in files:
        arr, desc = read(p)
        names, colors = parse(desc, arr.shape[0])
        rgb, info = render(arr, colors)
        base = os.path.basename(p)[: -len(".ome.tif")]
        Image.fromarray(rgb).save(os.path.join(dst, base + "_merge.png"))
        tifffile.imwrite(os.path.join(dst, base + "_merge.tif"), rgb, photometric="rgb")

        chex = " ".join("#%02X%02X%02X" % c for c in colors)
        win = " ".join("%d-%d" % (int(lo), int(hi)) for lo, hi in info)
        print("%-18s %-28s %-24s %s" % (base, ",".join(names), chex, win))

    print("\noutput -> %s" % dst)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: make_rgb.py <ome_dir> [out_dir]")
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(src, "..", "merge_rgb")
    main(src, dst)

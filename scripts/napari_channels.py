#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
用 napari 打开多通道 OME-TIFF：按通道拆成独立图层，
自动套用 OME 里记录的颜色、按 0.5-99.8% 分位设显示范围。

每个图层在右侧面板里可以单独调：
  contrast limits (min/max)、Gamma、Colormap、不透明度、显隐
多层同时开 -> 就是 merge 视图（blending = additive）
"""

import os
import re
import sys

import numpy as np
import tifffile


def read_ome(path):
    with tifffile.TiffFile(path) as tf:
        arr = tf.series[0].asarray()
        desc = tf.pages[0].description or ""
    if arr.ndim == 2:
        arr = arr[None]
    return arr, desc


def parse_channels(desc, n):
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
            colors.append((255, 255, 255))
    while len(names) < n:
        names.append("C%d" % (len(names) + 1))
        colors.append((255, 255, 255))
    return names[:n], colors[:n]


def make_colormap(rgb, name):
    from napari.utils import Colormap
    return Colormap(
        [[0.0, 0.0, 0.0, 1.0],
         [rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0, 1.0]],
        name=name,
    )


def main(path):
    import napari

    arr, desc = read_ome(path)
    names, colors = parse_channels(desc, arr.shape[0])

    viewer = napari.Viewer(title=os.path.basename(path))
    for i in range(arr.shape[0]):
        a = arr[i]
        lo, hi = np.percentile(a, (0.5, 99.8))
        hi = max(float(hi), float(lo) + 1.0)
        viewer.add_image(
            a,
            name=names[i],
            colormap=make_colormap(colors[i], names[i]),
            contrast_limits=(float(lo), hi),
            blending="additive",
            gamma=1.0,
        )
    viewer.scale_bar.visible = True
    napari.run()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: napari_channels.py <image>")
    main(sys.argv[1])

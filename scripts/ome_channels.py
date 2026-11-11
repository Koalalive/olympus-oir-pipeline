#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ome_channels.py  --  OME-TIFF 通道参数查看/修改/预览

三种操作
  info   列出通道参数 + 实测灰度分布（用于定 LUT 窗口）
  set    修改通道名/颜色/激发发射波长/针孔/像素尺寸（只改元数据，不动像素）
  render 按指定颜色+窗口+gamma 生成 RGB 合成预览图，用来检查设置是否合适

用法
  python ome_channels.py info   <文件或目录>
  python ome_channels.py set    <文件或目录> --ch 0 name=DAPI:color=0000FF:ex=405:em=470
  python ome_channels.py set    <文件或目录> --ch 1 name=CD31:color=FF0000 --compress zlib
  python ome_channels.py render <文件> <out.png> --ch 0 color=0000FF:win=100,1200 --ch 1 color=FF0000:win=0,600

通道参数（--ch 后面用 : 分隔 key=value）
  name=CH1          通道名
  color=0000FF      颜色 RRGGBB 或 #RRGGBB
  ex=405            激发波长 nm
  em=470            发射波长 nm
  pinhole=120       针孔 um
  illum=Transmitted 照明方式 (Fluorescence/Transmitted/...)
  mode=WideField    采集模式 (WideField/LaserScanningConfocalMicroscopy/...)
  win=lo,hi         【仅 render】显示窗口
  gamma=0.8         【仅 render】gamma

注意
  * Ex/Em/Pinhole/Gain 等是"采集参数"的记录值。改它们只是改标签，
    不会改变已采集的像素；若无正当理由不要改。
  * OME-XML 没有"显示窗口/gamma"字段，win/gamma 只能用于 render 预览，
    或在查看器（Fiji/Imaris）里设置。
"""

import sys, os, re, glob, argparse, shutil
import numpy as np
import tifffile
import xml.etree.ElementTree as ET

NS = "http://www.openmicroscopy.org/Schemas/OME/2016-06"
ET.register_namespace("", NS)
ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# ---------------------------------------------------------------- helpers
def q(tag):
    return "{%s}%s" % (NS, tag)


def hex_to_ome_color(h):
    v = h.lstrip("#")
    if len(v) == 8:
        v = v[2:]
    if len(v) != 6:
        raise ValueError("颜色要写成 RRGGBB，收到: %s" % h)
    r, g, b = int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
    rgba = (r << 24) | (g << 16) | (b << 8) | 0xFF
    return rgba - (1 << 32) if rgba >= (1 << 31) else rgba


def ome_color_to_hex(c):
    v = int(c) & 0xFFFFFFFF
    return "#%02X%02X%02X" % ((v >> 24) & 0xFF, (v >> 16) & 0xFF, (v >> 8) & 0xFF)


def parse_kv(s):
    out = {}
    for item in s.split(":"):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            continue
        k, v = item.split("=", 1)
        out[k.strip().lower()] = v.strip()
    return out


def read_ome(path):
    """返回 (xml_string, pixel_array, axes)"""
    with tifffile.TiffFile(path) as tf:
        desc = tf.pages[0].description or ""
        arr = tf.series[0].asarray()
        axes = tf.series[0].axes
    if "<OME" not in desc:
        raise RuntimeError("不是 OME-TIFF: %s" % path)
    return desc, arr, axes


def chan_elements(root):
    return root.iter(q("Channel"))


# ---------------------------------------------------------------- info
def cmd_info(path):
    for p in expand(path):
        desc, arr, axes = read_ome(p)
        root = ET.fromstring(desc)
        px = root.find(".//" + q("Pixels"))
        print()
        print("=" * 78)
        print(os.path.basename(p))
        print("  数组 %s  %s   像素 %.4f x %.4f um" % (
            axes, arr.shape, float(px.get("PhysicalSizeX", "nan")),
            float(px.get("PhysicalSizeY", "nan"))))
        print("  %-3s %-10s %-9s %-6s %-6s %-8s %s" %
              ("ch", "name", "color", "ex", "em", "pinhole", "min/p1/p50/p99/max   饱和%"))
        satmax = (1 << int(px.get("SignificantBits", "16"))) - 1
        for i, ch in enumerate(chan_elements(root)):
            a = arr[i] if arr.ndim == 3 else arr
            p1, p50, p99 = np.percentile(a, [1, 50, 99])
            sat = 100.0 * np.count_nonzero(a >= satmax) / a.size
            flag = "  <== 过曝" if sat > 0.5 else ""
            print("  %-3d %-10s %-9s %-6s %-6s %-8s %d / %d / %d / %d / %d   %5.2f%%%s" % (
                i, ch.get("Name", "-"), ome_color_to_hex(ch.get("Color", "16777215")),
                ch.get("ExcitationWavelength", "-"), ch.get("EmissionWavelength", "-"),
                ch.get("PinholeSize", "-"),
                a.min(), int(p1), int(p50), int(p99), a.max(), sat, flag))
        print("  建议窗口(0.5-99.8%): " + ", ".join(
            "C%d=%s" % (i, win_suggest(arr[i] if arr.ndim == 3 else arr))
            for i in range(arr.shape[0] if arr.ndim == 3 else 1)))


def win_suggest(a):
    lo, hi = np.percentile(a, [0.5, 99.8])
    return "%d,%d" % (int(lo), max(int(hi), int(lo) + 1))


# ---------------------------------------------------------------- set
def cmd_set(path, chans, compress=None, outdir=None):
    for p in expand(path):
        if outdir:
            os.makedirs(outdir, exist_ok=True)
            dst = os.path.join(outdir, os.path.basename(p))
        else:
            dst = p

        desc, arr, axes = read_ome(p)
        root = ET.fromstring(desc)
        changed = apply_to_xml(root, chans)
        new_xml = ET.tostring(root, encoding="unicode")

        if not changed:
            print("[skip] %s  (没有匹配的通道参数)" % os.path.basename(p))
            continue

        rerun = False
        if compress:
            rerun = True
        elif dst != p:
            rerun = True
        else:
            # 尝试原地改 XML：不复制 64 MB 像素
            ok = try_inplace(path, new_xml)
            if ok:
                print("[ok] %s  已就地更新 OME-XML (%d bytes)" % (os.path.basename(p), len(new_xml)))
                continue
            rerun = True

        if rerun:
            tifffile.imwrite(dst, arr, photometric="minisblack",
                             description=new_xml.encode("utf-8"), metadata=None,
                             compression=compress, ome=False)
            print("[ok] %s -> %s  (重写, 压缩=%s)" % (
                os.path.basename(p), os.path.basename(dst), compress or "none"))


def apply_to_xml(root, chans):
    changed = False
    ch_list = list(root.iter(q("Channel")))
    for idx, spec in chans.items():
        if idx >= len(ch_list):
            print("  ! 通道 %d 不存在（共 %d 个）" % (idx, len(ch_list)))
            continue
        ch = ch_list[idx]
        if "name" in spec:
            ch.set("Name", spec["name"])
            changed = True
        if "color" in spec:
            ch.set("Color", str(hex_to_ome_color(spec["color"])))
            changed = True
        for key, attr, unit in (("ex", "ExcitationWavelength", "ExcitationWavelengthUnit"),
                                ("em", "EmissionWavelength", "EmissionWavelengthUnit")):
            if key in spec:
                ch.set(attr, spec[key])
                ch.set(unit, "nm")
                changed = True
        if "pinhole" in spec:
            ch.set("PinholeSize", spec["pinhole"])
            ch.set("PinholeSizeUnit", "µm")
            changed = True
        if "illum" in spec:
            ch.set("IlluminationType", spec["illum"])
            changed = True
        if "mode" in spec:
            ch.set("AcquisitionMode", spec["mode"])
            changed = True
    return changed


def try_inplace(path, new_xml):
    """把新 XML 写回第一个 IFD 的 ImageDescription（用空格补齐到原长度）。
    新 XML 比原字段长时返回 False，调用方改为整文件重写。"""
    with tifffile.TiffFile(path) as tf:
        tag = tf.pages[0].tags.get("ImageDescription")
        if tag is None:
            return False
        count, off = int(tag.count), int(tag.valueoffset)
    data = new_xml.encode("utf-8")
    if len(data) > count:
        return False
    data = data + b" " * (count - len(data))
    with open(path, "r+b") as f:
        f.seek(off)
        f.write(data)
    return True


# ---------------------------------------------------------------- render
def cmd_compress(path, codec="zlib"):
    """不改元数据，只把像素重新压缩写出（zlib/lzw），用于缩小体积。"""
    for p in expand(path):
        desc, arr, axes = read_ome(p)
        tmp = p + ".tmp"
        tifffile.imwrite(tmp, arr, photometric="minisblack", description=desc.encode("utf-8"),
                         metadata=None, compression=codec, ome=False)
        before = os.path.getsize(p) / 1048576.0
        shutil.move(tmp, p)
        after = os.path.getsize(p) / 1048576.0
        print("[ok] %-18s %.1f MB -> %.1f MB  (%.0f%%)  %s" % (
            os.path.basename(p), before, after, 100.0 * after / before, codec))


def cmd_render(path, outpng, chans, scale=1.0):
    desc, arr, axes = read_ome(path)
    root = ET.fromstring(desc)
    n = arr.shape[0] if arr.ndim == 3 else 1
    if arr.ndim == 2:
        arr = arr[None, ...]

    h, w = arr.shape[1], arr.shape[2]
    if scale != 1.0:
        step = max(1, int(round(1.0 / scale)))
        arr = arr[:, ::step, ::step]
        h, w = arr.shape[1], arr.shape[2]

    rgb = np.zeros((h, w, 3), dtype=np.float32)
    for i in range(n):
        spec = chans.get(i, {})
        col = spec.get("color", ome_color_to_hex(list(root.iter(q("Channel")))[i].get("Color", "16777215")))
        c = np.array([int(col[1:3], 16), int(col[3:5], 16), int(col[5:7], 16)], dtype=np.float32) / 255.0
        if "win" in spec:
            lo, hi = [float(x) for x in spec["win"].split(",")]
        else:
            lo, hi = [float(x) for x in win_suggest(arr[i]).split(",")]
        g = float(spec.get("gamma", 1.0))
        a = np.clip((arr[i].astype(np.float32) - lo) / max(hi - lo, 1e-6), 0, 1) ** g
        rgb += a[..., None] * c[None, None, :]

    out = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
    from PIL import Image
    Image.fromarray(out).save(outpng)
    print("[ok] 预览图: %s   (%dx%d)" % (outpng, w, h))


# ---------------------------------------------------------------- main
def expand(path):
    if os.path.isdir(path):
        return sorted(glob.glob(os.path.join(path, "*.ome.tif")))
    return [path]


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("cmd", choices=["info", "set", "render", "compress"])
    ap.add_argument("path")
    ap.add_argument("extra", nargs="?")
    ap.add_argument("--ch", action="append", default=[], metavar="N:k=v:k=v")
    ap.add_argument("--compress", default=None, choices=[None, "zlib", "lzw", "deflate"])
    ap.add_argument("--out", default=None)
    ap.add_argument("--scale", type=float, default=1.0)
    a = ap.parse_args()

    chans = {}
    for s in a.ch:
        i, rest = s.split(":", 1) if ":" in s else (s, "")
        chans[int(i)] = parse_kv(rest)

    if a.cmd == "info":
        cmd_info(a.path)
    elif a.cmd == "set":
        cmd_set(a.path, chans, a.compress, a.out)
    elif a.cmd == "compress":
        cmd_compress(a.path, a.compress or "zlib")
    else:
        if not a.extra:
            raise SystemExit("render 需要输出 png 路径")
        cmd_render(a.path, a.extra, chans, a.scale)


if __name__ == "__main__":
    main()

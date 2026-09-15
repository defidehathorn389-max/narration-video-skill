# -*- coding: utf-8 -*-
"""通用合成器：口播稿 + AI 底图 → 16:9 讲解短片。

用法：python3 compose.py full --fps 25
配套：script.py（时间轴）、build_audio.py（音轨）、art/NN_场景.png
"""
"""
PIL 合成管线：AI 插画底图 + 运镜 + 氛围动效 + 逐字动画字幕。

版面：上方 1920×900 画窗（2.13:1，插画自适应取窗）＋ 下方 180px 纯色纸带（字幕专属区）
      → 字幕与插画物理隔离，永不重叠。

  python3 compose.py preview            输出每个镜头中点的样帧
  python3 compose.py test   --start 0 --end 24 --out /tmp/t.mp4
  python3 compose.py full   --fps 25
"""
import glob
import math
import os
import shutil
import subprocess
import sys
import time

import numpy as np
from scipy import ndimage
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

import imageio_ffmpeg
from script import build_timeline, LEAD

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "art")
OUT_MP4 = os.path.join(HERE, "成片.mp4")
NARRATION = os.path.join(HERE, "narration.mp3")   # 没有 mp3 时自动回退到 wav
if not os.path.isfile(NARRATION) and os.path.isfile(os.path.join(HERE, "narration.wav")):
    NARRATION = os.path.join(HERE, "narration.wav")

W, H = 1920, 1080
ART_H = 900                      # 画窗高度
BAR_TOP = ART_H                  # 纸带顶部（字幕专属区上沿）
BAR_H = H - ART_H                # 180
ZOOM = 1.16                      # 最大推近倍率（1.24 时只剩 80% 视野，高主体必被切）
ZMIN = 1.05                      # 起幅（留出漂移余量，保证全程都在游移）
# ---- 零件逐个入场（motion-graphics 式，取代"整块呼吸/旋转"那种贴纸感）----
REVEAL_MAX = 6                   # 一张图最多拆几个零件依次入场
REVEAL_DELAY = 0.08              # 第一个零件的入场时刻（秒，相对镜头起点）
REVEAL_STAG = 0.11               # 零件之间错开的间隔
REVEAL_DUR = 0.42                # 单个零件入场时长
REVEAL_SLIDE = 26.0              # 入场时向上滑的距离（像素）
REVEAL_SCALE = 0.965             # 入场时的起始缩放
MAX_LAYERS = 6                   # 拆出的零件上限
FIT_TOL = 1.00                   # 1.00 = 严格不切到主体
PAD = 1.18                       # 给底图加一圈纸边：造出运镜余量，同时成片更锐
HAND_X = 0.16                    # 手持微晃：横向漂移（占可取景范围的比例）
HAND_Y = 0.12                    # 手持微晃：纵向漂移
CREATE_FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
BOLD_FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
SC = 2                           # ttc 内 "Noto Sans CJK SC" 的 face 下标

BG_RGB = (243, 238, 229)
INK = (35, 32, 28)
RED = (228, 87, 46)
GOLD = (233, 168, 59)
FADE = 0.42                      # 镜头交叉溶解

# ---- 字幕版式 ----
CAP_MAXW = 1600
TRACK = 3                        # 字距
REV_DUR = 0.18                   # 单字浮现时长
POP_DUR = 0.44                   # 关键词弹动时长
CARD_DUR = 0.30                  # 荧光笔扫过时长
OUT_DUR = 0.20                   # 整条淡出
REVEAL_FRAC = 0.60               # 打字时间占字幕时长比例
SHOW_CARET = True                # 打字光标

# ---- 画面大字（压在插画留白处，突显关键信息）----
SLATE = (46, 74, 125)            # 冷静的板岩蓝：给"解方"类词
BIG_PAD = 30                     # 大字背后柔光外扩
BIG_MARGIN = 148
BIG_TOP = 130
BIG_BOTTOM = 812
BIG_POP = 0.52                   # 弹入时长
BIG_R = 1.12                     # 贴图预渲染倍率，保证缩放后仍然锐利
RED_WORDS = {"多巴胺", "劫持", "阈值", "更刺激", "赌局", "算法", "万一", "小红点",
             "继续滑", "注意力", "填不满", "二倍速", "快乐分子", "想要", "自制力差",
             "四十分钟", "大拇指", "差一张", "缝隙", "零点几秒", "压制", "闭嘴", "快乐"}
SLATE_WORDS = {"前额叶", "延迟满足", "重新训练", "等一等再要", "主导权", "真的想要",
               "出口", "机制", "载体"}

TITLE_LINES = []            # 片头标题卡；留空则不显示（配合 script.py 的 LEAD 使用）
TITLE_SIZE = 78

KEYS = ["四十分钟", "大拇指", "自制力差", "劫持", "继续滑", "多巴胺", "快乐分子", "快乐",
        "想要", "小红点", "万一", "阈值", "更刺激", "赌局", "算法", "注意力", "差一张",
        "重新训练", "二倍速", "前额叶", "延迟满足", "等一等再要", "压制", "闭嘴",
        "载体", "填不满", "购物", "抖音", "微信", "出口", "机制", "缝隙", "零点几秒",
        "主导权", "真的想要"]


_ROTCACHE = {}
_ALPHACACHE = {}


def rotated_tile(L, deg):
    """按角度分桶缓存旋转结果（相邻帧角度差 ~0.015°，命中率很高）。"""
    key = (id(L), round(deg / 0.15))
    t = _ROTCACHE.get(key)
    if t is None:
        if len(_ROTCACHE) > 32:                      # 简单 FIFO 清理
            for k in list(_ROTCACHE)[:12]:
                del _ROTCACHE[k]
        t = L["img"].rotate(deg, expand=True, resample=Image.BILINEAR)
        _ROTCACHE[key] = t
    return t


def clamp(x):
    return max(0.0, min(1.0, x))


def lerp(a, b, u):
    return a + (b - a) * u


def ease(u):
    u = clamp(u)
    return 1 - (1 - u) ** 3


_FONTS = {}


def font(size, bold=False):
    k = (size, bold)
    if k not in _FONTS:
        _FONTS[k] = ImageFont.truetype(BOLD_FONT if bold else CREATE_FONT, size, index=SC)
    return _FONTS[k]


# ------------------------------------------------------------------ 底图
class Plate:
    """一张插画：拆成「背景层 + 主体层」，两层独立运动形成视差。

    主体抠出来后，原位用纸色+颗粒补掉（周边 100% 是纸色，补完无痕）。
    主体只放大不缩小，且平移量小于放大量，所以永远不会露出补过的洞。
    """

    def __init__(self, path):
        im = Image.open(path).convert("RGB")
        w, h = im.size
        target = W / ART_H
        if w / h > target:
            nw = int(h * target)
            im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            im = self._best_window(im, int(w / target))
        im = im.resize((int(W * ZOOM), int(ART_H * ZOOM)), Image.LANCZOS)
        im = im.filter(ImageFilter.UnsharpMask(radius=1.5, percent=65, threshold=3))
        # 加一圈纸边：主体往往占满画面（86%），没有运镜余量，一推就切。
        # 扩边后主体占比降到 ~72%，取景窗 86% → 有 14% 余量可推可移，且成片更锐（放大倍率更低）。
        if PAD > 1.001:
            pw, ph = int(im.width * PAD), int(im.height * PAD)
            canvas = Image.new("RGB", (pw, ph), BG_RGB)
            grain = np.random.default_rng(3).normal(0, 2.2, (ph, pw, 3))
            canvas = Image.fromarray(np.clip(np.asarray(canvas).astype(np.float32) + grain, 0, 255).astype(np.uint8))
            canvas.paste(im, ((pw - im.width) // 2, (ph - im.height) // 2))
            im = canvas
        self.bw, self.bh = im.size
        self.bg, self.layers = self._split(im)
        self.sbox = self._subject_box()
        self.z_fit = self._fit_zoom()
        self.dens = self._density(self.bg)

    @staticmethod
    def _best_window(im, nh):
        """在保持比例的前提下滑动纵向取窗：尽量保留主体墨量，且让主体落在窗内偏中上。"""
        w, h = im.size
        if nh >= h:
            return im
        gw, gh = 120, max(1, int(120 * h / w))
        a = np.asarray(im.convert("L").resize((gw, gh))).astype(np.float32)
        ink = (a < 170).astype(np.float32)
        row = ink.sum(axis=1)
        scale = gh / h
        tot = row.sum() or 1.0
        best, best_score = 0, -1e18
        for off in range(0, h - nh + 1, max(1, (h - nh) // 60 or 1)):
            r0, r1 = int(off * scale), max(int(off * scale) + 1, int((off + nh) * scale))
            seg = row[r0:r1]
            keep = seg.sum() / tot
            cen = (float((seg * np.arange(r0, r1)).sum() / seg.sum()) if seg.sum() else 0.5)
            cen = (cen - r0) / max(r1 - r0, 1)
            score = keep - 3.0 * max(0.0, abs(cen - 0.48) - 0.12) ** 2
            if score > best_score:
                best_score, best = score, off
        return im.crop((0, best, w, best + nh))

    @staticmethod
    def _density(im):
        a = np.asarray(im.convert("L").resize((64, 30))).astype(np.float32)
        return (a < 175).astype(np.float32)

    def _split(self, im):
        """返回 (背景图, [主体层...])。

        每层只包含分给它的连通域 —— 层与层之间**绝不重叠**，
        否则同一个组件会被画两遍（重影），且大框缩放旋转后会被画面切掉（截断）。
        """
        a = np.asarray(im).astype(np.int16)
        d = np.abs(a - np.array(BG_RGB, np.int16)).sum(axis=2)
        mask = d > 42
        mask = ndimage.binary_closing(mask, np.ones((3, 3)))
        mask = ndimage.binary_opening(mask, np.ones((3, 3)))
        if mask.mean() > 0.72 or mask.sum() < 500:
            return im, []
        lab, n = ndimage.label(mask)
        if n == 0:
            return im, []

        sizes = ndimage.sum(mask, lab, range(1, n + 1))
        order = np.argsort(sizes)[::-1]
        keep = [i + 1 for i in order[:MAX_LAYERS] if sizes[i] > 0.0006 * mask.size]
        if not keep:
            return im, []

        # 未被收录的小碎块：归到中心最近的那一层，跟着邻居一起动
        cents = ndimage.center_of_mass(mask, lab, range(1, n + 1))
        layer_of = np.zeros(n + 1, np.int32)
        for lid in range(1, n + 1):
            if lid in keep:
                layer_of[lid] = keep.index(lid)
            else:
                cy, cx = cents[lid - 1]
                layer_of[lid] = min(range(len(keep)), key=lambda k: (cy - cents[keep[k] - 1][0]) ** 2
                                                                   + (cx - cents[keep[k] - 1][1]) ** 2)

        bg = np.array(im)
        rng = np.random.default_rng(7)
        layers = []
        for k in range(len(keep)):
            m = np.isin(lab, [lid for lid in range(1, n + 1) if layer_of[lid] == k])
            ys, xs = np.where(m)
            if len(xs) == 0:
                continue
            x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
            tile = im.crop((x0, y0, x1, y1)).convert("RGBA")
            tile.putalpha(Image.fromarray((m[y0:y1, x0:x1] * 255).astype(np.uint8)))
            layers.append({"img": tile, "x0": x0, "y0": y0,
                           "cx": (x0 + x1) / 2.0, "cy": (y0 + y1) / 2.0,
                           "w": x1 - x0, "h": y1 - y0})

        # 背景：把所有主体区域补成纸色 + 颗粒（周边是纯纸色，补完无痕）
        # 入场顺序：左 → 右（机制图大多是这样的因果方向）
        layers.sort(key=lambda L: L["cx"])
        for i, L in enumerate(layers):
            L["ord"] = i
        allsub = lab > 0
        noise = rng.normal(0, 2.6, size=allsub.sum())
        bg[allsub] = np.clip(np.array(BG_RGB, np.float32) + noise[:, None], 0, 255).astype(np.uint8)
        return Image.fromarray(bg), layers

    def _subject_box(self):
        """主体并集 bbox（base 坐标）；用于取景钳制，防止把主体挤出画面。"""
        if not self.layers:
            return None
        x0 = min(L["x0"] for L in self.layers)
        y0 = min(L["y0"] for L in self.layers)
        x1 = max(L["x0"] + L["w"] for L in self.layers)
        y1 = max(L["y0"] + L["h"] for L in self.layers)
        return (x0, y0, x1, y1)

    def _fit_zoom(self):
        """不切到主体的最大推近倍率。

        主体（含呼吸放大 + 平移余量）必须能装进取景窗：
            cw = bw / z >= 2*gw*FIT_TOL   →   z <= bw / (2*gw*FIT_TOL)
        有的底图主体直接顶到边缘（如 hook 的火锅碗），这种图只能少推。
        """
        if not self.sbox:
            return ZOOM
        bx0, by0, bx1, by1 = self.sbox
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        pad = 10.0
        gw = (bx1 - bx0) / 2 + pad
        gh = (by1 - by0) / 2 + pad
        zx = self.bw / max(1.0, 2 * gw * FIT_TOL)
        zy = self.bh / max(1.0, 2 * gh * FIT_TOL)
        return max(1.0, min(ZOOM, zx, zy))

    def ink(self, x, y, w, h):
        """画窗坐标下某矩形的墨量密度（0–1），越大说明那里越挤。"""
        gh, gw = self.dens.shape
        x0 = max(0, min(gw - 1, int(x / W * gw)))
        x1 = max(x0 + 1, min(gw, int((x + w) / W * gw)))
        y0 = max(0, min(gh - 1, int(y / ART_H * gh)))
        y1 = max(y0 + 1, min(gh, int((y + h) / ART_H * gh)))
        return float(self.dens[y0:y1, x0:x1].mean())

    def frame(self, z, px, py, t, t_shot=1e3):
        """t_shot＝距本镜头起点的秒数：零件按它依次滑入+淡入，到位后静止。"""
        cw, ch = int(self.bw / z), int(self.bh / z)
        sx = (self.bw - cw) / 2 * (1 + px)
        sy = (self.bh - ch) / 2 * (1 + py)
        sx = max(0, min(self.bw - cw, sx))
        sy = max(0, min(self.bh - ch, sy))
        # 取景钳制：把零件全部留在画面内
        if self.sbox:
            bx0, by0, bx1, by1 = self.sbox
            cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
            pad = 10.0
            gw = (bx1 - bx0) / 2 + pad
            gh = (by1 - by0) / 2 + pad
            gx0, gx1 = cx - gw, cx + gw
            gy0, gy1 = cy - gh, cy + gh
            if gx1 - gx0 <= cw:                       # 装得下 → 限制取景窗，绝不切到
                sx = max(gx1 - cw, min(gx0, sx))
            else:                                     # 装不下 → 让主体居中，两头对称切
                sx = cx - cw / 2
            if gy1 - gy0 <= ch:
                sy = max(gy1 - ch, min(gy0, sy))
            else:
                sy = cy - ch / 2
            sx = max(0, min(self.bw - cw, sx))
            sy = max(0, min(self.bh - ch, sy))
        out = self.bg.crop((int(sx), int(sy), int(sx) + cw, int(sy) + ch)) \
                      .resize((W, ART_H), Image.BILINEAR).convert("RGBA")
        if not self.layers:
            return out
        kx, ky = W / cw, ART_H / ch
        for L in self.layers:
            a = clamp((t_shot - (REVEAL_DELAY + L["ord"] * REVEAL_STAG)) / REVEAL_DUR)
            if a <= 0.0:
                continue                                    # 还没轮到它入场
            e = a * a * (3 - 2 * a)                         # smoothstep
            sc = REVEAL_SCALE + (1.0 - REVEAL_SCALE) * e
            dy = (1.0 - e) * REVEAL_SLIDE
            ow = max(1, int(L["w"] * sc * kx))
            oh = max(1, int(L["h"] * sc * ky))
            tile = L["img"].resize((ow, oh), Image.BILINEAR)
            if e < 0.995:                                   # 淡入（alpha 按 1/24 量化后缓存）
                q = max(1, int(e * 24)); ck = (id(L), ow, oh, q)
                tt = _ALPHACACHE.get(ck)
                if tt is None:
                    if len(_ALPHACACHE) > 128:
                        for k2 in list(_ALPHACACHE)[:48]:
                            del _ALPHACACHE[k2]
                    tt = tile.copy()
                    tt.putalpha(tile.getchannel("A").point(lambda v: int(v * q / 24)))
                    _ALPHACACHE[ck] = tt
                tile = tt
            ox = (L["cx"] - sx) * kx
            oy = (L["cy"] - sy) * ky + dy
            out.paste(tile, (int(ox - tile.width / 2), int(oy - tile.height / 2)), tile)
        return out


def load_plates():
    """art/ 下按场景归组：01_hook.png / 10b_maybe3.png → {scene: [Plate,...]}"""
    groups = {}
    for p in sorted(glob.glob(os.path.join(ART, "*.png"))):
        stem = os.path.basename(p)[:-4]
        if "_" not in stem:
            continue
        groups.setdefault(stem.split("_", 1)[1], []).append(Plate(p))
    return groups


# ------------------------------------------------------------------ 静态图层（只算一次）
def make_vignette(w, h):
    v = Image.new("L", (w, h), 0)
    ImageDraw.Draw(v).ellipse((-w * .35, -h * .35, w * 1.35, h * 1.35), fill=255)
    v = v.filter(ImageFilter.GaussianBlur(240))
    out = Image.new("RGBA", (w, h), (28, 24, 20, 255))
    out.putalpha(ImageChops.invert(v).point(lambda x: int(x * 0.34)))
    return out


def make_glow(cx, cy, r, color, strength=1.0, size=(W, ART_H)):
    g = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse((cx - r, cy - r, cx + r, cy + r), fill=color + (255,))
    g = g.filter(ImageFilter.GaussianBlur(r * .45))
    g.putalpha(g.getchannel("A").point(lambda v: int(v * .12 * strength)))
    return g


def make_grain(w, h, seed=7, amp=9):
    import random
    random.seed(seed)
    g = Image.new("L", (w // 2, h // 2))
    px = g.load()
    for y in range(g.height):
        for x in range(g.width):
            px[x, y] = random.randint(96, 160)
    g = g.resize((w, h), Image.BILINEAR)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    layer.putalpha(g.point(lambda v: int((v - 96) / 64.0 * amp)))
    return layer


_SWEEP = None


def make_sweep():
    """一条极淡的斜向光带，横向扫过画窗 —— 让整帧都有东西在动。"""
    g = Image.new("L", (W * 2, ART_H), 0)
    d = ImageDraw.Draw(g)
    for i in range(-400, W * 2, 900):
        d.polygon([(i, 0), (i + 240, 0), (i + 240 - 300, ART_H), (i - 300, ART_H)], fill=46)
    g = g.filter(ImageFilter.GaussianBlur(64))
    out = Image.new("RGBA", (W * 2, ART_H), (255, 252, 243, 0))
    out.putalpha(g)
    return out


def make_bar():
    """下方纸带：不透明米白 + 羽化上沿 + 纸纹，字幕与插画零重叠。"""
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(band)
    feather = 46
    for y in range(BAR_TOP - feather, BAR_TOP):
        k = (y - (BAR_TOP - feather)) / feather
        d.line([(0, y), (W, y)], fill=BG_RGB + (int(255 * (k * k * (3 - 2 * k))),))
    d.rectangle((0, BAR_TOP, W, H), fill=BG_RGB + (255,))
    band.alpha_composite(make_grain(W, BAR_H, seed=11, amp=5), (0, BAR_TOP))
    d.line([(0, BAR_TOP), (W, BAR_TOP)], fill=(35, 32, 28, 30))   # 极淡分隔线
    return band


# ------------------------------------------------------------------ 运镜
def ken_burns(idx, u, t=0.0):
    """六种运镜交替 + 开镜落位 + 手持微晃（双频漂移，整帧都在游移）。"""
    e = u * u * (3 - 2 * u)
    settle = 1.0 + 0.030 * math.exp(-4.0 * u)      # 镜头落位
    dx = HAND_X * math.sin(t * 1.10 + idx * 1.7) + HAND_X * 0.6 * math.sin(t * 1.97 + idx * 3.1)
    dy = HAND_Y * math.cos(t * 0.92 + idx * 2.3) + HAND_Y * 0.7 * math.sin(t * 1.61 + idx * 1.1)
    kind = idx % 6
    if kind == 0:
        z = ZMIN + (ZOOM - ZMIN) * e                                # 缓推
        return min(z * settle, ZOOM + 0.03), dx, dy
    if kind == 1:
        z = ZOOM - (ZOOM - ZMIN) * e                                # 缓拉
        return min(z * settle, ZOOM + 0.03), dx, dy
    if kind == 2:
        return min((ZMIN + (ZOOM - ZMIN) * e) * settle, ZOOM + 0.03), -0.9 + 1.8 * e + dx, dy
    if kind == 3:
        return min((ZMIN + (ZOOM - ZMIN) * e) * settle, ZOOM + 0.03), 0.9 - 1.8 * e + dx, dy
    if kind == 4:                                                    # 推 + 斜向下沉
        return min((ZMIN + (ZOOM - ZMIN) * e) * settle, ZOOM + 0.03), -0.5 * e + dx, -0.7 + 1.4 * e + dy
    return min((ZMIN + (ZOOM - ZMIN) * e) * settle, ZOOM + 0.03), 0.5 * e + dx, 0.7 - 1.4 * e + dy


# ------------------------------------------------------------------ 氛围动效
def atmosphere(img, t, idx):
    """漂浮粒子（只在画窗内活动，不会飘到字幕带上）。"""
    ov = Image.new("RGBA", (W, ART_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for i in range(30):
        sx = (i * 137.5) % W
        sy = (i * 219.7) % (ART_H * 0.72) + 50
        drift = math.sin(t * .62 + i) * 46
        rise = (t * (8 + i % 5) * 2.4 + i * 90) % (ART_H * 0.85)
        x = (sx + drift) % W
        y = 70 + (sy - rise) % (ART_H * 0.64)
        a = int(52 * (0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * .9 + i))))
        r = 3 + (i % 4)
        col = GOLD if i % 3 else (255, 250, 240)
        d.ellipse((x - r, y - r, x + r, y + r), fill=col + (a,))
    return Image.alpha_composite(img, ov)


# ------------------------------------------------------------------ 字幕
def spans_of(text):
    hits = []
    for k in KEYS:
        p = text.find(k)
        if p >= 0:
            hits.append((p, len(k)))
    hits.sort()
    merged = []
    for p, l in hits:
        if merged and p < merged[-1][0] + merged[-1][1]:
            continue
        merged.append((p, l))
    out, i = [], 0
    for p, l in merged:
        if p > i:
            out.append((text[i:p], False))
        out.append((text[p:p + l], True))
        i = p + l
    if i < len(text):
        out.append((text[i:], False))
    return out


_GLYPH = {}


def glyph(ch, size, hot):
    """单字贴图（缓存）：返回 (tile, dx, dy)，dx/dy 为贴图相对笔位原点的偏移。"""
    key = (ch, size, hot)
    g = _GLYPH.get(key)
    if g is None:
        f = font(size, hot)
        pad = int(size * 0.6)
        tmp = Image.new("RGBA", (size + pad * 2, size + pad * 2), (0, 0, 0, 0))
        ImageDraw.Draw(tmp).text((pad, pad), ch, font=f, fill=(RED if hot else INK) + (255,))
        bb = tmp.getbbox() or (pad, pad, pad + 1, pad + 1)
        g = (tmp.crop(bb), bb[0] - pad, bb[1] - pad)
        _GLYPH[key] = g
    return g


def cap_layout(text):
    """折行 + 逐字定位（每个字幕只算一次）。"""
    size = 56 if len(text) <= 28 else 50
    f_r, f_b = font(size, False), font(size, True)
    units = [(ch, hot) for seg, hot in spans_of(text) for ch in seg]

    lines, cur, w = [], [], 0.0
    closing = "，。、；：！？”）』」…"
    for ch, hot in units:
        adv = (f_b if hot else f_r).getlength(ch) + TRACK
        if w + adv > CAP_MAXW and cur:
            if ch in closing:
                cur.append((ch, hot)); lines.append(cur); cur, w = [], 0.0
                continue
            lines.append(cur); cur, w = [], 0.0
        cur.append((ch, hot)); w += adv
    if cur:
        lines.append(cur)

    lh = int(size * 1.42)
    block = lh * (len(lines) - 1) + size
    y0 = BAR_TOP + (BAR_H - block) / 2 - size * 0.30
    chars, spans = [], []
    y = y0
    for line in lines:
        total = sum((f_b if hot else f_r).getlength(ch) + TRACK for ch, hot in line)
        x = (W - total) / 2
        run = None
        for ch, hot in line:
            adv = (f_b if hot else f_r).getlength(ch) + TRACK
            chars.append({"ch": ch, "hot": hot, "size": size, "x": x, "y": y, "adv": adv})
            if hot:
                if run is None:
                    run = {"x0": x, "y": y, "size": size, "rt": None}
                run["x1"] = x + adv
            elif run is not None:
                spans.append(run); run = None
            x += adv
        if run is not None:
            spans.append(run)
        y += lh

    dur_hint = len(chars)
    return {"chars": chars, "spans": spans, "size": size, "n": dur_hint}


def cap_prep(cap):
    """给每个字算出现时刻（按字数均分，模拟语速）。"""
    lay = cap_layout(cap["text"])
    n = max(lay["n"], 1)
    dur = cap["end"] - cap["start"]
    rd = min(dur * REVEAL_FRAC, max(0.45, dur - 0.5))
    step = rd / n
    for i, c in enumerate(lay["chars"]):
        c["rt"] = cap["start"] + step * i
    for sp in lay["spans"]:
        sp["rt"] = min(c["rt"] for c in lay["chars"]
                       if c["hot"] and abs(c["y"] - sp["y"]) < 2 and c["x"] >= sp["x0"] - 1)
    lay["t_first"] = cap["start"]
    lay["t_last"] = cap["start"] + step * (n - 1)
    return lay


def draw_caption(img, lay, cap, t):
    a = clamp((t - cap["start"]) / 0.14) * clamp((cap["end"] - t) / OUT_DUR)
    if a <= 0.015:
        return img
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    # 1) 关键词荧光笔块（先画，压在字下面）
    for sp in lay["spans"]:
        k = clamp((t - sp["rt"]) / CARD_DUR)
        if k <= 0:
            continue
        pulse = 1 + 0.55 * math.sin(math.pi * k) * (1 - k)
        al = min(0.55, (0.15 + 0.40 * (1 - k)) * pulse) * a
        s = sp["size"]
        pad_x, r = s * 0.17, int(s * 0.28)
        box = (sp["x0"] - pad_x, sp["y"] + s * 0.10, sp["x1"] + pad_x, sp["y"] + s * 1.12)
        d.rounded_rectangle(box, radius=r, fill=GOLD + (int(255 * al),))

    # 2) 逐字浮现（关键词额外弹一下）
    next_x = None
    for c in lay["chars"]:
        k = clamp((t - c["rt"]) / REV_DUR)
        if k <= 0:
            next_x = (c["x"], c["y"], c["size"]) if next_x is None else next_x
            continue
        e = ease(k)
        dy = (1 - e) * 14
        tile, dx, dy0 = glyph(c["ch"], c["size"], c["hot"])
        px, py, tw, th = c["x"] + dx, c["y"] + dy0 + dy, tile.width, tile.height
        if c["hot"]:
            pk = clamp((t - c["rt"]) / POP_DUR)
            if pk < 1:
                sc = 1 + 0.16 * math.sin(math.pi * pk) * (1 - pk * 0.5)
                nw, nh = max(1, int(tw * sc)), max(1, int(th * sc))
                tile = tile.resize((nw, nh), Image.BILINEAR)
                px, py, tw, th = px + (tw - nw) / 2, py + (th - nh) / 2, nw, nh
        pos = (int(px), int(py))
        ca = a * e
        if ca >= 0.995:
            layer.paste(tile, pos, tile)
        else:
            layer.paste(tile, pos, tile.getchannel("A").point(lambda v: int(v * ca)))

    # 3) 打字光标
    if SHOW_CARET and t < lay["t_last"] + 0.12:
        if next_x is None:
            last = lay["chars"][-1]
            cx, cy, cs = last["x"] + last["adv"], last["y"], last["size"]
        else:
            cx, cy, cs = next_x
        fade = clamp((lay["t_last"] + 0.12 - t) / 0.12)
        d.rectangle((cx - 2, cy + cs * 0.22, cx + 3, cy + cs * 0.86),
                    fill=RED + (int(255 * 0.42 * a * fade),))

    return Image.alpha_composite(img, layer)


def draw_title(img, t):
    """片头标题卡：淡入 → 停顿 → 淡出（给开场留 3 秒）。"""
    a = clamp((t - 0.15) / 0.45) * clamp((LEAD - 0.15 - t) / 0.45)
    if a <= 0.02:
        return img
    k = clamp((t - 0.15) / 0.65)
    sc = 0.94 + 0.06 * ease(k)
    size = int(TITLE_SIZE * sc)
    f = font(size, True)
    lh = int(size * 1.30)
    y0 = int(ART_H * 0.40 - lh * 0.5)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i, line in enumerate(TITLE_LINES):
        w = f.getlength(line)
        d.text(((W - w) / 2, y0 + i * lh), line, font=f, fill=INK + (int(255 * a),))
    # 标题下的红线，随淡入横向扫出
    rw = clamp((t - 0.35) / 0.5)
    if rw > 0:
        lw = f.getlength(TITLE_LINES[-1])
        bw = int(lw * rw)
        d.rectangle(((W - bw) / 2, y0 + len(TITLE_LINES) * lh - size * 0.18,
                     (W + bw) / 2, y0 + len(TITLE_LINES) * lh - size * 0.18 + 6),
                    fill=RED + (int(255 * 0.9 * a),))
    return Image.alpha_composite(img, layer)


# ------------------------------------------------------------------ 画面大字
def ease_back(k):
    """回弹缓动：冲过一点再收回来。"""
    k = clamp(k)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (k - 1) ** 3 + c1 * (k - 1) ** 2


def big_size(word):
    n = len(word)
    return 124 if n <= 2 else 110 if n == 3 else 96 if n == 4 else 82 if n <= 6 else 68


def word_color(word):
    if word in RED_WORDS:
        return RED
    if word in SLATE_WORDS:
        return SLATE
    return INK


def place_word(plate, tw, th, used, hist):
    """在插画留白里挑位置：墨量越少越好，同时强制打散、不连着用同一个区。"""
    mx = BIG_MARGIN
    cands = [("左上", mx, BIG_TOP, -1),
             ("右上", W - mx - tw, BIG_TOP, 1),
             ("左下", mx, BIG_BOTTOM - th, -1),
             ("右下", W - mx - tw, BIG_BOTTOM - th, 1),
             ("上中", (W - tw) / 2, BIG_TOP, 0),
             ("左中", mx, (ART_H - th) / 2, -1),
             ("右中", W - mx - tw, (ART_H - th) / 2, 1)]
    best = None
    for name, x, y, dirx in cands:
        d = plate.ink(x - 44, y - 34, tw + 88, th + 68)
        pen = 0.0
        if d > 0.20:                                   # 真挤的地方基本不排
            pen += 1.2
        if hist and name == hist[-1]:
            pen += 0.55
        if len(hist) >= 2 and name == hist[-2]:
            pen += 0.28
        pen += 0.10 * hist.count(name)                 # 全局均衡
        pen += 0.10 * sum(1 for ux, uy, uw, uh in used
                          if abs(ux - x) < (tw + uw) * 0.6 and abs(uy - y) < (th + uh) * 0.6)
        if best is None or d + pen < best[0]:
            best = (d + pen, x, y, dirx, name, d)
    return best[1], best[2], best[3], best[5], best[4]


def build_big_events(shots, caps):
    """每个镜头挑 1–2 个关键词，在它被念到的那一刻砸到画面上。
    同一个词全片最多 2 次、间隔不小于 15 秒，避免刷屏。"""
    evs, last = [], {}
    for si, s in enumerate(shots):
        picks = []
        for c in caps:
            if c["end"] <= s["start"] or c["start"] >= s["end"]:
                continue
            hits = sorted((k for k in KEYS if k in c["text"]), key=len, reverse=True)
            if not hits:
                continue
            t0 = max(c["start"], s["start"] + 0.50)
            t1 = min(c["end"] + 0.65, s["end"] - 0.10)
            if t1 - t0 < 0.95:
                continue
            for w in hits:
                if sum(1 for e in evs if e["word"] == w) >= 2:
                    continue
                if w in last and t0 - last[w] < 15.0:
                    continue
                picks.append((t0, t1, w))
                break
        picks.sort()
        keep = []
        for p in picks:
            if not keep or p[0] - keep[-1][1] > 0.40:
                keep.append(p)
            if len(keep) >= 2:
                break
        for t0, t1, word in keep:
            evs.append({"t0": t0, "t1": t1, "word": word, "shot": si,
                        "scene": s["scene"]})
            last[word] = t1
    return evs


def prep_big(ev, plate, used, hist):
    """预渲染大字贴图与柔光，并定好位置。"""
    word = ev["word"]
    size = big_size(word)
    f = font(int(size * BIG_R), True)
    col = word_color(word)
    tw = f.getlength(word) + TRACK * (len(word) - 1)
    th = int(size * 1.16)
    canvas = Image.new("RGBA", (int(tw) + 40, int(th) + 40), (0, 0, 0, 0))
    ImageDraw.Draw(canvas).text((20, 20), word, font=f, fill=col + (255,))
    bb = canvas.getbbox() or canvas.getbbox()
    tile = canvas.crop(bb)

    # 柔和纸色光晕：保证压在插画上也读得清
    pw, ph = tile.width + BIG_PAD * 2 * BIG_R, tile.height + BIG_PAD * 2 * BIG_R
    halo = Image.new("RGBA", (int(pw), int(ph)), (0, 0, 0, 0))
    ImageDraw.Draw(halo).rounded_rectangle(
        (0, 0, pw - 1, ph - 1), radius=int(26 * BIG_R), fill=BG_RGB + (255,))
    halo = halo.filter(ImageFilter.GaussianBlur(16 * BIG_R))

    ev["tile"] = tile
    ev["halo"] = halo
    ev["tw"] = tile.width / BIG_R
    ev["th"] = tile.height / BIG_R
    ev["color"] = col
    ev["cache"] = {}
    x, y, dirx, dens, zone = place_word(plate, ev["tw"], ev["th"], used, hist)
    ev["zone"] = zone
    hist.append(zone)
    ev["x"], ev["y"], ev["dir"], ev["dens"] = x, y, dirx, dens
    used.append((x, y, ev["tw"], ev["th"]))


def draw_big(img, ev, t):
    a = clamp((t - ev["t0"]) / 0.16) * clamp((ev["t1"] - t) / 0.26)
    if a <= 0.015:
        return img
    k = clamp((t - ev["t0"]) / BIG_POP)
    sc = 0.86 + 0.14 * ease_back(k)
    slide = (1 - ease(k)) * ev["dir"] * 30
    cx, cy = ev["x"] + ev["tw"] / 2 + slide, ev["y"] + ev["th"] / 2
    buck = round(sc, 2)
    got = ev["cache"].get(buck)
    if got is None:
        got = (ev["halo"].resize((max(1, int(ev["halo"].width * sc / BIG_R)),
                                  max(1, int(ev["halo"].height * sc / BIG_R))), Image.BILINEAR),
               ev["tile"].resize((max(1, int(ev["tw"] * sc)),
                                  max(1, int(ev["th"] * sc))), Image.LANCZOS))
        ev["cache"][buck] = got
    halo, tile = got
    img.paste(halo, (int(cx - halo.width / 2), int(cy - halo.height / 2)),
              halo.getchannel("A").point(lambda v: int(v * 0.50 * a)))
    img.paste(tile, (int(cx - tile.width / 2), int(cy - tile.height / 2)),
              tile.getchannel("A").point(lambda v: int(v * a)))

    # 字下细线：随弹入横向扫出
    rw = clamp((t - ev["t0"] - 0.10) / 0.34)
    if rw > 0:
        w = int(ev["tw"] * sc * rw)
        bar = Image.new("RGBA", (max(1, w), 7), ev["color"] + (int(255 * 0.85 * a),))
        img.paste(bar, (int(cx - w / 2), int(cy + ev["th"] * sc / 2 + 18)), bar)
    return img


# ------------------------------------------------------------------ 主渲染
class Renderer:
    def __init__(self):
        self.shots, self.caps, self.total = build_timeline()
        self.plates = load_plates()
        self.finish = self._build_finish()
        self.missing = [s["scene"] for s in self.shots if s["scene"] not in self.plates]
        self._black = Image.new("RGBA", (W, ART_H), BG_RGB + (255,))
        self._lays = {}
        for i, c in enumerate(self.caps):
            self._lays[i] = cap_prep(c)
        self._cap_idx = {id(c): i for i, c in enumerate(self.caps)}
        # 画面大字：按镜头挑词、找留白、预渲染
        self.bigs = build_big_events(self.shots, self.caps)
        used = {}
        _zone_hist = []
        for ev in self.bigs:
            ps = self.plates.get(ev["scene"])
            if not ps:
                ev["skip"] = True
                continue
            prep_big(ev, ps[0], used.setdefault(ev["shot"], []), _zone_hist)

    def _build_finish(self):
        """画窗暗角 + 中心柔光 + 下方纸带：全部烘焙成一张静态图层。"""
        v = make_vignette(W, ART_H)
        v = Image.alpha_composite(v, make_glow(W / 2, ART_H * 0.42, 560, GOLD, 1.0))
        full = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        full.paste(v, (0, 0))
        return Image.alpha_composite(full, make_bar())

    def active_caption(self, t):
        for i, c in enumerate(self.caps):
            if c["start"] - 0.05 <= t < c["end"]:
                return i, c
        return None, None

    def plate_for(self, scene, u, idx, t, t_shot=1e3, shot_dur=1.0):
        ps = self.plates[scene]
        z, px, py = ken_burns(idx, u, t)
        z = min(z, ps[0].z_fit)                 # 不切到主体
        if len(ps) == 1:
            return ps[0].frame(z, px, py, t, t_shot)
        # 多状态帧：一个镜头内依次切换（这才是真动画）
        n = len(ps); hold = 1.0 / n
        seg = min(int(u / hold), n - 1)
        k = clamp(((u - seg * hold) / hold - 0.62) / 0.38) if seg < n - 1 else 0.0
        # 进场动画只在第一个状态时播；后续状态直接完整显示（不然会把零件重播一遍）
        img = ps[seg].frame(z, px, py, t, t_shot if seg == 0 else 1e3)
        if k > 0:
            img = Image.blend(img, ps[seg + 1].frame(z, px, py, t, 1e3), k * k * (3 - 2 * k))
        return img

    def frame(self, t):
        layers = []
        for i, s in enumerate(self.shots):
            if t < s["start"] - 0.001 or t > s["end"] + FADE:
                continue
            u = clamp((t - s["start"]) / max(s["end"] - s["start"], .001))
            op = min(clamp((t - s["start"]) / FADE), clamp((s["end"] + FADE - t) / FADE))
            if op <= 0.002:
                continue
            if s["scene"] in self.plates:
                layers.append((self.plate_for(s["scene"], u, i, t,
                                              t - s["start"], s["end"] - s["start"]), op, i))
            else:
                layers.append((Image.new("RGB", (W, ART_H), BG_RGB), op, i))
        if not layers:
            s = self.shots[0] if t < self.shots[0]["start"] else self.shots[-1]
            u = 0.0 if t < self.shots[0]["start"] else 1.0
            op = clamp((t - .25) / .9) if t < self.shots[0]["start"] \
                else clamp((s["end"] + 1.6 - t) / 1.2)
            img = self.plate_for(s["scene"], u, 0, t, t - s["start"], s["end"] - s["start"]) \
                if s["scene"] in self.plates \
                else Image.new("RGB", (W, ART_H), BG_RGB)
            layers.append((img, op, 0))

        img = layers[0][0].convert("RGBA")
        if layers[0][1] < 1.0:
            img = Image.blend(self._black, img, layers[0][1])
        for extra, op, _ in layers[1:]:
            img = Image.blend(img, extra.convert("RGBA"), op)

        img = atmosphere(img, t, layers[-1][2])
        full = Image.new("RGBA", (W, H), BG_RGB + (255,))
        full.paste(img, (0, 0))
        full = Image.alpha_composite(full, self.finish)

        if t < LEAD:
            full = draw_title(full, t)
        for ev in self.bigs:
            if not ev.get("skip") and ev["t0"] <= t <= ev["t1"]:
                full = draw_big(full, ev, t)

        ci, cap = self.active_caption(t)
        if cap is not None:
            full = draw_caption(full, self._lays[ci], cap, t)
        return full.convert("RGB")


# ------------------------------------------------------------------ 输出
CHUNK_DIR = os.path.join(HERE, "chunks")


def _ffmpeg_video(out, fps):
    """只编码视频、不接音轨的 ffmpeg 命令（帧走管道）。"""
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    return [ff, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", "%dx%d" % (W, H), "-r", str(fps), "-i", "-",
            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
            "-threads", "2", "-x264-params", "rc-lookahead=20:ref=3:bframes=3",
            "-pix_fmt", "yuv420p", out]


def _feed(proc, r, f0, n, fps, label):
    """把 [f0, f0+n) 帧写进 ffmpeg；返回 False 表示断管。"""
    t0 = time.time()
    for k in range(n):
        i = f0 + k
        try:
            proc.stdin.write(r.frame(i / fps).tobytes())
        except BrokenPipeError:
            print("\n!! %s 在第 %d 帧断开" % (label, i))
            return False
        if k % 200 == 0:
            el = time.time() - t0
            mem = 0
            try:
                for d in ("/proc/self/status", "/proc/%d/status" % proc.pid):
                    for ln in open(d):
                        if ln.startswith("VmRSS"):
                            mem += int(ln.split()[1])
            except Exception:
                pass
            print("  %s 帧 %5d/%d 用时 %5.1fs 剩余 %5.1fs 内存 %4dMB"
                  % (label, k, n, el, el / max(k + 1, 1) * (n - k - 1), mem / 1024), flush=True)
    return True


def chunk_bounds(r, fps, target=900):
    """在镜头切换处切段（不切断交叉溶解），返回每段的起止帧号。"""
    marks = sorted({0, int(round(r.total * fps))} |
                   {int(round(s["start"] * fps)) for s in r.shots[1:]})
    bounds, cur = [], 0
    for m in marks[1:]:
        if m - cur >= target:
            bounds.append((cur, m)); cur = m
    bounds.append((cur, marks[-1]))
    return bounds


def render_chunked(out, fps=25, start=0.0, end=None, with_audio=True):
    """分段编码再拼接——单段 ffmpeg 内存清零，长片不再中途断管。"""
    r = Renderer()
    end = r.total if end is None else min(end, r.total)
    if r.missing:
        print("!! 缺少底图的镜头:", r.missing)
    os.makedirs(CHUNK_DIR, exist_ok=True)
    bounds = chunk_bounds(r, fps)
    t0 = time.time()
    parts = []
    for ci, (a, b) in enumerate(bounds):
        part = os.path.join(CHUNK_DIR, "c%02d.mp4" % ci)
        parts.append(part)
        if os.path.exists(part) and os.path.getsize(part) > 100000:
            print("[%d/%d] %s 已存在，跳过" % (ci + 1, len(bounds), os.path.basename(part)))
            continue
        print("[%d/%d] 编码 %.1fs–%.1fs（%d 帧）" % (ci + 1, len(bounds), a / fps, b / fps, b - a))
        log = open(part + ".log", "w")
        proc = subprocess.Popen(_ffmpeg_video(part, fps), stdin=subprocess.PIPE, stderr=log)
        ok = _feed(proc, r, a, b - a, fps, "段%d" % (ci + 1))
        try:
            proc.stdin.close()
        except BrokenPipeError:
            pass
        rc = proc.wait(); log.close()
        if not ok or rc != 0 or not os.path.exists(part):
            print("!! 段 %d 失败 rc=%s" % (ci + 1, rc))
            print("   ffmpeg:", (open(part + ".log").read() or "(空)")[-800:])
            sys.exit(1)
        print("   → %.1f MB" % (os.path.getsize(part) / 1048576))

    lst = os.path.join(CHUNK_DIR, "list.txt")
    open(lst, "w").write("".join("file '%s'\n" % p for p in parts))
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ff, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst]
    audio = with_audio and abs(end - r.total) < 1e-6 and abs(start) < 1e-6
    if audio and os.path.exists(NARRATION):
        cmd += ["-i", NARRATION, "-c:a", "aac", "-b:a", "192k"]
    elif audio:
        print("!! 找不到音轨 %s，成片无声" % NARRATION)
    cmd += ["-c:v", "copy", "-movflags", "+faststart"]
    if audio:
        cmd += ["-shortest"]
    cmd += [out]
    print("拼接 %d 段 → %s" % (len(parts), out))
    if subprocess.run(cmd, capture_output=True).returncode != 0:
        print("!! 拼接失败"); sys.exit(1)
    print("完成：%s（%.2f MB，用时 %.1fs）" % (out, os.path.getsize(out) / 1048576, time.time() - t0))
    shutil.rmtree(CHUNK_DIR, ignore_errors=True)


def render(out, fps=25, start=0.0, end=None, with_audio=True):
    if end is None or end >= Renderer().total - 1e-6:
        return render_chunked(out, fps, start, end, with_audio)
    r = Renderer()
    end = min(end, r.total)
    if r.missing:
        print("!! 缺少底图的镜头:", r.missing)
    n = int(round((end - start) * fps))
    log = open("/tmp/ff.log", "w")
    proc = subprocess.Popen(_ffmpeg_video(out, fps), stdin=subprocess.PIPE, stderr=log)
    t0 = time.time()
    ok = _feed(proc, r, int(round(start * fps)), n, fps, "试片")
    try:
        proc.stdin.close()
    except BrokenPipeError:
        pass
    rc = proc.wait(); log.close()
    if not ok or rc != 0:
        print("ffmpeg 失败:", (open("/tmp/ff.log").read() or "(空)")[-1200:])
        sys.exit(1)
    print("完成：%s（%.2f MB，用时 %.1fs）" % (out, os.path.getsize(out) / 1048576, time.time() - t0))


def preview():
    r = Renderer()
    os.makedirs(os.path.join(HERE, "preview2"), exist_ok=True)
    if r.missing:
        print("!! 缺少底图:", r.missing)
    for i, s in enumerate(r.shots):
        if s["scene"] not in r.plates:
            continue
        t = (s["start"] + s["end"]) / 2
        r.frame(t).save(os.path.join(HERE, "preview2", "%02d_%s.jpg" % (i + 1, s["scene"])), quality=88)
    print("样帧已输出到 preview2/（共 %d 张）" % len(r.shots))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "preview"
    if mode == "preview":
        preview()
    else:
        a = sys.argv[2:]
        g = lambda k, d: (a[a.index(k) + 1] if k in a else d)
        render(g("--out", OUT_MP4), fps=float(g("--fps", 25)),
               start=float(g("--start", 0.0)),
               end=(float(g("--end", -1)) if "--end" in a else None),
               with_audio=(mode != "test"))

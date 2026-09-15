# -*- coding: utf-8 -*-
"""
口播稿 + 时间轴。

音频按 10 段生成（拿到每段的真实时长），再按“字数权重”把每段时长分摊到
每一句字幕上 —— 这样画面切换点严格贴合语音，而不是靠语速估算。
"""

LEAD = 1.6      # 片头留白
GAP = 0.34      # 段间停顿
TAIL = 2.2      # 片尾留白

# 每段：真实时长(秒) + 若干「镜」(每镜含 1~3 句字幕)
SEGMENTS = [
    {"dur": 20.24, "parts": [
        {"scene": "hook", "lines": [
            "你有没有过这种体验——手机拿起来，想看一眼时间，",
            "结果四十分钟过去了，你还在刷。"]},
        {"scene": "blank", "lines": [
            "放下手机的那一刻，",
            "你甚至想不起来刚才到底看了什么。"]},
        {"scene": "thumb", "lines": [
            "但你的大拇指，它记住了。",
            "它比你的大脑更清楚屏幕的滑动轨迹。"]},
    ]},
    {"dur": 13.92, "parts": [
        {"scene": "hijack", "lines": [
            "这不是你自制力差。",
            "这是你脑子里有一个东西，正在被一套极其精密的系统反复劫持。"]},
        {"scene": "system", "lines": [
            "这套系统不关心你过得好不好，",
            "它只关心一件事：你还能不能继续滑。"]},
    ]},
    {"dur": 9.72, "parts": [
        {"scene": "dopamine_title", "lines": [
            "这个东西叫多巴胺。",
            "但多巴胺不是你想象的那个“快乐分子”。"]},
        {"scene": "want", "lines": [
            "它从来不负责让你快乐，",
            "它只负责让你想要。"]},
    ]},
    {"dur": 18.64, "parts": [
        {"scene": "redot", "lines": [
            "每一次你解锁手机，看到那个小红点，",
            "多巴胺就开始工作。"]},
        {"scene": "maybe", "lines": [
            "它不给你满足，它给你的是“万一呢”。"]},
        {"scene": "maybe3", "lines": [
            "万一这条消息是好消息呢，",
            "万一这个视频很好笑呢，",
            "万一下面那个更好看呢。"]},
    ]},
    {"dur": 14.28, "parts": [
        {"scene": "chase", "lines": [
            "你永远在追那个“万一”，但你永远追不到。"]},
        {"scene": "threshold", "lines": [
            "因为多巴胺的机制就是：得到了，就立刻把阈值调高。",
            "下一轮，你需要更刺激的，才能触发同样的“想要”。"]},
    ]},
    {"dur": 12.60, "parts": [
        {"scene": "gamble", "lines": [
            "所以刷手机这件事，本质上是一场你永远赢不了的赌局。"]},
        {"scene": "table", "lines": [
            "庄家是算法，筹码是你的注意力，",
            "而你手里的牌，永远差一张。"]},
    ]},
    {"dur": 27.76, "parts": [
        {"scene": "retrain", "lines": [
            "更狠的是，这套系统正在重新训练你的大脑。"]},
        {"scene": "movie2x", "lines": [
            "你以前能安安静静看完一部电影，",
            "现在你连一个三分钟的视频都要开二倍速。"]},
        {"scene": "book", "lines": [
            "你以前能读完一本书，",
            "现在你读超过五行的文字，手就开始痒。"]},
        {"scene": "pfc", "lines": [
            "这不是你在退化，",
            "是你的前额叶——那个负责延迟满足、负责“等一等再要”的区域——",
            "正在被反复压制。"]},
    ]},
    {"dur": 18.56, "parts": [
        {"scene": "tug", "lines": [
            "它每一次想让你停下来，多巴胺就递过来一个新视频。",
            "前额叶说“该睡了”，多巴胺说“再看一个”。",
            "前额叶说“这个没意思”，多巴胺说“下一个可能有意思”。"]},
        {"scene": "shutup", "lines": [
            "久而久之，前额叶学会了闭嘴。"]},
    ]},
    {"dur": 33.36, "parts": [
        {"scene": "truth", "lines": [
            "但这里有一个反直觉的真相：",
            "你不是被手机控制的。你是被“想要”控制的。"]},
        {"scene": "carrier", "lines": [
            "这两者有本质区别。手机只是一个载体。",
            "真正让你停不下来的，是你脑子里那个永远填不满的“想要”。"]},
        {"scene": "swap", "lines": [
            "你今天戒了短视频，明天就会沉迷购物。",
            "你今天卸载了抖音，明天就会在微信里刷到凌晨。"]},
        {"scene": "outlet", "lines": [
            "因为问题不在那个 App 上，问题在那个“想要”的机制上。",
            "它需要一个出口，而你给了它手机。仅此而已。"]},
    ]},
    {"dur": 22.16, "parts": [
        {"scene": "ask", "lines": [
            "所以下次你拿起手机的时候，试着问自己一句话：",
            "我现在是真的“想要”什么，还是只是“想要”本身在驱动我？"]},
        {"scene": "gap", "lines": [
            "这个问题不会让你立刻放下手机。",
            "但它会在你和手机之间，插进一个零点几秒的缝隙。"]},
        {"scene": "ending", "lines": [
            "那个缝隙里，藏着你重新拿回主导权的可能。"]},
    ]},
]

_PUNCT_HEAVY = "。！？；"
_PUNCT_LIGHT = "，、：—…"


def weight(s: str) -> float:
    """估算一句字幕的朗读耗时权重。"""
    w = 0.0
    for ch in s:
        if ord(ch) > 0x2E80:          # 中日韩全角
            w += 1.0
        elif ch == ' ':
            w += 0.25
        else:
            w += 0.55
        if ch in _PUNCT_HEAVY:
            w += 0.85
        elif ch in _PUNCT_LIGHT:
            w += 0.30
    return max(w, 0.1)


def build_timeline():
    """返回 (shots, captions, total)

    shots   : [{scene, start, end}]            每镜的时间区间
    captions: [{text, start, end, scene}]      每句字幕的时间区间
    """
    shots, caps = [], []
    t = LEAD
    for seg in SEGMENTS:
        parts = seg["parts"]
        pw = [sum(weight(l) for l in p["lines"]) for p in parts]
        tot = sum(pw)
        for p, w in zip(parts, pw):
            shot_dur = seg["dur"] * (w / tot)
            line_w = [weight(l) for l in p["lines"]]
            lt = sum(line_w)
            tt = t
            for line, lw in zip(p["lines"], line_w):
                d = shot_dur * (lw / lt)
                caps.append({"text": line, "start": tt, "end": tt + d, "scene": p["scene"]})
                tt += d
            shots.append({"scene": p["scene"], "start": t, "end": t + shot_dur})
            t += shot_dur
        t += GAP
    return shots, caps, t + TAIL


if __name__ == "__main__":
    shots, caps, total = build_timeline()
    print("镜头数 %d · 字幕句数 %d · 总时长 %.2fs (%.1f 分钟)"
          % (len(shots), len(caps), total, total / 60))
    for s in shots:
        print("  %-16s %6.2f → %6.2f  (%.2fs)" % (s["scene"], s["start"], s["end"], s["end"] - s["start"]))

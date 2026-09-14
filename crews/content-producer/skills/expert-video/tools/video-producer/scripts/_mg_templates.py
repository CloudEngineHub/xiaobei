# -*- coding: utf-8 -*-
"""_mg_templates — motion-graphics 四件套高阶模板（非子命令，wrapper 不暴露）。

收编自 three-year-search v4 已验证组件（render_v4.py s17/s18/s20 + _v4_product.py）：
  dimension_grid   DNA 多维框架逐个点亮 + 数据流粒子 + 进度条（原 s17_framework）
  scroll_cards     卡组横向滚动 + 激活卡放大脉冲（原 s18_core）
  crew_panel       角色照片卡错峰上浮入位 + 落定辉光（原 crew_panel_anim）
  rec_highlight    录屏动态圈选：聚光暗角 + 呼吸描边 + 四角标 + 标签 chip（原 rec_highlight）

每个模板 = (prepare, draw, mode)：
  prepare(params, ctx) → 校验 + 补默认值后的 params（缺必填项抛 MgError）
  draw(img, t, p, ctx) → 在帧上绘制（t 为当前秒；img 为 RGBA）
  mode: "frame" = 画满整帧（暗底/图片底）；"overlay" = 只画覆盖层（视频底透出）
ctx: {"w","h","fps","dur","fonts","lib","state","spec_dir"}，state 跨帧缓存。
"""

from __future__ import annotations

import math

from PIL import Image, ImageDraw

import _mg_lib as L

TEMPLATES: dict[str, tuple] = {}  # name → (prepare, draw, mode)，文件尾注册


# ============================================================ dimension_grid
def prepare_dimension_grid(params: dict, ctx: dict) -> dict:
    dims = params.get("dims")
    if not isinstance(dims, list) or not dims or not all(isinstance(d, str) for d in dims):
        raise L.MgError("dimension_grid 需要非空字符串列表 params.dims（如 DNA 十维名）")
    p = {
        "title": params.get("title", ""),
        "subtitle": params.get("subtitle", ""),
        "dims": dims,
        "node_label": params.get("node_label", ""),
        "cols": int(params.get("cols", 5)),
        "accent": L.parse_color(params.get("accent", "GREEN")),
        "dot_color": L.parse_color(params.get("dot_color", "CYAN")),
        "card_w": int(params.get("card_w", 300)),
        "card_h": int(params.get("card_h", 110)),
        "gap": int(params.get("gap", 10)),
        "row_gap": int(params.get("row_gap", 180)),
        "y_top": int(params.get("y_top", 350)),
        "first_at": float(params.get("first_at", 0.5)),
        "stagger": float(params.get("stagger", 0.2)),
        "progress": bool(params.get("progress", True)),
    }
    if p["cols"] < 1 or p["cols"] > len(dims):
        p["cols"] = max(1, min(p["cols"], len(dims)))
    grid_w = p["cols"] * p["card_w"] + (p["cols"] - 1) * p["gap"]
    if grid_w > ctx["w"]:
        raise L.MgError(
            f"dimension_grid 网格总宽 {grid_w}px 超出画幅 {ctx['w']}px"
            f"——减 cols/card_w/gap 或加大 spec.width")
    return p


def draw_dimension_grid(img: Image.Image, t: float, p: dict, ctx: dict) -> None:
    w, h, fonts = ctx["w"], ctx["h"], ctx["fonts"]
    d = ImageDraw.Draw(img)
    accent, cw, ch = p["accent"], p["card_w"], p["card_h"]
    if p["title"]:
        d.text((w // 2, 150), p["title"], font=fonts.get("bold", 60),
               fill=L.with_alpha(L.PALETTE["WHITE"], 255), anchor="mm")
    if p["subtitle"]:
        d.text((w // 2, 230), p["subtitle"], font=fonts.get("med", 40),
               fill=L.with_alpha(L.PALETTE["MUTED"], 255), anchor="mm")

    # 网格布局：cols 列居中，行数由 dims 数量决定
    cols = p["cols"]
    pitch = cw + p["gap"]
    rows = math.ceil(len(p["dims"]) / cols)
    grid_w = cols * cw + (cols - 1) * p["gap"]
    x0 = (w - grid_w) // 2
    node = (w // 2, p["y_top"] + (rows - 1) * (ch + p["row_gap"]) + ch + 130)
    L.paste_glow(img, node, 700, accent, 50)
    d = ImageDraw.Draw(img)

    for k, name in enumerate(p["dims"]):
        r, c = divmod(k, cols)
        # 末行不满 cols 时居中
        row_n = min(cols, len(p["dims"]) - r * cols)
        row_x0 = (w - (row_n * cw + (row_n - 1) * p["gap"])) // 2
        x = row_x0 + c * pitch
        y = p["y_top"] + r * (ch + p["row_gap"])
        t0 = p["first_at"] + k * p["stagger"]
        lit = t >= t0 + 0.25
        prog_in = L.ease_out_back(L.seg(t, t0, t0 + 0.25))
        a = int(255 * L.seg(t, t0, t0 + 0.2))
        bx = [x, y, x + cw, y + ch]
        if lit:
            d.rounded_rectangle(bx, radius=20, fill=(24, 44, 40, 235),
                                outline=accent + (255,), width=3)
            d.text((x + cw / 2, y + ch / 2), name, font=fonts.get("bold", 48),
                   fill=(235, 255, 244, 255), anchor="mm")
            # 数据流：点从卡片底边流向中心节点
            flow = ((t - t0 - 0.25) * 0.55) % 1.0
            sx, sy = x + cw / 2, y + ch
            px = L.lerp(sx, node[0], flow)
            py = L.lerp(sy, node[1], flow)
            d.ellipse([px - 5, py - 5, px + 5, py + 5], fill=p["dot_color"] + (220,))
        else:
            al = int(90 * prog_in) if prog_in > 0 else 70
            d.rounded_rectangle(bx, radius=20, outline=(90, 110, 140, al), width=2)
            d.text((x + cw / 2, y + ch / 2), name, font=fonts.get("bold", 48),
                   fill=(120, 135, 158, a if a > 0 else 150), anchor="mm")

    if p["node_label"]:
        d.text(node, p["node_label"], font=fonts.get("bold", 50),
               fill=(235, 255, 244, 255), anchor="mm")
    if p["progress"]:
        bar_w = min(800, w - 400)
        bx0 = (w - bar_w) // 2
        prog = L.seg(t, p["first_at"], ctx["dur"] - 0.4)
        d.rounded_rectangle([bx0, h - 80, bx0 + bar_w, h - 68], radius=6, fill=(40, 52, 74, 255))
        if prog > 0:
            d.rounded_rectangle([bx0, h - 80, bx0 + int(bar_w * prog), h - 68],
                                radius=6, fill=accent + (255,))


# ============================================================ scroll_cards
def _wrap_sub(sub, max_chars: int) -> list[str]:
    if isinstance(sub, list):
        return [str(s) for s in sub]
    s = str(sub or "")
    return [s[i:i + max_chars] for i in range(0, len(s), max_chars)] or [""]


def prepare_scroll_cards(params: dict, ctx: dict) -> dict:
    cards = params.get("cards")
    if not isinstance(cards, list) or not cards:
        raise L.MgError("scroll_cards 需要非空 params.cards（[{name, sub}, ...]）")
    for c in cards:
        if not isinstance(c, dict) or not c.get("name"):
            raise L.MgError(f"scroll_cards 卡片须含 name: {c!r}")
    p = {
        "title": params.get("title", ""),
        "cards": cards,
        "footer": params.get("footer", ""),
        "active_label": params.get("active_label", ""),
        "scroll_speed": float(params.get("scroll_speed", 36)),
        "cycle": float(params.get("cycle", 1.35)),
        "card_w": int(params.get("card_w", 360)),
        "card_h": int(params.get("card_h", 520)),
        "pitch": int(params.get("pitch", 400)),
        "y": int(params.get("y", 620)),
        "accent": L.parse_color(params.get("accent", "CYAN")),
        "active_scale": float(params.get("active_scale", 1.07)),
        "sub_max_chars": int(params.get("sub_max_chars", 11)),
    }
    if p["cycle"] <= 0:
        raise L.MgError("scroll_cards params.cycle 必须 > 0")
    return p


def draw_scroll_cards(img: Image.Image, t: float, p: dict, ctx: dict) -> None:
    w, fonts = ctx["w"], ctx["fonts"]
    d = ImageDraw.Draw(img)
    accent = p["accent"]
    if p["title"]:
        d.text((w // 2, 140), p["title"], font=fonts.get("bold", 58),
               fill=L.with_alpha(L.PALETTE["WHITE"], 255), anchor="mm")
    scroll = p["scroll_speed"] * t
    active = int(t / p["cycle"]) % len(p["cards"])
    cw, ch = p["card_w"], p["card_h"]
    for k, card in enumerate(p["cards"]):
        x = 210 + k * p["pitch"] - scroll
        if x > w + cw or x + cw < -cw:
            continue
        is_act = (k == active)
        sc = p["active_scale"] if is_act else 1.0
        cw2, ch2 = int(cw * sc), int(ch * sc)
        cx, cy = x + cw / 2, p["y"]
        bx = [cx - cw2 / 2, cy - ch2 / 2, cx + cw2 / 2, cy + ch2 / 2]
        sub_lines = _wrap_sub(card.get("sub"), p["sub_max_chars"])
        if is_act:
            pl = L.pulse(t, 1.8)
            L.paste_glow(img, (cx, cy), 640, accent, int(46 + 30 * pl))
            d = ImageDraw.Draw(img)
            d.rounded_rectangle(bx, radius=30, fill=(20, 40, 52, 242),
                                outline=L.with_alpha(accent, 160 + 90 * pl), width=5)
            d.text((cx, cy - 130), card["name"], font=fonts.get("black", 84),
                   fill=(235, 250, 255, 255), anchor="mm")
            y_sub = cy + 40
            for ln in sub_lines[:2]:
                d.text((cx, y_sub), ln, font=fonts.get("med", 36),
                       fill=(180, 196, 216, 255), anchor="mm")
                y_sub += 70
            if p["active_label"]:
                d.text((cx, cy + 190), p["active_label"], font=fonts.get("med", 34),
                       fill=accent + (255,), anchor="mm")
        else:
            d.rounded_rectangle(bx, radius=30, fill=(20, 28, 46, 230),
                                outline=(70, 88, 118, 200), width=3)
            d.text((cx, cy - 110), card["name"], font=fonts.get("bold", 66),
                   fill=(140, 156, 180, 255), anchor="mm")
            y_sub = cy + 60
            for ln in sub_lines[:2]:
                d.text((cx, y_sub), ln, font=fonts.get("reg", 32),
                       fill=(120, 134, 156, 255), anchor="mm")
                y_sub += 56
    if p["footer"]:
        d.text((w // 2, ctx["h"] - 80), p["footer"], font=fonts.get("med", 38),
               fill=(160, 176, 198, 255), anchor="mm")


# ============================================================ crew_panel
def prepare_crew_panel(params: dict, ctx: dict) -> dict:
    roles = params.get("roles")
    if not isinstance(roles, list) or not roles:
        raise L.MgError("crew_panel 需要非空 params.roles（[{title, sub, accent, photo?}, ...]）")
    for r in roles:
        if not isinstance(r, dict) or not r.get("title"):
            raise L.MgError(f"crew_panel 角色须含 title: {r!r}")
        if r.get("photo"):
            from pathlib import Path
            pp = Path(r["photo"])
            # 相对路径按 spec 所在目录解析
            r["photo"] = pp if pp.is_absolute() else Path(ctx["spec_dir"]) / pp
            if not r["photo"].is_file():
                raise L.MgError(f"crew_panel 角色照片不存在: {r['photo']}")
    p = {
        "title": params.get("title", ""),
        "roles": roles,
        "footer": params.get("footer", ""),
        "card_w": int(params.get("card_w", 380)),
        "card_h": int(params.get("card_h", 440)),
        "gap": int(params.get("gap", 40)),
        "y": int(params.get("y", 330)),
        "first_at": float(params.get("first_at", 0.35)),
        "stagger": float(params.get("stagger", 0.45)),
        "enter_dur": float(params.get("enter_dur", 0.55)),
        "rise": int(params.get("rise", 130)),
        "glow": bool(params.get("glow", True)),
    }
    total_w = p["card_w"] * len(roles) + p["gap"] * (len(roles) - 1)
    if total_w > ctx["w"]:
        raise L.MgError(
            f"crew_panel 卡片总宽 {total_w}px 超出画幅 {ctx['w']}px"
            f"——减 card_w/gap/roles 数量或加大 spec.width")
    return p


def _role_card(r: dict, cw: int, chh: int, fonts) -> Image.Image:
    """单张角色卡 RGBA（照片圆裁在上、标题与副行文在下）——静态部分只画一次。"""
    accent = L.parse_color(r.get("accent", "CYAN"))
    img = Image.new("RGBA", (cw, chh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, cw - 1, chh - 1], radius=28, fill=(22, 30, 52, 235),
                        outline=accent + (255,), width=3)
    d.rounded_rectangle([28, 30, cw - 28, 44], radius=7, fill=accent + (220,))
    subs = r.get("sub") if isinstance(r.get("sub"), list) else ([r["sub"]] if r.get("sub") else [])
    if r.get("photo"):
        ps = 160
        ph = L.photo_circle(r["photo"], ps)
        ring = Image.new("RGBA", (ps + 12, ps + 12), (0, 0, 0, 0))
        ImageDraw.Draw(ring).ellipse([0, 0, ps + 11, ps + 11], outline=accent + (255,), width=4)
        px = (cw - ps) // 2
        L.safe_composite(img, ph, px, 64)
        L.safe_composite(img, ring, px - 6, 58)
        d = ImageDraw.Draw(img)
        d.text((cw // 2, 274), r["title"], font=fonts.get("bold", 50),
               fill=(240, 246, 255, 255), anchor="mm")
        y = 326
    else:
        d.text((cw // 2, 150), r["title"], font=fonts.get("bold", 56),
               fill=(240, 246, 255, 255), anchor="mm")
        y = 260
    for ln in subs:
        d.text((cw // 2, y), str(ln), font=fonts.get("med", 34),
               fill=(168, 182, 205, 255), anchor="mm")
        y += 52
    return img


def draw_crew_panel(img: Image.Image, t: float, p: dict, ctx: dict) -> None:
    w, fonts = ctx["w"], ctx["fonts"]
    state = ctx["state"]
    if "cards" not in state:  # 静态卡只渲染一次
        state["cards"] = [_role_card(r, p["card_w"], p["card_h"], fonts) for r in p["roles"]]
    cards = state["cards"]
    cw, gap = p["card_w"], p["gap"]
    total_w = cw * len(cards) + gap * (len(cards) - 1)
    x0 = (w - total_w) // 2
    L.paste_glow(img, (w // 2, 190), 900, L.PALETTE["GREEN"], 60)
    d = ImageDraw.Draw(img)
    if p["title"]:
        L.text_shadow(d, (w // 2, 190), p["title"], fonts.get("bold", 64))
    for ci, card in enumerate(cards):
        t0 = p["first_at"] + ci * p["stagger"]
        prog = L.ease_out_back(L.seg(t, t0, t0 + p["enter_dur"]))
        a = int(255 * L.seg(t, t0, t0 + 0.35))
        cy = p["y"] + int((1 - prog) * p["rise"])
        ccx = x0 + ci * (cw + gap) + cw // 2
        if p["glow"] and t > t0 + p["enter_dur"]:
            pl = L.pulse(t - t0 - p["enter_dur"], 1.1)
            L.paste_glow(img, (ccx, cy + p["card_h"] // 2), 560,
                         L.PALETTE["CYAN"], int(30 + 26 * pl))
        cv = card.copy()
        if a < 255:
            al = cv.getchannel("A").point(lambda v: v * a // 255)
            cv.putalpha(al)
        L.safe_composite(img, cv, int(x0 + ci * (cw + gap)), int(cy))
    if p["footer"]:
        d = ImageDraw.Draw(img)
        dur = ctx["dur"]
        fa = int(255 * L.seg(t, dur - 1.35, dur - 0.75))
        if fa > 0:
            d.text((w // 2, ctx["h"] - 200), p["footer"], font=fonts.get("med", 46),
                   fill=(200, 214, 232, fa), anchor="mm")


# ============================================================ rec_highlight
def prepare_rec_highlight(params: dict, ctx: dict) -> dict:
    zones = params.get("zones")
    if not isinstance(zones, list) or not zones:
        raise L.MgError("rec_highlight 需要非空 params.zones（[[x0,y0,x1,y1], ...]）")
    for z in zones:
        if not (isinstance(z, list) and len(z) == 4):
            raise L.MgError(f"rec_highlight zone 须为 [x0,y0,x1,y1]: {z!r}")
    p = {
        "zones": [[float(v) for v in z] for z in zones],
        "label": params.get("label", ""),
        "zone_color": L.parse_color(params.get("zone_color", "CYAN")),
        "corner_color": L.parse_color(params.get("corner_color", "GREEN")),
        "dim": int(params.get("dim", 110)),
        "move_dur": float(params.get("move_dur", 0.5)),
        "radius": int(params.get("radius", 26)),
        "cycle": params.get("cycle", "auto"),
    }
    return p


def draw_rec_highlight(img: Image.Image, t: float, p: dict, ctx: dict) -> None:
    """覆盖层绘制：聚光暗角（圆角洞）+ 呼吸描边 + 四角标 + 标签 chip；zones 依次移动。"""
    w, h, fonts = ctx["w"], ctx["h"], ctx["fonts"]
    dur = ctx["dur"]
    zones = p["zones"]
    seg_len = (dur if p["cycle"] == "auto" else float(p["cycle"])) / len(zones)
    if seg_len <= 0:
        seg_len = dur / len(zones)
    zi = min(int(t / seg_len), len(zones) - 1)
    mv = L.ease_out_cubic(L.seg(t, zi * seg_len, zi * seg_len + p["move_dur"]))
    x0, y0, x1, y1 = zones[zi]
    if zi > 0:
        px0, py0, px1, py1 = zones[zi - 1]
        cx = L.lerp((px0 + px1) / 2, (x0 + x1) / 2, mv)
        cy = L.lerp((py0 + py1) / 2, (y0 + y1) / 2, mv)
        wq = L.lerp(px1 - px0, x1 - x0, mv)
        hq = L.lerp(py1 - py0, y1 - y0, mv)
    else:
        cx, cy, wq, hq = (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0
    box = [cx - wq / 2, cy - hq / 2, cx + wq / 2, cy + hq / 2]
    pl = L.pulse(t, 1.6)

    # 暗角遮罩：洞外压暗，洞内透明
    mask = Image.new("L", (w, h), p["dim"])
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=p["radius"], fill=0)
    dim_layer = Image.new("RGBA", (w, h), (4, 8, 16, 255))
    dim_layer.putalpha(mask)
    img.alpha_composite(dim_layer)

    d = ImageDraw.Draw(img)
    lw = 5 + int(2 * pl)
    d.rounded_rectangle(box, radius=p["radius"],
                        outline=L.with_alpha(p["zone_color"], 150 + 90 * pl), width=lw)
    tick = 34
    col = p["corner_color"] + (255,)
    for bx, by, dx, dy in [(box[0], box[1], 1, 1), (box[2], box[1], -1, 1),
                           (box[0], box[3], 1, -1), (box[2], box[3], -1, -1)]:
        d.line([(bx, by), (bx + dx * tick, by)], fill=col, width=6)
        d.line([(bx, by), (bx, by + dy * tick)], fill=col, width=6)
    if p["label"]:
        f = fonts.get("bold", 34)
        tw = d.textlength(p["label"], font=f)
        lx, ly = box[0], box[1] - 54
        d.rounded_rectangle([lx, ly - 8, lx + tw + 34, ly + 40], radius=12,
                            fill=p["corner_color"] + (235,))
        d.text((lx + 17, ly + 15), p["label"], font=f,
               fill=L.PALETTE["INK"] + (255,), anchor="lm")


# ============================================================ 注册
TEMPLATES["dimension_grid"] = (prepare_dimension_grid, draw_dimension_grid, "frame")
TEMPLATES["scroll_cards"] = (prepare_scroll_cards, draw_scroll_cards, "frame")
TEMPLATES["crew_panel"] = (prepare_crew_panel, draw_crew_panel, "frame")
TEMPLATES["rec_highlight"] = (prepare_rec_highlight, draw_rec_highlight, "overlay")

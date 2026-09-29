"""
mv.design — оформление кадров по УТВЕРЖДЁННОМУ стайлгайду v1 «Маршрутка времени» (29.09.2026).
Источник: холст https://claude.ai/artifact/KvEBXG63fSQyJCAgKRbGnk (кадры Hook, Talk, Memory, End).

Слои 1080x1920 поверх видео: табло маршрута, хук, билетик с именем, субтитры,
страница книги для воспоминаний, концовка с часами «????».
Выделение в субтитрах: *слово* → абрикос (в акварели — охра).
"""

import random
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920

# ---------------------------------------------------------------- токены стайлгайда
C = {
    # салон (3D)
    "apricot": "#F4A261", "coral": "#E76F51", "teal": "#3FA39B", "cream": "#FBEBD3",
    "walnut": "#A0714A", "choco": "#6B4430", "plum": "#2E2433",
    # акварель
    "paper": "#F2E6CC", "sepia": "#7A5A3E", "azure": "#8DA7B8", "ochre": "#CFA052", "cinnabar": "#B65C4B",
    # служебные из макетов
    "board_bg": "#1E1A22", "amber": "#FFB547", "sub_fill": "#FFF8EC", "hook_sub": "#FFE6CF",
    "page": "#FBF5E6", "page_line": "#D9C9A6", "sepia_dark": "#5A4330", "mem_hl": "#F2C46A",
    "caption_sub": "#8A6A4E", "button_shadow": "#C9744A",
}
SHADOW = (46, 36, 51, 89)          # rgba(46,36,51,.35) — «твёрдая» тень макетов
SHADOW_SEPIA = (122, 90, 62, 89)

# безопасные зоны: сверху 200, снизу 380 (от y=1540), справа 130 (x≥950, y 900–1540)
SUB_CX, SUB_MAX_W = 505, 860

# ---------------------------------------------------------------- шрифты
FONT_FILES = {
    "russo": ["RussoOne-Regular.ttf"],
    "nunito900": ["Nunito-Black.ttf"],
    "nunito800": ["Nunito-ExtraBold.ttf", "Nunito-Black.ttf"],
    "press": ["PressStart2P-Regular.ttf"],
    "lora_i": ["Lora-Italic.ttf", "Lora-MediumItalic.ttf"],
    "lora": ["Lora-Regular.ttf", "Lora-Medium.ttf"],
}
FALLBACK = ["C:/Windows/Fonts/arialbd.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
FALLBACK_SERIF = ["C:/Windows/Fonts/georgiai.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf"]
FONT_DIRS = [Path(__file__).resolve().parent.parent / "fonts"]
_cache, _warned = {}, set()


def font(role, size):
    if (role, size) in _cache:
        return _cache[(role, size)]
    path = None
    for d in FONT_DIRS:
        for name in FONT_FILES[role]:
            hits = list(d.rglob(name)) if d.exists() else []
            if hits:
                path = hits[0]
                break
        if path:
            break
    if not path:
        pool = FALLBACK_SERIF if role.startswith("lora") else FALLBACK
        path = next((p for p in pool if Path(p).exists()), None)
        if role not in _warned:
            print(f"  [шрифт] нет {FONT_FILES[role][0]} в fonts/ — временно {Path(str(path)).name}")
            _warned.add(role)
    f = ImageFont.truetype(str(path), size)
    _cache[(role, size)] = f
    return f


def tlen(text, f, spacing=0):
    return ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength(text, font=f) + spacing * max(0, len(text) - 1)


def draw_spaced(d, xy, text, f, fill, spacing=0):
    if not spacing:
        d.text(xy, text, font=f, fill=fill)
        return
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) + spacing


# ---------------------------------------------------------------- базовые приёмы


def place(base, layer, xy, angle=0.0, shadow_dy=0, shadow=SHADOW):
    """Кладёт слой с поворотом (градусы CSS: минус = против часовой) и твёрдой тенью вниз."""
    if angle:
        w0, h0 = layer.size
        layer = layer.rotate(-angle, resample=Image.BICUBIC, expand=True)
        xy = (xy[0] - (layer.width - w0) // 2, xy[1] - (layer.height - h0) // 2)
    if shadow_dy:
        sh = Image.new("RGBA", layer.size, shadow)
        sh.putalpha(layer.getchannel("A").point(lambda a: a * shadow[3] // 255))
        base.alpha_composite(sh, (xy[0], xy[1] + shadow_dy))
    base.alpha_composite(layer, xy)


def rrect(size, radius, fill, border=None, bw=0):
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius, fill=fill,
                                         outline=border, width=bw)
    return im


# ---------------------------------------------------------------- текст реплик


def parse_marked(text):
    """'у нас *мечами* не' -> [('у',F),('нас',F),('мечами',T),('не',F)]; знаки препинания липнут к слову."""
    words = []
    for i, part in enumerate(re.split(r"\*", text)):
        for w in part.split():
            if words and re.fullmatch(r"[.,!?…:;»)]+", w):
                words[-1] = (words[-1][0] + w, words[-1][1])
            else:
                words.append((w, i % 2 == 1))
    return words


def chunk_words(words, n=5):
    """Куски субтитров (≤2 строки): по предложениям, затем по n слов; выделенную фразу не рвём."""
    chunks, cur = [], []
    for idx, w in enumerate(words):
        cur.append(w)
        nxt_hl = idx + 1 < len(words) and words[idx + 1][1]
        if w[0][-1] in ".!?…" and len(cur) >= 2:
            chunks.append(cur)
            cur = []
        elif len(cur) >= n and w[0][-1] != "," and not (w[1] and nxt_hl and len(cur) < n + 3):
            chunks.append(cur)
            cur = []
    if cur:
        if chunks and len(cur) <= 2 and len(chunks[-1]) + len(cur) <= n + 2:
            chunks[-1] += cur
        else:
            chunks.append(cur)
    return chunks or [[]]


def wrap(words, f, max_w):
    lines, cur = [], []
    for w in words:
        if cur and tlen(" ".join(x[0] for x in cur + [w]), f) > max_w:
            lines.append(cur)
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- элементы кадра


def draw_board(img, stop):
    """Табло: #1E1A22 в ореховой рамке 8 px, янтарь #FFB547, Press Start 2P 24/50, x90 y222 w900."""
    w, h = 900, 184
    board = rrect((w, h), 22, C["board_bg"], C["walnut"], 8)
    f1, f2 = font("press", 24), font("press", 50)
    t1, t2 = "СЛЕДУЮЩАЯ ОСТАНОВКА:", stop.upper()
    x1, x2 = (w - tlen(t1, f1, 1)) / 2, (w - tlen(t2, f2)) / 2
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).text((x2, 92), t2, font=f2, fill=(255, 181, 71, 166))
    board.alpha_composite(glow.filter(ImageFilter.GaussianBlur(7)))
    d = ImageDraw.Draw(board)
    draw_spaced(d, (x1, 40), t1, f1, (255, 181, 71, 217), 1)
    d.text((x2, 92), t2, font=f2, fill=C["amber"])
    place(img, board, (90, 222), shadow_dy=10)


def draw_hook(img, tag, title, sub, top=470):
    """Хук: коралл, кремовая рамка 8, радиус 34, наклон −2°, пилюля-тег, Russo One 76, подпись 36."""
    w = 940
    f_tag, f_title, f_sub = font("nunito900", 26), font("russo", 76), font("nunito800", 36)
    lines = []
    for word in title.upper().split():
        test = f"{lines[-1]} {word}" if lines else word
        if lines and tlen(test, f_title) <= w - 104:
            lines[-1] = test
        else:
            lines.append(word)
    h = 34 + (60 + 16 if tag else 0) + len(lines) * 78 + (16 + 44 if sub else 0) + 40 + 16
    card = rrect((w, h), 34, C["coral"], C["cream"], 8)
    d = ImageDraw.Draw(card)
    y = 34 + 8
    if tag:
        t = tag.upper()
        tw = tlen(t, f_tag, 2)
        d.rounded_rectangle([52, y, 52 + tw + 36, y + 52], 26, fill=C["plum"])
        draw_spaced(d, (70, y + 9), t, f_tag, C["cream"], 2)
        y += 52 + 20
    for line in lines:
        d.text((52, y), line, font=f_title, fill=C["sub_fill"])
        y += 78
    if sub:
        d.text((52, y + 16), sub, font=f_sub, fill=C["hook_sub"])
    place(img, card, (70, top), angle=-2, shadow_dy=16)


def draw_ticket(img, stub, name, role, stub_color, role_color, y, memory=False):
    """Билетик: корешок (№ / «за кадром») + пунктир + кремовая часть с именем и ролью, наклон −2°."""
    f_stub = font("lora_i", 28) if memory else font("russo", 28)
    f_name, f_role = font("nunito900", 40), font("nunito800", 24)
    body_bg = C["page"] if memory else C["cream"]
    name_col = C["sepia_dark"] if memory else C["plum"]
    sw = int(tlen(stub, f_stub)) + 32
    bw = int(max(tlen(name, f_name), tlen(role, f_role) if role else 0)) + 52
    h = 96 if role else 72
    t = Image.new("RGBA", (sw + bw, h), (0, 0, 0, 0))
    mask = rrect((sw + bw, h), 14, (255, 255, 255, 255))
    d = ImageDraw.Draw(t)
    d.rectangle([0, 0, sw, h], fill=stub_color)
    d.rectangle([sw, 0, sw + bw, h], fill=body_bg)
    for yy in range(0, h, 12):
        d.rectangle([sw - 2, yy, sw + 1, yy + 6], fill=C["page"] if memory else C["cream"])
    d.text(((sw - tlen(stub, f_stub)) / 2, (h - f_stub.size) / 2 - 4), stub, font=f_stub, fill=C["sub_fill"])
    d.text((sw + 26, 8), name, font=f_name, fill=name_col)
    if role:
        d.text((sw + 26, 56), role, font=f_role, fill=role_color)
    t.putalpha(Image.composite(t.getchannel("A"), Image.new("L", t.size, 0), mask.getchannel("A")))
    place(img, t, (80, y), angle=-2, shadow_dy=8, shadow=SHADOW_SEPIA if memory else SHADOW)


def draw_subs(img, words, y, memory=False):
    """Субтитры: Nunito 900 66 (акварель 62), #FFF8EC, обводка 14 px (7 наружу), тень 0 6, ≤2 строк."""
    size = 62 if memory else 66
    stroke = C["sepia_dark"] if memory else C["plum"]
    hl = C["mem_hl"] if memory else C["apricot"]
    f = font("nunito900", size)
    lines = wrap(words, f, SUB_MAX_W)
    if len(lines) > 2:
        f = font("nunito900", size - 10)
        lines = wrap(words, f, SUB_MAX_W)
    lh = int(f.size * 1.12)
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ds, dl = ImageDraw.Draw(shadow), ImageDraw.Draw(layer)
    sp = tlen(" ", f)
    for line in lines:
        total = sum(tlen(w, f) for w, _ in line) + sp * (len(line) - 1)
        x = SUB_CX - total / 2
        for w, is_hl in line:
            ds.text((x, y + 6), w, font=f, fill=(46, 36, 51, 102), stroke_width=7, stroke_fill=(46, 36, 51, 102))
            dl.text((x, y), w, font=f, fill=hl if is_hl else C["sub_fill"], stroke_width=7, stroke_fill=stroke)
            x += tlen(w, f) + sp
        y += lh
    img.alpha_composite(shadow)
    img.alpha_composite(layer)


def draw_caption(img, title, sub):
    """Подпись воспоминания: бумажная карточка, Lora Italic 52 + Lora 24 капсом, наклон −1°."""
    w, h = 860, 140
    card = rrect((w, h), 6, C["page"], C["page_line"], 2)
    d = ImageDraw.Draw(card)
    f1, f2 = font("lora_i", 52), font("lora", 24)
    d.text(((w - tlen(title, f1)) / 2, 18), title, font=f1, fill=C["sepia"])
    s = sub.upper()
    draw_spaced(d, ((w - tlen(s, f2, 2)) / 2, 90), s, f2, C["caption_sub"], 2)
    place(img, card, (110, 240), angle=-1, shadow_dy=6, shadow=SHADOW_SEPIA)


# ---------------------------------------------------------------- слои и фоны


def overlay_png(path, *, words, speaker=None, characters=None, board=None, hook=None,
                mode="salon", voiceover=False):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    memory = mode == "memory"
    if board and not memory:
        draw_board(img, board)
    if hook:
        draw_hook(img, hook.get("tag", ""), hook.get("title", ""), hook.get("sub", ""))
    ticket_y, subs_y = 1160, 1284
    if speaker:
        ch = (characters or {}).get(speaker, {})
        if memory or voiceover:
            draw_ticket(img, "за кадром", speaker, "", C["sepia"], C["sepia"], ticket_y, memory=True)
            subs_y = 1270
        else:
            draw_ticket(img, f"№{ch.get('num', '')}", speaker, ch.get("role", ""),
                        ch.get("color", C["choco"]), ch.get("role_color", C["walnut"]), ticket_y)
    if words:
        draw_subs(img, words, subs_y, memory=memory)
    img.save(path)


def torn_mask(size, seed=7, margin=28):
    rnd = random.Random(seed)
    w, h = size
    pts = [(x, margin + rnd.randint(-16, 16)) for x in range(0, w, 16)]
    pts += [(w - margin + rnd.randint(-16, 16), y) for y in range(0, h, 16)]
    pts += [(x, h - margin + rnd.randint(-16, 16)) for x in range(w, 0, -16)]
    pts += [(margin + rnd.randint(-16, 16), y) for y in range(h, 0, -16)]
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    return m.filter(ImageFilter.GaussianBlur(3))


def paper_texture(size):
    """Лёгкое зерно бумаги сепией."""
    noise = Image.effect_noise(size, 22).point(lambda v: 128 + (v - 128) // 3)
    tint = Image.new("RGBA", size, (122, 90, 62, 0))
    tint.putalpha(noise.point(lambda v: max(0, v - 128) // 2))
    return tint


def memory_base(src_image, out_path, caption=None, caption_sub=None):
    """Страница книги: бумага #F2E6CC, акварель с рваными краями, виньетка, корешок, загнутый угол, подпись."""
    bg = Image.new("RGBA", (W, H), C["paper"])
    art = Image.open(src_image).convert("RGBA")
    box = (940, 1200)
    s = max(box[0] / art.width, box[1] / art.height)
    art = art.resize((int(art.width * s) + 1, int(art.height * s) + 1), Image.LANCZOS)
    left, top = (art.width - box[0]) // 2, (art.height - box[1]) // 2
    art = art.crop((left, top, left + box[0], top + box[1]))
    art.putalpha(torn_mask(box))
    bg.alpha_composite(art, (70, 390))
    bg.alpha_composite(paper_texture((W, H)))
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse([-260, -260, W + 260, H + 160], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(160))
    edge = Image.new("RGBA", (W, H), (184, 156, 110, 115))
    edge.putalpha(vig.point(lambda v: 115 - v * 115 // 255))
    bg.alpha_composite(edge)
    spine = Image.new("RGBA", (70, H), (0, 0, 0, 0))
    for x in range(70):
        ImageDraw.Draw(spine).line([(x, 0), (x, H)], fill=(122, 90, 62, int(71 * (1 - x / 70))))
    bg.alpha_composite(spine)
    fold = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(fold).polygon([(W - 140, 0), (W, 0), (W, 140)], fill="#E4D3B0")
    bg.alpha_composite(fold)
    if caption:
        draw_caption(bg, caption, caption_sub or "")
    bg.convert("RGB").save(out_path)


def draw_watch(img, cx, cy, r=196):
    d = ImageDraw.Draw(img)
    d.arc([cx - 90, cy - r - 150, cx + 150, cy - r + 10], 200, 320, fill="#D8A64A", width=10)
    d.rounded_rectangle([cx - 24, cy - r - 58, cx + 24, cy - r - 14], 12, fill="#D8A64A")
    d.ellipse([cx - 24, cy - r - 36, cx + 24, cy - r + 12], outline="#D8A64A", width=12)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#E7C065", outline="#A87B2D", width=12)
    ri = int(r * 0.82)
    d.ellipse([cx - ri, cy - ri, cx + ri, cy + ri], fill=C["sub_fill"], outline="#D8A64A", width=6)
    for a, b in (((0, -ri + 4), (0, -ri + 24)), ((0, ri - 24), (0, ri - 4)),
                 ((-ri + 4, 0), (-ri + 24, 0)), ((ri - 24, 0), (ri - 4, 0))):
        d.line([(cx + a[0], cy + a[1]), (cx + b[0], cy + b[1])], fill=C["plum"], width=6)
    d.line([(cx, cy), (cx, cy - 88)], fill=C["plum"], width=8)
    d.line([(cx, cy), (cx + 60, cy - 36)], fill=C["plum"], width=8)
    d.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=C["plum"])
    f = font("russo", 100)
    d.text((cx - tlen("????", f) / 2, cy - 10), "????", font=f, fill=C["coral"])
    f2 = font("nunito900", 28)
    d.text((cx - tlen("ГОД", f2) / 2, cy + 96), "ГОД", font=f2, fill=C["walnut"])


def endcard_png(path, bg_image=None, title="Куда поедем\nдальше?",
                sub="Напишите в комментариях эпоху —\nПалыч уже заводит мотор",
                button="Подписаться", line="За проезд — *подпиской!*", characters=None):
    if bg_image and Path(bg_image).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
        bg = Image.open(bg_image).convert("RGB")
        s = max(W / bg.width, H / bg.height)
        bg = bg.resize((int(bg.width * s) + 1, int(bg.height * s) + 1))
        left, top = (bg.width - W) // 2, (bg.height - H) // 2
        bg = bg.crop((left, top, left + W, top + H)).filter(ImageFilter.GaussianBlur(6)).convert("RGBA")
    else:
        bg = Image.new("RGBA", (W, H), C["plum"])
    bg.alpha_composite(Image.new("RGBA", (W, H), (46, 36, 51, 158)))
    draw_watch(bg, 540, 520)
    d = ImageDraw.Draw(bg)
    y = 790
    f = font("russo", 78)
    for ln in title.split("\n"):
        d.text(((W - tlen(ln, f)) / 2, y), ln, font=f, fill=C["sub_fill"])
        y += 82
    f = font("nunito800", 38)
    y += 26
    for ln in sub.split("\n"):
        d.text(((W - tlen(ln, f)) / 2, y), ln, font=f, fill=C["cream"])
        y += 50
    fb = font("nunito900", 56)
    bw, bh = int(tlen(button, fb)) + 144, 60 + 72
    btn = rrect((bw, bh), bh // 2, C["apricot"])
    ImageDraw.Draw(btn).text((72, 28), button, font=fb, fill=C["plum"])
    sh = rrect((bw, bh), bh // 2, C["button_shadow"])
    by = y + 30
    bg.alpha_composite(sh, ((W - bw) // 2, by + 12))
    bg.alpha_composite(btn, ((W - bw) // 2, by))
    ch = (characters or {}).get("Семён Палыч", {})
    draw_ticket(bg, "№1", "Семён Палыч", "", ch.get("color", C["choco"]), C["walnut"], 1340)
    draw_subs(bg, parse_marked(line), 1430)
    bg.convert("RGB").save(path)

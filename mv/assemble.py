"""
mv.assemble — сборка ролика 1080x1920 из кадров, озвучки, субтитров и музыки (ffmpeg).
Запускается через `python mv.py build <папка выпуска>`.
"""

import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import design  # оформление по стайлгайду

W, H, FPS = 1080, 1920, 30
CHARS_PER_SEC = 14          # скорость чтения, если нет озвучки
SCENE_PAD = 0.35            # пауза после реплики, сек
WORDS_PER_SUB = 5           # слов в одном кусочке субтитров

# ---------------------------------------------------------------- утилиты


def run(cmd):
    """Запускает ffmpeg/ffprobe и показывает ошибку понятно."""
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("\nОШИБКА ffmpeg:\n", " ".join(map(str, cmd)), "\n", res.stderr[-2000:])
        sys.exit(1)
    return res.stdout


def check_ffmpeg():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        sys.exit("Не найден ffmpeg. Установи его и добавь в PATH (см. docs/SETUP.md).")


def media_duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(path)])
    return float(out.strip())


def find_font(custom=None):
    candidates = [custom] if custom else []
    candidates += [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    sys.exit("Не нашёл шрифт с кириллицей. Укажи путь к .ttf в scenario.json -> \"font\".")


# ---------------------------------------------------------------- озвучка


def tts_speechkit(text, voice, out_path, speed=1.0, emotion=None):
    import requests
    key = os.environ.get("YANDEX_API_KEY")
    if not key:
        sys.exit("Для SpeechKit задай YANDEX_API_KEY в .env.")
    data = {"text": text, "lang": "ru-RU", "voice": voice,
            "format": "mp3", "speed": str(speed)}
    if emotion:
        data["emotion"] = emotion
    if os.environ.get("YANDEX_FOLDER_ID"):
        data["folderId"] = os.environ["YANDEX_FOLDER_ID"]
    r = requests.post("https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize",
                      headers={"Authorization": f"Api-Key {key}"}, data=data, timeout=60)
    if r.status_code != 200:
        sys.exit(f"SpeechKit ошибка {r.status_code}: {r.text[:300]}")
    out_path.write_bytes(r.content)


# ---------------------------------------------------------------- простое оформление (без "design" в scenario.json)


def wrap_px(draw, text, font, max_w=W - 140):
    """Переносит текст по реальной ширине в пикселях."""
    lines, cur = [], ""
    for word in text.split():
        test = f"{cur} {word}".strip()
        if draw.textlength(test, font=font) <= max_w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_text_block(draw, lines, font, y, fill, stroke=6):
    for line in lines:
        w = draw.textlength(line, font=font)
        draw.text(((W - w) / 2, y), line, font=font, fill=fill,
                  stroke_width=stroke, stroke_fill=(0, 0, 0))
        y += font.size + 14
    return y


def subtitle_png(path, text, speaker, font_path, hook=None, accent=(255, 214, 0)):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if hook:  # крупный текст-крючок сверху
        f_hook = ImageFont.truetype(font_path, 78)
        draw_text_block(d, wrap_px(d, hook.upper(), f_hook), f_hook, 200, accent, stroke=8)
    y = int(H * 0.68)
    if speaker:
        f_sp = ImageFont.truetype(font_path, 46)
        label = speaker.upper()
        tw = d.textlength(label, font=f_sp)
        d.rounded_rectangle([(W - tw) / 2 - 24, y - 10, (W + tw) / 2 + 24, y + 62],
                            radius=18, fill=(0, 0, 0, 170))
        d.text(((W - tw) / 2, y), label, font=f_sp, fill=accent)
        y += 90
    if text:
        f_tx = ImageFont.truetype(font_path, 64)
        draw_text_block(d, wrap_px(d, text, f_tx), f_tx, y, (255, 255, 255))
    img.save(path)


def endcard_png(path, text, bg_image, font_path):
    if bg_image and Path(bg_image).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
        bg = Image.open(bg_image).convert("RGB")
        bg = cover(bg).filter(ImageFilter.GaussianBlur(25))
        bg = Image.blend(bg, Image.new("RGB", (W, H), (0, 0, 0)), 0.45)
    else:
        bg = Image.new("RGB", (W, H), (15, 15, 20))
    d = ImageDraw.Draw(bg)
    f = ImageFont.truetype(font_path, 84)
    lines = wrap_px(d, text.upper(), f)
    total = len(lines) * (f.size + 14)
    draw_text_block(d, lines, f, (H - total) / 2, (255, 214, 0), stroke=8)
    bg.save(path)


def cover(im):
    """Растягивает картинку, чтобы она заполнила 9:16 без полос."""
    scale = max(W / im.width, H / im.height)
    im = im.resize((math.ceil(im.width * scale), math.ceil(im.height * scale)), Image.LANCZOS)
    left, top = (im.width - W) // 2, (im.height - H) // 2
    return im.crop((left, top, left + W, top + H))


# ---------------------------------------------------------------- сборка сцены


def chunk_text(text, n=WORDS_PER_SUB):
    """Режет реплику на кусочки: сначала по предложениям, потом по n слов."""
    import re
    chunks = []
    for sent in re.split(r"(?<=[.!?…])\s+", text.strip()):
        words = sent.split()
        while len(words) > n + 2:          # не оставляем «хвост» из 1–2 слов
            chunks.append(" ".join(words[:n]))
            words = words[n:]
        if words:
            chunks.append(" ".join(words))
    return chunks or [""]


def render_scene(i, scene, base, work, font_path, tts_cfg, hook, cfg=None):
    cfg = cfg or {}
    styled = bool(cfg.get("design"))
    src = base / scene["image"]
    if not src.exists():
        sys.exit(f"Нет файла сцены: {src}")
    raw_text = scene.get("text", "")
    text = raw_text.replace("*", "")          # звёздочки — только для выделения в субтитрах
    speaker = scene.get("speaker", "")
    mode = scene.get("mode", "salon")
    if styled and mode == "memory" and src.suffix.lower() not in {".mp4", ".mov", ".webm", ".mkv"}:
        page = work / f"memory_{i:02d}.png"
        design.memory_base(src, page, scene.get("caption"), scene.get("caption_sub"))
        src = page

    # 1. звук реплики
    audio = None
    if scene.get("audio"):
        audio = base / scene["audio"]
    elif text and tts_cfg.get("engine") == "speechkit":
        voices = tts_cfg.get("voices", {})
        v = voices.get(speaker, voices.get("default", "filipp"))
        voice = v if isinstance(v, str) else v.get("voice", "filipp")
        speed = 1.0 if isinstance(v, str) else v.get("speed", 1.0)
        emotion = None if isinstance(v, str) else v.get("emotion")
        audio = work / f"tts_{i:02d}.mp3"
        print(f"  озвучка сцены {i + 1} голосом {voice}…")
        tts_speechkit(text, voice, audio, speed, emotion)

    if scene.get("duration"):
        dur = float(scene["duration"])
    elif audio:
        dur = media_duration(audio) + SCENE_PAD
    else:
        dur = max(1.5, len(text) / CHARS_PER_SEC + SCENE_PAD)

    # 2. субтитры кусочками по времени
    overlays, t = [], 0.0
    if styled:
        chunks = design.chunk_words(design.parse_marked(raw_text)) if raw_text else [[]]
        total_chars = sum(len(" ".join(w for w, _ in c)) for c in chunks) or 1
        board = scene.get("board", cfg.get("stop")) if scene.get("board", True) else None
        for k, c in enumerate(chunks):
            seg = dur * len(" ".join(w for w, _ in c)) / total_chars if raw_text else dur
            png = work / f"sub_{i:02d}_{k:02d}.png"
            design.overlay_png(png, words=c, speaker=speaker, characters=cfg.get("characters"),
                               board=board, mode=mode, voiceover=scene.get("voiceover", False))
            overlays.append((png, t, t + seg))
            t += seg
        if i == 0 and isinstance(hook, dict):   # карточка-хук первые секунды
            png = work / "hook.png"
            design.overlay_png(png, words=None, hook=hook)
            overlays.append((png, 0.0, min(dur, hook.get("seconds", 2.0))))
    else:
        chunks = chunk_text(text) if text else [""]
        total_chars = sum(len(c) for c in chunks) or 1
        for k, c in enumerate(chunks):
            seg = dur * len(c) / total_chars if text else dur
            png = work / f"sub_{i:02d}_{k:02d}.png"
            subtitle_png(png, c, speaker, font_path, hook=hook if (i == 0) else None)
            overlays.append((png, t, t + seg))
            t += seg

    # 3. видео ряд
    out = work / f"scene_{i:02d}.mp4"
    is_video = src.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv"}
    cmd = ["ffmpeg", "-y"]
    if is_video:
        cmd += ["-stream_loop", "-1", "-t", f"{dur:.3f}", "-i", str(src)]
        vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
              f"fps={FPS},setsar=1[bg]")
    else:
        frames = int(dur * FPS) + 1
        zoom = scene.get("zoom", 0.0003 if mode == "memory" else 0.0007)
        cmd += ["-loop", "1", "-t", f"{dur:.3f}", "-i", str(src)]
        vf = (f"[0:v]scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,"
              f"crop={W * 2}:{H * 2},"
              f"zoompan=z='min(zoom+{zoom},1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
              f":d={frames}:s={W}x{H}:fps={FPS},setsar=1"
              + (",fade=t=in:st=0:d=0.6:color=0xFBEBD3" if mode == "memory" else "") + "[bg]")
    for png, _, _ in overlays:
        cmd += ["-i", str(png)]
    last = "bg"
    for k, (_, a, b) in enumerate(overlays):
        nxt = f"v{k}"
        vf += f";[{last}][{k + 1}:v]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})'[{nxt}]"
        last = nxt

    # звук: реплика + эффект (sfx) или тишина
    n_in = 1 + len(overlays)
    audio_inputs = []
    if audio:
        cmd += ["-i", str(audio)]
        audio_inputs.append(n_in)
        n_in += 1
    if scene.get("sfx"):
        cmd += ["-i", str(base / scene["sfx"])]
        audio_inputs.append(n_in)
        n_in += 1
    if audio_inputs:
        parts = "".join(f"[{a}:a]aresample=44100,aformat=channel_layouts=stereo[a{j}];"
                        for j, a in enumerate(audio_inputs))
        mix = "".join(f"[a{j}]" for j in range(len(audio_inputs)))
        vf += (f";{parts}{mix}amix=inputs={len(audio_inputs)}:normalize=0,"
               f"apad,atrim=0:{dur:.3f}[aout]")
    else:
        cmd += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=44100:cl=stereo"]
        vf += f";[{n_in}:a]anull[aout]"

    cmd += ["-filter_complex", vf, "-map", f"[{last}]", "-map", "[aout]",
            "-t", f"{dur:.3f}", "-r", str(FPS),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", str(out)]
    run(cmd)
    return out, dur


def render_endcard(text, bg, work, font_path, dur=3.0, styled=False, characters=None):
    png = work / "endcard.png"
    if styled:
        opts = text if isinstance(text, dict) else {}
        design.endcard_png(png, bg_image=bg, characters=characters, **opts)
    else:
        endcard_png(png, text, bg, font_path)
    out = work / "scene_99_end.mp4"
    run(["ffmpeg", "-y", "-loop", "1", "-t", f"{dur}", "-i", str(png),
         "-f", "lavfi", "-t", f"{dur}", "-i", "anullsrc=r=44100:cl=stereo",
         "-vf", f"scale={W}:{H},fps={FPS},setsar=1",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", "-shortest", str(out)])
    return out


# ---------------------------------------------------------------- главный сборщик


def build(project_dir):
    check_ffmpeg()
    base = Path(project_dir).resolve()
    cfg = json.loads((base / "scenario.json").read_text(encoding="utf-8"))
    work = base / "_work"
    work.mkdir(exist_ok=True)
    font_path = find_font(cfg.get("font"))
    tts_cfg = cfg.get("tts", {"engine": "none"})

    print(f"Собираю «{cfg.get('title', base.name)}»: {len(cfg['scenes'])} сцен")
    parts, total = [], 0.0
    for i, sc in enumerate(cfg["scenes"]):
        p, d = render_scene(i, sc, base, work, font_path, tts_cfg, cfg.get("hook"), cfg)
        parts.append(p)
        total += d
        print(f"  сцена {i + 1}: {d:.1f} c")
    if cfg.get("end_card"):
        parts.append(render_endcard(cfg["end_card"], base / cfg["scenes"][0]["image"],
                                    work, font_path, styled=bool(cfg.get("design")),
                                    characters=cfg.get("characters")))
        total += 3.0

    lst = work / "list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    joined = work / "joined.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)])

    out_dir = base / "output"
    out_dir.mkdir(exist_ok=True)
    final = out_dir / f"{base.name}.mp4"
    if cfg.get("music"):
        vol = cfg.get("music_volume", 0.12)
        run(["ffmpeg", "-y", "-i", str(joined), "-stream_loop", "-1", "-i", str(base / cfg["music"]),
             "-filter_complex",
             f"[1:a]volume={vol},aresample=44100[m];[0:a][m]amix=inputs=2:normalize=0:duration=first[a]",
             "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-t", f"{total:.3f}", str(final)])
    else:
        shutil.copy(joined, final)
    print(f"\nГотово: {final}  ({total:.1f} c)")
    if total > 60:
        print("Внимание: ролик длиннее 60 секунд — для клипов лучше 25–45 c.")
    return final

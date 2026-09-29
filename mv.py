#!/usr/bin/env python3
"""
Маршрутка времени — конвейер коротких роликов.

  python mv.py check                       проверить ffmpeg, шрифты, ключи
  python mv.py demo                        собрать тестовый ролик из заглушек
  python mv.py prompts episodes/ep01_rycar промпты в prompts.txt (для ручной генерации в Шедевруме)
  python mv.py images episodes/ep01_rycar  сгенерировать кадры (YandexART)
  python mv.py build  episodes/ep01_rycar  озвучка + монтаж → output/ep01_rycar.mp4
  python mv.py publish episodes/ep01_rycar загрузить в VK + пакет для Rutube
  python mv.py all    episodes/ep01_rycar  images → build (публикация — отдельно, после проверки)
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from mv.config import ROOT, load_env


def cmd_check(_):
    ok = True
    for tool in ("ffmpeg", "ffprobe"):
        found = shutil.which(tool)
        print(f"{'OK ' if found else 'НЕТ'} {tool}")
        ok &= bool(found)
    fonts = ["RussoOne-Regular.ttf", "Nunito-Black.ttf", "Nunito-ExtraBold.ttf",
             "PressStart2P-Regular.ttf", "Lora-Italic.ttf", "Lora-Regular.ttf"]
    for f in fonts:
        found = list((ROOT / "fonts").rglob(f))
        print(f"{'OK ' if found else 'НЕТ'} шрифт {f}")
    for k in ("YANDEX_API_KEY", "YANDEX_FOLDER_ID", "VK_USER_TOKEN", "VK_GROUP_ID"):
        print(f"{'OK ' if os.environ.get(k) else '-- '} {k}")
    try:
        import PIL, requests  # noqa: F401
        print("OK  python-пакеты")
    except ImportError:
        print("НЕТ python-пакеты: pip install -r requirements.txt")
        ok = False
    print("\nГотово к сборке." if ok else "\nЕсть что доустановить (см. docs/SETUP.md).")


def cmd_demo(_):
    from PIL import Image, ImageDraw
    from mv import assemble
    src = ROOT / "episodes" / "ep01_rycar"
    demo = ROOT / "episodes" / "_demo"
    shutil.rmtree(demo, ignore_errors=True)
    demo.mkdir(parents=True)
    cfg = json.loads((src / "scenario.json").read_text(encoding="utf-8"))
    cfg["tts"]["engine"] = "none"
    colors = ["#6B4430", "#3FA39B", "#E76F51", "#3FA39B", "#6B4430", "#CFA052", "#A0714A", "#6B4430"]
    for sc, col in zip(cfg["scenes"], colors * 3):
        p = demo / sc["image"]
        p.parent.mkdir(parents=True, exist_ok=True)
        im = Image.new("RGB", (1024, 1820), col)
        ImageDraw.Draw(im).text((60, 880), "заглушка: " + p.stem, fill="white")
        im.save(p, format="PNG")
    (demo / "scenario.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    assemble.build(demo)


def cmd_prompts(a):
    from mv import images
    images.export_prompts(a.episode)


def cmd_images(a):
    from mv import images
    images.generate_episode(a.episode, variants=a.variants, force=a.force)


def cmd_build(a):
    from mv import assemble
    ep = Path(a.episode)
    cfg = json.loads((ep / "scenario.json").read_text(encoding="utf-8"))
    if cfg.get("tts", {}).get("engine") == "speechkit" and not os.environ.get("YANDEX_API_KEY"):
        print("Нет YANDEX_API_KEY — собираю без озвучки (длина сцен по тексту).")
        cfg["tts"]["engine"] = "none"
    missing = [s["image"] for s in cfg["scenes"] if not (ep / s["image"]).exists()]
    if missing:
        raise SystemExit("Нет кадров: " + ", ".join(missing) + "\nСгенерируй: python mv.py images " + str(ep))
    if cfg.get("tts", {}).get("engine") == "none":
        # собираем по временной копии конфига, не трогая оригинал
        (ep / "_work").mkdir(exist_ok=True)
        orig = (ep / "scenario.json").read_text(encoding="utf-8")
        try:
            (ep / "scenario.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            assemble.build(ep)
        finally:
            (ep / "scenario.json").write_text(orig, encoding="utf-8")
    else:
        assemble.build(ep)


def cmd_publish(a):
    from mv import publish
    if not a.skip_vk:
        publish.vk(a.episode, dry_run=a.dry_run)
    publish.rutube_package(a.episode)


def cmd_all(a):
    cmd_images(a)
    cmd_build(a)
    print("\nПроверь ролик, потом: python mv.py publish", a.episode)


def main():
    load_env()
    ap = argparse.ArgumentParser(description="Маршрутка времени — конвейер роликов")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    sub.add_parser("demo").set_defaults(fn=cmd_demo)
    p = sub.add_parser("prompts")
    p.add_argument("episode")
    p.set_defaults(fn=cmd_prompts)
    for name, fn in (("images", cmd_images), ("build", cmd_build), ("all", cmd_all)):
        p = sub.add_parser(name)
        p.add_argument("episode")
        p.add_argument("--variants", type=int, default=2, help="сколько вариантов каждого кадра")
        p.add_argument("--force", action="store_true", help="перегенерировать существующие кадры")
        p.set_defaults(fn=fn)
    p = sub.add_parser("publish")
    p.add_argument("episode")
    p.add_argument("--skip-vk", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="показать, что будет опубликовано")
    p.set_defaults(fn=cmd_publish)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()

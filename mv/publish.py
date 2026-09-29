"""
mv.publish — публикация готового ролика.

VK: загрузка видео в сообщество через VK API (video.save → upload_url → POST файла).
    Вертикальные короткие видео VK обычно показывает и в Клипах, но это решает сама
    площадка — проверь после первой загрузки. Нужно в .env: VK_USER_TOKEN, VK_GROUP_ID.
    Токен — пользовательский, с правами video и offline, от аккаунта-админа сообщества.

Rutube: открытого API загрузки для авторов нет, поэтому скрипт готовит «пакет публикации»
    (файл + название + описание + теги) для ручной загрузки в studio.rutube.ru
    или для сервиса автопостинга (например, Postmypost).
"""

import json
from pathlib import Path

import requests

from .config import env

VK_API = "https://api.vk.com/method/"
VK_V = "5.199"


def load_meta(ep):
    meta_path = ep / "publish.json"
    if not meta_path.exists():
        raise SystemExit(f"Нет {meta_path}. Попроси Claude сделать пакет публикации для выпуска.")
    return json.loads(meta_path.read_text(encoding="utf-8"))


def video_file(ep):
    f = ep / "output" / f"{ep.name}.mp4"
    if not f.exists():
        raise SystemExit(f"Нет готового ролика {f}. Сначала: python mv.py build {ep}")
    return f


def vk(ep_dir, dry_run=False):
    ep = Path(ep_dir)
    meta, f = load_meta(ep), video_file(ep)
    desc = meta["description"] + "\n\n" + " ".join(meta.get("hashtags", []))
    if dry_run:
        print("VK (пробный режим):", meta["title"], "\n", desc)
        return
    token, group = env("VK_USER_TOKEN"), env("VK_GROUP_ID").lstrip("-")
    r = requests.post(VK_API + "video.save", data={
        "access_token": token, "v": VK_V, "group_id": group,
        "name": meta["title"], "description": desc,
        "wallpost": 1 if meta.get("wallpost", True) else 0,
    }, timeout=60).json()
    if "error" in r:
        raise SystemExit(f"VK video.save: {r['error'].get('error_msg')}")
    upload_url = r["response"]["upload_url"]
    with open(f, "rb") as fh:
        up = requests.post(upload_url, files={"video_file": fh}, timeout=600).json()
    if "error" in up:
        raise SystemExit(f"VK загрузка: {up}")
    vid = up.get("video_id") or r["response"].get("video_id")
    print(f"VK: загружено → https://vk.com/video-{group}_{vid}")


def rutube_package(ep_dir):
    ep = Path(ep_dir)
    meta, f = load_meta(ep), video_file(ep)
    out = ep / "output" / "rutube.txt"
    out.write_text(
        f"ФАЙЛ: {f.name}\n\nНАЗВАНИЕ:\n{meta['title']}\n\nОПИСАНИЕ:\n{meta['description']}\n\n"
        f"ТЕГИ:\n{', '.join(t.lstrip('#') for t in meta.get('hashtags', []))}\n\n"
        f"КОММЕНТАРИЙ ДЛЯ ЗАКРЕПА:\n{meta.get('pinned_comment', '')}\n", encoding="utf-8")
    print(f"Rutube: пакет готов → {out}\nЗагрузи файл в studio.rutube.ru как Shorts и вставь тексты.")

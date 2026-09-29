"""
mv.images — генерация кадров через YandexART (Yandex Cloud / AI Studio).

Для каждой сцены с полем "prompt" и без готовой картинки:
  1. отправляет асинхронный запрос imageGenerationAsync (формат 9:16),
  2. ждёт результат, сохраняет в img/<имя из поля image>,
  3. дополнительные варианты кладёт в img/_variants/ — можно выбрать лучший вручную.

Нужно в .env: YANDEX_API_KEY, YANDEX_FOLDER_ID.
Документация: https://aistudio.yandex.ru/docs/ru/ai-studio/concepts/generation/
"""

import base64
import json
import time
from pathlib import Path

import requests

from .config import env, expand_prompt, style

URL_ASYNC = "https://llm.api.cloud.yandex.net/foundationModels/v1/imageGenerationAsync"
URL_OP = "https://llm.api.cloud.yandex.net:443/operations/{}"


def _headers():
    return {"Authorization": f"Api-Key {env('YANDEX_API_KEY')}",
            "x-folder-id": env("YANDEX_FOLDER_ID")}


def split_prompt(prompt, limit=500):
    """YandexART принимает до ~500 символов в одном сообщении — режем по запятым на несколько."""
    parts, cur = [], ""
    for piece in prompt.split(", "):
        test = f"{cur}, {piece}" if cur else piece
        if cur and len(test) > limit:
            parts.append(cur)
            cur = piece
        else:
            cur = test
    return parts + [cur] if cur else parts


def full_prompt(sc, st):
    base = st["blocks"]["BASE_B" if sc.get("mode") == "memory" else "BASE_A"]
    return f"{expand_prompt(sc['prompt'], st)}, {base}"


def export_prompts(ep_dir):
    """Файл prompts.txt с полными промптами + негатив — для ручной генерации в Шедевруме/Kandinsky."""
    ep = Path(ep_dir)
    cfg = json.loads((ep / "scenario.json").read_text(encoding="utf-8"))
    st = style()
    out = [f"НЕГАТИВ (поле «негативный промпт», если есть):\n{st['blocks']['NEGATIVE']}\n"]
    for sc in cfg["scenes"]:
        if sc.get("prompt"):
            out.append(f"=== {sc['image']} ===\n{full_prompt(sc, st)}\n")
    (ep / "prompts.txt").write_text("\n".join(out), encoding="utf-8")
    print(f"Готово: {ep / 'prompts.txt'} — генерируй, сохраняй кадры в img/ под этими именами.")


def generate(prompt, out_path, seed=None, timeout=240):
    folder = env("YANDEX_FOLDER_ID")
    body = {
        "modelUri": f"art://{folder}/yandex-art/latest",
        "generationOptions": {"aspectRatio": {"widthRatio": "9", "heightRatio": "16"}},
        "messages": [{"weight": "1", "text": part} for part in split_prompt(prompt)],
    }
    if seed is not None:
        body["generationOptions"]["seed"] = str(seed)
    r = requests.post(URL_ASYNC, headers=_headers(), json=body, timeout=60)
    if r.status_code != 200:
        raise SystemExit(f"YandexART ошибка {r.status_code}: {r.text[:300]}")
    op_id = r.json()["id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(5)
        op = requests.get(URL_OP.format(op_id), headers=_headers(), timeout=60).json()
        if op.get("done"):
            if "error" in op:
                raise SystemExit(f"YandexART отказал: {op['error']}")
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            Path(out_path).write_bytes(base64.b64decode(op["response"]["image"]))
            return out_path
    raise SystemExit("YandexART: не дождался картинки, попробуй ещё раз.")


def generate_episode(ep_dir, variants=1, force=False):
    ep = Path(ep_dir)
    cfg = json.loads((ep / "scenario.json").read_text(encoding="utf-8"))
    st = style()
    todo = [s for s in cfg["scenes"] if s.get("prompt") and (force or not (ep / s["image"]).exists())]
    if not todo:
        print("Все кадры уже есть. Для перегенерации: --force")
        return
    print(f"Генерирую {len(todo)} кадров × {variants} вар.")
    for sc in todo:
        prompt = full_prompt(sc, st)
        target = ep / sc["image"]
        for v in range(variants):
            out = target if v == 0 else ep / "img" / "_variants" / f"{target.stem}_v{v + 1}{target.suffix}"
            print(f"  {out.name} …")
            generate(prompt, out, seed=sc.get("seed", 1000 + v))
    print("Готово. Просмотри img/ и img/_variants/, неудачные кадры замени вариантами.")

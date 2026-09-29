"""Загрузка настроек из .env и prompts/style.json."""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env(path=ROOT / ".env"):
    """Простой парсер .env: KEY=VALUE, строки с # — комментарии."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def env(name, required=True):
    val = os.environ.get(name, "")
    if required and not val:
        raise SystemExit(f"Не задан {name}. Впиши его в файл .env (образец — .env.example).")
    return val


def style():
    return json.loads((ROOT / "prompts" / "style.json").read_text(encoding="utf-8"))


def expand_prompt(text, st=None):
    """Подставляет {PALYCH}, {VALYA}, {SALON}, {KNIGHT} … из prompts/style.json."""
    st = st or style()
    for key, val in st.get("blocks", {}).items():
        text = text.replace("{" + key + "}", val)
    return text

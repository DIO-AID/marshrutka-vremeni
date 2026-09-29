# Маршрутка времени

Конвейер коротких вертикальных роликов (9:16, 30–45 с) для VK Клипов и Rutube Shorts.
Старый ПАЗ ездит сквозь эпохи, водитель-историк Семён Палыч рассказывает один настоящий факт в каждом выпуске.

```
сценарий (Claude) → кадры (Шедеврум вручную или YandexART) → озвучка (SpeechKit) → монтаж по стайлгайду (ffmpeg) → VK + пакет для Rutube
```

## Быстрый старт

```bash
pip install -r requirements.txt
python mv.py check          # что установлено, чего не хватает
python mv.py demo           # тестовый ролик из заглушек → episodes/_demo/output/
```

Дальше — [docs/SETUP.md](docs/SETUP.md): шрифты, ключи Yandex Cloud и VK.

## Один выпуск

```bash
python mv.py prompts episodes/ep01_rycar   # промпты в prompts.txt — для ручной генерации в Шедевруме
python mv.py images  episodes/ep01_rycar   # или кадры автоматически через YandexART
python mv.py build   episodes/ep01_rycar   # озвучка + монтаж → output/ep01_rycar.mp4
python mv.py publish episodes/ep01_rycar   # VK + output/rutube.txt для ручной загрузки
```

Публикация — всегда отдельной командой, после того как ты посмотрел ролик.

## Что где

| Путь | Что это |
| --- | --- |
| `mv.py` | Команды конвейера |
| `mv/assemble.py` | Монтаж: кадры, наезд камеры, субтитры, звук, склейка |
| `mv/design.py` | Оформление по **утверждённому** стайлгайду v1: табло, хук, билетики, субтитры, страница-воспоминание, концовка с часами |
| `mv/images.py` | Генерация кадров через YandexART, экспорт промптов |
| `mv/publish.py` | Загрузка в VK, пакет для Rutube |
| `prompts/style.json` | Утверждённые БАЗА А (3D), БАЗА Б (акварель), негатив и паспорта героев — не менять |
| `episodes/<выпуск>/scenario.json` | Сцены: промпт кадра, кто говорит, текст |
| `episodes/<выпуск>/publish.json` | Название, описание, хештеги, закреп |
| `docs/` | План, архитектура, настройка |

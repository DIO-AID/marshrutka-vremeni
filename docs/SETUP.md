# Настройка (один раз)

## 1. Программы
- **Python 3.10+** — python.org, при установке отметь «Add to PATH».
- **ffmpeg** — «release essentials» с https://www.gyan.dev/ffmpeg/builds/, распакуй в `C:\ffmpeg`, добавь `C:\ffmpeg\bin` в PATH.
- В папке проекта: `pip install -r requirements.txt`

## 2. Шрифты стайлгайда → папка `fonts/`
| Шрифт | Где | Какие файлы |
| --- | --- | --- |
| Russo One | https://fonts.google.com/specimen/Russo+One | RussoOne-Regular.ttf |
| Nunito | https://fonts.google.com/specimen/Nunito | Nunito-Black.ttf, Nunito-ExtraBold.ttf (папка static) |
| Press Start 2P | https://fonts.google.com/specimen/Press+Start+2P | PressStart2P-Regular.ttf |
| Lora | https://fonts.google.com/specimen/Lora | Lora-Italic.ttf, Lora-Regular.ttf (папка static) |

## 3. Ключи → файл `.env`
Скопируй `.env.example` в `.env`. **Ключи никому не отправляй и не вставляй в чат.** `.env` в GitHub не попадает.

**Yandex Cloud (картинки + озвучка)**
1. console.yandex.cloud → создать платёжный аккаунт, пополнить (для начала 1000 ₽).
2. Каталог → скопировать его ID → `YANDEX_FOLDER_ID`.
3. Сервисные аккаунты → создать, роли `ai.imageGeneration.user` и `ai.speechkit-tts.user` (или `ai.editor`).
4. У аккаунта → «Создать API-ключ» → `YANDEX_API_KEY`.

**VK**
1. Создать сообщество «Маршрутка времени», ID (цифры) → `VK_GROUP_ID`.
2. Получить пользовательский токен админа с правами `video,offline` (через своё VK-приложение / VK ID) → `VK_USER_TOKEN`.
   Если с токеном не выходит — публикуй вручную, скрипт всё равно готовит тексты.

**Rutube** — ключ не нужен: `publish` готовит `output/rutube.txt`, ролик загружается в studio.rutube.ru.

## 4. Проверка
```bash
python mv.py check
python mv.py demo
```

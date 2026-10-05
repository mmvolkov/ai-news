# ai-news

Генерация материалов по еженедельному выпуску AI-новостей с YouTube-канала
[@ProdAdvice](https://www.youtube.com/@ProdAdvice) для публикации в Telegram и Instagram Reels.

Из одного ролика пайплайн делает:

1. **Дайджест для Telegram**: список новостей, где заголовок — ссылка (на первоисточник из описания
   ролика, а если его нет — на нужную секунду видео) и короткое описание.
2. **Контроль объёма**: подпись гарантированно влезает в лимит Telegram для подписи под фото/видео —
   **1024 видимых символа** (HTML-разметка и адреса ссылок в лимит не входят). Если текст длиннее,
   последние новости отбрасываются автоматически.
3. **Промпт для ChatGPT** — иллюстрация-обложка, она же первый кадр Reels, формат 9:16 (1080×1920).
4. **Сценарий Reels** на 25–35 секунд: хук, сцены, текст на экране, закадровый текст, музыка, подпись.
5. **Задание для Google Gemini (Veo) / Omni** — промпт на генерацию вертикального ролика по сценарию
   (с разбивкой на клипы по 8 с) и полный текст для озвучки.

## Установка

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...   # или `ant auth login`
```

## Запуск

```bash
# Всё автоматически: метаданные + субтитры с YouTube -> Claude -> материалы
python -m ai_news https://youtu.be/rc1MGVebM-4

# YouTube недоступен (сервер, VPN и т. п.): передайте субтитры и описание файлами
yt-dlp --skip-download --write-auto-subs --sub-langs ru --write-description -o "v" https://youtu.be/rc1MGVebM-4
python -m ai_news https://youtu.be/rc1MGVebM-4 --transcript v.ru.vtt --description v.description \
    --title "AI-новости недели" --date 20261004

# Без API: собрать готовый промпт и вставить его в Claude/ChatGPT вручную
python -m ai_news https://youtu.be/rc1MGVebM-4 --prompt-only

# Отредактировали issue.json руками — перерендерить пост и материалы
python -m ai_news https://youtu.be/rc1MGVebM-4 --from-json issues/20261004_rc1MGVebM-4/issue.json
```

Результат появляется в папке `issues/<дата>_<id ролика>/`:

| Файл | Что внутри |
|---|---|
| `telegram_post.html` | Готовая подпись для Telegram (`parse_mode=HTML`), ≤ 1024 символов |
| `materials.md` | Всё сразу: пост, промпт обложки, сценарий Reels, задание для Gemini/Omni, текст озвучки |
| `issue.json` | Структурированный ответ модели (можно править и перерендерить) |
| `transcript.txt` | Транскрипт с таймкодами, по которому делался выпуск |

## Как устроено

- `ai_news/fetch.py` — загрузка названия, описания, глав и субтитров (yt-dlp) или чтение локального
  транскрипта (`.vtt`, `.srt`, `.json3`, `.txt` с таймкодами `12:34`).
- `prompts/system_prompt.md` — редакционная инструкция: правила дайджеста, обложки, сценария и видеопромпта.
  Меняйте стиль канала здесь.
- `ai_news/generate.py` — запрос к Claude (`claude-opus-5-5`) со структурированным выводом по схеме
  `ai_news/schema.py`. Включён серверный fallback: если запрос отклонит классификатор безопасности,
  API повторит его на рекомендованной модели.
- `ai_news/render.py` — сборка HTML-подписи Telegram с подсчётом видимой длины (в UTF-16, как считает
  Telegram) и `materials.md`.

Тесты: `python -m pytest -q`.

## Дальше

Пайплайн легко завернуть в n8n: Schedule Trigger (раз в неделю) → RSS канала
`https://www.youtube.com/feeds/videos.xml?channel_id=<id>` → Execute Command `python -m ai_news {{url}}` →
Telegram `sendPhoto` / `sendVideo` с `caption` из `telegram_post.html` и `parse_mode=HTML`.

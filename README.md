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
npm install -g @anthropic-ai/claude-code   # Claude Code — через него идут запросы по подписке
claude login                               # вход с подпиской Claude Pro/Max
```

Без подписки можно работать через Claude API: `export ANTHROPIC_API_KEY=...` — если переменная задана,
пайплайн обращается к API напрямую, а не к `claude`.

### GitHub Actions

Workflow `.github/workflows/ai-news.yml` запускается вручную: **Actions → AI-новости → Run workflow**,
готовые материалы — в артефакте `issue` на странице запуска. Секреты репозитория
(**Settings → Secrets and variables → Actions**):

- `CLAUDE_CODE_OAUTH_TOKEN` — токен подписки: выполните `claude setup-token` у себя на компьютере
  и вставьте выведенный токен (действует год);
- `GEMINI_API_KEY` — ключ Gemini API ([aistudio.google.com/apikey](https://aistudio.google.com/apikey),
  бесплатный тариф): Gemini сам открывает ролик по ссылке и делает транскрипт с таймкодами;
- `YOUTUBE_API_KEY` — ключ YouTube Data API v3 из того же проекта Google Cloud: название, дата и описание
  ролика со ссылками на источники;
- `ELEVENLABS_API_KEY` — ключ ElevenLabs для озвучки.
- `VEO_API_KEY` — для рилса через Veo (см. ниже).

### Рилс 9:16 через Veo

Галочка **reels** при запуске workflow (локально — флаг `--reels`) генерирует 4 клипа Veo по 8 с
по `video_clips` из выпуска, склеивает их ffmpeg в `reels.mp4` 1080×1920 и накладывает текст каждого клипа.
Клипы сохраняются в `clips/`: при повторном запуске уже готовые не генерируются заново.

#### Через Flow2API (кредиты Google Flow)

Если заданы секреты `FLOW2API_URL` и `FLOW2API_KEY`, клипы генерируются через ваш сервер
[Flow2API](https://github.com/TheSmallHanCat/flow2api) — неофициальную обёртку над Google Flow,
которая тратит кредиты аккаунта Flow (бесплатно — 50 в день; клип `veo-3.1-lite-8s-portrait` — 10 кредитов,
рилс из 4 клипов — 40). Модель меняется переменной `FLOW2API_MODEL`.

1. На своей ВМ: `git clone https://github.com/TheSmallHanCat/flow2api && cd flow2api && docker-compose up -d`.
2. Откройте `http://<ВМ>:8000`, войдите `admin` / `admin` и **сразу смените пароль**; задайте API-ключ,
   добавьте сессию Google-аккаунта Flow и настройте решение капчи (см. README Flow2API).
3. Сделайте сервер доступным из интернета по HTTPS (GitHub Actions ходит к нему снаружи).
4. Секреты GitHub: `FLOW2API_URL` — адрес сервера, `FLOW2API_KEY` — API-ключ из шага 2.

Риски: это автоматизация потребительского продукта Google в обход официального API — аккаунт могут
ограничить или заблокировать, поэтому лучше отдельный Google-аккаунт. Сервер хранит сессию этого
аккаунта: закрывайте его сильным паролем и ключом. Обёртка зависит от устройства Flow и может ломаться
при его изменениях. Flow доступен не во всех странах.

#### Через Gemini API

**Veo в Gemini API платный, бесплатного тарифа нет.** Нужен ключ из проекта Google Cloud с подключённой
оплатой — секрет `VEO_API_KEY` (лучше отдельный проект, чтобы транскрипт Gemini оставался бесплатным).
Модель — `VEO_MODEL`, по умолчанию `veo-3.1-fast-generate-preview`: около $0,10 за секунду 720p,
то есть ≈ $3 за рилс ~32 с.

С серверов GitHub YouTube отвечает yt-dlp «Sign in to confirm you're not a bot», поэтому при заданном
`GEMINI_API_KEY` ролик загружается через Google (`ai_news/google_api.py`), а не через yt-dlp. Запасной
вариант для yt-dlp — секрет `YOUTUBE_COOKIES` с содержимым `cookies.txt` с youtube.com
(локально — `YTDLP_COOKIES=путь/к/cookies.txt`).

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

- `ai_news/google_api.py` — транскрипт через Gemini (модели `GEMINI_MODEL` через запятую, по умолчанию `gemini-3.8-flash,gemini-3.6-flash`;
  при 429/5xx — повторы с паузами, при сбое — следующая модель)
  и метаданные через YouTube Data API; используется, если задан `GEMINI_API_KEY`.
- `ai_news/fetch.py` — загрузка названия, описания, глав и субтитров (yt-dlp) или чтение локального
  транскрипта (`.vtt`, `.srt`, `.json3`, `.txt` с таймкодами `12:34`).
- `prompts/system_prompt.md` — редакционная инструкция: правила дайджеста, обложки, сценария и видеопромпта.
  Меняйте стиль канала здесь.
- `ai_news/generate.py` — запрос к Claude (`claude-opus-5-5`) со структурированным выводом по схеме
  `ai_news/schema.py`: через `claude -p --json-schema` (подписка) или, при заданном `ANTHROPIC_API_KEY`,
  через Claude API с серверным fallback — если запрос отклонит классификатор безопасности,
  API повторит его на рекомендованной модели.
- `ai_news/render.py` — сборка HTML-подписи Telegram с подсчётом видимой длины (в UTF-16, как считает
  Telegram) и `materials.md`.

Тесты: `python -m pytest -q`.

## Скилл для Hermes Agent

`hermes/skills/media/ai-news-digest/` — скилл для [Hermes Agent](https://github.com/NousResearch/hermes-agent):
агент сам клонирует этот репозиторий, запускает пайплайн и отдаёт пост, материалы и рилс. Без подписки Claude
тексты пишет модель Hermes (`--prompt-only` → `issue.json` → `scripts/render_issue.py`).

`hermes/skills/media/youtube-download/` — самостоятельный скилл загрузки с YouTube: метаданные, транскрипт
с таймкодами, видео mp4, аудио m4a (`scripts/yt.py`). Если YouTube блокирует сервер, метаданные берутся
из YouTube Data API, транскрипт — из Gemini.

```bash
mkdir -p ~/.hermes/skills/media
cp -r hermes/skills/media/ai-news-digest hermes/skills/media/youtube-download ~/.hermes/skills/media/
hermes chat --toolsets skills -q "Сделай выпуск AI-новостей по https://youtu.be/<id>"
hermes chat --toolsets skills -q "Скачай аудио и транскрипт https://youtu.be/<id>"
```

## Дальше

Пайплайн легко завернуть в n8n: Schedule Trigger (раз в неделю) → RSS канала
`https://www.youtube.com/feeds/videos.xml?channel_id=<id>` → Execute Command `python -m ai_news {{url}}` →
Telegram `sendPhoto` / `sendVideo` с `caption` из `telegram_post.html` и `parse_mode=HTML`.

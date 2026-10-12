# AI-новости • 11 октября — Reels

- `ai-news_2026-10-11_reels.mp4` — готовый ролик 1080×1920, 29,4 с, со звуком.
- 9 новостей сменяются карточками в нижней трети кадра (~2,5 с каждая), в конце — плашка со ссылкой на https://t.me/MultiCloudFriendsClub.

Пересборка:
1. `node render_cards.mjs cards` — рендер карточек (Playwright + Chromium, шрифты Inter и Noto Color Emoji).
2. Положить исходник рядом как `ai-news_vmm.mp4` и запустить `bash compose.sh`.

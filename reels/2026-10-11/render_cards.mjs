import { chromium } from '/opt/node-tools/node_modules/playwright/index.mjs';
const out = process.argv[2];
const news = [
 ['⚡','Claude Haiku 5.5','Быстрые массовые задачи. Для запросов до 100&nbsp;тыс. токенов: <b>$0,10&nbsp;/&nbsp;$0,50</b> за миллион входных / выходных.'],
 ['🇫🇷','Mistral Large 4','Новая модель для кода и агентов. API в превью, веса обещают к концу октября.'],
 ['🧩','GPT-6 + Intelligent UI','ChatGPT отвечает интерактивными схемами, калькуляторами и мини-приложениями.'],
 ['🚀','Sol Ultrafast','По данным OpenAI, генерирует токены <b>до&nbsp;8× быстрее</b> стандартного Sol в Codex.'],
 ['💰','Claude Max / Team','Ежемесячные API-кредиты: Max — <b>$100&nbsp;/&nbsp;$200</b>, Team — <b>до&nbsp;$500</b> на команду.'],
 ['🎨','Nano Banana 2.1','Улучшены качество картинок, текст и постоянство персонажей.'],
 ['🔎','SynthID Detector','Открыт всем: ищет водяные знаки ИИ в фото, видео и аудио совместимых моделей.'],
 ['🎬','HeyGen Video','Генерация видео со звуком из текста и изображений.'],
 ['🛡','ИИ-безопасность','По данным Axios, ИИ-компании готовятся к возможной масштабной кибератаке.'],
];
const css = `
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1920px;background:transparent;font-family:'Inter',sans-serif;-webkit-font-smoothing:antialiased}
.wrap{position:absolute;left:84px;right:84px;bottom:300px}
.card{position:relative;border-radius:36px;padding:34px 40px 36px;
 background:linear-gradient(160deg,rgba(14,22,44,.86),rgba(8,12,26,.90));
 box-shadow:0 20px 60px rgba(0,0,0,.55),0 0 0 2px rgba(110,200,255,.35) inset,0 0 40px rgba(70,170,255,.25)}
.card:before{content:'';position:absolute;inset:0;border-radius:36px;padding:2px;
 background:linear-gradient(120deg,#5fd4ff,#7c6bff 55%,#ff8bd1);
 -webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;opacity:.9}
.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:22px}
.tag{font-size:26px;font-weight:700;letter-spacing:.06em;color:#bfe9ff;text-transform:uppercase;
 background:rgba(95,212,255,.12);border:1.5px solid rgba(95,212,255,.45);padding:8px 18px;border-radius:999px}
.cnt{font-size:28px;font-weight:700;color:#8fa6c8}.cnt b{color:#fff}
.title{display:flex;align-items:center;gap:20px;font-size:58px;line-height:1.08;font-weight:800;color:#fff;margin-bottom:16px;letter-spacing:-.01em}
.emo{font-family:'Noto Color Emoji';font-size:60px;line-height:1}
.body{font-size:38px;line-height:1.32;font-weight:500;color:#dbe6f7}
.body b{color:#ffd56b;font-weight:700}
.bar{display:flex;gap:8px;margin-top:28px}.bar i{flex:1;height:7px;border-radius:4px;background:rgba(255,255,255,.16)}
.bar i.on{background:linear-gradient(90deg,#5fd4ff,#7c6bff)}
.tgemo{font-family:'Noto Color Emoji'}
.cta .title{font-size:52px}
.btn{display:flex;align-items:center;gap:22px;margin-top:24px;padding:22px 28px;border-radius:26px;
 background:linear-gradient(90deg,#2aa3e8,#1d7fd6);box-shadow:0 10px 30px rgba(42,163,232,.45)}
.btn svg{flex:none}
.btn .l1{font-size:28px;font-weight:600;color:rgba(255,255,255,.85)}
.btn .l2{font-size:40px;font-weight:800;color:#fff;letter-spacing:-.01em}
`;
const tg = `<svg width="78" height="78" viewBox="0 0 240 240"><circle cx="120" cy="120" r="120" fill="#fff"/><path fill="#229ED9" d="M54 117l114-44c5-2 10 1 8 10l-19 91c-1 6-5 8-11 5l-29-21-14 13c-2 2-3 3-6 3l2-30 55-50c2-2 0-3-3-1l-68 43-29-9c-6-2-6-6 0-10z"/></svg>`;
const header = `<span class="tag"><span class="tgemo">🤖</span> AI-новости • 11 октября</span>`;
const pages = news.map(([e,t,b],i)=>`<div class="wrap"><div class="card">
 <div class="top">${header}<span class="cnt"><b>${i+1}</b> / ${news.length}</span></div>
 <div class="title"><span class="emo">${e}</span><span>${t}</span></div>
 <div class="body">${b}</div>
 <div class="bar">${news.map((_,j)=>`<i class="${j<=i?'on':''}"></i>`).join('')}</div></div></div>`);
pages.push(`<div class="wrap"><div class="card cta">
 <div class="top">${header}</div>
 <div class="btn">${tg}<div><div class="l1">Все AI-новости — в нашем Telegram</div><div class="l2">t.me/MultiCloudFriendsClub</div></div></div>
 </div></div>`);
const b = await chromium.launch();
const p = await b.newPage({viewport:{width:1080,height:1920}});
for (let i=0;i<pages.length;i++){
  await p.setContent(`<html><head><style>${css}</style></head><body>${pages[i]}</body></html>`);
  await p.evaluate(()=>document.fonts.ready);
  await p.screenshot({path:`${out}/card${String(i).padStart(2,'0')}.png`,omitBackground:true});
}
await b.close();

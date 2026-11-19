# GoVita Reels Agency — loyiha bilim bazasi

> Bu fayl loyihaning yagona haqiqat manbai. Muhim qaror o'zgarsa — shu yerni yangilang.

## 1. Maqsad
GoVita (govita.uz — O'zbekistondagi onlayn vitamin, sport nutrition va apteka do'koni; agentlikning mijozi) uchun
**har kuni 1 ta tayyor Instagram Reels** avtomatik ishlab chiqarish va 08:00 (Asia/Tashkent) gacha Telegram bot orqali yuborish:
1. Video — 9:16, 1080×1920, 30fps, 40–90s (ideal 55–70s), o'zbekcha ovoz, karaoke-subtitr, musiqa, end-card
2. Cover — 1080×1920 JPG (4:5 grid zonasida ham o'qiladi)
3. Caption + hashtaglar + pin-komment
4. Hisobot — mavzu tanlovi sababi, trend dalillari, fakt manbalari, compliance, ish vaqti

## 2. Biznes qoidalari
- Video **foydali kontent**, reklama emas. Brend oxirgi 20% da bir marta, yumshoq tilga olinadi.
- Har video **hook** bilan boshlanadi (0–3s, ≤12 so'z) va aniq **engagement CTA** bilan tugaydi (komment/saqlash/ulashish).
- Mavzu — o'zbek odamlarining real sog'liq og'riqlari (`knowledge/uz-audience-pains.md`), oxirgi 60 kunda takrorlanmaydi.
- Compliance qat'iy (`knowledge/compliance-rules.md`): davolash kafolati, tashxis, doza tavsiyasi, before/after — yo'q. Har raqam manbali.
- Media faqat litsenziyali (Pexels, Pixabay, Adobe Stock litsenziyalangan bank). YouTube/raqobatchi kontenti faqat **tahlil** qilinadi, montajda ishlatilmaydi.
- Ovoz: ElevenLabs (bu loyiha uchun mijoz qarori, default). VoiceLab (o'zbekcha nativ) ham tayyor: `TTS_PROVIDER=voicelab`.
  VoiceLab timestamp bermaydi → STT bilan so'z timing olinadi va asl matnga moslanadi (`agency/tts/voicelab.py`).
- SFX faqat haqiqiy yozilgan tovushlardan (real-sfx, `brand/sfx/`), sintez yo'q. Agentlar eshita olmaydi — ovoz haqida
  faqat o'lchangan raqamlar (earshot) bilan gapiriladi.

## 3. Arxitektura
```
supercronic 05:00 → bin/run-daily (flock + timeout) → python -m agency.pipeline run
  research   claude -p --agent researcher    → brief.json        (YouTube API, yt-dlp, Meta Ad Library, WebSearch)
  copy       claude -p --agent copywriter    → script.json
  compliance claude -p --agent compliance    → compliance.json   FIX → copy (≤2), FAIL → keyingi g'oya
  tts        agency.tools.tts (ElevenLabs)   → voice.mp3 + alignment.json   davomiylik oralig'idan chiqsa → copy
  assets     claude -p --agent asset-hunter  → assets.json + bank/
  edit       claude -p --agent editor        → timeline.json → build_composition → composition/ (HyperFrames)
  render     agency.tools.render + cover     → final.mp4 (−14 LUFS, ≤45MB) + cover.jpg
  sound      claude -p --agent sound-designer (real-sfx) → SFX qo'shilgan final.mp4   (brand/sfx bo'sh bo'lsa o'tkaziladi)
  qa         qa_check (auto + earshot) + claude -p --agent qa → qa.json   FAIL → edit (≤2)
  send       Telegram: video, cover (doc), caption, pin-komment, hisobot (👍/👎/🔁)
  finalize   state.sqlite (mavzu, hook, asset), oraliq fayllarni tozalash
```
**Prinsip:** LLM faqat fikrlash kerak joyda (tadqiqot, ssenariy, compliance, kadr tanlash, montaj qarorlari, QA).
Deterministik ishlar — Python tool'lar. Timing ovozdan (alignment) olinadi → subtitr/kesimlar 100% sinxron.

Har bosqich `runs/DATE/.stages/<stage>.done` yozadi → qayta ishga tushirilsa joyidan davom etadi.
Max obuna: har agent alohida `claude -p` jarayoni; auth — `CLAUDE_CODE_OAUTH_TOKEN` (`claude setup-token`).

## 4. Stack
- Docker (node:22-bookworm-slim) + Debian chromium + ffmpeg + Python 3.11 + supercronic
- Claude Code CLI 2.1.327 (subagentlar: `.claude/agents/*.md`)
- HyperFrames 0.9.65 (HTML → MP4), GSAP 3.15.1, Inter (@fontsource)
- Python: requests, jsonschema, playwright (system chromium), yt-dlp
- SQLite (`data/state.sqlite`)

## 5. Papkalar
| Yo'l | Nima |
|---|---|
| `agency/` | Python paket: `pipeline.py` (orkestr), `claude_runner.py`, `telegram.py`, `state.py`, `validate.py`, `bot_listener.py`, `doctor.py` |
| `agency/tools/` | Agentlar chaqiradigan CLI tool'lar (yt_trends, yt_transcripts, ad_library, stock_search, tts, build_composition, render, cover, qa_check) |
| `agency/tts/` | TTS adapterlari: `elevenlabs`, `silent` (test) |
| `.claude/agents/` | 6 ta subagent |
| `.claude/skills/govita-video/` | **Mijozning montaj skill'i** (hozir placeholder) |
| `.claude/skills/*` (boshqalar) | Tashqi skill'lar — `skills.lock.json` (pinned commit), `bin/install-skills` o'rnatadi, git'da yo'q |
| `bin/setup-mac` | Mac: global skill'lar + Premiere / After Effects / VoiceLab / earshot MCP |
| `schemas/` | Agentlar orasidagi JSON-kontraktlar |
| `templates/reel/`, `templates/cover/` | HyperFrames va cover HTML shablonlari |
| `knowledge/` | Auditoriya og'riqlari, hooklar, compliance, rubrikalar, raqobatchilar, talaffuz, YouTube so'rovlari |
| `brand/` | `brand.json` (ranglar, shriftlar), logo, musiqa, `products.json` |
| `runs/DATE/` | Kunlik ish papkasi (git'da yo'q) |
| `bank/` | Litsenziyali media banki + `index.json` + `license.csv` (git'da yo'q) |

## 6. Env o'zgaruvchilar (qiymatlar faqat `.env` da)
`CLAUDE_CODE_OAUTH_TOKEN`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `ELEVENLABS_MODEL`, `ELEVENLABS_LANGUAGE_CODE`,
`TTS_PROVIDER`, `YOUTUBE_API_KEY`, `PEXELS_API_KEY`, `PIXABAY_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
`DRY_RUN`, `REEL_MIN_SECONDS`, `REEL_MAX_SECONDS`, `MAX_COPY_LOOPS`, `MAX_EDIT_LOOPS`, `AGENT_TIMEOUT_MIN`,
`PIPELINE_TIMEOUT_MIN`, `RENDER_WORKERS`, `RENDER_QUALITY`, `FINAL_CRF`, `DOCKER_CPUS`, `DOCKER_MEM`. To'liq ro'yxat: `.env.example`.

## 7. Buyruqlar
```bash
docker compose up -d --build                       # ishga tushirish (cron + bot)
docker compose exec agency bin/doctor --claude --telegram   # diagnostika
docker compose exec agency bin/run-daily           # bugungi pipeline (yoki davom ettirish)
docker compose exec agency bin/run-daily --from edit        # montajdan qayta
docker compose exec agency bin/run-daily --idea next        # boshqa g'oya bilan
docker compose exec agency python3 -m agency.pipeline status
bin/install-skills [--global] [--check]            # tashqi skill'lar
bin/setup-mac                                      # Mac: MCP'lar (Premiere, AE, VoiceLab, earshot)
docker compose logs -f agency
pytest tests/test_units.py                         # tez testlar
pytest -m slow tests/                              # render + soxta-claude pipeline testlari
```
Telegram: `/status`, `/run`, `/regen`, tugmalar 👍 / 👎 / 🔁.

## 8. Konventsiyalar
- Agent ↔ agent faqat fayl kontrakti orqali; har kontrakt `python -m agency.validate <schema> <file>` dan o'tadi.
- Tool'lar stdout'ga JSON chiqaradi, xatoda non-zero exit.
- Yangi tashqi manba → `agency/tools/` da tool + agent `.md` da qo'llanma.
- HyperFrames: har timed element `data-start` + `data-duration` + `class="clip"`; faqat deterministik JS; template literal (`${}`) script ichida yo'q (lint xato beradi).
- Commit: Conventional Commits.

## 9. Qarorlar va sabablari
| Qaror | Sabab |
|---|---|
| Har agent alohida `claude -p --agent` | Kichik kontekst, bosqichma-bosqich resume, timeout, Max limitini tejash |
| Timing ovozdan, LLM'dan emas | Subtitr va kesimlar sinxronligi kafolatlanadi |
| `build_composition` shablon + editor boyitadi | Har kuni barqaror sifat; ijodiy erkinlik skill orqali |
| Meta Ad Library — headless brauzer | Rasmiy API faqat siyosiy/EU reklamalarni beradi |
| Debian chromium (Playwright browser emas) | Mac arm64 + x86 da bitta yo'l |
| Bind-mount repo + `node_modules` volume | VS Code'da tahrir darhol konteynerda; `git pull` bilan yangilanish |
| Adobe Stock API o'chiq | Adobe fayllari bank orqali qayta ishlatiladi |
| "AirShot" = **earshot** (Leonxlnx/earshot) | Agentga "quloq": QA'da ovoz/miks o'lchovi; Docker'da `WITH_EARSHOT=1` |
| Tashqi skill'lar vendor qilinmaydi, lock + installer | Litsenziya (Clipwing/skills'da LICENSE yo'q), yangilash oson, repo yengil |
| Premiere/AE MCP faqat Mac'da, interaktiv (`/premiere-polish`) | Ular GUI ilova + CEP/ScriptUI panel talab qiladi; soat 05:00 dagi avtomatik pipeline'da ishonchsiz. Avtomatik render — HyperFrames |
| video-storyboard skill o'rnatilmadi | `image_gen` tool talab qiladi (Codex/ChatGPT), Claude Code'da yo'q |

## 10. Uchinchi tomon integratsiyalar
YouTube Data API v3 (kvota 10k/kun, ~2.5k sarf) · yt-dlp · Meta Ad Library (veb) · Pexels API · Pixabay API ·
ElevenLabs `/v1/text-to-speech/{voice}/with-timestamps` · VoiceLab `/v1/tts` + `/v1/stt` · Telegram Bot API (sendVideo ≤50MB) ·
Claude Code CLI (Max) · Skill'lar: hyperframes, hyperframes-cli, hyperframes-registry, media-use, find-skills, real-sfx,
hyperframes-to-after-effects, earshot, premiere-pro-mcp · Mac MCP: Premiere Pro (CEP), After Effects, VoiceLab, earshot, Blender (qo'lda).

## 11. Glossary
- **Hook** — videoning birinchi 0–3 soniyasidagi diqqatni ushlovchi jumla
- **Rubrika / pillar** — haftaning kuni bo'yicha kontent turi (`knowledge/content-pillars.md`)
- **Shot** — sahna ichidagi bitta kadr (1.5–3s)
- **Bank** — qayta ishlatiladigan litsenziyali media to'plami
- **Max-ekv.** — `claude -p` qaytaradigan `total_cost_usd` (Max obunada pul yechilmaydi, faqat yuk indikatori)

## 12. Known pitfalls
- Mac uyquga ketsa cron ishlamaydi → Energy Saver'da "Prevent sleep" yoki serverga ko'chirish.
- `--dangerously-skip-permissions` root ostida ishlamaydi → konteyner `node` user bilan.
- YouTube yt-dlp ba'zan "bot emasligingizni tasdiqlang" so'raydi → transkriptsiz davom etadi (`partial`).
- Meta Ad Library login so'rasa → `partial: true`, researcher WebSearch bilan to'ldiradi.
- ElevenLabs o'zbekcha talaffuzi modelga bog'liq → `knowledge/pronunciation.json` va `ELEVENLABS_MODEL` bilan sozlang.
- Stok klip shot'dan qisqa bo'lsa kadr muzlaydi → `build_composition` warning beradi.
- Telegram bot 50MB limit → render CRF'ni avtomatik oshiradi.
- Max limiti tugasa agent xato beradi → Telegram alert, keyin `bin/run-daily` bilan davom.
- earshot birinchi ishga tushishda CLAP+AST modellarini yuklaydi (~1GB, `model_cache` volume) — birinchi QA sekin.
- Premiere MCP telemetriyasi default yoqiq — `bin/setup-mac` uni o'chiradi (`~/.premiere-mcp-bridge/config.json`).
- `@voicelab/mcp` npm'da chop etilmagan — manbadan build qilinadi.

## 13. TODO
- [ ] Mijozning `govita-video` skill'ini qo'yish
- [ ] Logo, brend shriftlari, 3–5 litsenziyali musiqa (`brand/`)
- [ ] `brand/products.json` — haqiqiy assortiment
- [ ] Disklaymer matnini yurist bilan tasdiqlash (`knowledge/compliance-rules.md`)
- [ ] ElevenLabs o'zbekcha ovozni tanlash va talaffuzni sinash
- [ ] Haftalik `weekly_review` agenti (👍/👎 → hook-library yangilash)
- [ ] Instagram'ga avtomatik joylash (Meta Graph API) — ixtiyoriy, qo'lda tasdiqdan keyin
- [ ] `brand/sfx/` ga haqiqiy SFX pak (whoosh/hit/pop/riser) — sound bosqichi shundan keyin yoqiladi
- [ ] Mustafo skill paki (mustafo-montaj-usuli, reels-zonali-montaj, viral-reels-scriptwriter …) — arxiv kelgach integratsiya

## 14. Kelajakdagi yaxshilanishlar
- Haqiqiy Instagram statistikasi (reach, saqlash, komment) bilan mavzu tanlovini o'qitish
- Bir nechta mijoz uchun multi-tenant (`clients/<name>/` konfiguratsiya)
- Musiqa beat'iga kesimlarni moslash (`hyperframes beats`)

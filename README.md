# GoVita Reels Agency

Har kuni avtomatik **1 ta tayyor Instagram Reels** (video + cover + matn + hisobot) ishlab chiqarib,
Telegram bot orqali yuboradigan multi-agent tizim. Lokal Docker'da, **Claude Max obunasi** orqali ishlaydi.

```
Tadqiqot → Kopirayter ⇄ Compliance → Ovoz (ElevenLabs | VoiceLab) → Kontent yig'uvchi → Montaj (HyperFrames)
        → Render → SFX (real-sfx) → QA (+ earshot) → Telegram
```

Batafsil arxitektura, qoidalar va qarorlar: [CLAUDE.md](CLAUDE.md).

---

## O'rnatish (bir marta, ~20 daqiqa)

### 1. Talablar
- Docker Desktop (Mac) yoki Docker Engine (Linux), kamida 8 GB RAM
- Node 22+ (faqat host'da `claude setup-token` uchun)

### 2. Klon
```bash
git clone git@github.com:Elmun-Technologies/govita-reels.git
cd govita-reels
cp .env.example .env
```

### 3. Kalitlarni olish va `.env` ni to'ldirish
| Kalit | Qayerdan | Narx |
|---|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | Host'da: `npm i -g @anthropic-ai/claude-code && claude setup-token` (Max akkaunt bilan kiring) | Max obuna |
| `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` | elevenlabs.io → Profile → API Keys; Voices → ovoz ID | ElevenLabs tarifi |
| `YOUTUBE_API_KEY` | console.cloud.google.com → yangi loyiha → "YouTube Data API v3" yoqish → Credentials → API key | bepul |
| `PEXELS_API_KEY` | pexels.com/api | bepul |
| `PIXABAY_API_KEY` | pixabay.com/api/docs (login qilgach sahifada) | bepul |
| `TELEGRAM_BOT_TOKEN` | Telegram'da @BotFather → /newbot | bepul |
| `TELEGRAM_CHAT_ID` | Botga /start yozing → `https://api.telegram.org/bot<TOKEN>/getUpdates` dan `chat.id` | — |

### 4. Brend materiallari
- `.claude/skills/govita-video/` — **video montaj skill'ingizni** shu papkaga qo'ying (`SKILL.md` + fayllari)
- `brand/logo/logo-light.png` — logo (shaffof fon)
- `brand/music/*.mp3` — 3–5 ta litsenziyali trek
- `brand/brand.json` — ranglar va shriftlar
- `brand/products.json` — GoVita assortimenti

### 4.1 Skill'lar va Mac MCP'lar
Docker konteyner skill'larni o'zi o'rnatadi (`skills.lock.json`). Mac'da ham Claude Code bilan ishlash uchun **bir marta**:
```bash
bin/setup-mac        # global skill'lar + Premiere Pro, After Effects, VoiceLab, earshot MCP
claude mcp list      # tekshirish
```
| Vosita | Nima uchun | Qayerda ishlaydi |
|---|---|---|
| hyperframes, hyperframes-cli, -registry, media-use | Montaj, render, tayyor bloklar, rang/audio | Docker pipeline (editor) |
| real-sfx | Kesim/overlay'ga haqiqiy SFX (`brand/sfx/` kerak) | Docker pipeline (sound) |
| earshot | Agentga "quloq": loudness, sync, miks tekshiruvi | Docker pipeline (QA) + Mac MCP |
| find-skills | "… uchun skill top" — yangi skill qidirish | Mac / interaktiv |
| Premiere Pro MCP + skill | `/premiere-polish` — bugungi videoni Premiere'da tahrir uchun yig'ish | Faqat Mac (Premiere ochiq) |
| After Effects MCP, hyperframes-to-after-effects | AE'da motion, HyperFrames → AE | Faqat Mac |
| VoiceLab MCP | O'zbekcha TTS/STT (MCP), pipeline'da `TTS_PROVIDER=voicelab` | Mac MCP + Docker |
| watch (claude-video) | YouTube videoni "ko'rish": `/watch <havola> ...`; researcher top videolar hook'ini tahlil qiladi | Docker/bulut (transkript) + Mac (kadrlar ham) |
| ig-* (13 ta Instagram skill) | Copywriter: hook formulalari va reytingi, caption, "AI hidi"ni tozalash. Interaktiv: `/ig-plan`, `/ig-audit`, `/ig-profile`, `/ig-viral`, `/ig-reply`, `/ig-dm` … | Docker/bulut + Mac |
| Blender MCP | 3D sahnalar — qo'lda o'rnatiladi (`bin/setup-mac` oxirida yo'riqnoma) | Faqat Mac |

### 5. Ishga tushirish
```bash
docker compose up -d --build
docker compose exec agency bin/doctor --claude --telegram   # hammasi ✅ bo'lishi kerak
```

### 6. Birinchi test
```bash
# Test rejimi: Telegram xabarlari [TEST] prefiksi bilan, ovoz jim (ElevenLabs krediti sarflanmaydi)
docker compose exec -e DRY_RUN=1 -e TTS_PROVIDER=silent agency bin/run-daily --force
```
Natijani tekshirgach — haqiqiy ovoz bilan: `docker compose exec agency bin/run-daily --from tts`

Shundan keyin tizim **har kuni 05:00 da o'zi ishlaydi**, 08:30 da video yuborilmagan bo'lsa ogohlantiradi.

---

## Kundalik foydalanish

**Telegram bot:**
- 👍 / 👎 — videoga baho (keyingi mavzu tanloviga ta'sir qiladi)
- 🔁 — bugun boshqa g'oya bilan qayta yaratish
- `/status` — bosqichlar holati · `/run` — qo'lda ishga tushirish · `/regen` — boshqa g'oya

**Terminal (VS Code):**
```bash
docker compose exec agency bin/run-daily                 # davom ettirish (to'xtagan joyidan)
docker compose exec agency bin/run-daily --from edit     # montajdan qayta
docker compose exec agency bin/run-daily --idea B        # B g'oya bilan
docker compose exec agency python3 -m agency.pipeline status
docker compose logs -f agency
```
Kunlik barcha fayllar: `runs/YYYY-MM-DD/` (brief, ssenariy, compliance, assetlar, composition, final.mp4, cover.jpg, log.md).

**Qo'lda tahrir (Claude Code orqali):** loyiha papkasida `claude` → `/daily-reel` yoki `/reel-status`.

## Vaqtni o'zgartirish
`docker/crontab` → `0 5 * * *` ni o'zgartiring → `docker compose restart agency`.

## Test
```bash
pip install -r requirements.txt && npm ci
pytest tests/test_units.py                 # tez
CHROMIUM_PATH=$(which chromium || which google-chrome) pytest -m slow tests/   # render + pipeline (soxta claude bilan)
```

## Muammolar
| Belgi | Yechim |
|---|---|
| `Max obuna limiti tugagan` | Limit tiklanishini kuting → `bin/run-daily` (joyidan davom etadi) |
| Mac'da cron ishlamadi | Mac uyquda bo'lgan: System Settings → Energy → uyquni o'chiring yoki serverga ko'chiring |
| Ovoz noto'g'ri o'qiydi | `knowledge/pronunciation.json` ga almashtirish qo'shing; boshqa `ELEVENLABS_MODEL` sinang |
| Video juda uzun/qisqa | `REEL_MIN_SECONDS` / `REEL_MAX_SECONDS` |
| Mac qotib qoladi | `.env` da `DOCKER_CPUS=2`, `DOCKER_MEM=4g`, `RENDER_WORKERS=2` |
| Docker image juda katta | `.env` da `WITH_EARSHOT=0` → `docker compose build` (earshot'siz, ~1.5GB kichik) |
| SFX qo'shilmayapti | `brand/sfx/` ga wav/mp3 qo'ying → `docker compose exec agency bin/install-skills` |
| Premiere MCP ulanmadi | Premiere → Window > Extensions > MCP Bridge (CEP) → Start; `premiere-pro-mcp --doctor` |

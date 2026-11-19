---
description: (Faqat Mac, Premiere ochiq) Bugungi Reels'ni Premiere Pro'da tahrir uchun yig'ish — klip, ovoz, musiqa, subtitr bilan sequence
argument-hint: "[YYYY-MM-DD]"
allowed-tools: Bash, Read, Glob, Skill
---

Maqsad: avtomatik tayyorlangan bugungi videoni inson qo'lda "polish" qilishi uchun Premiere Pro loyihasiga aylantirish.

1. `premiere-pro-mcp` skill'ini yukla va unga amal qil. Avval `verify_premiere_connection` — ulanmagan bo'lsa,
   foydalanuvchiga ayt: Premiere'ni oching → Window > Extensions > MCP Bridge (CEP) → Start. To'xta.
2. Sana: `$ARGUMENTS` (bo'sh bo'lsa bugun, Asia/Tashkent). Papka: `runs/<sana>/`.
3. O'qi: `timeline.json`, `alignment.json`, `composition/index.html` (shot va overlay timing'lari `data-start`/`data-duration`
   dan), `script.json`.
4. Premiere'da: yangi loyiha `runs/<sana>/premiere/GoVita_<sana>.prproj`, sequence 1080×1920, 30fps.
   - V1: timeline'dagi stok kliplar — composition'dagi `shotNN` vaqtlarida, `media_start` bilan
   - A1: `voice.mp3`, A2: musiqa (timeline.music, volume ≈ −20 dB), A3: `sfx_work/` dagi SFX trek (bo'lsa)
   - Subtitr: `alignment.json` so'zlaridan SRT yasab (`runs/<sana>/captions.srt`) import qil
   - Marker'lar: har sahna boshida (rol: hook/problem/…)
   - Reference sifatida `final.mp4` ni alohida bin'ga qo'y
5. Loyihani saqla va foydalanuvchiga qisqa xulosa: nima import qilindi, qayerda.
Hech narsani render qilma va mavjud fayllarni o'chirma.

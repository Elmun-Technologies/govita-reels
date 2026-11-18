---
description: Bugungi GoVita Reels pipeline'ini ishga tushirish yoki davom ettirish (qo'lda / debug uchun)
argument-hint: "[--from STAGE] [--idea next|A|B|C] [--date YYYY-MM-DD]"
allowed-tools: Bash, Read
---

Production pipeline'ni ishga tushir va natijani qisqa xulosa qil.

1. `python -m agency.pipeline status $ARGUMENTS` — hozirgi holat.
2. `bin/run-daily $ARGUMENTS` — pipeline (har bosqich `claude -p --agent ...` orqali alohida ishlaydi; bu buyruq uzoq davom etishi mumkin — 60–150 daqiqa).
3. Tugagach `runs/<sana>/log.md` ni o'qi va xulosa ber: qaysi bosqichlar o'tdi, xato bo'lsa sababi va qanday davom ettirish.

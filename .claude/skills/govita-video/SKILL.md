---
name: govita-video
description: GoVita Reels montaj qoidalari (mijoz skill'i). Editor agent har montajdan oldin o'qiydi. PLACEHOLDER — haqiqiy skill bilan almashtiring.
---

# ⚠️ PLACEHOLDER

Bu fayl o'rniga mijozning haqiqiy video skill'ini qo'ying:

```
.claude/skills/govita-video/
├── SKILL.md          # asosiy qoidalar (frontmatter: name, description)
└── ...               # skill'ga tegishli boshqa fayllar (references/, assets/, examples/)
```

Haqiqiy skill qo'yilguncha editor agent quyidagi standart qoidalarga amal qiladi:

1. Birinchi 1 soniyada harakat (punch-in yoki tez kesim), hook matni katta va o'qiladigan.
2. Kesim har 1.5–3 soniyada, bir kadr 3.5 soniyadan uzoq qolmaydi.
3. Subtitrlar so'zma-so'z (karaoke), aktiv so'z aksent rangida.
4. Musiqa ovozdan past (volume 0.08–0.14), oxirida fade-out.
5. Oxirida 1.6s end-card: logo + govita.uz.
6. Brend ranglari va shriftlari faqat `brand/brand.json` dan.

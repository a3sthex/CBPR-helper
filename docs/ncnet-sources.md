# NC//NET source verification notes

Дата проверки: 2026-08-19.

## Эпоха и карта

- R. Talsorian Games, **Cyberpunk: Edgerunners Mission Kit**: официальный продукт подтверждает правила и материалы Night City 2070-х, включая карты:  
  https://rtalsoriangames.com/cyberpunk-edgerunners-mission-kit/
- Официальный Cyberpunk 2077 patch archive перечисляет Watson, City Center, Westbrook, Heywood и Santo Domingo как районы карты:  
  https://www.cyberpunk.net/en/news/39092/patch-1-3-list-of-changes
- Структура district/subdistrict дополнительно сверена по индексу карты Cyberpunk 2077: City Center (Corpo Plaza, Downtown), Heywood (Wellsprings, Vista del Rey, The Glen), Pacifica (West Wind Estate, Coastview), Santo Domingo (Arroyo, Rancho Coronado), Watson (Little China, Kabuki, Northside, Arasaka Waterfront), Westbrook (Japantown, North Oak, Charter Hill), Badlands:  
  https://game-maps.com/C77/Cyberpunk-2077-World-Map.asp

Текущая карта NC//NET использует подтверждённую владельцем кампании карту **NightCity.io v0.04.1** (design credit внутри самого изображения: `DESIGN_SETH`) с сохранённым брендингом и ссылкой на источник. Локальная копия: `app/static/maps/night-city-v04-nightcityio.jpg`; поверх неё NC//NET рисует только интерактивные Contract markers. Проверочный архив публикации карты: https://mycyberpunk.de/cyberpunk-2077-news/night-city-io-eine-cyberpunk-2077-map-im-tron-legacy-design/ . Это fan-created 2077-era district artwork, а не официальный asset R. Talsorian Games/CDPR.

Канонические subdistrict IDs соответствуют подписям карты: Watson (Arasaka Waterfront, Northside Industrial District, Little China, Kabuki), Westbrook (Japantown, North Oak, Charter Hill), City Center (Downtown, Corpo Plaza), Heywood (Wellsprings, Vista del Rey, The Glen), Santo Domingo (Arroyo, Rancho Coronado), Pacifica (Coastview, West Wind Estate). По решению владельца кампании Badlands разделены на `Near Westbrook`, `Near Santo Domingo`, `Near Pacifica`; `Orbital Air Space Center` является отдельной локацией. Старые parent district IDs остаются валидными для обратной совместимости.

## Quick Reference

- General Difficulty Values: Cyberpunk RED Corebook, p. 129.
- Range DV: Cyberpunk RED Corebook, pp. 172–173, плюс импортированные Data Pool source tables.
- Autofire: Cyberpunk RED Corebook, pp. 173–174.
- Wound States: Cyberpunk RED Corebook, pp. 186–187.
- Critical Injuries: Cyberpunk RED Corebook, pp. 187–190.
- Rule Book CEMK используется для правил 2070-х, Neuroport и совместимости с Edgerunners Mission Kit.

Проверочная последовательность для каждого нового правила:

1. локальный/официальный PDF;
2. книга и страница в `RULE_SOURCES`;
3. backend regression;
4. frontend display regression;
5. HTTP smoke соответствующего API.

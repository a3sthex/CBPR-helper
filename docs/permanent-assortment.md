# Постоянный ассортимент продавцов (Permanent Supply)

**Связано:** `docs/product-backlog.md` §20.10 (Пакет A — Market Rework).

## Принцип

Постоянный ассортимент — это **всегда доступные, обычные, легальные/базовые** товары по **стандартной книжной цене** (без уличного множителя ±50% из Night Market). Они не участвуют в дневной ротации (`nm_rotation`) и не зависят от `market_stock` (для них действует отдельная модель «бесконечного» stock, см. конфликт №4 в §21).

**Критерии отбора:**
- базовые/универсальные предметы (generic «Standard Quality», а не экзотика и не уникальные бренды);
- дешёвые и доступные (обычно нижняя часть ценового диапазона категории);
- легальные или повсеместные в мире;
- НЕ расходная фарма/наркотики (27 предметов уходят к новому продавцу **Street Pharmacy**, см. §20.9);
- редкое/тяжёлое/экзотическое снаряжение остаётся **только в дневной ротации** Night Market.

Каждый продавец получает свой небольшой permanent-слой + отдельную вкладку (§20.10).

---

## 🔫 Gunmart After Dark — боеприпасы, обычное оружие, ближний бой, гранаты

| Item ID | Цена | Название |
|---|---:|---|
| `ammo-0` | 10 | Basic (универсальные пули, all-purpose) |
| `ammo-1` | 100 | Armor-Piercing (стандартный AP) |
| `ammo-4` | 100 | Expansive (стандартный Hollow Point) |
| `ammo-8` | 10 | Rubber (less-lethal) |
| `guns-0` | 50 | Medium Pistol (Standard) |
| `guns-1` | 100 | Heavy Pistol (Standard) |
| `guns-2` | 100 | Very Heavy Pistol (Standard) |
| `guns-3` | 100 | SMG (Standard) |
| `guns-5` | 500 | Shotgun (Standard) |
| `guns-6` | 500 | Assault Rifle (Standard) |
| `guns-8` | 100 | Bow (Standard) |
| `guns-9` | 100 | Crossbow (Standard) |
| `melee-0` | 50 | Light Melee Weapon |
| `melee-1` | 50 | Medium Melee Weapon |
| `melee-2` | 100 | Heavy Melee Weapon |
| `melee-3` | 500 | Very Heavy Melee Weapon |
| `grenades-14` | 20 | Molotov Cocktail |
| `grenades-7` | 50 | Smoke Grenade |
| `grenades-3` | 100 | Flashbang Grenade |

> Спец-боеприпасы (AP, HP, Incendiary, Slugs/Shells специфичных типов), экзотика, Heavy Weapons и брендовое оружие — только в дневной ротации.

---

## 🛡️ Iron Shell — базовая броня и щиты

| Item ID | Цена | Название |
|---|---:|---|
| `armor-1` | 20 | Leathers |
| `armor-2` | 50 | Kevlar® |
| `armor-3` | 100 | Light Armorjack |
| `armor-5` | 100 | Medium Armorjack |
| `armor-6` | 500 | Heavy Armorjack |
| `armor-0` | 100 | Bulletproof Shield |

> Брендовая/модная броня, Bodyweight Suit, спец-костюмы — только в ротации.

---

## 🦾 Chrome Saint — обычные импланты и Fashionware

| Item ID | Цена | Название | Тип |
|---|---:|---|---|
| `cyberware-49` | 10 | EMP Threading | Fashionware |
| `cyberware-56` | 10 | Memory Chip | Chipware |
| `cyberware-31` | 20 | Standard Cyberfinger | Cyberfingers |
| `cyberware-2` | 100 | Budget Chipware Socket | Neuralware |
| `cyberware-1` | 100 | Discount Cyberaudio Suite | Cyberaudio |
| `cyberware-90` | 100 | Radio Communicator | Cyberaudio |
| `cyberware-88` | 100 | Internal Agent | Cyberaudio |

> Боевой хром (Cyberarm/Leg/Eye foundations, Reflex Co-Processor, Sandevistan, Borgware и т.д.) и дорогие опции — только в ротации/через Fixer.

---

## 💾 Ghost Packet — базовые NET-деки и защитные программы

| Item ID | Цена | Название |
|---|---:|---|
| `net_stuff-5` | 20 | Kirama Training Deck |
| `net_stuff-4` | 100 | Kirama Entry Deck |
| `net_stuff-19` | 100 | Backup Drive |
| `programs-14` | 20 | Shield |
| `programs-12` | 50 | Armor |
| `programs-13` | 50 | Flak |
| `programs-6` | 50 | Sword |
| `programs-0` | 50 | Banhammer |

> Старшие деки, Attack-программы, Black ICE и Hardware-опции — только в ротации.

---

## 🎒 Back-Alley General — инструменты, электроника, расходные материалы повседневные (без наркотиков)

| Item ID | Цена | Название | Equip |
|---|---:|---|---|
| `gear-22` | 20 | Duct Tape | |
| `gear-27` | 20 | Flashlight | EQUIP |
| `gear-47` | 20 | Lock Picking Set | |
| `gear-60` | 20 | Personal CarePack | |
| `gear-72` | 20 | Rope (60m) | |
| `gear-10` | 20 | Carryall | |
| `gear-1` | 20 | Anti-Smog Breathing Mask | |
| `gear-0` | 50 | Airhypo | EQUIP |
| `gear-6` | 50 | Binoculars | |
| `gear-13` | 50 | Computer | |
| `gear-19` | 50 | Disposable Cellphone | |
| `gear-31` | 50 | Handcuffs | |
| `gear-50` | 100 | Medtech Bag | |
| `gear-67` | 100 | Radio Communicator | |
| `gear-82` | 100 | Techtool | |
| `gear-91` | 100 | Agent (Standard) | |

> Наркотики и фарма (27 предметов) — к новому продавцу **Street Pharmacy** (§20.9), не сюда.

---

## 💊 Street Pharmacy (новый продавец, §20.9) — фарма и уличные наркотики

**Решение владельца:** базовая **фарма — постоянный ассортимент**, уличные **наркотики — только дневная ротация**.

### Постоянная фарма (легальные медицинские препараты)

| Item ID | Цена | Название | Источник |
|---|---:|---|---|
| `gear-150` | 200 | Antibiotic | CP:R 150 |
| `gear-151` | 200 | Rapidetox | CP:R 150 |
| `gear-152` | 200 | Sedative | DL:HP 4 |
| `gear-153` | 200 | Speedheal | CP:R 150 |
| `gear-154` | 200 | Stim | CP:R 150 |
| `gear-155` | 200 | Surge | CP:R 150 |
| `gear-156` | 200 | Veritas | DL:HP 4 |
| `gear-157` | 60 | Anti-Cerebral | IR5 127 |
| `gear-164` | 100 | Immunoblockers | CEMK 30 |

### Только ротация (уличные наркотики и боевые наркопрепараты)

`gear-158` Berserker · `gear-159` Black Lace · `gear-160` Blue Glass · `gear-161` Boost · `gear-162` Deliriant · `gear-163` Emerald City · `gear-165` Mindfire · `gear-166` Mortalis · `gear-167` Piranha Smash · `gear-168` Prime Time · `gear-169` Red Lace · `gear-170` Rime · `gear-171` Six Gun · `gear-172` Smash · `gear-173` Synthcoke · `gear-174` Terrifier · `gear-175` Timewarp · `gear-176` White Lace *(18 предметов)*

> Граница «фарма vs наркотик» уточняема: сюда отнесены Medtech-препараты (CP:R 150 + явно медицинские), туда — рекреационные/боевые наркотики (CP:R 357–358 + DLC). Список можно скорректировать.

---

## Итого по constant-слою

- **Gunmart**: 19 позиций · **Iron Shell**: 6 · **Chrome Saint**: 7 · **Ghost Packet**: 8 · **Back-Alley General**: 16 · **Street Pharmacy**: 9 (постоянная фарма)
- ≈ **65 позиций** постоянного базового ассортимента (+18 уличных наркотиков у Street Pharmacy остаются в ротации).

## Принятые решения (2026-08-23)

1. **Базовая фарма у Street Pharmacy — постоянная** (9 медицинских препаратов); уличные наркотики (18) — только ротация.
2. **AP/HP патроны у Gunmart — постоянные** (`ammo-1` Armor-Piercing, `ammo-4` Expansive).
3. **Цена постоянного ассортимента — стандартная книжная**, без уличного множителя.
4. **Хранение — отдельная таблица `market_permanent`** (см. модель ниже).

## Модель хранения `market_permanent`

```text
market_permanent
- vendor_id        TEXT NOT NULL          -- handle продавца (gunmart-after-dark, street-pharmacy, …)
- item_id          TEXT NOT NULL          -- catalog item ID
- sort_order       INTEGER NOT NULL DEFAULT 0
- created          REAL NOT NULL
- PRIMARY KEY (vendor_id, item_id)
```

- Заполняется curated-сидом при первой миграции из списка выше; не ключуется по `market_day` (в отличие от `market_stock`) — stock «бесконечный».
- `GET /api/nightmarket` отдаёт permanent-предложения отдельным блоком у каждого vendor (флаг `permanent: true`, без `street_price`/`stock`/`new_today`).
- `POST /api/buy` для permanent-item: проверяет наличие в `market_permanent` (а не в дневной ротации), цену берёт книжную, не трогает `market_stock`.
- Новый продавец **Street Pharmacy** добавляется в `NIGHT_MARKET_VENDORS` с persona-стилем ripperdoc/clinic; `gear`-расходники исключаются из пула Back-Alley General.

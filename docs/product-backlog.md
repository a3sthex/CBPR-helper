# NC//NET — продуктовый аудит и рабочий backlog

**Статус:** живой документ для дальнейшего обсуждения  
**Дата:** 2026-08-21  
**Ветка:** `arena/01a020fb-cbpr-helper`

Этот документ фиксирует обнаруженные проблемы, идеи владельца проекта и рекомендации по их развитию. Это пока не спецификация реализации: спорные решения вынесены в отдельные вопросы.

## 1. Продуктовые принципы

1. **NC//NET остаётся внутриигровой сетью, а не просто таблицей правил.** Магазины, жильё, контракты, публикации и персонажи должны быть частью мира.
2. **Доверие + прозрачный аудит — основной режим кампании.** Игрок может свободно вести персонажа, а постоянные изменения попадают в понятный журнал before/after. Строгий режим подтверждения GM можно оставить опциональным для других кампаний.
3. **Database и Market — разные сущности.** Database отвечает на вопрос «что существует и как работает», Market — «что сейчас реально можно купить и у кого».
4. **Удаление не должно незаметно разрушать историю.** Для связанных сущностей сначала используются archive/tombstone/trash, а hard delete выполняется с предварительным показом зависимостей.
5. **Атмосфера не должна мешать пониманию.** Внутриигровые термины можно оставлять на английском, но действия, фильтры и пояснения должны быть однозначными в выбранном языке.
6. **Публичный Dossier не равен полному Character JSON.** Нужны уровни видимости для биографии, механики, имущества и служебных заметок.

---

## 2. Night Market, продавцы и Full Catalog

### Текущее состояние

- Night Market Showcase ежедневно выбирает набор предметов и меняет цены.
- В Showcase нельзя открыть нормальное описание предмета.
- У Showcase нет поиска, сортировки и удобной группировки.
- Full Catalog позволяет немедленно купить почти любой предмет по каталожной цене.
- Из-за этого Night Market теряет игровую и механическую ценность.

### Предлагаемая структура

#### A. Database / Codex

Справочник, а не магазин:

- все существующие предметы;
- полное описание и источник;
- характеристики и совместимость;
- фильтры и сравнение;
- **без мгновенной покупки**;
- действие `Find on Market` / `Найти продавца`.

#### B. Legal Retail / Common Supply (опционально)

Постоянно доступные обычные товары:

- базовое оружие и патроны;
- одежда;
- стандартные услуги;
- предметы до заданной Availability/Price Category;
- фиксированная цена.

Этот слой нужен только если кампания хочет разрешить свободную покупку обычных предметов вне Night Market.

#### C. Night Market Vendors

Несколько продавцов с отдельным ассортиментом, характером и ценами. Например:

| Продавец | Ассортимент |
|---|---|
| **Chrome Saint** | Cyberware, Fashionware, услуги установки |
| **Gunmart After Dark** | Guns, Melee, Ammo, Gun Upgrades |
| **Iron Shell** | Armor, Shields, защитное снаряжение |
| **Ghost Packet** | Programs, NET Gear, Black ICE |
| **Nomad Exchange** | Vehicles, Vehicle Upgrades, тяжёлое снаряжение |
| **Back-Alley General** | Gear, Drugs, Tools, Consumables, случайный хлам |

У каждого продавца:

- собственная Persona;
- локация на карте;
- категории и уровень редкости;
- отдельный price multiplier;
- время обновления ассортимента;
- отношение/репутационный порог;
- ограниченный остаток товара;
- специальные предложения;
- кнопка информации и полное описание.

### Сортировка и фильтры Market

- по имени;
- по цене;
- по скидке/наценке;
- по категории и Type;
- по источнику;
- по Damage, ROF, SP, HL;
- «доступно моему персонажу»;
- «могу себе позволить»;
- «совместимо с моим оружием/cyberware»;
- «только consumable»;
- «только новое сегодня».

### Рекомендация

Главное решение: **Full Catalog перестаёт быть универсальным магазином**. Он остаётся справочником. Реальная покупка идёт через постоянную розницу или конкретных продавцов Night Market. Это делает Showcase полезным и усиливает атмосферу.

---

## 3. Предметы: использование, расходники и состояние

### Требование

Предметы, которые можно использовать, должны иметь действие `Use`. При использовании количество уменьшается. Для расходников нужна явная пометка `Consumable`.

### Предлагаемая модель

Поля каталога:

```text
stackable             можно складывать в один inventory stack
consumable            расходуется при использовании
consume_amount        сколько единиц тратится за действие (обычно 1)
charges_max           число зарядов, если предмет многоразовый
use_effect             структурированный эффект или текст
use_context            combat | downtime | medical | net | general
```

Состояние экземпляра:

```text
carried
stored
equipped
installed
consumed
broken
```

### Действия

- `Use 1` — уменьшает `qty`;
- `Use multiple` — для патронов, медикаментов и ресурсов;
- `Equip / Unequip`;
- `Install / Uninstall` для cyberware;
- `Reload` для ammo;
- `Repair`;
- `Move to Stash`;
- `Discard`;
- `Give to Character` (будущее расширение).

Каждое постоянное действие попадает в Character Ledger.

### Важное ограничение

Не стоит автоматически считать расходником всё в категориях Ammo/Grenades/Gear. Лучше импортировать структурированный флаг и иметь ручные исключения: некоторые предметы имеют заряды, некоторые являются контейнерами, некоторые не исчезают после применения.

---

## 4. Свободное редактирование Character Sheet

### Решение владельца проекта

Оставить свободное редактирование персонажей. Игрокам не нужно каждый раз отвлекать GM ради найденного предмета, траты денег или исправления листа. Контроль осуществляется через журнал изменений.

### Рекомендуемая реализация

#### Режим кампании по умолчанию: Trust + Audit

Владелец персонажа может менять:

- narrative-поля;
- характеристики и навыки;
- роли;
- Cash/IP с указанием причины;
- inventory;
- armor/cyberware;
- Lifestyle/Housing;
- custom items.

Сервер:

- ограничивает типы и разумные диапазоны;
- не позволяет записать повреждённый JSON;
- создаёт одну агрегированную запись журнала на сохранение;
- хранит before/after/diff, actor, time и reason;
- позволяет GM посмотреть и откатить изменение;
- опционально уведомляет GM о крупных изменениях.

#### Дополнительный режим: Strict Approval

Можно предусмотреть позже как настройку кампании, но не делать обязательным:

- механические изменения создают request;
- GM подтверждает или отклоняет.

### UX журнала

Журнал должен показывать не сырой JSON, а понятные события:

```text
V · 21 Aug 01:40
Cash: 1250 → 750 (-500)
Inventory: + Grapple Gun
Reason: loot from session
```

Желательны:

- фильтры по категории;
- сравнение before/after;
- `Revert this change` для GM/Admin;
- отметка `Player edit`, `Market`, `Aftermath`, `GM correction`, `Import`.

### Риск

Audit не предотвращает читерство, а только делает его видимым. Для закрытой дружеской кампании это приемлемо. Перед открытой публичной регистрацией нужен переключатель режима кампании.

---

## 5. Character Sheet и печать

### Проблемы текущей печати

- используется обычный экранный layout;
- книжная ориентация неудобна;
- в печать попадают кнопки и интерактивные элементы;
- получается слишком много страниц;
- структура не похожа на привычный лист Cyberpunk RED.

### Рекомендация

Не пытаться чинить это только `@media print` поверх текущего экрана. Нужен отдельный **Print Character Sheet renderer**.

Предлагаемый формат:

```text
A4 Landscape / Letter Landscape
Page 1: Identity, Role, Stats, Derived, Skills, Combat
Page 2: Weapons, Armor, Inventory, Cyberware, Lifepath, Notes
```

Требования:

- никаких кнопок, вкладок, scroll-контейнеров и sticky-элементов;
- фиксированная сетка;
- повторяемые заголовки таблиц;
- разрывы страниц только между секциями;
- чёрно-белый режим;
- режим с тематическими цветами;
- предварительный просмотр;
- компактный и полный варианты;
- Portrait включается опционально.

### Импорт/экспорт оригинального листа

Разделить задачу на этапы:

1. **JSON import без подтверждения GM** — самый надёжный первый этап.
2. **Fillable PDF import** — чтение AcroForm-полей официального заполняемого PDF, mapping → draft → preview → import.
3. **Скан/фото PDF** — OCR; значительно сложнее и ошибочнее, не первая версия.

Импорт выполняет сам владелец персонажа. Перед сохранением показывается preview и предупреждения, но GM approval не требуется. В ledger создаётся событие `Character imported`.

Нужно отдельно проверить лицензионные ограничения перед распространением заполненного официального PDF-шаблона. Импорт пользовательского файла безопаснее, чем включение чужого шаблона в публичную поставку.

---

## 6. Crew Registry и Portraits

### Проблемы

- нет Portrait на карточке персонажа;
- Portrait не показывается в открытом roster modal;
- не показывается Avatar владельца;
- группировка строится вокруг имени владельца, что конфликтует с privacy;
- публичный payload сейчас раскрывает слишком много полей Character Sheet.

### Предлагаемый дизайн карточки

```text
[Character Portrait]
V
Solo 4 · PUBLIC
HP 35/40 · HUM 42/50
[маленький Avatar владельца] Player Name (если разрешено privacy)
```

Правила:

- Character Portrait — главный визуальный элемент;
- Account Avatar — маленький secondary badge;
- если `show_display_name=false`, Account Avatar и имя не показываются;
- seed/Folio characters получают отдельную архивную подпись;
- при отсутствии Portrait используется Role art или тематический placeholder.

Лучше перейти от маленького modal к полноценному маршруту публичного Dossier.

### Privacy до публичного запуска

Публичный Dossier нужно разделить на уровни:

- Public: Handle, Role, Portrait, Appearance, публичная Biography;
- Optional: Stats, Skills, Inventory, Lifepath;
- Owner/GM only: Notes, Cash, IP, служебные поля.

Реальные имена из Folio не должны автоматически публиковаться в интернете.

---

## 7. Database: непонятные и непереведённые теги

### Причина текущего поведения

`shortField()` содержит жёстко заданные русские подписи:

```text
Mag → «маг »
ROF → «СКО »
```

поэтому они появляются даже в английской версии. Числа из Excel хранятся строками вида `12.0`, `1.0`, поэтому UI показывает лишний `.0`. Поле `Hands` вообще может выводиться как голое `1.0` без подписи.

### Что эти поля означают

- `Mag 12` — вместимость магазина;
- `ROF 2` — Rate of Fire, число атак за Action;
- `Hands 1` — сколько рук требуется;
- `Conceal` — можно ли скрыть оружие;
- `Damage 2d6` — урон.

### Исправление

1. Карточки Database должны использовать нормализованный `mechanics`, а не первые случайные поля Excel.
2. Убирать `.0` у целых значений на этапе импорта.
3. Ввести EN/RU labels:

| Key | EN | RU |
|---|---|---|
| magazine | Mag | Магазин |
| rof | ROF | Скорострельность |
| hands | Hands | Руки |
| concealable | Concealable | Скрываемое |
| damage | Damage | Урон |
| quality | Quality | Качество |

4. Не показывать голые значения без label.
5. Добавить tooltip/legend «Что означает тег?».

### Armor tags

Импорт уже вычисляет `armor_locations` и `armor_bundled`, но Database почти не показывает эти данные. Добавить явные теги:

```text
HEAD
BODY
SHIELD
HEAD + BODY SET
PURCHASED SEPARATELY
```

На русском:

```text
ГОЛОВА
ТЕЛО
ЩИТ
ПОЛНЫЙ КОМПЛЕКТ
ПОКУПАЕТСЯ РАЗДЕЛЬНО
```

Также показывать SP, penalties и bundled/separate semantics.

---

## 8. Theme consistency audit

### Подтверждённая причина кнопки Open Contracts

`.btn-primary` использует жёстко заданные цвета:

```css
background: linear-gradient(135deg, #00c9e0, #0079a8);
border-color: #00d5f0;
color: #041018;
```

Поэтому кнопка не реагирует на Custom Theme. В проекте есть и другие hardcoded `rgba(0,229,255,...)`, `rgba(255,45,120,...)` и hex-цвета.

### Что нужно сделать

Полный theme audit:

- кнопки;
- hover/focus;
- badges;
- nav active state;
- cards;
- map markers;
- modals;
- form focus;
- glow/shadow;
- scrollbar;
- mobile navigation;
- connect gate;
- print colors.

Все компоненты переводятся на semantic variables:

```text
--color-primary
--color-on-primary
--color-secondary
--color-accent
--color-danger
--surface-1/2/3
--border
--focus
--shadow-primary
```

Для градиента кнопки использовать `color-mix()` от текущего `--primary`, а не исходный cyan.

### «Криво вырезанная» Open Contracts

Нужно отдельно воспроизвести на фактическом разрешении владельца. Возможные причины:

- line-height/padding у ссылки с `.btn-primary`;
- baseline alignment в `.page-head`;
- перенос `.row`;
- отличия `<a>` от `<button>`;
- clipping родителем на конкретной ширине/масштабе шрифта.

Добавить визуальные regression screenshots для основных тем и ширин 390/768/1440 px.

---

## 9. Карта: zoom, pan и слои

### Zoom/Pan

Добавить:

- кнопки `+`, `−`, `Reset`;
- zoom колёсиком;
- pinch zoom на телефоне;
- drag/pan;
- ограничение границ;
- сохранение положения;
- keyboard controls;
- доступный текстовый список как альтернатива.

Важно масштабировать карту и SVG marker overlay одной матрицей, чтобы маркеры не уезжали.

### Layers

```text
Contracts
Housing
Storylines
Vendors
Personas / Factions
Session locations
```

При большом количестве точек понадобится clustering.

---

## 10. Housing map

Идея хорошо соответствует diegetic-концепции.

### Модель

```text
Property
- district/subdistrict
- building/name
- type
- lifestyle
- rent
- capacity
- description
- map coordinates

Residence
- character_id
- property_id
- since/until
- roommates
- visibility: private | crew | public
- custom label
```

### Возможности

- игрок отмечает жильё персонажа;
- roommates/crew housing;
- история переездов;
- rent reminders;
- Lifestyle/Housing синхронизируются с Dossier;
- GM может создавать известные здания;
- фильтр жилых объектов на карте;
- личные и публичные pins.

### Privacy

На карте отображаются только **внутриигровые адреса**, никогда реальные адреса игроков. По умолчанию residence private.

---

## 11. Удаление контента

### Требование

- Admin может удалять архивные и активные записи;
- пользователи могут удалять созданный ими контент.

### Рекомендация

Не делать один безусловный `DELETE FROM ...`.

#### Пользователь

- свой Feed post: `Withdraw/Delete`;
- свой Comment: tombstone `Комментарий удалён автором`, чтобы не ломать thread;
- свой Dossier: hard delete без связей, archive при наличии истории;
- своя заявка на Contract: withdraw;
- GM удаляет/архивирует свои Contracts, Personas и Storylines.

#### Admin

- `Archive`;
- `Hide` с причиной;
- `Move to Trash`;
- `Restore`;
- `Permanent purge`.

Перед permanent purge показывать dependency preview:

```text
Contract #12 references:
- 5 signups
- 1 session
- 3 feed posts
- 2 media files
```

Связанный исторический контент лучше tombstone/anonymize, а не разрушать. Audit log не удаляется обычной кнопкой; emergency purge создаёт отдельную admin audit запись.

Рекомендуемый Trash retention: 30 дней.

---

## 12. Чат

### Оценка идеи

Полноценный общий чат полезен, но дорог по сложности: real-time transport, unread, moderation, retention, attachments, privacy и abuse controls. Он также частично дублирует Discord/VK и City Feed.

### Рекомендуемый первый этап

Не общий мессенджер, а контекстные каналы:

1. **Contract Crew Channel** — доступен GM и Crew;
2. **Session Channel** — короткие сообщения во время игры;
3. **Persona/Character identity** — сообщение публикуется от выбранного автора;
4. System messages: join, leave, promotion, time changed.

Для маленькой кампании достаточно polling раз в 5–10 секунд или SSE; WebSocket-инфраструктуру можно не вводить сразу.

После проверки востребованности добавить:

- личные сообщения;
- общий OOC канал;
- attachments;
- reactions;
- moderation.

City Feed остаётся публичной асинхронной лентой, Chat — оперативной коммуникацией.

---

## 13. Дополнительные предложения

### Calendar

- календарь Contracts;
- RSVP `Yes / Maybe / No`;
- `.ics` export;
- напоминания;
- отображение в Europe/Moscow и локальном часовом поясе.

### Dice Log

Сохранение бросков с visibility:

```text
private | crew | session | public | gm
```

### Notifications

- unread badge;
- polling;
- mark all read;
- filters;
- настройки типов уведомлений.

### Backup/Restore

- ежедневный SQLite online backup;
- backup uploads;
- 7–14 поколений;
- Admin показывает время последней успешной копии.

### PWA

- установка на телефон;
- offline Quick Reference;
- кэш последнего Dossier;
- manifest/icons.

### LAN deployment mode

Добавить официальную команду установки:

```text
deploy/install.sh --lan
```

которая безопасно настраивает `0.0.0.0`, non-Secure cookie для домашнего HTTP и ограничение firewall локальной подсетью. Сейчас это делается ручным systemd override.

---

## 14. Приоритеты

### P0 — до публичного доступа

1. Privacy payload для Dossiers/Roster/Folio.
2. Сильные пароли, invite registration, session controls.
3. Атомарные транзакции для Crew, Market, IP.
4. Проверка URL schemes.
5. Автоматические backups.

### P1 — основной продуктовый пакет

1. Trust + Audit character editor.
2. Предметные состояния и consumables.
3. Market vendors + Database без универсальной покупки.
4. Database tags/i18n/armor locations.
5. Crew Registry portraits.
6. Dedicated landscape print sheet.
7. JSON import.

### P2 — расширение мира

1. Map zoom/pan/layers.
2. Housing map.
3. Contract Crew Chat.
4. Calendar.
5. Notifications badge.
6. Fillable PDF import.

### P3 — технический долг

1. Разделить `server.py`, `app.js`, `ncnet.js`, CSS.
2. Убрать N+1 queries.
3. Pagination/summary endpoints.
4. Browser E2E и visual regression по темам.
5. Health endpoint, HEAD, self-hosted fonts.

---

## 15. Предлагаемый порядок ближайшей реализации

### Пакет A — Catalog & Market Rework

1. Исправить numeric normalization и EN/RU item tags.
2. Добавить item detail во все Market cards.
3. Добавить sorting/filtering/compare.
4. Вывести armor locations.
5. Убрать мгновенную покупку из Database/Full Catalog.
6. Добавить Vendor Personas и vendor-specific stock.

### Пакет B — Character Ownership

1. Вернуть безопасное свободное редактирование.
2. Расширить ledger до понятных diff events и revert.
3. Добавить custom/found items.
4. Consumable/use/equip/install.
5. JSON import.

### Пакет C — Visual/Print/Roster

1. Theme consistency audit.
2. Исправить Open Contracts.
3. Portraits и owner avatars в Crew Registry.
4. Новый landscape print renderer.
5. Visual regression по темам и разрешениям.

### Пакет D — World Layer

1. Zoomable layered map.
2. Housing.
3. Vendor locations.
4. Contract Crew Channel.

---

## 16. Открытые вопросы для следующего просмотра

1. Какие предметы должны быть всегда доступны в Legal Retail, если Full Catalog больше не магазин?
2. Сколько продавцов Night Market нужно в первой версии: 3, 5 или 6?
3. Stock ограничивается по количеству или только по наличию позиции?
4. Может ли игрок создавать полностью custom item без каталога?
5. Нужна ли GM notification на изменения Stats/IP/Cash при Trust + Audit?
6. Какие части публичного Dossier видны по умолчанию?
7. Печатный лист должен быть на 1, 2 или 3 страницах?
8. Fillable PDF import ограничивается конкретной официальной формой или поддерживает mapping profiles?
9. Chat нужен только внутри Contract или также общий OOC?
10. Housing влияет на ежемесячные расходы автоматически или остаётся narrative?
11. Может ли Admin permanent-purge audit history?
12. Нужен ли отдельный Stash для жилья/crew вместо единого Inventory?

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
Key Locations / POI
Housing
Storylines
Vendors
Personas / Factions
Session locations
```

### Key Locations / Points of Interest

Добавить постоянные маркеры известных мест Night City, например:

```text
Afterlife
Arasaka Tower
Konpeki Plaza
Totentanz
Trauma Team / Hospitals
NCPD precincts
Megabuildings
Major corporate offices
Fixer bars and clubs
Transit hubs
Gang headquarters
Campaign-specific landmarks
```

Список и состояние мест должны соответствовать выбранной эпохе 2070-х. Перед добавлением системного POI нужно сверять название, статус и положение с CEMK/картой/официальным источником; места другой эпохи помечаются как historical/ruined/rebuilt, а не молча смешиваются.

Предлагаемая модель:

```text
locations
- id / slug
- name_en / name_ru
- kind
- district_id / subdistrict_id
- map_x / map_y (normalized coordinates)
- address_text
- status: active | closed | ruined | rebuilt | secret
- visibility: public | crew | gm
- era_from / era_to
- public_description
- gm_description
- source / source_page
- image_media_id
- owner_persona_id / organization_persona_id
- parent_location_id
- created_by / created / updated
```

Категории POI:

- Bars & Clubs;
- Corporate;
- Medical;
- Government/NCPD;
- Gang Territory;
- Shops & Vendors;
- Housing/Megabuildings;
- Transit;
- Landmarks;
- Mission Sites;
- Memorials.

Поведение карты:

- отдельная форма и цвет marker для каждого kind;
- фильтры по категориям;
- поиск по имени;
- marker clustering при отдалении;
- tooltip с названием, категорией и районом;
- click открывает Location card;
- deep link `#/locations/:id`;
- кнопки `Build Contract Here`, `Open Vendor`, `Show Residents`, `Related Feed` согласно правам;
- Public/GM/Classified layers;
- связь с Contracts, Storylines, Feed posts, Personas, Organizations, Vendors, Housing и Sessions.

Location card может показывать:

- изображение;
- публичное описание;
- владельца/контролирующую организацию;
- связанных Personas;
- текущего Vendor;
- персонажей-резидентов согласно privacy;
- активные и исторические Contracts;
- связанные City Feed публикации;
- историю смены статуса/владельца.

GM/Admin нужен визуальный редактор координат: открыть карту, перетащить marker в нужную точку, сохранить normalized `x/y`. Системные каноничные POI загружаются seed-данными, пользовательские места кампании хранятся отдельно и могут редактироваться без изменения seed.

Afterlife связывается сразу с несколькими будущими механиками:

- постоянный POI на карте;
- Persona/Organization;
- Location page;
- Afterlife Menu и Legacy Drinks;
- Memorial Wall;
- место встречи Contract;
- Feed и Storyline events.

При большом количестве точек понадобится clustering.

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

## 14. Preview перед публикацией Feed post и Contract

### Требование

Перед окончательной публикацией пользователь должен увидеть материал так, как его увидят остальные. Это особенно важно для изображений, длинного текста, выбранной Persona/Character, classified-полей и карточки Contract на карте.

### Feed post preview

В composer добавляется последовательность:

```text
Edit → Preview → Publish
```

Preview должен показывать:

- выбранного Character/Persona и Portrait;
- формат публикации;
- Feed card;
- полный detail view;
- Headline, Lead и Body с реальными переносами;
- изображение с итоговым соотношением сторон;
- District;
- Event Time и Publication Time;
- reply/related post context;
- desktop и mobile width toggle;
- явную подпись `This post will publish immediately` для Player.

Кнопки:

```text
Back to Edit
Save Draft (если доступно)
Publish Now
```

Возврат из Preview не должен очищать форму, изображение или crop-настройки.

### Contract preview

Редактор Contract получает несколько режимов предпросмотра:

1. **List Card** — карточка в списке Contracts;
2. **Map Signal** — marker, title и краткая информация;
3. **Public View** — то, что видит любой пользователь;
4. **Crew/Classified View** — то, что увидит подтверждённый Crew;
5. **Service/GM View** — служебные поля и реальные участники.

Preview должен показывать Cover в итоговом соотношении, Posting Persona, Risk, Reward, время, Crew Capacity, Requirements, Content Notes и все public/classified participants.

Нужна заметная плашка:

```text
PREVIEW — NOT PUBLISHED
```

чтобы GM случайно не принял preview за уже опубликованный Contract.

### Техническая рекомендация

- Preview и опубликованная карточка должны использовать **одни и те же render functions**, иначе они быстро начнут отличаться.
- Желательно добавить серверные endpoints `feed preview` и `contract preview`, которые выполняют ту же нормализацию, permission checks и validation, но ничего не записывают в БД.
- Final Publish всё равно повторно валидирует данные: между Preview и Publish состояние Storyline/Contract/Media могло измениться.
- Кнопка Publish блокируется после первого нажатия, чтобы не создавать дубликаты.
- Загруженный draft media остаётся unattached и удаляется существующей очисткой, если пользователь закрыл редактор без публикации.
- Ошибка публикации возвращает пользователя к форме без потери введённых данных.

### Дополнительная возможность

После реализации общей preview-системы её можно использовать и для:

- Character Dossier visibility preview;
- City Feed moderation preview;
- печатного Character Sheet;
- Admin preview «как видит Player/GM/Public».

---

## 15. Admin editing, Persona organizations и Fallen Edgerunners

### 15.1 Admin редактирует персонажей других игроков

Admin должен иметь возможность открыть любой Character Sheet в режиме редактирования. Это полезно для исправления повреждённых/старых данных, помощи новому игроку, разрешения спорных изменений и ведения персонажа отсутствующего участника.

Рекомендуемые правила:

- отдельная кнопка `Edit as Admin`, чтобы просмотр не превратился в редактирование случайно;
- обязательная причина перед сохранением;
- полный before/after diff в Character Ledger;
- actor всегда остаётся реальным Admin, изменение нельзя записывать от имени владельца;
- владелец получает уведомление;
- GM/Admin может откатить change set;
- Admin может редактировать active, archived, retired и deceased Dossiers, но для архивных/умерших нужен дополнительный confirm;
- право редактировать Dossier не даёт автоматического права публиковаться в Feed от имени Character — impersonation остаётся отдельным разрешением;
- для массового ремонта старых данных нужен migration/admin tool, а не ручное открытие каждого листа.

Вопрос для настройки кампании: разрешать ли обычным GM редактировать чужие Dossiers или оставить это только Admin. Безопасный default — owner + Admin, а GM-доступ выдаётся отдельно или настройкой кампании.

### 15.2 Personas и организации

Организации уже могут существовать как Persona (`organization`, `gang`, `corporation`, `government`, `outlet`), поэтому не нужно создавать параллельную сущность только ради названия организации. Нужна структурированная связь membership между Personas.

Предлагаемая таблица:

```text
persona_memberships
- id
- member_persona_id
- organization_persona_id
- role_title
- status: active | former | secret | expelled | deceased
- visibility: public | gm | classified
- since_at / until_at
- note
- sort_order
```

Возможности:

- одна Persona состоит в нескольких организациях;
- публичная и секретная принадлежность разделены;
- должность/ранг внутри организации;
- история переходов между фракциями;
- бывшие участники;
- организация показывает roster участников;
- профиль участника показывает affiliations;
- организация используется как Vendor, Contract client, Feed author или Storyline participant;
- связи можно отображать на карте и faction graph.

Поле `affiliation` можно временно оставить для совместимости, затем мигрировать в memberships.

Дополнительное развитие:

- parent/child organizations;
- подразделения и филиалы;
- allies/enemies/owned_by relationships;
- организация-владелец Night Market Vendor;
- репутация Character у конкретной организации.

### 15.3 Fallen Edgerunners / Memorial Wall

Смерть персонажа не должна выглядеть как обычное удаление. Нужен отдельный lifecycle status:

```text
active
retired
missing
deceased
archived
```

При выборе `Mark as Deceased` открывается форма:

```text
Date and time of death
Location
Cause / circumstances
Epitaph / signature
Last words (optional)
Public obituary text
Visibility
Related Contract / Session / Feed post
```

После подтверждения:

- создаётся immutable death event в Character Ledger;
- Dossier становится read-only по механике, но memorial-текст можно дополнять;
- Character убирается из Active Dossiers и активной записи на будущие Contracts;
- исторические Contracts, Feed posts и Sessions сохраняются;
- при необходимости публикуется obituary в City Feed;
- Character появляется в отдельной категории Crew Registry: `Fallen Edgerunners` / `Memorial Wall`;
- показываются Portrait, Role, дата смерти, эпитафия, основные достижения и ссылки на историю;
- owner/Admin могут управлять видимостью реального имени игрока независимо от memorial.

Смерть должна быть обратима только Admin/GM с обязательной причиной: это защищает от случайного клика, но позволяет отменить ошибку или сюжетное возвращение.

Для `retired` и `missing` лучше иметь отдельные секции, чтобы не приравнивать уход игрока к смерти персонажа.

### 15.4 Afterlife Legacy Drink

Особо отличившимся Fallen Edgerunners GM/Admin может присвоить Afterlife Legacy.

Предлагаемые поля:

```text
afterlife_legacy
- character_id
- drink_name
- ingredients
- preparation
- served_as / glass
- garnish
- quote
- legend_story
- awarded_by
- awarded_at
- image_media_id
```

В Memorial Wall появляется badge:

```text
AFTERLIFE LEGEND
Signature Drink: The V
```

Отдельная страница `Afterlife Menu` может показывать:

- Portrait персонажа;
- название напитка;
- рецепт;
- цитату;
- краткую историю, за что его помнят;
- связанные Contract/Feed события.

Рекомендации:

- напиток не выдаётся автоматически каждому умершему персонажу — это отдельная награда за легендарность;
- назначает GM/Admin;
- рецепт можно редактировать до публикации, после публикации изменения аудируются;
- допустим безалкогольный вариант и произвольные внутриигровые ингредиенты;
- владелец Character может предложить рецепт, а GM утвердить его;
- не смешивать Memorial status и Afterlife award: персонаж может быть Fallen Edgerunner без собственного напитка.

### Связанный автоматический flow

После завершения Session GM может выполнить:

```text
Mark Character as Deceased
→ record death event
→ preserve Contract history
→ compose obituary preview
→ publish to City Feed
→ add to Memorial Wall
→ optionally award Afterlife Legacy
```

Этот flow должен быть транзакционным и не удалять существующую историю при ошибке на одном из шагов.

---

## 16. Дополнительные системы кампании

Ниже — идеи, которые хорошо связывают уже запланированные Dossiers, Organizations, Locations, Market, Sessions и City Feed. Их не стоит реализовывать одновременно; сначала лучше выбрать несколько систем с максимальной пользой за игровым столом.

### 16.1 Session Recap / Chronicle

Aftermath сейчас связывает Contract, Feed и награды, но полноценный итог сыгранной сессии заслуживает отдельной записи.

```text
Session date
GM and participants
Related Contract / Storyline
Public summary
Private GM summary
Important choices
NPC status changes
Locations visited
Loot / Cash / IP
Injuries / Humanity changes
Quotes and screenshots
```

Recap автоматически пополняет:

- Character history;
- Storyline timeline;
- Location history;
- Organization history;
- Memorial achievements;
- City Feed draft.

Это один из самых полезных следующих модулей: он превращает сыгранные партии в общую хронику, а не только в разрозненные посты.

### 16.2 Crew Stash, transfer и trade

Игрокам нужна возможность передавать найденные предметы без ручного удаления у одного Character и добавления другому.

Функции:

- `Give to Character`;
- `Move to Crew Stash`;
- `Take from Crew Stash`;
- `Split Stack`;
- `Loan Item`;
- `Return Item`;
- `Trade`;
- история владельцев предмета.

Crew Stash может быть связан с Housing/Location: квартира, гараж, база команды, Nomad vehicle cargo. Все движения попадают в ledger обеих сторон.

### 16.3 Downtime Planner

Между сессиями игрок выбирает действия на неделю/месяц:

- Hustle;
- Therapy;
- лечение Critical Injuries;
- восстановление Humanity;
- установка/удаление cyberware;
- ремонт Armor/Vehicle;
- Fabrication/Upgrade/Invention;
- поиск предмета через Fixer;
- работа с Contact/Organization;
- переезд и Lifestyle;
- подготовка к Contract.

Downtime связывается с календарём кампании и создаёт понятный журнал вместо сообщений GM в чате.

### 16.4 Organization Reputation, Favor и Heat

Одной общей Reputation недостаточно. Нужны отношения конкретного Character/Crew с организациями:

```text
reputation       известность/уважение
favor            накопленные услуги и долги
heat             внимание полиции/корпорации/банды
standing         allied | friendly | neutral | hostile | hunted
```

Это может:

- открывать Vendors и редкие товары;
- менять цены;
- давать доступ к classified Locations;
- влиять на Contracts;
- порождать City Feed/rumors;
- показываться на Organization page.

Не стоит сразу делать сложную автоматическую симуляцию: первая версия — ручные изменения GM с ledger и простыми порогами.

### 16.5 Intel, Rumors и Case Board

City Feed показывает публичную информацию, но игрокам нужен личный слой знаний.

`Intel Fragment` может быть связан с:

- Persona;
- Organization;
- Location;
- Contract;
- Storyline;
- Feed post;
- Item;
- датой и источником.

Visibility:

```text
private character
crew
shared players
gm truth
```

Case Board позволяет закреплять карточки, соединять их нитями, писать гипотезы и отмечать подтверждённые/ложные сведения. Это особенно полезно для Media, Fixer, Lawman и расследовательских Storylines.

### 16.6 Relationships Graph

На основе Persona memberships и connections можно построить интерактивный граф:

```text
Character ↔ Persona ↔ Organization ↔ Location ↔ Storyline
```

У связи есть тип, visibility, период действия и комментарий. Public graph показывает известные связи, GM graph — секретные. Лучше строить его поверх структурированных данных, а не хранить отдельную несогласованную схему.

### 16.7 Medical Record

Отдельный медицинский блок Dossier:

- Critical Injuries;
- treatment status;
- attending Medtech/Clinic;
- therapy sessions;
- Humanity history;
- installed/removed cyberware history;
- invoices and debt;
- expected recovery date.

Клиники являются Locations/Vendors, а Medtech Persona или Character может быть указан исполнителем.

### 16.8 Vehicle Garage

Для Nomad и транспортных кампаний:

- vehicles и ownership;
- condition/SDP;
- upgrades;
- seats/cargo;
- fuel/ammo;
- current Location;
- assigned driver;
- garage/home base;
- repair history;
- shared Crew vehicles.

Vehicle marker можно отображать на карте только владельцу/Crew/GM согласно visibility.

### 16.9 Achievements, Reputation Moments и Quotes

Не игровые «ачивки ради ачивок», а отмеченные GM события:

```text
Survived the Watson Blackout
Saved a Crew member
Betrayed Militech
Won a legendary firefight
First published investigation
```

Они попадают в Dossier history, Recap и Memorial Wall. Значимые achievements могут быть основанием для Afterlife Legacy.

### 16.10 City Pulse

Небольшой атмосферный слой главной страницы:

- текущая дата/время кампании;
- погода и предупреждения;
- NCPD threat level;
- district alerts;
- активные gang/corporate conflicts;
- Night Market opening announcements;
- system messages из последних Storyline events.

Первая версия может управляться GM вручную. Автоматическую симуляцию города лучше не делать до появления реальной необходимости.

### 16.11 NET Architecture Builder (отдельный большой модуль)

Для Netrunner можно добавить:

- конструктор этажей Architecture;
- Password/File/Control Node/Black ICE;
- DV и defenses;
- Initiative внутри NET;
- программы и REZ;
- live run tracker;
- скрытый GM view и открываемый player view.

Это крупная самостоятельная система. Её лучше проектировать после стабилизации Dossiers, Sessions и предметной модели, а не добавлять маленькими несвязанными фрагментами.

### 16.12 NPC Manager и полноценные statblocks

Текущий NPC Template хранит в основном HP, SP, Shield, Ammo, LUCK, MOVE, Initiative, Conditions и Injuries. Этого хватает для счётчика ресурсов, но не для ведения боя: GM не видит характеристики, навыки, оружие, атаки, cyberware и специальные способности.

Нужны два режима шаблона:

#### Quick NPC

Для массовки и случайных противников:

```text
Name / Type / Threat Tier
Initiative
HP
SP Head / Body
MOVE
Primary Attack Base
Weapon / Damage / ROF / Mag
Secondary Attack
Key Skills
Morale / Tactics
```

Создаётся за несколько секунд из presets `Mook`, `Security`, `Booster`, `Drone`, `Lieutenant`.

#### Full NPC

Для важных NPC и боссов:

```text
10 STATs
Derived HP / Death Save / Seriously Wounded
Skills and calculated Bases
Roles / Role Abilities (optional)
Weapons and Attacks
Armor / Shield
Ammo / Reload state
Cyberware and Humanity (если важно)
Gear / Consumables
Special Abilities
Critical Injuries / Conditions
Tactics / Morale / Escape trigger
Portrait / Token
Persona / Organization / Location links
Public description / GM secret
```

### Weapons and Attacks

Оружие выбирается из Database или создаётся как custom attack. Для каждого attack:

```text
name
catalog_item_id / custom
skill + stat
attack_base override
mode: ranged | melee | autofire | suppressive | explosive | net
Damage / ROF / Hands
Mag current / max / reserve
Range DV profile
armor interaction
special effect
```

В Session Dashboard GM получает кнопки:

```text
Attack
Damage
Fire
Reload
Autofire
Apply Damage
Roll Critical Injury
```

Не нужно заставлять GM каждый раз собирать формулу вручную.

### Skills

Показывать не все навыки подряд, а:

- key skills на компактной карточке;
- полный список в раскрывающемся блоке;
- автоматически рассчитанный Base;
- custom skill для необычных NPC;
- Perception, Evasion, Resist Torture/Drugs, Concentration и основные боевые навыки как быстрые поля.

### Threat tiers и presets

```text
Mook
Standard
Elite
Lieutenant
Boss
Cyberpsycho
Netrunner
Drone / Robot
Vehicle
```

Tier не должен автоматически «балансировать» Cyberpunk как D&D CR, но может задавать стартовые диапазоны и предупреждать GM о явно слабых/сильных параметрах.

### Template и Session snapshot

При добавлении NPC в Session создаётся snapshot. Последующее редактирование исходного Template не должно неожиданно менять уже идущую сессию. Нужна отдельная кнопка `Refresh from Template` с preview diff.

### Player View

Для каждого NPC GM отдельно выбирает, что видно игрокам:

- Name/Portrait;
- примерное состояние HP вместо точного числа;
- Armor;
- Conditions/Injuries;
- Initiative;
- видимое оружие;
- публичное описание.

Skills, exact attack bases, tactics и secrets остаются GM-only.

### Import и библиотека

В перспективе:

- импорт NPC из структурированного JSON;
- готовые campaign archetypes;
- clone/variant (`Guard`, `Guard Elite`, `Guard Wounded`);
- связь важного NPC Template с Persona;
- usage history: в каких Sessions участвовал NPC.

### 16.13 Netrunner Program Manager

В каталоге уже есть Programs и Black ICE с ATK/DEF/REZ/PER/SPD, но после покупки они остаются обычными предметами. Нужен отдельный Netrunner loadout вместо общего Inventory list.

#### Cyberdeck model

```text
Cyberdeck instance
- name / catalog item
- hardware slots
- program slots
- installed Hardware
- installed Programs
- carried Programs
- active/rezzed Programs
- backup copies
- notes / custom icon
```

Server должен проверять вместимость, несовместимость и количество копий.

#### Program lifecycle

Программа не является обычным consumable. Её состояния:

```text
carried
installed
rezzed
derezzed
destroyed
```

Для программ с REZ:

```text
REZ current / max
Activate / Deactivate
Take REZ damage
Derezz at 0 REZ
Deactivate + Activate to restore full REZ
Destroy
Load backup copy
```

Rezzing не уменьшает количество программы. Derezzed Program остаётся установленной/«запущенной», но не работает; для восстановления требуется Deactivate и затем Activate. Количество теряется только при уничтожении конкретной копии согласно правилам/эффекту.

Поведение зависит от Class:

- Booster/Defender остаются Rezzed и дают постоянный эффект;
- Attacker выполняет атаку/эффект и автоматически Deactivate;
- Black ICE создаёт самостоятельную активную сущность в NET;
- Destroyed copy удаляется из Cyberdeck и требует replacement/backup.

#### Rezzed Black ICE / «призываемые» программы

Killer, Dragon, Sabertooth, Hellhound и другие Black ICE нельзя отображать как обычную включённую иконку. После Activate они становятся отдельными участниками NET combat со своими PER/SPD/ATK/DEF/REZ, target, Initiative и текущим Floor.

Black ICE занимает два Cyberdeck slots. Install/Uninstall Black ICE — downtime-операция, а Activate/Deactivate — NET Action.

При нажатии `Rez Black ICE` UI предлагает разрешённый режим:

```text
LIE IN WAIT
- разместить на текущем Floor
- выбрать target rules
- недоступно во время combat

DEPLOY IN COMBAT
- выбрать допустимую цель
- добавить Black ICE на верх Initiative Queue
- начать преследование
```

Runtime instance:

```text
net_entity_id
source_program_instance_id
owner_netrunner_id
type: black_ice
class: anti_personnel | anti_program
floor_id
target_entity_id / target_netrunner_id
PER / SPD / ATK / DEF
REZ current / max
initiative
status: lying_in_wait | hunting | derezzed | destroyed | slid
activated_at
```

Black ICE действует узко по своей Class и не является универсальным цифровым питомцем. GM ведёт его Turns, даже если Black ICE принадлежит Player Netrunner; интерфейс может подсвечивать запрограммированную цель и разрешённое действие.

Чтобы переназначить цель, Netrunner тратит NET Action на Deactivate и ещё один NET Action на повторный Activate. После повторной активации ICE возвращается в Initiative с новой допустимой целью.

##### Killer

Killer — `Anti-Program Black ICE`:

```text
PER 4
SPD 8
ATK 6
DEF 2
REZ 20
Effect: 4d6 REZ damage to a Program;
if damage would Derezz it, the Program is Destroyed instead.
```

Flow в интерфейсе:

```text
Rez Killer
→ choose enemy Netrunner / valid Program source
→ Killer enters NET Initiative
→ on Killer Turn select/randomize valid Rezzed enemy Program
→ roll Killer ATK + 1d10 vs Program DEF + 1d10
→ on hit roll 4d6 REZ damage
→ if target reaches 0, mark target Program Destroyed
→ update Cyberdeck and ledger
```

Anti-Program Black ICE продолжает преследовать вражеского Netrunner как источник Programs, даже если в конкретный момент у него нет Rezzed Programs. При появлении допустимой цели оно может продолжить свою запрограммированную атаку. Slide переводит ICE в состояние `lying_in_wait` на Floor, где от него ушли.

Нужно поддерживать несколько копий одной Black ICE как разные Program instances: каждая занимает свои slots, имеет собственный REZ и может быть Rezzed отдельно. Нельзя создать больше runtime ICE, чем реально установлено копий.

##### NET combat board

Rezzed Black ICE показывается отдельной карточкой/токеном:

```text
[KILLER]  REZ 20/20
Floor 3 · Hunting Armor.exe
SPD 8 · ATK 6 · DEF 2
Next: Black ICE Turn

Attack · Damage · Change Target (2 NET Actions) · Deactivate
```

В Case/Activity log записываются Activate, target assignment, attack, REZ damage, Slide, Derezz и Destroy.

#### Program categories

UI группирует программы по фактическому Class:

- Booster;
- Defender;
- Anti-Personnel Attacker;
- Anti-Program Attacker;
- Anti-Personnel Black ICE;
- Anti-Program Black ICE;
- Hardware;
- custom.

Числа из Data Pool нормализуются (`ATK 1`, а не `1.0`) и получают понятные tooltips.

#### Netrunner combat panel

На Dossier/Session:

```text
Interface Rank
NET Actions this Turn
Cyberdeck slots
Active Programs
Program modifiers
Current Floor / Node
Enemy Black ICE
REZ trackers
```

Быстрые действия:

```text
Interface Check
Pathfinder
Backdoor
Scanner
Control
Eye-Dee
Slide
Virus
Zap
Program Attack
```

Panel рассчитывает текущие modifiers активных Booster/Defender Programs, но показывает формулу GM/Player, а не скрывает её за одной цифрой.

#### Enemy Netrunner NPC

Threat tier `Netrunner` использует тот же Program Manager:

- Interface;
- cyberdeck;
- Programs;
- NET Initiative;
- preferred actions/tactics;
- Black ICE support;
- Meatspace weapons and armor.

Так не потребуется отдельная несовместимая модель программ для NPC.

#### Связь с NET Architecture

Program Manager лучше реализовать до полноценного Architecture Builder. Последовательность:

1. нормализовать Programs/Hardware в каталоге;
2. добавить Cyberdeck loadout;
3. добавить Program states и REZ;
4. сделать Netrunner Session panel;
5. затем добавить NET Architecture floors/nodes и live run.

### Рекомендуемые дополнения с максимальной отдачей

Если выбирать только пять следующих идей вне уже утверждённого backlog:

1. **Session Recap / Chronicle**;
2. **Crew Stash и transfer**;
3. **Downtime Planner**;
4. **Organization Reputation / Favor / Heat**;
5. **Intel / Case Board**.

Они чаще используются в реальной кампании, чем общий чат или сложная автоматическая симуляция города, и хорошо переиспользуют уже существующие данные.

---

## 17. Приоритеты

### P0 — до публичного доступа

1. Privacy payload для Dossiers/Roster/Folio.
2. Сильные пароли, invite registration, session controls.
3. Атомарные транзакции для Crew, Market, IP.
4. Проверка URL schemes.
5. Автоматические backups.

### P1 — основной продуктовый пакет

1. Trust + Audit character editor, включая Admin edit чужих Dossiers.
2. Предметные состояния и consumables.
3. Market vendors + Database без универсальной покупки.
4. Database tags/i18n/armor locations.
5. Feed/Contract preview перед публикацией.
6. NPC Manager: stats, skills, weapons, attacks и full templates.
7. Netrunner Cyberdeck/Program Manager.
8. Crew Registry portraits.
9. Dedicated landscape print sheet.
10. JSON import.

### P2 — расширение мира

1. Map zoom/pan/layers.
2. Key Locations / POI и Location pages.
3. Housing map.
4. Persona organization memberships.
5. Fallen Edgerunners / Memorial Wall / Afterlife Menu.
6. Contract Crew Chat.
7. Calendar.
8. Notifications badge.
9. Fillable PDF import.
10. Session Recap / Chronicle.
11. Crew Stash и item transfer.
12. Downtime Planner.
13. Organization Reputation / Favor / Heat.
14. Intel / Case Board.
15. NET Architecture Builder после Program Manager.

### P3 — технический долг

1. Разделить `server.py`, `app.js`, `ncnet.js`, CSS.
2. Убрать N+1 queries.
3. Pagination/summary endpoints.
4. Browser E2E и visual regression по темам.
5. Health endpoint, HEAD, self-hosted fonts.

---

## 18. Предлагаемый порядок ближайшей реализации

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

### Пакет C — Publishing Preview

1. Вынести Feed/Contract cards и detail views в общие render functions.
2. Добавить серверную validation preview без записи в БД.
3. Сделать Feed preview: card/detail/mobile/desktop.
4. Сделать Contract preview: card/map/public/classified/service.
5. Сохранять состояние формы при возврате из preview и блокировать double publish.

### Пакет D — Visual/Print/Roster

1. Theme consistency audit.
2. Исправить Open Contracts.
3. Portraits и owner avatars в Crew Registry.
4. Новый landscape print renderer.
5. Visual regression по темам и разрешениям.

### Пакет E — World Layer

1. Zoomable layered map.
2. Key Locations / POI data model, filters and Location pages.
3. Seed основных мест 2070-х с source metadata.
4. GM coordinate editor и custom campaign locations.
5. Housing.
6. Vendor locations.
7. Contract Crew Channel.

### Пакет F — Organizations & Legacy

1. Добавить Persona memberships и organization roster.
2. Перенести строковый `affiliation` в структурированные связи.
3. Добавить Dossier statuses: active/retired/missing/deceased/archived.
4. Реализовать death flow и Memorial Wall в Crew Registry.
5. Добавить obituary preview и связь с Feed/Contract/Session.
6. Реализовать Afterlife Legacy award и Afterlife Menu.

### Пакет G — Campaign Operations

1. Session Recap / Chronicle и автоматические history links.
2. Crew Stash, item transfer и ownership history.
3. Downtime Planner с лечением, Therapy, Crafting и поиском предметов.
4. Organization Reputation / Favor / Heat.
5. Intel Fragments и Case Board.
6. Medical Record и Vehicle Garage после стабилизации базовых модулей.

### Пакет H — GM Combat & NET

1. Расширить NPC Template до Quick/Full statblock.
2. Добавить STATs, Skills, calculated Bases, Weapons и Attacks.
3. Реализовать Session snapshot, one-click attacks и ammo/reload.
4. Добавить NPC threat presets и Player View visibility.
5. Нормализовать Programs/Black ICE/Hardware в каталоге.
6. Добавить Cyberdeck loadout, slots, Program states и REZ.
7. Реализовать Rezzed Black ICE как отдельные `net_entities` с target/floor/initiative.
8. Добавить Killer/Dragon/Sabertooth attack flows, Slide и Destroyed Programs.
9. Реализовать Netrunner Session panel и Enemy Netrunner profile.
10. После стабилизации добавить NET Architecture Builder/live run.

---

## 19. Открытые вопросы для следующего просмотра

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
13. Могут ли обычные GM редактировать чужие Dossiers или только Admin?
14. Кто может отметить Character как deceased: owner, GM или Admin?
15. Должен ли deceased Dossier полностью блокировать механику или разрешать посмертные исправления владельцу?
16. Кто утверждает Afterlife drink: любой GM, владелец Storyline или только Admin?
17. Может ли Persona иметь несколько публичных и секретных memberships одновременно?
18. Какие POI входят в обязательный seed первой версии и по какому источнику сверяются координаты?
19. Могут ли игроки создавать свои Location markers или только предлагать их GM?
20. Нужна ли история контроля территории/владельца Location по датам?
21. Crew Stash принадлежит конкретному Crew, Housing или всей кампании?
22. Item transfer происходит сразу или требует подтверждения получателя?
23. Downtime длится фиксированную неделю или произвольный отрезок календаря?
24. Reputation/Favor/Heat индивидуальны для Character или могут принадлежать Crew?
25. Intel Board общий для Crew или каждый Character имеет собственную картину расследования?
26. Какие поля обязательны в Quick NPC, а какие скрываются в Full mode?
27. Нужны ли системные NPC presets из источников или только пользовательские templates?
28. Важный NPC связан с Persona один-к-одному или один Persona может иметь несколько combat profiles?
29. Показывать игрокам точные HP NPC или только состояния Healthy/Wounded/Mortally Wounded?
30. Program Manager должен одновременно поддерживать CP:R и CEMK/2070 ruleset profiles?
31. Нужны ли отдельные backup copies Programs и история уничтоженных копий?
32. Может ли GM вручную переопределять calculated Skill/Attack Base NPC без изменения STAT/Skill?
33. Следуем ли правилу, что Turns даже player-owned Black ICE ведёт GM, или даём кампании опцию player control?
34. Выбор цели Anti-Program Black ICE всегда случайный среди Rezzed Programs или GM получает rules-aware randomize button с возможностью override?
35. Нужен ли отдельный визуальный token/icon editor для внешнего вида призванной Black ICE?

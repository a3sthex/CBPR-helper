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

### Текущее состояние после пакета A

- Night Market ежедневно и детерминированно формирует ассортимент шести Vendor Personas.
- У продавцов есть собственные категории, цены, поиск, фильтры, сортировка и полные карточки предметов.
- Database / Codex работает как справочник без мгновенной покупки.
- Сервер разрешает покупку только из текущего Night Market.
- Пока ассортимент является ежедневным snapshot без постоянного количества единиц: у предложения нет `available/reserved/sold`.
- Один catalog item пока адресуется только по item ID, поэтому независимые предложения одного предмета от нескольких продавцов ещё не различаются.
- `New Today`, Reservation, Sold Out, Reputation/Favor gates, Legal Retail и Fixer Requests ещё не реализованы.

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

### Продолжение Market — пакет A.2 (запланировано, не реализовано)

**Проверка статуса 2026-08-21:** все восемь пунктов ниже подтверждены как идеи и пока не реализованы.

1. ☐ **Finite Stock по количеству.** Каждое предложение получает собственный `offer_id` и серверные количества `available`, `reserved`, `sold`. Покупка атомарно уменьшает остаток, чтобы две вкладки не могли забрать последнюю единицу одновременно.
2. ☐ **New Today.** Метка и фильтр сравнивают новый snapshot с предыдущим ассортиментом продавца. Это именно новое предложение/возврат в продажу, а не любой предмет текущего дня.
3. ☐ **Vendor Locations.** У продавца появляется связь с Location/POI, кнопка перехода на карту и возможные location-specific offers. Геометрия и страницы локаций реализуются вместе с пакетом E, но Market хранит стабильный `location_id`.
4. ☐ **Reputation / Favor requirements.** Offer может требовать отношение к конкретной Organization/Vendor. Проверка выполняется сервером; скрытые требования не отправляются обычному игроку. Полная механика зависит от Organization Reputation/Favor/Heat.
5. ☐ **Один предмет у нескольких продавцов.** Один `catalog_item_id` может одновременно иметь несколько независимых offers с разной ценой, количеством, требованиями и Vendor Persona. Покупка адресуется по `offer_id`, а не только по item ID.
6. ☐ **Legal Retail / Common Supply.** Опциональная постоянная розница с явным campaign allowlist, фиксированной ценой и отдельными правилами доступности. Она не должна снова превращать весь Codex в универсальный магазин.
7. ☐ **Fixer Item Requests.** Character отправляет запрос на catalog/custom item, количество, бюджет и срок. Fixer/GM может принять запрос, назначить цену/продавца/время и превратить его в персональный либо Crew offer с ledger/history.
8. ☐ **Reserved / Sold Out.** Карточка остаётся видимой после исчерпания товара с понятным статусом. Reservation имеет владельца, срок действия и освобождается после отмены/таймаута; простое добавление в локальную корзину не считается резервом.

### Подтверждённое поведение покупки оружия

- ✅ Купленное в Market огнестрельное оружие создаётся **разряженным**: `magazine = 0`, даже если у Character уже есть совместимые патроны.
- Боеприпасы остаются отдельными Inventory stacks с точным rounds balance и не вставляются в оружие автоматически.
- Зарядка выполняется только явным действием `Reload`; оружие, полученное не через Market, может иметь состояние, заданное источником/сессией.

#### Рекомендуемый порядок A.2

1. `offer_id` + persisted daily stock + atomic Sold Out;
2. несколько offers одного item у разных Vendors;
3. `New Today` и история snapshots;
4. Reservation с TTL;
5. Legal Retail и Fixer Requests;
6. Reputation/Favor gates и Vendor Locations после появления зависимых World/Organization моделей.

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

### Equippable / Active Gear — подтверждённая идея

Наличие предмета в Inventory не означает, что он автоматически готов к работе. Предметы вроде **Radio Communicator**, **Flashlight**, оптики, сканеров, инструментов и другого активного снаряжения получают явное свойство `equippable`.

Каталог хранит декларативные поля:

```text
equippable            предмет можно подготовить к использованию через Equip
equip_modes           held | worn | mounted | ready
equip_slots           hand | belt | ear | eye | head | body | weapon | vehicle | workspace | other
hands_required        сколько рук занимает режим held
equip_limit           допустимое число одновременно экипированных копий
exclusive_group       взаимоисключающие предметы/режимы
requires_host_type    тип host для mounted mode
active_actions        действия, доступные только когда предмет экипирован
active_effects        structured effects: while_equipped / while_active
```

Состояние конкретного экземпляра дополняется полями:

```text
state                 carried | equipped | installed | stored | broken
equipped_mode         held | worn | mounted | ready
equipped_slot         выбранный slot
host_instance_id      конкретное оружие/броня/vehicle для mounted mode
active                включён ли уже экипированный предмет
```

`Equip` и `Activate` — разные действия. Например:

- **Radio Communicator**: лежащая в Stash рация не даёт доступ к коммуникационным действиям; экипированная рация считается готовой, а включение/канал могут храниться как active/configuration state;
- **Flashlight**: можно держать в руке либо закрепить на совместимом host; экипированный фонарь может быть отдельно включён или выключен;
- handheld tool занимает руку только в режиме `held`, но может оставаться обычным `carried` предметом вне использования;
- mounted gear ссылается на стабильный `host_instance_id`, а не только на название оружия или транспорта.

Правила поведения:

1. `carried` предмет не применяет эффекты `while_equipped` и не предоставляет equipment-only actions.
2. `equipped`, но выключенный предмет применяет только эффекты `while_equipped`; `while_active` требует `active=true`.
3. Нельзя экипировать сломанный, consumed или находящийся в чужом Stash экземпляр.
4. Сервер проверяет руки, hard slots, compatible host, `exclusive_group` и лимит копий.
5. `Equip / Unequip / Activate / Deactivate / Mount / Unmount` записываются в Character Ledger.
6. Character Sheet и Session panel показывают отдельный **Active Gear / Loadout**, чтобы готовое снаряжение не терялось в полном Inventory.
7. Не нужно превращать всё снаряжение в жёсткий «инвентарный тетрис»: строгие ограничения обязательны для рук, mounts и rules-defined hosts; обычный `ready` gear может использовать мягкий campaign limit.

Флаг нельзя назначать автоматически всей категории Gear. Нужна курируемая разметка Data Pool и ручные исключения: часть вещей является passive equipment, часть требует `Use`, часть расходуется, а часть может работать в нескольких equip modes.

### Важное ограничение

Не стоит автоматически считать расходником всё в категориях Ammo/Grenades/Gear. Лучше импортировать структурированный флаг и иметь ручные исключения: некоторые предметы имеют заряды, некоторые являются контейнерами, некоторые не исчезают после применения.

### Upgrades и Attachments прямо в Character Sheet

Сейчас Gun Upgrades и Vehicle Upgrades можно купить как обычный предмет, но нельзя установить на конкретное оружие или машину. Они остаются отдельной строкой Inventory и не меняют характеристики host item.

#### Обязательное изменение Inventory model

Для модификаций недостаточно `catalog key + qty`. Два одинаковых Medium Pistol могут иметь разные attachments, состояние и имя. Нужны отдельные экземпляры:

```text
item_instances
- instance_id
- character_id / stash_id
- catalog_item_id
- custom_name
- state: carried | equipped | installed | stored | broken
- quantity (только для stackable)
- condition
- notes
- acquired_at / source
```

Модификации связываются с конкретным экземпляром:

```text
item_modifications
- id
- host_instance_id
- upgrade_instance_id / catalog_upgrade_id
- slot_type
- installed_at
- installed_by Character/Persona
- source: purchased | nomad_access | tech_upgrade | loot | custom
- active
- configuration_json
- notes
```

Нельзя привязывать upgrade только по имени или catalog key: при передаче, продаже и наличии двух одинаковых предметов связь станет неоднозначной.

#### Weapon Upgrade UI

В разделе Weapons каждая карточка показывает:

```text
Militech Assault Rifle
Damage 5d6 · ROF 1 · Mag 25 · Hands 2
Upgrade Slots 2/3
- Smartgun Link
- Infrared Nightvision Scope

Manage Upgrades
```

`Manage Upgrades` открывает:

- установленные attachments;
- свободные slots;
- совместимые upgrades в Inventory;
- поиск по Database/Market;
- Install / Remove / Replace;
- preview итоговых mechanics до подтверждения;
- причины несовместимости;
- source/page rules.

Server проверяет:

- допустимый weapon type/skill;
- Exotic/Non-Exotic ограничения;
- запрещённые комбинации;
- количество slots;
- unique upgrades;
- наличие реального upgrade instance у Character;
- эффекты Extended/Drum Magazine, Underbarrel и rebuilds;
- custom/Tech override отдельно от catalog rule.

Карточка должна показывать base и modified значение, например:

```text
Magazine: 25 → 50 (Drum Magazine)
Attack checks: +1 (Smartgun Link, requirements satisfied)
```

#### Vehicle Upgrade UI

В Dossier/Garage:

```text
Compact Groundcar
SDP · Seats · Speed
Installed Upgrades
Available Upgrade Capacity / Access
Cargo
Mounted Weapons
```

Действия:

- Install Vehicle Upgrade;
- Remove/Replace;
- выбрать mounted weapon и его ammo;
- применить Armored Chassis/Bulletproof Glass/Seating/NOS и другие эффекты;
- отметить источник `Nomad Access` или купленный upgrade;
- Repair/Disable;
- перенести vehicle между Character/Crew Garage.

`Nomad Access` в Data Pool нельзя трактовать просто как цену или обычный slot: это отдельное правило доступа, которое нужно хранить структурированно и проверять по активной Role/Moto setup.

#### Другие host types

Та же система должна поддерживать:

- Cyberdeck Hardware и Programs;
- Cyberware Options → foundation/host slots;
- Armor/Shield Tech upgrades;
- Vehicle mounted weapons;
- Tool/Agent/gear modifications;
- Tech Maker Upgrade как custom modification.

Для каждого host type задаются собственные slot/compatibility rules, но UI и ledger используют общую модель `host instance → modifications`.

#### Trust + Audit flow

В выбранном режиме кампании игрок устанавливает upgrade сам, без GM approval:

```text
Manage Upgrades
→ choose compatible item
→ preview mechanics
→ Install
→ Character Ledger event
```

Ledger:

```text
Installed Smartgun Link on Militech Assault Rifle #2
Slots: 1/3 → 2/3
Attack modifier: 0 → +1
Source: Character Inventory
Actor: V
```

GM/Admin видит историю и может откатить change set.

#### Market и Loot integration

После покупки upgrade:

```text
Keep in Inventory
Install Now…
Move to Stash
```

`Install Now` предлагает только совместимые host instances. Найденный на сессии/custom upgrade использует тот же flow.

#### Transfer, sale и deletion

Если host item передаётся или продаётся, UI обязательно спрашивает:

```text
Transfer/Sell with installed upgrades
Detach upgrades first
Cancel
```

Нельзя тихо удалить host и оставить orphan modifications. Передача комплектом сохраняет историю и все instance links; отсоединение создаёт отдельные inventory instances.

### Structured Effects & Modifiers Engine

Многие предметы не просто занимают место в Inventory. Они могут:

- менять STAT;
- давать бонус/штраф к Skill или конкретному Check;
- менять Initiative, MOVE, BODY, Humanity и Derived values;
- менять Damage, ROF, Magazine, Hands, Concealability или Quality оружия;
- изменять SP/penalties брони;
- давать сопротивление, immunity или situational bonus;
- создавать временный эффект после Use;
- менять NET Actions, Interface checks и Program stats;
- работать только при выполнении требования или в определённом контексте.

Нельзя реализовывать каждый такой предмет отдельным `if item.name == ...` в разных экранах. Нужен единый декларативный движок эффектов.

#### Base, effective и current values

Система хранит отдельно:

```text
base_value        купленное/развитое постоянное значение
modifiers         активные источники бонусов и штрафов
effective_value   результат расчёта
current_value     расходуемое состояние, если применимо
```

Пример:

```text
REF base: 8
Armor penalty: -2
Drug effect: +1
REF effective: 7
```

Экипировка не должна переписывать `base REF 8` на `6`. Иначе после снятия предмета невозможно надёжно восстановить исходное значение.

Для Skill:

```text
Handgun Level: 6        (покупается за IP)
Situational modifier: +1
Effective Check Base: REF effective + Handgun Level + modifiers
```

Стоимость следующего Skill Level считается от базового Level, а не от временного бонуса.

#### Effect definition

У Catalog Item, Upgrade, Cyberware, Program, Condition или Consumable появляется массив структурированных эффектов:

```json
{
  "id": "smartgun-attack-bonus",
  "target": "weapon.attack_check",
  "operation": "add",
  "value": 1,
  "scope": {"host_instance": true},
  "active_when": ["installed", "requirements_met"],
  "stack_group": "smartgun_link",
  "stack_policy": "highest",
  "duration": "while_installed",
  "priority": 200,
  "source": "CP:R page ..."
}
```

Разрешённые targets должны быть белым списком, например:

```text
character.stat.INT/REF/DEX/TECH/COOL/WILL/LUCK/MOVE/BODY/EMP
character.initiative
character.hp_max
character.death_save
character.humanity_current/max
skill.<name>.check
skill.<name>.level (редко; отдельно от progression)
weapon.damage
weapon.attack_check
weapon.rof
weapon.magazine
weapon.hands
weapon.quality
weapon.concealable
weapon.autofire_max
armor.sp
armor.penalty.REF/DEX/MOVE
vehicle.sdp/speed/seats/cargo
netrunner.net_actions
program.PER/SPD/ATK/DEF/REZ
check.<context>
```

Operations:

```text
add
set
minimum
maximum
multiply
replace_notation
grant_action
grant_resistance
grant_tag
```

Нельзя хранить исполняемый JavaScript/Python в данных предмета. Только проверенная JSON-схема и серверный allowlist.

#### Activation conditions

Эффект работает, когда источник:

```text
carried
held
equipped
installed
rezzed
consumed
activated
inside vehicle
at location
```

И может иметь условия:

```text
requirements_met
specific weapon type/skill
specific target
melee/ranged/autofire only
while Seriously Wounded
while in NET Architecture
once per Turn/Round/Session
manual GM toggle
```

Если требования перестали выполняться, effect отключается, но сам item не исчезает.

#### Duration и temporary effects

```text
permanent
while_equipped
while_installed
while_rezzed
until_end_of_turn
rounds: N
minutes/hours: N
until_rest
until_treated
session
manual
```

Consumable после `Use` создаёт отдельный `active_effect_instance`. Сам предмет уменьшается в количестве, но эффект продолжает жить до окончания duration, даже если stack уже исчез из Inventory.

```text
active_effect_instances
- id
- character/session/weapon target
- effect_definition_id / custom snapshot
- source_item_instance_id
- applied_by
- started_at / expires_at / remaining_rounds
- active
- notes
```

#### Stacking rules

Для каждого эффекта явно задаётся политика:

```text
stack                 складываются
highest               работает наибольший
lowest                работает самый строгий штраф
unique                только одна копия
replace               новый заменяет старый
independent            отдельные target instances
```

UI должен объяснять конфликт:

```text
Smartgun Link +1 — ACTIVE
Second Smartgun Link +1 — NOT STACKED (same stack group)
Heavy Armor REF -2 — ACTIVE (strictest armor penalty)
```

#### Set Bonuses и item synergies

Некоторые эффекты появляются не у одного item, а только при наличии набора или нескольких копий. Их лучше хранить отдельными `synergy_rules`, а не дублировать один эффект в каждом предмете.

```text
synergy_rules
- id
- required_all[]
- required_counts{}
- required_states[]
- effects[]
- stack_group / stack_policy
- source/page
```

Пример комплекта Fashionware:

```text
Light Tattoo installations: 3/3
→ +2 to Wardrobe & Style checks
→ bonus applies once

Chemskin: installed
TechHair: installed
→ +2 to Personal Grooming checks
→ bonus applies once
```

Если у Character установлены три Light Tattoo, Chemskin и TechHair одновременно, итоговые бонусы независимы:

```text
Wardrobe & Style checks: +2
Personal Grooming checks: +2
```

Это не `+6`: три Light Tattoo являются условием одного set bonus, а Chemskin + TechHair — условием другого set bonus. Все пять Fashionware имеют HL 0, но остаются отдельными item instances/installations.

Пример определения:

```json
{
  "id": "light-tattoo-trio",
  "required_counts": {
    "catalog:cyberware-52": {"minimum": 3, "state": "installed"}
  },
  "effects": [
    {
      "target": "skill.Wardrobe & Style.check",
      "operation": "add",
      "value": 2,
      "stack_group": "light_tattoo_style_bonus",
      "stack_policy": "unique"
    }
  ]
}
```

```json
{
  "id": "chemskin-techhair-combo",
  "required_all": [
    {"catalog_id": "cyberware-51", "state": "installed"},
    {"catalog_id": "cyberware-55", "state": "installed"}
  ],
  "effects": [
    {
      "target": "skill.Personal Grooming.check",
      "operation": "add",
      "value": 2,
      "stack_group": "chemskin_techhair_grooming_bonus",
      "stack_policy": "unique"
    }
  ]
}
```

Character Sheet показывает прогресс даже до активации:

```text
FASHION SYNERGIES
Light Tattoo Ensemble       2/3   INACTIVE
Chemskin + TechHair         2/2   ACTIVE   Personal Grooming +2
```

При снятии/удалении одной Light Tattoo количество становится 2/3 и Wardrobe & Style bonus автоматически выключается, не меняя base Skill Level. При удалении Chemskin или TechHair выключается только Personal Grooming bonus. Оба изменения записываются в Ledger.

Эта же модель подходит для парного cyberware, armor sets, weapon+ammo synergies, installed Hardware combinations и других комплектов.

#### Recalculation order

Нужен детерминированный pipeline, одинаковый на сервере и в UI:

1. base values;
2. `set/minimum/maximum` foundations по priority;
3. additive modifiers;
4. multipliers/replacements;
5. caps и rules exceptions;
6. derived values;
7. current resource clamping без потери history.

Порядок должен быть покрыт тестами на конфликты эффектов. Клиент показывает preview, но сервер остаётся авторитетным и возвращает breakdown.

#### Character Sheet UI

Каждое изменённое значение получает индикатор:

```text
REF 7  [base 8]
```

По нажатию:

```text
REF breakdown
Base                         8
Heavy Armor                 -2
Active Drug                 +1 (34 min remaining)
Effective                    7
```

Для оружия:

```text
Magazine 50 [base 25]
Damage 5d6
Attack +1
```

Breakdown показывает источник, duration, requirements и почему effect активен/неактивен.

#### Rolls и Session

Все Skill/Attack/Damage rolls используют effective values из одного evaluator. Нельзя считать бонус на карточке, но забывать его в Dice Roller или NPC Session.

Session хранит snapshot/temporary effects и Round duration. Permanent character source остаётся в Dossier, временное состояние сессии не загрязняет постоянный Ledger после завершения.

#### Import strategy

Автоматически разбирать весь свободный текст описаний в effects рискованно. Рекомендуемый порядок:

1. нормализовать очевидные поля из Data Pool;
2. создать curated overrides для предметов с механическими эффектами;
3. добавить schema validation и source/page;
4. помечать неподдержанный эффект `manual_resolution_required`;
5. постепенно расширять покрытие с regression tests.

Карточка честно показывает:

```text
AUTOMATED EFFECT
```

или:

```text
MANUAL RULE — read description
```

Так система не будет притворяться, что применила правило, которое на самом деле не распознано.

#### Custom effects

В Trust + Audit режиме игрок/Admin может добавить custom modifier:

```text
Target: Perception checks
Modifier: +2
Duration: while equipped
Reason: Tech-upgraded optics
```

Custom effect всегда заметно помечается, содержит автора/причину и попадает в Ledger. GM может отключить или откатить его.

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

### Ruleset Profiles и House Rules — ОТЛОЖЕНО

**Решение от 2026-08-21:** не реализовывать полноценные Ruleset Profiles и редактор House Rules до выхода ожидаемого обновления системы Cyberpunk и решения кампании о переходе/адаптации. Сейчас есть высокий риск построить дорогой слой конфигурации вокруг правил, которые вскоре изменятся.

До появления новой системы делаем только технически дешёвую подготовку:

- source/page metadata у автоматизированного правила;
- `rules_version` в Session/Character snapshots;
- декларативные item/effect definitions вместо разбросанных `if`;
- отделение base data от calculated/effective values;
- migration-friendly stable IDs;
- честная пометка `manual_resolution_required`, если правило не автоматизировано.

Пока **не делаем**:

```text
Ruleset switcher CP:R/CEMK/New System
House Rules UI
несколько параллельных rule engines
автоматическую конвертацию персонажей
сложные per-Session overrides
```

После официального релиза нужен отдельный этап Rules Review:

1. получить и изучить финальный текст новой системы;
2. составить таблицу отличий от текущего Hybrid;
3. решить, переходит ли кампания полностью или частично;
4. определить, нужен один новый ruleset или несколько profiles;
5. спроектировать миграцию Character/NPC/Items/Programs;
6. только после этого возвращать Ruleset Profiles в активный backlog.

Таким образом, текущие продуктовые функции можно разрабатывать дальше, но новые глубокие автоматизации правил не должны намертво привязываться к сегодняшним формулам.

### Storyline / Faction Clocks

Простые progress tracks для долгих угроз и проектов:

```text
Arasaka Investigation        4/8
Tyger Claws Retaliation      2/6
Crew Safehouse Construction  5/8
```

Clock может быть Public/Crew/GM, связан со Storyline, Organization, Contract или Location и обновляться Session Recap/Downtime. Это даёт GM понятный инструмент развития мира без сложной автоматической симуляции.

### Universal Search и Entity Links

Command Palette стоит расширить до поиска по данным:

- Characters;
- Personas;
- Organizations;
- Locations;
- Contracts;
- Feed;
- Items;
- Sessions;
- Intel;
- Storylines.

Любое текстовое поле с поддержкой связей может вставлять безопасную entity reference, а не копировать название строкой. Например `@Dex`, `#Watson-Blackout`, `⌖Afterlife`. При переименовании entity ссылки не ломаются.

### Safety Tools

Для живых и online-сессий:

- Lines & Veils кампании;
- Content Notes на Contract/Session;
- анонимный `Pause / X-card` сигнал GM;
- настройка видимости safety preferences;
- Session debrief/check-in;
- отсутствие публичного журнала о том, кто нажал safety signal.

Это не должно превращаться в бюрократию, но базовый приватный механизм полезнее ещё одной декоративной функции.

### Co-GM, Assistant и Observer permissions

Помимо Player/GM/Admin нужны назначения в рамках конкретной Session/Storyline:

```text
Session Owner
Co-GM
Assistant GM
Observer / Spectator
Rules Helper
```

Co-GM может вести NPC/Initiative, не получая глобальные Admin-права. Observer получает только выбранный Player View. Все действия остаются в audit/activity log.

### QR и physical integration

Для живой встречи печатные материалы могут содержать QR:

- Character Quick Sheet → Dossier;
- NPC card → GM statblock;
- Item card → Database description;
- Handout → media/full text;
- Location → map page;
- Session Pack → join/presentation screen.

QR не должен открывать classified данные без авторизации. Для общего экрана используется короткоживущий read-only Session token/PIN.

### Full Campaign Export / Import

Помимо backup нужен переносимый Campaign Bundle:

```text
manifest/version
SQLite logical export or structured JSON
uploads/media
custom Locations/Items/Rules
settings
checksums
```

Перед импортом — preview, version migration и conflict report. Это позволит переносить кампанию между домашним сервером и VPS без ручного копирования неизвестных файлов.

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
Mag current / max / loaded ammo + shared ammo source
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

### 16.14 Online VTT и поддержка живых встреч

На далёкую перспективу NC//NET может получить собственный tabletop, но не стоит пытаться сразу копировать весь Foundry/Roll20. Сильнее будет специализированный Cyberpunk tabletop, напрямую связанный с Dossiers, NPC, Items, Effects, Sessions, NET и Locations.

#### Терминология: формат игры отдельно от типа подключения

Предыдущее описание ошибочно смешивало «offline» с отсутствием интернета. Здесь используются две независимые оси:

```text
ФОРМАТ ИГРЫ
- Online/VTT: игра проходит на цифровом tabletop
- Live/Offline: живая встреча за физическим столом
- Hybrid: часть участников за столом, часть удалённо

ПОДКЛЮЧЕНИЕ ONLINE/VTT
- Internet: игроки подключаются удалённо через интернет
- LAN: игроки подключаются к тому же VTT по локальной сети
```

То есть **online mode может работать и через интернет, и по локалке**. Слово online означает цифровую синхронизированную игровую среду, а не обязательный выход в интернет.

**Offline mode означает живую встречу**: люди находятся за одним физическим столом, используют живое общение, бумажные/печатные материалы, физические кубики и при желании миниатюры. NC//NET в этом режиме выступает помощником, а не обязательной виртуальной доской.

#### Режим Online/VTT через интернет

- один общий цифровой tabletop;
- GM и игроки находятся удалённо;
- сервер обычно размещён на VPS;
- Scenes, Tokens, Dice, Initiative и Dossiers синхронизируются;
- нужны presence/reconnect/permissions;
- голос и видео остаются внешнему сервису.

#### Режим Online/VTT по LAN

- тот же функциональный tabletop;
- все устройства подключены к локальному серверу;
- интернет не обязателен;
- подходит для цифрового стола, телевизора, планшетов или компьютерного клуба;
- правила и интерфейс не должны отличаться от internet VTT;
- меняется только способ подключения и deployment.

#### Режим Live/Offline — живая встреча

В этом режиме VTT не обязателен. NC//NET помогает до, во время и после физической игры:

```text
BEFORE SESSION
- Session Pack
- печатные Character/NPC sheets
- Contract briefing
- maps/handouts
- initiative cards
- список Crew и equipment

DURING SESSION
- GM dashboard на одном ноутбуке (optional)
- быстрые NPC/Rules/Resolvers
- ручной ввод результатов физических бросков
- Initiative/HP/SP tracker (optional)
- показ handout/map на общем экране (optional)

AFTER SESSION
- Recap
- Loot/Cash/IP
- Injuries/Humanity
- Character Ledger
- Aftermath/Feed draft
```

Поддерживаемые варианты живой встречи:

1. **Fully Analog** — сайт используется только для подготовки и печати; во время игры устройства не нужны.
2. **GM Assisted** — один ноутбук GM ведёт Initiative/NPC/Session, игроки используют бумагу и физические кубики.
3. **Shared Screen** — дополнительно телевизор/проектор показывает карту, handouts и текущий turn.
4. **Companion Phones** — игроки по желанию открывают Dossiers/Inventory, но это не обязательное условие игры.

#### Hybrid

- физический стол остаётся центром живой встречи;
- удалённые участники подключаются к digital scene/session;
- общий экран стола может показывать ту же сцену;
- физические броски можно вносить вручную в общий Dice Log;
- digital и physical actions используют один Session event stream.

#### Рекомендуемая стратегия развёртывания

Один и тот же Online/VTT server поддерживает два варианта подключения:

- LAN deployment на домашнем Ubuntu server;
- Internet deployment на VPS/публичном server.

Live/Offline mode не требует отдельной копии БД: это другой UX поверх той же Campaign/Session. Для полностью аналоговой встречи GM заранее экспортирует/печатает Session Pack, а после игры вносит итоговые изменения.

Optional relay и local-first replication остаются техническими возможностями далёкого будущего, но не определяют различие между online и offline форматом игры.

#### Online VTT MVP

Первая полезная версия:

1. Scenes/Battle Maps;
2. square/hex/gridless режим;
3. Tokens;
4. drag & drop;
5. измерение расстояния;
6. Initiative tracker;
7. HP/SP/Shield/Ammo/Conditions на token;
8. Dice Log;
9. ручной Fog of War;
10. GM/Player permissions;
11. Player shared screen;
12. reconnect без потери состояния.

Не включать в MVP:

- voice/video;
- marketplace модулей;
- сложное динамическое освещение;
- 3D dice;
- macro language;
- полноценную plugin API.

Эти функции дороги и уже хорошо решаются внешними инструментами.

#### Scene model

```text
vtt_scenes
- id
- session_id / location_id
- name
- kind: encounter | city | net_architecture | handout
- background_media_id
- width / height
- grid_type / grid_size / grid_offset
- scale / distance_unit
- fog_config
- active
- created_by / updated
```

Layers:

```text
background
map drawings
walls/cover
GM notes
fog
public tokens
hidden tokens
templates/effects
pings
```

#### Token model

Token не дублирует Dossier без связи, а ссылается на entity:

```text
vtt_tokens
- id
- scene_id
- entity_type: character | npc | persona | vehicle | black_ice | custom
- entity_id / session_combatant_id
- name / image
- x / y / rotation / size
- elevation
- visible
- owner_user_ids
- vision settings
- status icons
- revision
```

Session combatant остаётся источником HP/SP/Ammo/Conditions. Token отвечает за положение и визуальное состояние.

#### Cyberpunk-specific interactions

При выборе token доступны действия из его sheet:

```text
Attack
Damage
Autofire
Reload
Move / Measure
Apply Armor
Critical Injury
Use Consumable
Skill Check
Open Dossier
```

Targeting flow:

```text
Select attacker
→ choose weapon/action
→ select target
→ measure range
→ choose DV / Evasion
→ roll preview
→ apply result with GM confirmation or Trust mode
→ write Session Activity
```

Cover, aimed shots, melee armor halving, Autofire и Critical Injuries используют существующий Rules/Effects Engine.

#### Инструменты живой встречи (необязательные)

##### Session Pack для полностью физической игры

Одной кнопкой GM получает printable/export bundle:

```text
- Contract public/classified brief
- список участников
- компактные Character summaries
- NPC statblocks и attack cards
- Initiative cards
- карты без/с GM annotations
- handouts
- loot/reward sheet
- blank Session notes / Recap form
```

Так живая встреча остаётся полностью играбельной без телефонов и цифровой карты.

##### GM Screen

- Initiative/NPC/resources;
- secrets и hidden notes;
- быстрые Rules/Resolvers;
- ручной ввод физических dice results;
- damage/armor/critical injury helpers;
- Session clock и notes.

##### Shared Table Screen (optional)

- карта или handout без GM controls;
- текущий turn;
- видимые tokens/status;
- изображения/схемы/NET Architecture;
- presentation mode для телевизора/проектора.

##### Player Phone (optional)

- собственный Dossier;
- Inventory/Consumables;
- Rules reference;
- Session recap notes;
- физический бросок можно внести вручную;
- цифровые dice/actions доступны только если группа хочет их использовать.

Специальный `#/table/:session` является вспомогательным presentation mode, а не обязательной основой offline/live игры.

#### Online/VTT mode requirements

Дополнительно нужны:

- presence/connected users;
- reconnect и state snapshot;
- cursor/ping throttling;
- permissions на token;
- invite/session link;
- rate limits;
- asset access control;
- latency-safe optimistic movement;
- authoritative dice/events на server.

Voice/video лучше оставить Discord/другому сервису.

#### Real-time architecture

Текущий `ThreadingHTTPServer` подходит для существующего приложения, но не для полноценного VTT real-time слоя. В будущем потребуется:

- WebSocket-capable application server;
- authoritative Session state;
- append-only `vtt_events` с последовательным `seq`;
- периодические snapshots;
- optimistic revisions;
- idempotent commands;
- reconnect from last acknowledged event;
- presence как ephemeral state, не вечная запись в БД.

```text
Client command
→ server permission/rules validation
→ transaction
→ append event
→ update snapshot
→ broadcast to connected clients
```

Сначала это можно реализовать отдельным VTT service рядом с текущим Python server, а не переписывать весь NC//NET за один этап.

#### Fog, walls и lighting

Порядок:

1. ручная маска Fog;
2. reveal/hide polygons;
3. walls/doors/cover metadata;
4. простая token vision;
5. динамическое освещение только после профилирования производительности.

Для Cyberpunk большую пользу раньше дадут Cover, range measurement и elevation, чем сложные красивые источники света.

#### Handouts и journals

GM может отправить игрокам:

- изображение;
- текстовый документ;
- Item;
- Intel Fragment;
- Location;
- Persona;
- NET File;
- evidence.

Handout можно раскрыть отдельному Character, Crew или всем игрокам. Открытие фиксируется в Session log, если это важно для сюжета.

#### NET tabletop mode

NET Architecture отображается как отдельный scene kind:

- Floors/Nodes вместо метровой карты;
- Netrunner и Black ICE tokens;
- Password/File/Control Node;
- Initiative;
- Program/REZ cards;
- скрытые GM nodes;
- reveal по Pathfinder/движению;
- Meatspace Session и NET scene идут в одном Round timeline.

#### LAN resilience и continuity живой встречи

Для Online/VTT по LAN:

- все критические JS/CSS/fonts/assets хранятся локально;
- никакой зависимости от Google Fonts/CDN;
- server продолжает работать без внешнего интернета;
- локальный DNS/понятный адрес и QR;
- browser reconnect после сна телефона;
- PWA кэширует shell и справочники.

Для Live/Offline встречи:

- Session Pack доступен заранее в печатном/PDF/JSON виде;
- автоматический backup создаётся перед Session и после Session;
- GM может записывать результаты на бумажной Recap form;
- после восстановления сервера изменения вносятся одним After-Session flow;
- `Export Session Bundle` позволяет аварийно перенести материалы на другой ноутбук.

#### Этапы Tabletop

```text
TABLE-0 Подготовка: item instances, effects, NPC, Session events, permissions
TABLE-1 Live Session Pack, GM quick screen, print/export flow
VTT-1   Scenes, tokens, shared screen, movement, initiative
VTT-2   Cyberpunk attacks/range/damage/conditions
VTT-3   Fog, drawings, handouts, journals
VTT-4   NET Architecture scene
VTT-5   Internet/LAN deployment, hybrid reconnect/relay
VTT-6   Walls/vision/lighting and extension API if still needed
```

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
2. Item instances, Structured Effects Engine, consumables и host-based Upgrades/Attachments.
3. Market vendors + Database без универсальной покупки.
4. Database tags/i18n/armor locations.
5. Feed/Contract preview перед публикацией.
6. NPC Manager: stats, skills, weapons, attacks и full templates.
7. Netrunner Cyberdeck/Program Manager.
8. Crew Registry portraits.
9. Dedicated landscape print sheet.
10. JSON import.

Полный Ruleset/Profile layer временно исключён из P1 до выхода и изучения обновлённой системы Cyberpunk.

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
15. Storyline/Faction Clocks.
16. Universal Search/Entity Links.
17. Safety Tools.
18. Session-scoped Co-GM/Observer permissions.
19. NET Architecture Builder после Program Manager.

### P3 — технический долг

1. Разделить `server.py`, `app.js`, `ncnet.js`, CSS.
2. Убрать N+1 queries.
3. Pagination/summary endpoints.
4. Browser E2E и visual regression по темам.
5. Health endpoint, HEAD, self-hosted fonts.

### P4 — далёкое будущее / Cyberpunk Tabletop

1. Live/Offline Session Pack и GM companion для живой встречи.
2. Optional Shared Screen/Player Phone для живой встречи.
3. Online VTT через Internet или LAN: Scenes/Tokens/Initiative/Event Stream.
4. Cyberpunk attack/range/damage integration.
5. Fog/Handouts/Journals.
6. NET Architecture tabletop scene.
7. Online presence/reconnect и optional hybrid relay.
8. Walls/vision/lighting только после полезного MVP.

### DEFERRED / WATCHLIST — обновлённая система Cyberpunk

До официального релиза не оценивать и не реализовывать:

- Ruleset Profiles UI;
- House Rules constructor;
- массовую конвертацию Character Sheets;
- новый rules automation layer;
- совместимость старых/новых statblocks;
- migration Programs/Vehicles/Items под неподтверждённые правила.

Триггер возврата задачи: доступен финальный официальный текст, выполнен Rules Review и принято решение кампании.

---

## 18. Предлагаемый порядок ближайшей реализации

### Пакет 0 — Foundation, Privacy & Data Safety

1. Privacy payload для Dossiers/Roster/Folio.
2. Invite registration, password/session controls.
3. Атомарные транзакции и регулярные backups.
4. Full Campaign Export/Import bundle.
5. Source metadata, `rules_version` snapshots и migration-friendly IDs без Ruleset UI.
6. Session-scoped Co-GM/Observer permissions.
7. Базовые Safety Tools.

Ruleset Profiles, House Rules UI и конвертация под новую систему остаются в deferred/watchlist до официального релиза.

### Пакет A — Catalog & Market Rework

**Статус A.1 — базовая переработка реализована.**

1. ✅ Исправить numeric normalization и EN/RU item tags.
2. ✅ Добавить item detail во все Market cards.
3. ✅ Добавить sorting/filtering/compare.
4. ✅ Вывести armor locations.
5. ✅ Убрать мгновенную покупку из Database/Full Catalog.
6. ✅ Добавить Vendor Personas и vendor-specific stock.

**A.2 остаётся в backlog:** persisted finite stock, `Reserved/Sold Out`, независимые multi-vendor offers, `New Today`, Legal Retail, Fixer Requests, Reputation/Favor gates и Vendor Locations. Подробная спецификация и порядок находятся в разделе 2.

### Пакет B — Character Ownership

**Статус B.1 — реализован фундамент stable item instances:**

- добавлена additive migration `item_instances`, не требующая сброса БД;
- старые durable stacks безопасно разделяются на отдельные экземпляры, ammunition остаётся stack;
- Inventory, Cyberware, equipped Armor и Weapon State получают стабильные `instance_id`;
- новые покупки durable gear создают отдельный экземпляр на каждую единицу;
- продажа адресуется к конкретному экземпляру, а не удаляет все предметы с одинаковым catalog key;
- добавлен owner/GM API списка экземпляров; чужие приватные экземпляры сервер не выдаёт;
- JSON внутри Dossier временно остаётся compatibility projection для поэтапного перехода UI и правил.

**Статус B.2 — реализована первая версия Trust + Audit:**

- владелец открывает отдельный Character Sheet Editor и свободно меняет narrative, STATs, Skills, primary Role/Rank, Cash, IP, Reputation, HP/Humanity, Inventory, Cyberware и Armor;
- каждое сохранение требует причину, `revision` защищает от перезаписи изменений из другой вкладки;
- сервер нормализует catalog items и не доверяет присланным клиентом характеристикам предмета;
- одно сохранение создаёт агрегированный change set с понятными строками `до → после`, actor, time и reason;
- полный before/after snapshot остаётся на сервере и не перегружает обычный Ledger response;
- последний change set можно безопасно откатить целиком; после следующего изменения старый snapshot блокируется от опасного отката;
- generic Profile PUT остаётся ограниченным и не превращается обратно в неаудируемую замену JSON;
- Admin editing чужих Dossiers и более детальный field-by-field editor остаются следующими подэтапами.

**Статус B.3 — реализованы Custom / Found Items:**

- Database item можно добавить как найденный/полученный без Market purchase с источником `Loot`, `Gift`, `Crafted`, `Role Access`, `GM Award`, `Custom` или `Other`;
- полностью custom item получает собственные name, description, category, reference value, quantity, `stackable`, acquisition details и private notes;
- custom item заметно помечается `CUSTOM · MANUAL` и `manual_resolution_required`, пока Structured Effects не опишет его механику;
- custom data не может внедрить поддельные Damage, SP, HL, mechanics, requirements или Cyberware installation rules;
- durable custom quantity разделяется на стабильные экземпляры, explicit stackable остаётся одним stack;
- конкретный экземпляр можно переименовать, исправить описание/value/source и удалить независимо от одноимённых вещей;
- acquisition source сохраняется в `item_instances`, а private item/acquisition notes вырезаются из public Dossier на сервере;
- добавление, изменение и удаление входят в обычный Trust + Audit change set и безопасный revert.

**Статус B.4 — реализована первая версия Consumables и Active Gear:**

- Data Pool получает курируемые декларативные флаги `consumable`, `stackable`, `use_effect`, `equippable`, equip modes/slots, hands и activation requirement;
- Pharma и Street Drugs размечены как расходники с `Use`, уменьшением количества и ручным эффектом по официальному описанию;
- `Flashlight`, `Radio Communicator`, `Agent (Standard)`, `Airhypo`, `Techtool` и `Medtech Bag` размечены как Active Gear;
- Character Sheet показывает `Active Gear / Loadout`, состояния `READY / ACTIVE / OFF` и equipment-only actions;
- доступны server-authoritative `Use / Equip / Unequip / Activate / Deactivate`, проверка carried/broken/stored, mode/slot и занятых рук;
- израсходованный последний экземпляр исчезает из Inventory, а последний item action можно безопасно откатить через Ledger;
- custom item не может сам назначить себе consumable/equippable или внедрить use/equip mechanics;
- mounted host links, мягкий ready limit и автоматическое применение Structured Effects остаются следующими подэтапами.

**Статус B.5 — реализован фундамент Structured Effects & Modifiers:**

- effect/synergy definitions вынесены в отдельный declarative `effects.json` с `rules_version`, allowlist targets/operations/fields и fail-closed validation;
- данные эффектов не могут содержать JavaScript/Python или произвольные поля;
- серверный pipeline поддерживает `set / minimum / maximum / add / multiply`, priority и `stack / highest / lowest / unique / replace`;
- Character Sheet хранит base Skill/STAT без перезаписи и возвращает отдельные modifiers/effective values;
- Skill table и dice rolls используют effective check base, а IP progression продолжает считать стоимость от base Skill Level;
- Armor penalties и Humanity-derived EMP включены в общий readable stat breakdown;
- подтверждённые правила `3+ Light Tattoo → Wardrobe & Style checks +2` и `Chemskin + TechHair → Personal Grooming checks +2` работают независимо и только один раз;
- UI показывает прогресс набора, ACTIVE/INACTIVE, источник и итоговый бонус; активация/деактивация synergy попадает в readable Ledger diff;
- temporary/custom active effect instances и duration/round tracking вынесены в следующий подэтап B.5.2.

**Статус B.5.2 — реализованы Active Effect Instances и базовая duration model:**

- additive migration создаёт `active_effect_instances` с immutable definition snapshot, actor, reason, source, started/expires/remaining rounds и archive state;
- владелец в Trust + Audit может добавить allowlisted custom modifier для STAT или Skill Check; GM может включать, отключать, архивировать и вручную двигать round duration;
- custom effect проходит тот же серверный schema validator и stacking pipeline, что curated effects; неизвестные поля и executable payload отклоняются;
- поддерживаются `manual`, `real_time` и `rounds`: real-time истекает по серверному времени, rounds уменьшаются только явным `Tick`, а не притворяются связанными с Session clock;
- effect creation/state changes повышают Dossier `revision`, создают readable Ledger events и защищены от stale tabs;
- Character Sheet показывает status, target, operation/value, duration, actor/reason и кнопки Disable/Enable/Tick/Archive;
- активные экземпляры меняют effective STAT/Skill checks и реальные rolls, не меняя base values;
- public Dossier не получает private reason/actor/source instance details;
- автоматическая связь `Use → active effect` вынесена в следующий curated подэтап; Session-authoritative round ticking и campaign clock остаются будущими интеграциями.

**Статус B.5.3 — запущены Curated Item Effect Overrides:**

- `effects.json` поддерживает отдельные `item_effect_rules` с catalog ID, `active_when`, automated effects, manual rules и source/page metadata;
- сервер строго валидирует item rule fields, item IDs, activation conditions и manual-rule snapshots;
- первый curated override: активный экипированный `Agent (Standard)` автоматически даёт `+2 Library Search Check` один раз, независимо от числа Agents;
- условный `+2 Wardrobe & Style` от сезонного комплекта Agent не автоматизируется без подтверждения одежды и честно показывается как `MANUAL RULE`;
- Database, Market и owned item cards различают `AUTOMATED EFFECT` и `MANUAL RULE`;
- Character Sheet показывает Curated Item Effects, requirement state, source и manual condition; реальные rolls используют автоматический modifier;
- Equip/Activate/Deactivate меняют состояние item effect и создают отдельную readable строку активации в Ledger;
- custom item не может подделать себе effect coverage;
- расширение curated overrides продолжается постепенно с source-specific regression tests.

**Статус B.5.4 — реализована первая связь `Use → Active Effect`:**

- `effects.json` поддерживает строго валидируемые `use_effect_rules` с catalog item, duration, automated definitions, manual secondary rules и source/page;
- migration 9 добавляет `preset_id/context_json`, поэтому manual secondary rules и source snapshot остаются рядом с Active Effect даже после исчезновения использованной дозы;
- первые безопасные presets: `Boost → INT +2 на 24 часа игрового времени` и `Synthcoke → REF +1 на 4 часа игрового времени`;
- in-world часы хранятся как `campaign_time` metadata и пока завершаются вручную: они намеренно не приравнены к реальным часам сервера до появления Campaign Clock;
- использование дозы атомарно уменьшает Inventory и создаёт связанный `active_effect_instance` с `source_item_instance_id`;
- повторная доза с `replace` не складывает бонус: новый primary effect заменяет прежний;
- Secondary Effect, addiction, Humanity Loss и roleplay-условия не симулируются без проверок и показываются отдельным `MANUAL RULE`;
- Use Resolution явно разделяет автоматический modifier, ручные последствия и полное описание предмета;
- item-action Ledger хранит created/replaced effect IDs; безопасный revert возвращает дозу, архивирует созданный эффект и восстанавливает предыдущий ещё не истёкший effect;
- Pharma/Drug правила без однозначного allowlisted numeric effect остаются ручными до появления нужных targets/resources/conditions.

**Статус B.6.1 — реализован фундамент Host / Modification Model:**

- migration 10 создаёт `item_modifications` со стабильными `host_instance_id → upgrade_instance_id`, active/removal history, slots, permanent flag, installer, config snapshot и source;
- importer нормализует Gun Upgrades: `host_type`, attachment slots, compatibility text, rebuild/attachment kind, unique/group conflicts, permanent installation и manual compatibility marker;
- первый host type — конкретный экземпляр ranged weapon; одинаковые пистолеты получают независимые наборы upgrades;
- сервер проверяет ownership, carried/installed state, weapon category/type/Skill, Exotic/Non-Exotic ограничения, Bows/Pistols/Shoulder Arms и attachment capacity;
- сложные source rules не угадываются: они требуют явного `manual_confirm` и записываются в Trust + Audit;
- Character Sheet показывает slots и установленные upgrades; `Manage Upgrades` предлагает совместимые экземпляры из Inventory с причинами блокировки;
- Install/Remove атомарно меняют upgrade instance state, relational link, Dossier revision и readable Ledger;
- modified host/installed upgrade нельзя тихо удалить или продать; сначала требуется снять modification;
- linked Ledger revert восстанавливает relational link и Inventory state вместе, а небезопасный автоматический redo блокируется;
- permanent attachments нельзя снять обычным Remove, а их installation change set не получает опасную кнопку revert;
- effective weapon mechanics от конкретных upgrades, Compatibility Rail capacity и Tech/manual override effects вынесены в B.6.2.

**Статус B.6.2 — подключены первые Effective Weapon Mechanics:**

- `effects.json` поддерживает строго валидируемые `weapon_modification_rules`; installation сохраняет immutable rule snapshot и rules version в modification config;
- `Drum Magazine` и `Extended Magazine` меняют effective magazine по официальной таблице CP:R 343 и делают оружие несрываемым под одеждой, не переписывая base mechanics;
- `Smartgun Link` даёт `+1 Attack Check` только при установленных Interface Plugs или Subdermal Grip; при невыполненном requirement upgrade остаётся установленным, но bonus показывает INACTIVE;
- `Bayonet` автоматически меняет effective Concealability, а alternate Light Melee Weapon action остаётся честным `MANUAL RULE`;
- weapon card показывает base→effective Magazine/Concealability, Attack modifier, source, requirement status и manual rules;
- magazine state синхронизируется с effective capacity при Install/Remove/Reload: увеличение не создаёт патроны, уменьшение безопасно clamp-ит current magazine;
- upgrade effect применяется только к конкретному host instance; второй одноимённый пистолет сохраняет base mechanics;
- config snapshot защищает уже установленный upgrade от тихого изменения будущего catalog rule;
- остальные underbarrel/rebuild/IR effects и Tech overrides продолжаются только через отдельные curated definitions.

**Статус B.6.3 — реализованы Advanced Weapon Slot Pools:**

- importer различает general attachment, scope и underbarrel slot types, а также declarative `grants_slots`;
- Compatibility Rail на Exotic weapon создаёт отдельный `scope 0/1`, не превращая его в универсальный attachment slot;
- Scope изначально несовместим с Exotic host и становится доступным только после установки конкретного Rail instance;
- scope capacity считается отдельно от general slots; второй scope блокируется понятной причиной;
- Rail нельзя снять, пока установленный scope зависит от выданного им slot; сначала снимается dependent modification;
- Character Sheet и Manage Upgrades показывают usage каждого slot pool;
- Compatibility Rail помечается как automated slot grant, а Infrared Nightvision Scope и Sniping Scope показывают source-specific `MANUAL RULE`;
- situational scope bonuses не добавляются ко всем атакам: darkness/range/Aimed Shot/TeleOptics conditions остаются ручными до появления контекстного attack evaluator;
- rail/scope rules сохраняются в installation snapshot и участвуют в том же atomic Ledger lifecycle.

**Статус B.6.4 — реализованы Underbarrel Weapon Profiles:**

- Grenade Launcher Underbarrel и Shotgun Underbarrel создают отдельный alternate attack profile на конкретном host instance;
- profiles имеют собственные Skill, Damage, ROF, Magazine state и source snapshot, не заменяя основную атаку оружия;
- Grenade profile: Heavy Weapons, 6d6, Mag 1; Shotgun profile: Shoulder Arms, 5d6, Mag 2;
- новый underbarrel всегда устанавливается разряженным; временный отдельный reserve этого этапа заменён реальным Inventory ammo transfer в B.7.5;
- Fire/Reload являются server-authoritative modification actions с revision guard, readable Ledger и безопасным revert resource state;
- снятие underbarrel удаляет его active profile/state, а revert восстановления modification возвращает snapshot;
- требование держать host двумя руками показывается как `MANUAL RULE`: система пока не притворяется, что умеет отслеживать текущий хват оружия;
- Character Sheet показывает alternate profile, Attack/Damage, отдельный Mag/Reserve и controls под основной карточкой host;
- общий ammo ownership/transfer между несколькими weapons и automatic two-hand enforcement остаются следующими combat/loadout интеграциями.

**Статус B.6.5 — реализованы Configurable Autofire Upgrades:**

- `weapon_modification_rules` поддерживает allowlisted Autofire profiles, enhancement conditions и required installation configuration;
- Pistol Autosear добавляет Autofire (Machine Pistol 3) и Suppressive Fire; Excellent Quality или уже имевший Autofire pistol получает multiplier 4;
- SMG Cyclic Internals требует явный выбор при Install: `SMG 4` или `Machine Pistol 4`; выбор валидируется сервером и сохраняется в immutable modification snapshot;
- Character Sheet показывает Autofire Skill Base, выбранную table, maximum multiplier, ammo cost 10 и Suppressive Fire, а Dice button бросает effective Autofire Check;
- неправильная, отсутствующая или подменённая configuration блокируется; complex Weaponstech/source rule по-прежнему требует `manual_confirm`;
- SMG Cyclic нельзя поставить на оружие без базового Autofire (SMG 3);
- Shotgun Auto Control Group пока показывает `MANUAL RULE`, поскольку результат зависит от реально загруженных slugs/shells, расхода 4 rounds, другого Skill и dodge penalty;
- Autofire damage по margin/DV и фактическое списание 10 rounds остаются будущей combat action integration, а не симулируются простой кнопкой.

**Статус B.6.6 — реализованы Weapon Rebuild identities и requirements:**

- Power/Smart/Tech Rebuild остаются взаимоисключающими через `weapon_rebuild` group и занимают по 2 attachment slots;
- каждый rebuild декларативно выдаёт effective tag `Power Weapon`, `Smart Weapon` или `Tech Weapon`, не переписывая base item;
- Smart Rebuild автоматически даёт `+1 Ranged Attack Check` только при Interface Plugs/Subdermal Grip, аналогично проверенному Smartgun requirement;
- Improved Smart Ammunition остаётся manual ammo rule до единого loaded-ammo state;
- Power Critical Injury +5 и ricochet trajectory/penalties показываются source-specific `MANUAL RULE`, поскольку требуют результата damage/critical и геометрии атаки;
- Tech charge, 20-round/60-second duration, Thin Cover и half-SP charged shot показываются как manual state/action rules, а не как постоянное игнорирование SP;
- Character Sheet показывает rebuild tag, active/inactive requirement, automated Attack bonus и все ручные действия с source/page;
- base ROF/Damage/SP не изменяются до выполнения контекстного attack flow.

**Статус B.6.7 — реализована Range Table Modification:**

- installation требует обязательный выбор replacement Range Table, вычисленный сервером для конкретного host instance;
- допустимые families разделены на Pistol, SMG, Shotgun, Rifle, Bow, Grenade Launcher и Rocket/Missile Launcher;
- Pistol может выбрать Snubnose/Pistol/Long Barrel family, но не может подменить таблицу на Sniper Rifle; cross-family payload блокируется;
- base Range Table хранится отдельно, Character Sheet показывает `Pistol → Long Barrel Pistol`, а Remove возвращает base;
- Damage, ammunition types, Magazine и остальные mechanics не меняются;
- выбор хранится в immutable modification config snapshot и проходит тот же Trust + Audit lifecycle;
- Range Table Modification остаётся manual-confirmed из-за source-specific individual eligibility, даже когда family choice валиден;
- фактический Range DV picker/attack context будет использовать effective table в будущем combat action, но текущий этап уже создаёт единый authoritative value.

**Статус B.7.1 — реализован Vehicle Garage и instance-bound upgrades:**

- importer нормализует Vehicle Upgrades: availability, Nomad Access, repeatability, prerequisites, conditional host prerequisites, conflicts, permanent/manual markers и source;
- общая `item_modifications` model теперь поддерживает второй host type `vehicle` без отдельной несовместимой таблицы;
- Character Sheet показывает Vehicle Garage с конкретными vehicle instances, base SDP/protection/Seats/Speed/Nomad Access и установленными upgrades;
- Manage Vehicle Upgrades показывает physical upgrades из Inventory, availability, причины блокировки, prerequisites/conflicts и repeatable limit;
- Heavy Chassis блокируется на Bikes/Jetskis/Gyrocopters; Housing Capacity на Compact/High Performance Groundcar требует установленный Heavy Chassis;
- prerequisite upgrade нельзя снять раньше зависимого; permanent vehicle weapons/parts нельзя удалить обычным Remove;
- Nomad Access остаётся отдельной семантикой: купленный/найденный physical upgrade устанавливается независимо от Role, а item с source `Role Access` требует соответствующий Nomad Rank;
- Install/Remove используют те же atomic revision, stable instance links, Ledger и safe revert, что weapon modifications;
- effective Vehicle durability, mounted weapons и Garage resource state вынесены в B.7.2.

**Статус B.7.2 — реализована Effective Vehicle Durability:**

- vehicle protection разделено на `SDP current/max`, `Body SP` и `Glass HP per window`; общий неоднозначный `SP` больше не используется в Garage;
- importer отдельно извлекает Body SP и Glass HP из готовых combat vehicles, включая машины только с бронированным стеклом;
- Heavy Chassis добавляет `+20 Max SDP`, но не выдаёт SP; при Install/Remove сохраняется уже полученный damage, а не создаётся бесплатный ремонт;
- Armored Chassis устанавливает `Body SP 13` и не меняет Glass;
- Bulletproof Glass даёт 15 HP/window первой установкой и 30 HP/window второй; окна остаются individual damage по manual rule;
- Seating Upgrade добавляет +2 numeric Seats за каждую разрешённую установку; non-numeric per-room seats не автоматизируются;
- Cycle Armor устанавливает Body SP 7, Reinforced Frame добавляет +5 Max SDP;
- Vehicle Garage показывает `base → effective`, current/max SDP, Body SP, Glass HP/window, Seats и source/manual rules;
- доступны server-authoritative SDP damage/repair controls с revision guard и Ledger;
- base vehicle mechanics не переписываются, а старые installed upgrades получают curated effects через safe fallback rules.

**Статус B.7.3 — реализованы Vehicle Actions и Mounted Weapon Profiles:**

- каждый установленный NOS получает отдельный server-authoritative tank state `uses remaining/max`; `Use NOS` атомарно тратит конкретный tank, защищён revision и записывается в Vehicle Ledger;
- автоматический календарный reset намеренно не подменяет Campaign Clock: `Reset Campaign Day` выполняется явно с обязательной причиной, а дополнительное Move Action/условие «водитель использует Action» показано как `MANUAL RULE`;
- Onboard Machinegun получает front-facing Autofire-only Assault Rifle profile: Autofire Skill, Assault Rifle Range Table, multiplier 4, Suppressive Fire, Mag 30 и расход 10 rounds на server-authoritative Fire;
- Onboard Flamethrower получает обязательную allowlisted ориентацию front/side/rear, Heavy Weapons, Shotgun Range Table, 3d6, ROF 1 и Mag 4; incendiary ignition остаётся manual resolution;
- Onboard Rocket Pod получает front-facing Heavy Weapons profile, Rocket Launcher Range Table, 8d6, ROF 1 и drum 3; существующие Heavy Chassis/availability/permanent checks продолжают применяться;
- каждое mounted weapon устанавливается разряженным и имеет собственный Magazine и Fire/Reload/Attack/Damage controls; временный reserve snapshot этого этапа позже заменён реальным shared ammo transfer в B.7.5;
- условие `Cannot reload while driving` показывается явно, но не блокирует Reload автоматически до появления authoritative driving/session state;
- все resource actions сохраняют base item неизменным, попадают в readable Ledger и безопасно revert-ятся как resource state;
- Vehicle Heavy Weapon Mount, cargo/rooms/Housing и полноценные repair workflows были вынесены в следующие Garage этапы.

**Статус B.7.4 — реализованы Heavy Weapon Mount и Interior Capacity:**

- Vehicle Heavy Weapon Mount создаёт отдельный пустой mount resource и уменьшает effective Seats на 1; установка по-прежнему требует Heavy Chassis и manual compatibility confirmation;
- `Mount · Action` привязывает конкретный stable instance только двуручного ranged weapon, переводит его в `installed`, хранит vehicle/modification links и блокирует повторную экипировку, продажу, удаление и обход Garage weapon actions;
- `Unmount · Action` возвращает тот же instance в `carried`, не сбрасывая его Magazine/Reserve; занятый mount нельзя удалить до снятия оружия;
- bound weapon использует собственные effective mechanics, weapon upgrades, Skill, Damage, Range Table и общий weapon state; Fire/Reload revision-guarded, Ledger-audited и безопасно revert-ятся;
- для Tsunami Arms Helix распознаются Autofire-only, multiplier 5, расход 20 rounds и 2 Actions to Reload; другие source-specific critical/armor/explosion rules остаются manual;
- первый mount разрешён на совместимом vehicle, а дополнительные — только на Cabin Cruiser/Yacht/Aerozep либо Groundcar с Housing Capacity; каждый mount требует доступное сиденье;
- Housing Capacity создаёт структурированный Kombi для Groundcar/AV-4 либо добавляет normal room для Cabin Cruiser/Yacht/Aerozep; Garage показывает total/normal/luxury/complex rooms, beds и amenities;
- Luxury Vehicle Room заменяет одну доступную комнату без mechanics-бонуса; Complex Vehicle Room требует allowlisted purpose и даёт seat contribution 6 для Cabin Cruiser/Aerozep или 12 для Yacht;
- Cargo Bay purpose, Smuggling Upgrade и Bicycle Smuggling Compartment отображаются как структурированные cargo modules; DV17, hidden holsters и ограничения размеров сохранены, но фактическое содержимое остаётся `MANUAL CARGO`;
- Housing нельзя снять, пока от него зависят room upgrades или несколько Groundcar mounts; количество upgraded rooms не может превысить rooms total;
- выдача Family gift weapon, точные room layouts/cargo contents и полноценные repair workflows были оставлены следующим этапам.

**Статус B.7.5 — реализованы Shared Ammo и Vehicle Repair Workflow:**

- ammo stack теперь хранит точное `ammo_rounds` отдельно от количества купленных packs; legacy stacks безопасно получают rounds по `quantity_per_purchase`, а частично использованный pack не превращается обратно в полный;
- Reload для обычного оружия, Underbarrel profiles, Onboard weapons и bound Heavy Weapon Mount требует выбрать конкретный совместимый ammo instance и атомарно переносит реальные rounds из Inventory в Magazine;
- старые приватные `Reserve` snapshots обнуляются; Character Sheet показывает общий совместимый `Shared` ammo pool, а удалённый после полного расхода stack также удаляется из stable item instances;
- Magazine запоминает загруженный catalog ammo type; другой тип нельзя смешать до опустошения магазина, а при Magazine 0 loaded-ammo identity очищается;
- Reload/Fire защищены revision, попадают в readable Ledger и revert-ят Magazine и ammo stack одним change set; прямой обход Garage для bound weapon остаётся закрыт;
- Market добавляет новые packs в точный rounds balance; при resale продаются только целые оставшиеся packs, а неполный последний pack продать нельзя;
- положительные SDP adjustments и `Repair Full` удалены из обычного resource action: восстановление проходит только через отдельный Vehicle Repair Workflow;
- Start Repair автоматически определяет Skill: Basic Tech для Bicycle, Land/Sea/Air Vehicle Tech для соответствующего транспорта;
- severity фиксируется по текущему SDP: Minor при половине Max SDP или выше — DV9/3 hours, Major ниже половины — DV13/1 day, Destroyed при 0 SDP — DV17/1 week (`CP:R 140`); workflow хранит technician, исходный/целевой SDP и source;
- Resolve Repair Check сравнивает введённый итог с authoritative DV: success восстанавливает транспорт до perfect condition, failure не меняет SDP и требует начать работу заново; Cancel завершает work order без ремонта;
- все start/resolve/cancel events revision-guarded, Ledger-audited, revertible и сохраняются в ограниченной repair history;
- paid NPC repair pricing, Campaign Clock completion, выгрузка заряженных патронов и общий Crew ammo/cargo stash остаются будущими интеграциями.

**Статус B.8.1 — реализованы Cyberdeck Hosts и Loadout Foundation:**

- конкретные Cyberdeck instances стали третьим полноценным host type общей `item_modifications` model;
- каталог runtime-нормализует Cyberdeck Hardware и Programs: Hardware занимает 1–3 slots по source text, обычная Program — 1 slot, Black ICE — 2 slots;
- поддерживаются отдельные `program`, `hardware`, `mixed` и Kaliya `Flak-only` slot pools для всех 18 Cyberdeck models из Database;
- Install/Uninstall привязывает конкретный stable Hardware/Program instance к выбранной деке, переводит item в `installed`, блокирует продажу и проходит revision/Ledger/revert lifecycle;
- server проверяет model-specific restrictions: Kirama Entry classes, Microtech Assault Black ICE-only, Kerberos Hellhound-only, Verdant Knight Sword/Shield, Warlock’s Book, Kaliya и MicroMate;
- Swamp Mist не допускает non-Wisp Black ICE, а Perfume Shoppe динамически уменьшает Skunk до 1 slot; Perfume Shoppe нельзя снять, если после этого loadout станет перегружен;
- Character Sheet получил Netrunning/Cyberdeck Loadout panel, раздельные Hardware/Programs, slot breakdown и Manage Loadout;
- все Hardware effects пока отображаются как source-backed `MANUAL RESOLUTION`: произвольный исполняемый код в Hardware/Program data не добавлен;
- Program runtime, REZ current/max, Rez/Derez, destroyed copies и Black ICE NET entities были вынесены в следующие Netrunning подэтапы.

**Статус B.8.2 — реализован Non-Black-ICE Program Runtime:**

- каждый установленный Program instance получает собственный server-authoritative `program_state`: deck/modification links, category, status, REZ current/max, run count и last run time;
- Booster/Defender поддерживают `Rez`, REZ damage, automatic `derezzed` at 0, explicit `Derez` и обязательный `Deactivate` перед повторной активацией или Uninstall;
- Deactivate восстанавливает runtime к готовому inactive state, а повторный Rez начинает с полного REZ; source restrictions `Only 1 copy ... running` проверяются сервером;
- Attacker Programs используют отдельный `Run · Manual Effect`: запуск и audit фиксируются, но неоднозначный target/effect/damage не симулируется автоматически;
- `Destroy Copy` деактивирует relational installation, освобождает Cyberdeck slots, переводит конкретный stable item в `broken` и поддерживает linked Ledger revert;
- установленный Backup Drive сохраняет уничтоженные non-Black-ICE Programs вместе с их runtime snapshot; Meat Action Restore атомарно проверяет текущие model restrictions/slots и возвращает все доступные copies;
- удаление Backup Drive с сохранёнными Programs стирает contents по source rule и специально создаёт non-revertible Ledger entry;
- Character Sheet показывает status, REZ, Program actions, saved-program count и Backup restore controls;
- попытка обычного `Rez` для Black ICE блокируется: система не изображает его обычной включённой Program и передаёт управление отдельному NET entity deployment;
- Program effects, targets, NET checks и особые Hardware triggers пока остаются `MANUAL RESOLUTION`, без JavaScript/Python в item data.

**Статус B.8.3 — реализованы Black ICE NET Entities:**

- каждая установленная Black ICE copy может создать не более одной active `net_entity`, связанную со stable Program instance, Cyberdeck и Character;
- deployment имеет два явных режима: `LIE IN WAIT` размещает ICE на указанном Floor без target/Initiative, `DEPLOY IN COMBAT` требует target и сохраняет server roll `SPD + 1d10`;
- entity получает source-backed PER/SPD/ATK/DEF/REZ snapshot и target type: Anti-Personnel преследует enemy Netrunner, Anti-Program — enemy Program source;
- поддерживаются authoritative actions `REZ Damage`, `Slide`, `Engage`, `Deactivate` и `Destroy Entity & Copy`; Slide возвращает ICE в lying-in-wait, а Engage назначает новую цель и Initiative;
- REZ 0 переводит entity и Program runtime в `derezzed`; Deactivate архивирует entity и возвращает concrete Program в inactive/full-REZ state для будущего deployment;
- Destroy архивирует entity, освобождает Cyberdeck slots и переводит source copy в `broken`; linked Ledger revert восстанавливает installation, runtime и entity context одним snapshot;
- Character Sheet показывает отдельную Black ICE entity card со stats, status, Floor, Target и Initiative; deploy/entity controls защищены revision и требуют audit reason;
- публичный Dossier server-side скрывает Floor, target, Character owner и raw initiative roll даже при открытом Equipment;
- Floor/Target этого этапа начинались как validated manual labels; связь с Session NET context была вынесена в B.8.4.

**Статус B.8.4 — реализована Live NET Session Integration:**

- schema migration 11 добавляет additive `net_state_json` в `nc_sessions`; перед pending migration сохраняется автоматический SQLite backup, сброс базы не требуется;
- GM/Co-GM создаёт validated Session NET Floors; active entity блокирует удаление используемого Floor;
- Character, добавленный в Session combatants, автоматически получает scoped `crew` access и видит доступные Live NET contexts, Floors и допустимые target combatants;
- Black ICE deployment может быть связан с конкретными `session_id`, `floor_id` и `target_combatant_id`; сервер заменяет пользовательские labels данными Session и запрещает self/foreign targets;
- Session хранит links на canonical Character `net_entities`, а не копирует runtime stats; Character JSON остаётся authoritative source REZ/status, Session — authoritative Floor/target/visibility/queue context;
- GM Session Dashboard получил отдельный `LIVE NET` board, validated Floors, Black ICE cards, NET Round и независимую NET Initiative Queue;
- Session-scoped GM/Assistant с `edit_combatants` может применять REZ damage, Slide, Engage, Deactivate и Destroy через character endpoint без глобального доступа к чужому Dossier;
- initial `Lie in Wait` скрыт из Player View; combat deployment и Engage делают entity видимой, после чего Player View показывает отдельную NET queue со stats/REZ/Floor/Target;
- все deploy/entity/turn/floor операции пишутся в Session Activity; linked Character Ledger revert атомарно возвращает и Character runtime, и Session NET context snapshot;
- Floor и target стали validated внутри Session; полноценный topology graph был вынесен в B.8.5.

**Статус B.8.5 — реализован NET Architecture Graph Foundation:**

- существующий Session `net_state_json` расширен allowlisted `nodes` и `paths` без новой schema migration: B.8.4 migration 11 уже предоставляет безопасный контейнер;
- GM создаёт nodes типов `Access Point`, `Password`, `File`, `Control`, `Black ICE` и `Objective` с validated Floor, DV 0–29, defense 0–29, reveal/resolved state и приватной заметкой;
- paths соединяют только существующие разные nodes, имеют `bidirectional`/`one_way` direction, reveal state и optional label; duplicate/self/orphan edges блокируются;
- dependency-safe deletion запрещает удалять Floor с nodes, node с paths либо node/Floor, используемый active Black ICE entity;
- Black ICE deployment и Engage теперь могут требовать конкретный validated node; combat deployment автоматически reveal-ит выбранный node, а entity хранит canonical node link;
- Session Dashboard получил Architecture Graph builder, node reveal/resolve controls, path creation/reveal и topology cards рядом с LIVE NET queue;
- Player View получает только revealed nodes и paths, причём path показывается лишь когда reveal-разрешены оба endpoint nodes; `gm_note`, internal Floor links и hidden topology server-side не отправляются;
- вся topology validation выполняется по строгим типам и bounded полям; JavaScript/Python/произвольные effect payloads в nodes не поддерживаются;
- Pathfinder/Eye-Dee/Backdoor/Control Actions, движение по paths, Password blocking и attack checks были вынесены в B.8.6.

**Статус B.8.6 — реализован NET Action Resolution:**

- Session NET state хранит authoritative Netrunner positions: combatant/Character link, Jacked In status, current/previous node, Interface Rank и recorded action count;
- Interface Rank всегда берётся с конкретного Character Netrunner Role; Player может действовать только своим combatant, а Session GM/Assistant — через scoped `edit_combatants`;
- `Jack In` разрешён только через Access Point, `Move` — только по revealed path с учётом one-way direction; unresolved Password блокирует движение вперёд, но сохраняет возможность отступить;
- Pathfinder делает server roll `Interface + 1d10` против bounded node DV и при success reveal-ит target node и connecting path;
- Backdoor проверяет текущий Password, Eye-Dee reveal-ит текущий node, Control делает Interface check и записывает controlling combatant;
- Program Attack требует installed Attacker Program и Black ICE entity на текущем node; сервер бросает `Interface + Program ATK + 1d10` против `ICE DEF + 1d10`;
- Attack result содержит totals/success и trusted source effect text как `MANUAL EFFECT`; неоднозначный damage/target consequence не применяется автоматически;
- Program Attack увеличивает runtime run count, revision-защищён, получает Character Ledger entry с `session_id`, а topology actions записываются в Session Activity/NET Action Log;
- GM Dashboard получил Netrunner position cards и action launcher; Player View показывает Jacked In position и только безопасный action summary;
- Black ICE autonomous attacks, Program effect application, Cloak/Scanner/Virus и action-budget enforcement остаются следующими NET combat подэтапами.

1. ✅ Вернуть безопасное свободное редактирование владельцем.
2. ✅ Расширить ledger до понятных diff events и безопасного revert последнего change set.
3. ✅ Мигрировать stack inventory к стабильным item instances.
4. ✅ Добавить custom/found items и acquisition provenance.
5. ✅ Consumable/use и базовый Equippable Active Gear: equip modes, hands/slots, Activate/Deactivate, Active Loadout.
   - остаётся: mounted host links и расширение курируемой разметки предметов.
6. ✅ Structured Effects & Modifiers declarative schema/evaluator и первые curated synergies.
7. ✅ Base/modifiers/effective breakdown для STAT/Skill checks в Character Sheet и Rolls.
8. ✅ Temporary/custom active effect instances; manual/real-time duration и explicit round ticking.
   - остаётся: Session-authoritative rounds и campaign clock.
9. ◐ Curated effect overrides для Data Pool с source metadata.
   - готово: item-effect/use-effect schemas, coverage markers, Agent (Standard), Boost и Synthcoke;
   - дальше: только подтверждённые source-specific overrides и presets с доступными engine targets.
10. ✅ Общая relational host/modification model и atomic lifecycle.
11. ◐ Weapon Upgrades прямо в Character Sheet.
    - готово: instance binding, slot pools, lifecycle, Magazines/Smartgun/Bayonet/scopes, Underbarrels, Autofire/Rebuild profiles и host-specific Range Table choices;
    - дальше: contextual ricochet/charge, full Autofire action/ammo и Tech overrides.
12. ◐ Vehicle Upgrades и Garage integration.
    - готово: vehicle instances, compatibility/access/prerequisites, lifecycle, effective durability, NOS, Onboard/Heavy Mount profiles, Housing/rooms/cargo modules, real shared ammo transfer и Vehicle Repair Workflow;
    - дальше: ammo unload/type-change flow, paid repair services, Campaign Clock completion и Crew cargo/ammo stash.
13. ◐ Cyberdeck/Cyberware/Armor/Tech modification hosts.
    - готово: Cyberdeck/Program runtime, Black ICE, Live NET graph/queue и Netrunner topology actions/Program Attack checks;
    - дальше: Black ICE attacks/effect application, затем Cyberware/Armor/Tech hosts.
14. JSON import.

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
5. Storyline/Faction Clocks.
6. Intel Fragments и Case Board.
7. Universal Search и stable Entity Links.
8. Medical Record и Vehicle Garage после стабилизации базовых модулей.

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

### Пакет I — Tabletop Foundations (далёкое будущее)

1. Подготовить stable entity IDs, permissions и authoritative Session events.
2. Сначала реализовать Live Session Pack, print/export и GM quick screen для живых встреч.
3. Добавить QR links для Character/NPC/Item/Location/Handout и short-lived Session PIN.
4. Добавить optional Shared Screen и Player Companion, не делая их обязательными.
5. Добавить официальный Online/LAN deployment mode и локальные assets.
6. Реализовать Online VTT Scenes, Tokens, Grid/Measurement и Initiative sync — одинаково для Internet и LAN.
7. Связать token actions с Dossiers/NPC/Weapons/Effects.
8. Добавить server-authoritative Dice/Event Log и reconnect snapshots.
9. Реализовать manual Fog, Drawings и Handouts.
10. Добавить internet presence и remote session access на VPS/relay.
11. Реализовать NET Architecture как отдельный scene type.
12. Только затем рассматривать walls/vision/lighting/plugin API.

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
36. Сколько upgrade slots у разных weapon/vehicle host types и где нужны source-specific exceptions?
37. Nomad Access создаёт виртуальный upgrade или физический item instance, который можно снять/передать?
38. Как Tech Maker Upgrade сочетается и складывается с catalog attachments?
39. Vehicle принадлежит одному Character, Family/Crew или Organization, и кто может управлять upgrades?
40. Разрешено ли передавать/продавать host вместе со всеми upgrades одной операцией по умолчанию?
41. Какой порядок `set/add/multiply/cap` использовать для конфликтующих modifiers и какие rules exceptions нужны?
42. Какие item effects автоматизируются в первой версии, а какие остаются `manual_resolution_required`?
43. Может ли Player создавать custom effect свободно или только через Trust + Audit editor с обязательной причиной?
44. Temporary effects отсчитываются по реальному времени, campaign clock или Session rounds?
45. Нужно ли показывать base/effective breakdown публичным зрителям Dossier или только owner/GM?
46. Для Online/VTT canonical server обычно домашний LAN или VPS, и нужен ли optional relay между ними?
47. Какой Live/Offline вариант основной: Fully Analog, GM Assisted, Shared Screen или Companion Phones?
48. Какие материалы входят в обязательный Live Session Pack и нужен ли единый PDF?
49. Должен ли ручной ввод результата физических кубиков попадать в общий Dice Log?
50. Какие карты обязательны в Online VTT MVP: square, hex и gridless одновременно или начать с gridless/square?
51. Применяет ли GM урон сразу или target owner подтверждает результат в Trust mode?
52. Нужен ли Shared Table Screen без авторизации через короткий read-only PIN?
53. Насколько рано нужны Fog/Walls/Vision и стоит ли полностью отказаться от dynamic lighting в пользу простоты?
54. Set bonuses и active effect breakdown видны всем или только owner/GM?
55. Должен ли Live/Offline flow позволять полностью провести встречу без запуска сервера после печати Session Pack?
56. DEFERRED: после выхода новой системы — переходит ли кампания полностью, частично или остаётся на текущем Hybrid?
57. DEFERRED: после Rules Review — нужен один новый ruleset или параллельные profiles для старых и новых персонажей?
58. Storyline/Faction Clock обновляется только GM или поддерживает автоматические triggers от Recap/Downtime?
59. Entity Links вставляются только через picker или также распознаются из `@/#/⌖` синтаксиса?
60. Как обеспечить анонимность Safety signal даже от остальных Admin/Co-GM, кроме назначенного получателя?
61. Какие точные разрешения получают Co-GM/Assistant/Rules Helper в Session?
62. Сколько живёт read-only QR/PIN из печатного Session Pack и можно ли отозвать его после встречи?

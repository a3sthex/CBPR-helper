# NC//NET — архитектура иммерсивной сети Найт-Сити

**Статус:** утверждённое направление редизайна  
**Дата:** 2026-08-19  
**Целевая эпоха:** 2070-е / Cyberpunk: Edgerunners Mission Kit  
**Язык продукта:** English по умолчанию, переключатель EN/RU сохраняется

## 1. Видение продукта

NC//NET — внутриигровая городская сеть для общей кампании в Найт-Сити. Это не витрина функций и не абстрактный «помощник по правилам».

Через NC//NET:

- ГМы размещают контракты от лица Фиксеров, корпораций, банд, редакций и других персонажей;
- игроки записываются на партии своими персонажами;
- завершённые партии порождают противоречивые публикации от лица жителей и организаций города;
- разные ГМы ведут общую историю, объединяя материалы необязательными Storylines;
- персонажи игроков существуют как публичные Dossiers и авторы City Feed;
- правила, Night Market и инструменты сессии встроены в мир как сервисы городской сети.

Публичный интерфейс должен быть максимально diegetic. Реальные аккаунты, права доступа и организационные данные существуют в отдельном служебном слое.

## 2. Зафиксированные продуктовые решения

### 2.1 Мир и структура

- Один общий Найт-Сити.
- Контракт, публикация и персона могут быть связаны с необязательной Storyline.
- Storyline — сюжетная линия общей истории, а не отдельная копия мира.
- Владелец Storyline назначает GM-соавторов.
- Целевая эпоха всей сети — 2070-е.

### 2.2 Контракты

- Публичная подача максимально иммерсивная.
- Реальный GM показывается только в небольшом Service Information блоке.
- Запись мгновенная.
- После заполнения команды новые участники автоматически попадают в резерв.
- При освобождении места первый участник резерва автоматически переводится в основной состав.
- Контракт поддерживает произвольное число персон с ролями: poster, client, broker, contact, target, informant и custom.
- Участник контракта может быть публичным или classified.
- Reward поддерживает точную сумму, диапазон, договорную или скрытую награду.
- Есть публичный и закрытый briefing.
- Закрытый briefing доступен основному составу, владельцу контракта, GM-соавторам и Admin.
- Связь контракта с публикациями City Feed необязательная.

### 2.3 City Feed

- Одна смешанная хронологическая лента.
- Форматы первой версии:
  - Short Post;
  - Screamsheet / News Article;
  - Personal Blog;
  - Official Bulletin;
  - Statement / Reaction;
  - Rumor / Intercept.
- Хранятся отдельно event time и publication time.
- Лента сортируется по publication time.
- Публикации после выхода публичны для всех.
- Игрок публикует материал от лица собственного Character сразу, без ожидания одобрения GM.
- Владелец может редактировать или архивировать собственную публикацию; GM/Admin могут скрыть её после публикации с обязательной причиной в audit log.
- Комментарии полноценные, появляются сразу и публикуются только от лица Character или доступной GM-персоны.
- Вложенность комментариев ограничивается одним уровнем; более глубокий ответ хранит ссылку/цитату.
- GM и Admin могут скрывать комментарии.
- Для GM хранится скрытая оценка достоверности: true, partially_true, false, propaganda, unknown.

### 2.4 Personas

Persona может представлять:

- человека или NPC;
- организацию;
- редакцию;
- банду;
- корпорацию;
- государственную структуру;
- анонимный канал.

Режимы доступа:

- Private — видит и использует создавший GM;
- Shared — видят и используют все GM;
- System — системная персона, управляемая Admin.

Все GM могут редактировать Shared Persona. Любое изменение и публикация от её лица попадают в append-only audit log.

Игрок не создаёт отдельные Personas: автором для него выступает принадлежащий ему Character.

### 2.5 Rules и сессии

- Quick Reference и Resolvers доступны всем пользователям.
- GM Session Dashboard доступен только GM/Admin.
- Инструмент можно использовать как справочник или как опциональный Resolver.
- NPC представлены короткой боевой карточкой и могут создаваться из шаблонов.
- Player View активной сессии настраивается GM.
- Все значения правил перед реализацией повторно сверяются с Corebook/CEMK PDF и официальными источниками.
- Каждая справочная карточка показывает источник и страницу.

### 2.6 Night Market и Character data

- Покупка на Night Market немедленно меняет Cash и Inventory и считается каноничной.
- Владелец продолжает свободно редактировать свой Character Sheet.
- Постоянные изменения записываются в Character Ledger.
- HP, текущий SP, Ammo, LUCK и временные состояния хранятся в Session Activity, чтобы не засорять постоянный Ledger.

### 2.7 Визуальный и звуковой слой

- Название сети: **NC//NET**.
- Главная: точная карта Найт-Сити + City Feed.
- Базовая оболочка холодная: black/navy/white/red.
- Persona, организации и типы публикаций добавляют собственные неоновые цвета.
- Карта строится по официальному источнику 2070-х и подтверждается владельцем проекта до финальной отрисовки.
- На мобильных устройствах список Contracts является полной альтернативой карте.
- Звук — значимая часть атмосферы, но запускается только после пользовательского действия.
- Всегда доступны Mute, volume, сохранение настройки и безопасный режим без резких сигналов/мерцания.
- Используются только оригинальные или лицензированные звуки.

### 2.8 VK

- Первая версия отправляет сообщения только в общую беседу VK.
- OAuth-привязка пользователя нужна для корректных упоминаний в беседе.
- В VK отправляются:
  - новый Contract с публичными данными;
  - изменение времени;
  - перенос или отмена;
  - «crew full»;
  - появление свободного места;
  - In Progress;
  - Completed / Failed.
- Сообщение не отправляется на каждую отдельную запись игрока.
- Classified briefing, Discord/VTT и секретные участники никогда не отправляются в VK.
- City Feed и комментарии не отправляются в VK.

## 3. Информационная архитектура

### 3.1 Публичные маршруты SPA

| Route | Назначение |
|---|---|
| `#/` | NC//NET Dashboard: карта, Contracts, City Feed |
| `#/contracts` | Полный список и фильтры Contracts |
| `#/contracts/:id` | Public/Service/Classified Contract view |
| `#/feed` | City Feed |
| `#/feed/:id` | Публикация и комментарии |
| `#/personas/:id` | Публичный профиль Persona |
| `#/crew` | Crew Registry |
| `#/dossiers` | Персонажи текущего пользователя |
| `#/dossiers/:id` | Character Sheet / Dossier |
| `#/market` | Night Market |
| `#/database` | Codex и правила |
| `#/database/quick-reference` | Публичные таблицы и Resolvers |
| `#/profile` | Account, privacy, VK, notifications |

### 3.2 GM/Admin routes

| Route | Назначение |
|---|---|
| `#/gm` | GM OPS Dashboard |
| `#/gm/personas` | Persona CRUD и audit |
| `#/gm/storylines` | Storylines и collaborators |
| `#/gm/contracts` | Drafts, active и archive |
| `#/gm/feed` | Drafts, moderation и publishing |
| `#/gm/sessions` | Active Session Dashboard |
| `#/admin` | Users, roles, system settings, integrations |

### 3.3 Legacy redirects

| Старый route | Новый route |
|---|---|
| `#/jobs` | `#/contracts` |
| `#/news` | `#/feed` |
| `#/characters` | `#/dossiers` |
| `#/roster` | `#/crew` |
| `#/calc` | `#/database/quick-reference` |
| `#/codex` | `#/database` |

Legacy route должен продолжать открываться по сохранённой ссылке.

## 4. Роли и разрешения

Роль аккаунта не является публичной Persona.

| Действие | Player | GM | Admin |
|---|:---:|:---:|:---:|
| Читать public Contracts/Feed | ✓ | ✓ | ✓ |
| Записаться Character на Contract | ✓ | ✓ | ✓ |
| Комментировать своим Character | ✓ | ✓ | ✓ |
| Сразу опубликовать Feed post своим Character | ✓ | ✓ | ✓ |
| Создать Persona | — | ✓ | ✓ |
| Использовать Shared Persona | — | ✓ | ✓ |
| Создать Contract | — | ✓ | ✓ |
| Модерировать Feed | — | ✓ | ✓ |
| Создать/вести Session | — | ✓ | ✓ |
| Назначать GM/Admin | — | — | ✓ |
| System Persona и integrations | — | — | ✓ |

### 4.1 Выдача прав

- Новый аккаунт всегда Player.
- GM и Admin назначаются только существующим Admin.
- Переключатель «I am a GM» удаляется из регистрации и Profile.
- Backend проверяет роль на каждом защищённом endpoint; скрытие кнопки не считается защитой.
- Несколько Admin разрешены.

### 4.2 Приватность аккаунта

Пользователь выбирает, показывать ли display name другим участникам Contract. Account avatar следует той же настройке приватности: владельцу он доступен всегда, остальным — только при открытом display name. Публичные страницы по умолчанию показывают только Characters и Personas.

## 5. Модель данных

Названия таблиц предварительные. Миграции должны быть additive и backward-compatible.

### 5.1 Users

Дополнения к существующему `users`:

```text
account_role          player | gm | admin
show_display_name     boolean, default false
vk_user_id            nullable
vk_linked_at          nullable
notification_prefs    JSON
avatar_media_id       nullable; visibility follows show_display_name
```

Существующее `is_gm` временно сохраняется для совместимости, затем удаляется отдельной миграцией после проверки ролей.

### 5.2 Personas

```text
personas
├── id
├── owner_user_id
├── access             private | shared | system
├── kind               person | organization | outlet | gang | corporation | government | anonymous
├── handle             unique public handle
├── display_name
├── avatar_media_id
├── cover_media_id
├── accent_color
├── short_bio
├── public_bio
├── affiliation
├── public_connections JSON
├── status              active | missing | dead | dissolved | destroyed | archived
├── secret_bio          GM-only
├── goals               GM-only
├── voice_notes         GM-only
├── secret_connections  GM-only JSON
├── created
└── updated
```

```text
persona_audit
├── id
├── persona_id
├── actor_user_id
├── action
├── before_json
├── after_json
└── created
```

Audit нельзя редактировать или удалять через обычный UI.

### 5.3 Storylines

```text
storylines
├── id
├── owner_user_id
├── title
├── code_name
├── public_summary
├── private_summary
├── status       active | paused | completed | archived
├── created
└── updated
```

```text
storyline_collaborators
├── storyline_id
├── user_id
└── can_edit
```

```text
storyline_timeline
├── id
├── storyline_id
├── event_at
├── public_text nullable
├── private_text
├── contract_id nullable
├── feed_post_id nullable
├── created_by
└── created
```

### 5.4 Contracts

```text
contracts
├── id
├── owner_user_id
├── storyline_id nullable
├── status        draft | open | crew_full | in_progress | completed | failed | cancelled | archived
├── title
├── teaser
├── public_brief
├── classified_brief
├── district_id
├── risk_level
├── reward_mode   exact | range | negotiable | hidden
├── reward_exact nullable
├── reward_min nullable
├── reward_max nullable
├── reward_text nullable
├── scheduled_at
├── timezone
├── duration_text nullable
├── crew_capacity
├── requirements
├── content_notes
├── service_format
├── service_contact
├── service_vtt_url
├── service_notes
├── cover_media_id
├── created
└── updated
```

`service_contact`, `service_vtt_url` и classified content не возвращаются публичному API-клиенту без разрешения.

```text
contract_participants
├── id
├── contract_id
├── persona_id
├── role_key       poster | client | broker | contact | target | informant | custom
├── role_label
├── visibility     public | classified
├── note
└── sort_order
```

```text
contract_signups
├── id
├── contract_id
├── user_id
├── character_id
├── status         crew | waitlist | withdrawn | removed
├── queue_position
├── joined_at
└── updated
```

Инварианты:

- Character принадлежит user;
- один Character не записывается на Contract дважды;
- количество `crew` не превышает capacity;
- смена crew/waitlist выполняется одной DB transaction;
- после освобождения места первый waitlist автоматически становится crew;
- повышение в crew открывает classified briefing.

### 5.5 City Feed

```text
feed_posts
├── id
├── format       short | article | blog | bulletin | statement | rumor
├── status       draft | published | hidden | archived
├── creator_user_id
├── hidden_by_user_id nullable
├── hidden_reason nullable
├── author_persona_id nullable
├── author_character_id nullable
├── storyline_id nullable
├── contract_id nullable
├── reply_to_post_id nullable
├── district_id nullable
├── headline nullable
├── lead nullable
├── body
├── image_media_id nullable
├── truth_status  true | partially_true | false | propaganda | unknown (GM-only)
├── event_at nullable
├── published_at nullable
├── created
└── updated
```

Ровно один из `author_persona_id` и `author_character_id` обязателен.

```text
feed_post_links
├── post_id
├── linked_post_id
└── relation
```

```text
feed_comments
├── id
├── post_id
├── parent_comment_id nullable
├── author_persona_id nullable
├── author_character_id nullable
├── body
├── created
├── hidden_at nullable
├── hidden_by nullable
└── hidden_reason nullable
```

Комментарии появляются сразу. Backend проверяет владельца Character или GM-доступ к Persona.

### 5.6 Character Ledger

Постоянные события:

```text
character_ledger
├── id
├── character_id
├── actor_user_id
├── session_id nullable
├── contract_id nullable
├── category  cash | ip | role | skill | stat | reputation | inventory | cyberware | armor | reward
├── delta_json
├── before_json
├── after_json
├── reason
└── created
```

Ledger append-only. Он не заменяет существующий IP ledger, пока отдельная миграция и UI не будут готовы.

### 5.7 VK Outbox

```text
vk_outbox
├── id
├── event_key unique
├── event_type
├── contract_id nullable
├── payload_json
├── status       pending | sent | failed | suppressed
├── attempts
├── next_attempt_at
├── last_error
├── created
└── sent_at nullable
```

Используется transactional outbox: изменение Contract и запись уведомления создаются в одной DB transaction. Повторная отправка не должна дублировать сообщение.

VK secrets, community token и peer/chat id хранятся только в server environment/configuration, не в Git и не в БД профиля пользователя.

## 6. Contract workflow

```text
Draft
  └── Publish → Open
                 ├── capacity reached → Crew Full
                 ├── GM starts → In Progress
                 ├── GM cancels → Cancelled
                 └── reschedule → Open/Crew Full + notification

In Progress
  ├── Complete → Completed
  ├── Fail → Failed
  └── Cancel → Cancelled

Completed / Failed / Cancelled
  └── Archive → Archived
```

### 6.1 Public Contract card

- cover/avatar;
- title;
- primary poster;
- visible client;
- district;
- risk;
- reward representation;
- Connection Window;
- Crew Capacity;
- status;
- Storyline marker.

### 6.2 Service Information

- GM display name только если разрешено настройками;
- дата, timezone, duration;
- формат партии;
- системные требования;
- content notes.

### 6.3 Classified package

- classified briefing;
- Discord/VTT;
- secret contacts/participants;
- private attachments;
- дополнительные инструкции.

Проверка classified access выполняется на backend при каждом запросе.

## 7. City Feed workflow

### 7.1 GM post

```text
Draft → Preview → Publish → Published → Archive
```

### 7.2 Player post

```text
Draft (optional local/server draft)
  └── Player publish as owned Character → Published

Published
  ├── Owner edit → Published + revision entry
  ├── Owner archive → Archived
  └── GM/Admin hide with reason → Hidden
```

Предварительное одобрение GM не требуется. История редакций и post-publication moderation сохраняются в audit log.

### 7.3 Comments

- публикация мгновенная;
- один уровень визуальной вложенности;
- GM/Admin может hide/unhide;
- hard delete только Admin в технических случаях;
- скрытый комментарий не исчезает из audit trail.

## 8. GM Quick Reference и Session Dashboard

### 8.1 Quick Reference — реализовано

- Ranged Attack DV;
- Autofire DV;
- Attack Resolver;
- Damage and Armor;
- Critical Injuries Body/Head;
- Wounds and Death Saves;
- General Difficulty;
- Rules Search.

Для каждого инструмента:

- режим lookup без броска;
- режим resolver;
- EN/RU UI;
- source book и page;
- automated regression на таблицы;
- повторная ручная сверка с PDF.

### 8.2 Session Dashboard — реализовано

```text
sessions
├── id
├── contract_id
├── owner_user_id
├── status
├── round
├── active_turn
├── player_view_config JSON
├── notes
├── created
└── updated
```

Участники:

- Characters из crew;
- NPC combat cards;
- NPC из templates;
- скрытые участники.

Ресурсы:

- Initiative;
- HP;
- Head/Body SP;
- Shield;
- Ammo;
- LUCK;
- conditions;
- Critical Injuries;
- Death Save Penalty.

Player View управляется конфигурацией GM и никогда не возвращает скрытые NPC fields через API. Initiative order вычисляется сервером; активный участник сохраняется при добавлении, удалении и изменении Initiative. Dashboard даёт Previous/Next Turn, автоматический переход раундов, быстрые resource controls и независимые переключатели видимости Initiative, ally HP, Armor, Shield, Ammo, MOVE, LUCK, Conditions и Injuries.

## 9. Визуальная оболочка

### 9.1 Desktop dashboard

```text
┌ NC//NET ─ NETWORK / GM OPS ─ CITY TIME ─ ACTIVE DOSSIER ─ ⌕ ─ ACCOUNT ┐
├──────────────┬──────────────────────────────────────┬──────────────────┤
│ CITY         │                                      │ ACTIVE SIGNALS   │
│ CONTRACTS    │     NIGHT CITY MAP / WORKSPACE       │ CITY FEED        │
│ FEED         │     Contract markers and pages       │ CONTEXT STATUS   │
│ DOSSIERS     │                                      │                  │
│ ───────────  │                                      │                  │
│ DATA LAYER   │                                      │                  │
└──────────────┴──────────────────────────────────────┴──────────────────┘
```

- desktop использует постоянную left rail с четырьмя основными маршрутами;
- Database, Market, Quick Reference, Crew, Personas и Archive сгруппированы в Data Layer;
- верхняя system bar содержит время Найт-Сити, Active Dossier, command palette, sensory controls и аккаунт;
- GM получает явный переключатель `NETWORK / GM OPS`, а не россыпь служебных кнопок в публичной навигации;
- главная строится как карта 2/3 + колонка Active Signals/City Feed 1/3;
- выбран плотный HUD, но labels, keyboard focus и обычные HTML controls остаются приоритетом.

### 9.2 Mobile

- фиксированная нижняя навигация City / Contracts / Feed / Dossier / More;
- Data Layer открывается отдельной панелью More;
- карта и сигналы складываются в одну колонку;
- Active Dossier доступен через Dossier route, если не помещается в system bar;
- все действия доступны без hover.

### 9.3 Audio lifecycle

- до пользовательского жеста audio context не создаётся;
- Connect screen активирует звук;
- master mute и volume сохраняются локально и в Profile;
- reduced motion/sensory mode отключает резкие сигналы;
- скрытая вкладка не воспроизводит фоновые циклы;
- notification sounds не накладываются бесконтрольно.

## 10. Безопасность

- Авторизация и permissions проверяются на backend.
- Classified fields не должны сначала приходить в JSON с последующим скрытием CSS.
- Private character Portrait сохраняет текущую ownership-защиту.
- Media проверяет owner, attachment type и visibility.
- User-generated HTML не принимается; body хранится как текст/ограниченный безопасный markup.
- Все пользовательские строки экранируются.
- Cookie использует HttpOnly, SameSite и Secure в production.
- State-changing requests проверяют Origin/CSRF policy.
- Login, posting и comments получают rate limits.
- Audit log append-only.
- Shared Persona edit требует GM/Admin и пишет before/after snapshot.
- VK webhook проверяет signature/secret согласно выбранному официальному API flow.
- Секреты не сохраняются в репозитории.

## 11. Миграция существующих данных

Миграция не удаляет и не обнуляет рабочие данные.

### 11.1 Users

1. Добавить `account_role` с default `player`.
2. Существующих `is_gm = true` перевести в `gm`.
3. Первых Admin назначить явной server configuration до удаления GM checkbox.
4. Удалить возможность self-assign GM из UI/API.
5. Старое поле `is_gm` временно синхронизировать для backward compatibility.

Нельзя автоматически делать первый новый аккаунт Admin.

### 11.2 Jobs → Contracts

- сохранить owner GM, title, description, time, system, slots, status и signups;
- добавить legacy id mapping;
- использовать System Persona `NC//NET Contract Archive` как poster, пока GM не назначит подходящую Persona;
- существующие signups распределить в crew/waitlist по времени создания;
- old route открывает новый Contract.

### 11.3 News → Feed

- импортировать как `article`;
- сохранить title, body, tag, created и original owner в private migration metadata;
- публичным источником временно сделать `NC//NET City Archive`;
- Admin/GM может заменить source Persona после миграции;
- old route открывает Feed.

### 11.4 Characters

- данные и ownership не изменять;
- текущие Character URL redirect в Dossier;
- IP ledger сохранить;
- общий Character Ledger включать только для новых событий после точки миграции, не генерируя фиктивную историю.

### 11.5 Rollback

Каждая schema migration должна:

- иметь version marker;
- быть идемпотентной;
- создавать backup перед преобразованием legacy rows;
- не требовать reset БД;
- проходить regression на копии БД.

## 12. Этапы реализации

**Текущий статус:** функциональный вертикальный срез Phase 0–7 реализован. Внешние интеграции автоматически остаются отключёнными до появления server-side credentials. Владелец кампании подтвердил NightCity.io v0.04.1 как рабочую картографическую подложку; NC//NET сохраняет её атрибуцию и накладывает отдельный интерактивный Contract layer.

### Phase 0 — Verification and migration harness ✅

- backup/migration tests;
- role bootstrap configuration;
- legacy API inventory;
- fixture copy of DB;
- no visual changes.

### Phase 1 — Foundation vertical slice ✅

- account roles Admin/GM/Player;
- убрать self-assign GM;
- NC//NET shell и routes;
- Persona CRUD + audit;
- Storyline CRUD + collaborators;
- базовый Contract CRUD;
- crew/waitlist transaction;
- classified access;
- legacy Jobs migration;
- список Contracts вместо финальной карты.

### Phase 2 — City Feed ✅

- post formats;
- direct Character publishing without pre-moderation;
- structured owner/GM revision history, one-level comments and reasoned post/comment hide moderation;
- GM-only truth classification with a dedicated audited endpoint;
- moderation lock prevents a post owner from republishing GM-hidden content while preserving owner archive rights;
- optional Feed images, lead, district and event time with server-side timestamp/link validation;
- nested crop modal preserves the underlying Feed/Contract editor and its unsaved form state;
- legacy News migration;
- Persona/Character author pages.

### Phase 3 — Dashboard and map ✅

- проверка официального map source;
- пользователь подтверждает districts/boundaries;
- SVG layers;
- markers и filters;
- mobile list alternative;
- City Feed side panel.

### Phase 4 — Dossiers and Ledger ✅

- Dossier routes;
- permanent Character Ledger;
- Market transaction events;
- contract history;
- authored posts/comments;
- history-aware deletion: Dossier без ссылок удаляется, а с Contract/Feed/Session history становится private read-only archive без разрушения attribution.

### Phase 5 — GM Quick Reference ✅

- PDF/source audit;
- source/page metadata;
- public lookup;
- optional Resolvers;
- regression tables.

### Phase 6 — Session Dashboard ✅

- Session from Contract;
- private/shared NPC templates with edit, clone and history-safe archive;
- stable turn order/resources and round transitions;
- Previous/Next Turn controls;
- configurable Player View with server-side field filtering;
- structured/filterable session activity log without recursive raw snapshots;
- private GM JSON export and copyable Player View link;
- completion outcome.

### Phase 7 — VK, Aftermath, sound and polish ✅

- transactional VK outbox;
- group conversation events;
- OAuth link for mentions;
- one-shot Aftermath creation flow with immutable completed Crew;
- audio system;
- publication visual themes;
- keyboard-operable network cards/map markers, skip link, focus-visible states and modal focus trap/restore;
- ARIA live notifications plus final mobile/localization pass.

## 13. Acceptance criteria первого вертикального пакета

- Новый пользователь всегда Player.
- Только Admin назначает GM/Admin.
- Existing users/characters/jobs не теряются.
- GM создаёт Private/Shared Persona.
- Shared Persona редактируется GM и пишет audit.
- GM создаёт Storyline и назначает collaborators.
- GM создаёт Draft Contract с public/classified briefing.
- Contract содержит произвольные Persona roles.
- Player мгновенно записывает принадлежащий ему Character.
- При заполнении capacity следующий Character попадает в waitlist.
- При выходе crew первый waitlist автоматически становится crew.
- Classified briefing не возвращается неавторизованному пользователю.
- EN остаётся default locale; весь новый UI имеет EN/RU.
- Legacy `#/jobs` и API продолжают работать через compatibility layer.
- Tests, syntax checks, migration smoke и HTTP permission smoke проходят.

## 14. Контрольные точки, требующие подтверждения перед этапом

1. **Initial Admins:** явный список существующих аккаунтов в server configuration.
2. **Map source:** NightCity.io v0.04.1 подтверждена владельцем кампании как рабочая карта; официальный статус источника явно не заявляется.
3. **VK:** community, conversation peer id и официальный API flow; секреты только через environment.
4. **Audio assets:** лицензия/оригинальность каждого файла.
5. **Rules:** страницы Corebook/CEMK для каждой таблицы до включения в production.

## 15. Внешние активационные ограничения

Функциональный код всех этапов присутствует, но следующие возможности требуют внешней конфигурации или финального подтверждения:

- VK worker отправляет outbox только при наличии `VK_COMMUNITY_TOKEN` и `VK_PEER_ID`;
- VK OAuth требует `VK_CLIENT_ID`, `VK_CLIENT_SECRET` и `VK_REDIRECT_URI`;
- ссылки и изображения в сообщении VK требуют `NCNET_PUBLIC_URL`;
- NightCity.io v0.04.1 хранится локально с неизменённой встроенной атрибуцией и внешней ссылкой; Contract markers остаются отдельным NC//NET SVG overlay;
- процедурные Web Audio сигналы не требуют внешних лицензий; будущие записанные audio assets должны проходить отдельную проверку лицензии;
- Quick Reference содержит source/page metadata, а любые новые правила добавляются только после повторной сверки с PDF.

Отсутствие этих внешних параметров не блокирует Contracts, City Feed, Personas, Storylines, Dossiers, Ledger, GM OPS, Sessions, Player View и Aftermath.

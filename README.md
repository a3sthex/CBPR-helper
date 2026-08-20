# NC//NET

Иммерсивная сеть Найт-Сити 2070-х для общих кампаний по **Cyberpunk RED / CEMK**. ГМы размещают контракты от лица внутриигровых персон, игроки используют Character Dossiers, а сыгранные события превращаются в City Feed. Каталог предметов собирается из `Data Pool.xlsx`, стартовый ростер — из листа `Folio`.

Полная архитектура, модель данных и миграции описаны в [`docs/ncnet-redesign.md`](docs/ncnet-redesign.md), а проверенные карты/правила и страницы источников — в [`docs/ncnet-sources.md`](docs/ncnet-sources.md). NC//NET обновляет существующую базу без reset.

## Что внутри

| Раздел | Описание |
| --- | --- |
| 🛰️ **Network Shell** | Плотный diegetic HUD с desktop left rail, system telemetry, Active Dossier, command palette, явным NETWORK/GM OPS mode switch и mobile bottom navigation. |
| 🧬 **Dossiers** | Шестишаговый мастер и интерактивный официальный-inspired Character Sheet: Portrait upload/crop, Corebook role art, EN/RU, persistent draft, Hybrid Lifepath, 62/86, parent-pools, Shopping compatibility, Cyberware hosts/paired slots, HP/LUCK/Armor/ammo trackers, dice rolls, IP progression, multiclass, JSON/Print и read-only архив с сохранением NC//NET history. |
| 👤 **Profile** | Account avatar с квадратной crop-обработкой, privacy display name/avatar, Appearance, audio volume, VK linking и управляемые Admin роли. |
| ♿ **Accessibility** | Skip link, видимый keyboard focus, Enter/Space activation для Contracts/Feed/Personas/map markers, modal focus trap/restore, ARIA live notifications и reduced-motion support. |
| 📖 **Гайды** | Мини-гайды из «Spes Desperata»: пошаговое создание персонажа (роли, 62 очка статов, 86 очков навыков, стартовая закупка), боёвка FNFF (действия, DV-таблицы, крит. травмы, укрытия, транспорт) и нетраннинг (СЕТевые действия, Interface-способности). |
| 📋 **Crew Registry** | Все публичные персонажи всех игроков. При старте импортируется ростер вашей партии из Folio (13 эджраннеров). |
| 🕶️ **Чёрный рынок** | Ночная витрина (обновляется ежедневно в 00:00 МСК, уличные цены ±50%), полный каталог на 1092 предмета, скупка хлама за 50%, выплаты от ГМ. |
| 📚 **Справочник** | Поиск по 14 категориям с ценами, характеристиками, описаниями и ссылками на книги (`CP:R 341` = Corebook, `BC` = Black Chrome, `CEMK` = Edgerunners Mission Kit). |
| 🎲 **Quick Reference** | Damage/SP, Critical Injuries, Autofire, Death Saves, Range DV и General Difficulty с указанием книг и страниц; инструменты можно использовать как справочник или Resolver. |
| ◈ **Personas / Storylines** | Private/Shared/System персоны, общий audit log, GM-соавторы сюжетных линий и публичная/закрытая хронология. |
| 📡 **City Feed** | Шесть форматов, прямые Character-публикации, optional images с preset/custom crop, отображение полного соотношения без обрезки и полноразмерный lightbox, event/publication time, metadata, replies, revisions, moderation и скрытая GM truth. |
| 📞 **Contracts** | Карта NightCity.io v0.04.1 с интерактивным marker overlay, необязательные cover images с nested crop editor, произвольные Persona-роли, public/classified briefing, reward modes, мгновенная запись Character, waitlist, исторический Crew и Aftermath. |
| ⚙️ **GM OPS** | Поиск и фильтры для Sessions/NPC Templates/Storylines, улучшенные Storyline/collaborator/timeline editors, стабильный initiative order, HP/SP/Shield/Ammo/LUCK/MOVE/Injuries controls, фильтруемый activity log, private GM JSON export и независимо настраиваемый Player View. |

## Запуск

Только Python 3.8+ из стандартной библиотеки, ничего ставить не нужно:

```bash
python3 app/server.py            # http://0.0.0.0:8000
python3 app/server.py --port 8080
```

- `app/import_data.py` — пересборка `app/data/items.json` из `Data Pool.xlsx` (запускается автоматически, если файла нет);
- `app/data/cbpr.db` — SQLite, создаётся при первом старте (в git не хранится);
- новый аккаунт всегда получает роль **Player**;
- **GM** и **Admin** назначаются только через Admin Console;
- перед первой выдачей прав существующий аккаунт явно указывается в `CBPR_ADMIN_USERS` и сервер перезапускается;
- альтернативный путь БД для smoke/tests задаётся через `CBPR_DB_PATH`.

Пример безопасного назначения первого Admin после регистрации аккаунта `operator`:

```bash
CBPR_ADMIN_USERS=operator python3 app/server.py
```

Для systemd переменная задаётся в конфигурации службы, после чего сервис перезапускается. Не добавляйте имена администраторов вместе с секретами или токенами в Git.

Опциональная интеграция с общей беседой VK и OAuth-привязка пользователей включаются только серверными переменными:

```bash
VK_COMMUNITY_TOKEN=...          # токен сообщества
VK_PEER_ID=...                  # peer_id общей беседы
VK_CLIENT_ID=...                # VK OAuth app
VK_CLIENT_SECRET=...
VK_REDIRECT_URI=https://example.com/api/vk/oauth/callback
NCNET_PUBLIC_URL=https://example.com
CBPR_SECURE_COOKIES=1
```

Секреты не сохраняются в SQLite, frontend или Git. Без этих переменных NC//NET работает полностью, а VK outbox остаётся в состоянии pending.

Проверка правил и каталога:

```bash
python3 -m unittest discover -s tests -v
node --check app/static/creation-data.js
node --check app/static/ncnet.js
node --check app/static/app.js
```

## Установка на Ubuntu Server (сайт работает постоянно)

Нужен только сервер с Ubuntu и доступ по SSH. Скопируй команды по шагам:

```bash
# 1. Подключись к серверу (с своего компьютера):
ssh root@IP_СЕРВЕРА            # например: ssh root@95.123.45.67

# 2. Обнови систему и поставь git + python:
apt update && apt install -y git python3

# 3. Забери код проекта:
git clone https://github.com/a3sthex/CBPR-helper.git
cd CBPR-helper

# 4. Запусти установщик — он сам создаст службу с автозапуском:
bash deploy/install.sh          # можно свой порт: bash deploy/install.sh 8080
```

После установки сайт живёт по адресу `http://IP_СЕРВЕРА:8000` и **переживает перезагрузку сервера**.

Полезные команды:

```bash
journalctl -u cbpr -f                # смотреть логи вживую
systemctl restart cbpr               # перезапустить сайт
cd CBPR-helper && git pull && systemctl restart cbpr   # обновить до новой версии
```

Если сайт не открывается снаружи — открой порт 8000 в панели хостинга (группа безопасности) и/или `ufw allow 8000/tcp`.

**Резервная копия** (все аккаунты, персонажи и посты лежат в одном файле `app/data/cbpr.db`):

```bash
systemctl stop cbpr
cp CBPR-helper/app/data/cbpr.db ~/cbpr-backup-$(date +%F).db
tar -czf ~/cbpr-uploads-$(date +%F).tar.gz -C CBPR-helper/app/data uploads 2>/dev/null || true
systemctl start cbpr
```

### Свой домен и HTTPS (по желанию)

```bash
apt install -y nginx                # nginx на порту 80 проксирует сайт
cp deploy/nginx-cbpr.conf /etc/nginx/sites-available/cbpr
ln -sf /etc/nginx/sites-available/cbpr /etc/nginx/sites-enabled/cbpr
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# HTTPS, когда домен привязан A-записью к IP сервера:
apt install -y certbot python3-certbot-nginx
certbot --nginx -d твой-домен.ru
```

## Используемые правила

Правила создания сверены с `Spes Desperata`, **Cyberpunk RED Corebook** (Lifepath стр. 43–69, Complete Package стр. 78–104, броня стр. 96), **CEMK Rule Book** (Lifepath стр. 19–24, правила 2070-х и Neuroport стр. 25+) и описаниями предметов из **Black Chrome/Data Pool**.

- Создание: все характеристики начинают с 5, но итог должен содержать ровно **62 очка** (каждая 2–8); навыки — ровно **86 очков** (минимум 2 в 13 обязательных, максимум 6, ×2-навыки стоят 2 очка). Language, Local Expert, Martial Arts, Science и Play Instrument используют покупаемый parent-pool, распределяемый между специализациями; культурный язык 4 бесплатен, Streetslang 2 оплачивается. Старт: **2550€$** на снаряжение + **800€$** на Fashion/Fashionware. Бесплатный и платный Neuroport взаимоисключающие.
- Draft мастера версионирован и автоматически хранится в `localStorage` отдельно для каждого пользователя до успешного создания или подтверждённого полного сброса. Draft v2 автоматически мигрирует на шестишаговую v3-схему; старые персонажи и старые Lifepath-значения остаются читаемыми.
- Интерфейс по умолчанию английский, переключатель `EN/RU` сохраняется локально; гайды намеренно остаются на русском. Новые персонажи по умолчанию приватные.
- Каталог содержит нормализованные `mechanics`, `requirements`, `capacity` и совместимость: Damage notation/dice/average, ROF, Hands, Magazine, ammo links, Cyberware foundations, paired hosts и Option Slots. Клиентские ограничения повторно проверяются сервером.
- Character Portrait обрабатывается в браузере (crop/zoom/rotate), хранится вне Git в `app/data/uploads/` и наследует приватность персонажа. Неиспользованные draft uploads очищаются через 7 дней.
- После создания доступны расход LUCK, HP, Armor/Shield, магазины и reserve ammo, Skill/Attack/Damage rolls, immutable IP ledger, parent-pool progression, свободное перераспределение children и multiclass с active Role Rank 4 gate.
- Appearance Settings содержат presets и Custom Theme для всех основных цветов, font scale, density, glow и reduced motion; сервер хранит настройки профиля, localStorage используется как fallback.
- HP = `10 + 5×⌈(BODY+WILL)/2⌉`; серьёзная рана — половина HP (вверх); смертельное ранение — HP < 1 (−4 ко всем действиям, −6 MOVE, спасброски смерти); спасбросок смерти = `1d10 ≤ BODY − штраф` (10 — всегда провал).
- Текущая человечность после установки = `EMP×10 − Σ HL`; максимум человечности = `EMP×10 − 2 за каждый обычный хром − 4 за Borgware`. Fashionware и бесплатный стартовый Neuroport CEMK исключены; текущий EMP = человечность ÷ 10 (вниз).
- Критические травмы: 2+ шестёрки на кубах урона = 2d6 по таблице + 5 HP (броня не снижает).
- Броня покупается отдельно для головы и тела; SP слоёв не складывается — действует наибольший. Все слои локации абляируются вместе, а самый строгий штраф к REF/DEX/MOVE применяется один раз.
- Урон: если урон > SP — броня пробита и абляируется на 1, иначе броня держит.
- Ближний бой: SP цели делится на 2 (вверх).
- Автоогонь: урон = `2d6 × (бросок − DV)`, максимум множителя ×3 (SMG) / ×4 (винтовки, пулемёты).

*Неофициальный фанатский инструмент. Cyberpunk RED © R. Talsorian Games.*

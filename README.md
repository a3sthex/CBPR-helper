# NC//NET

Иммерсивная сеть Найт-Сити 2070-х для общих кампаний по **Cyberpunk RED / CEMK**. ГМы размещают контракты от лица внутриигровых персон, игроки используют Character Dossiers, а сыгранные события превращаются в City Feed. Каталог предметов собирается из `Data Pool.xlsx`, стартовый ростер — из листа `Folio`.

Полная архитектура, модель данных и миграции описаны в [`docs/ncnet-redesign.md`](docs/ncnet-redesign.md), а проверенные карты/правила и страницы источников — в [`docs/ncnet-sources.md`](docs/ncnet-sources.md). NC//NET обновляет существующую базу без reset.

## Что внутри

| Раздел | Описание |
| --- | --- |
| 🛰️ **Network Shell** | Плотный diegetic HUD с desktop left rail, system telemetry, Active Dossier, command palette, явным NETWORK/GM OPS mode switch и mobile bottom navigation. |
| 🧬 **Dossiers** | Шестишаговый мастер и интерактивный официальный-inspired Character Sheet: Portrait upload/crop, Corebook role art, EN/RU, persistent draft, Hybrid Lifepath, 62/86, parent-pools, Shopping compatibility, concrete Cyberware hosts/paired slots, left/right sides, clinic audit, Quick Change, curated option payloads, tracked Integrated Cyberweapons, permanent generic Popup bindings, concrete Armor/Shield hosts, Armor SP +1 Tech Upgrades, manual/Jeeves/paid Armor Repair, Popup Shield replacement, Therapy и Humanity-safe Install/Uninstall, HP/LUCK/Armor/ammo trackers, dice rolls, IP progression, multiclass, JSON/Print и read-only архив с сохранением NC//NET history. |
| 👤 **Profile** | Account avatar с квадратной crop-обработкой, privacy display name/avatar, Appearance, audio volume, VK linking и управляемые Admin роли. |
| ♿ **Accessibility** | Skip link, видимый keyboard focus, Enter/Space activation для Contracts/Feed/Personas/map markers, modal focus trap/restore, ARIA live notifications и reduced-motion support. |
| 📖 **Гайды** | Мини-гайды из «Spes Desperata»: пошаговое создание персонажа (роли, 62 очка статов, 86 очков навыков, стартовая закупка), боёвка FNFF (действия, DV-таблицы, крит. травмы, укрытия, транспорт) и нетраннинг (СЕТевые действия, Interface-способности). |
| 📋 **Crew Registry** | Все публичные персонажи всех игроков. При старте импортируется ростер вашей партии из Folio (13 эджраннеров). |
| 🕶️ **Чёрный рынок** | Шесть продавцов-Personas с отдельным ежедневным ассортиментом, описаниями, фильтрами, сортировкой и уличными ценами ±50%; скупка хлама за 50% и выплаты GM. Купить можно только реально выставленный товар. |
| 📚 **Справочник** | Reference-only база на 1092 предмета в 14 категориях: нормализованные mechanics, EN/RU labels, описания, Armor locations и ссылки на книги (`CP:R 341`, `BC`, `CEMK`). Справочник не является универсальным магазином. |
| 🎲 **Quick Reference** | Damage/SP, Critical Injuries, Autofire, Death Saves, Range DV и General Difficulty с указанием книг и страниц; инструменты можно использовать как справочник или Resolver. |
| ◈ **Personas / Storylines** | Private/Shared/System персоны, общий audit log, GM-соавторы сюжетных линий и публичная/закрытая хронология. |
| 📡 **City Feed** | Шесть форматов, прямые Character-публикации, optional images с preset/custom crop, отображение полного соотношения без обрезки и полноразмерный lightbox, event/publication time, metadata, replies, revisions, moderation и скрытая GM truth. |
| 📞 **Contracts** | Theme-aware карта с district/subdistrict markers; optional covers с preset/custom resolution crop, полным соотношением без обрезки и lightbox; Persona-роли, public/classified briefing, rewards, запись, waitlist, исторический Crew и Aftermath. |
| ⚙️ **GM OPS** | Поиск и фильтры для Sessions/NPC Templates/Storylines, scoped Session-роли Co-GM/Assistant/Rules Helper/Observer, стабильный initiative order, HP/SP/Shield/Ammo/LUCK/MOVE/Injuries controls, анонимные Pause/X-card Safety signals, Lines/Veils, activity log, private GM JSON export и настраиваемый Player View. |

## Запуск

Только Python 3.8+ из стандартной библиотеки, ничего ставить не нужно:

```bash
python3 app/server.py            # http://127.0.0.1:8000
python3 app/server.py --port 8080
python3 app/server.py --host 0.0.0.0  # только для изолированной dev-сети без production-данных
```

- `app/import_data.py` — пересборка `app/data/items.json` из `import/Data Pool.xlsx` (запускается автоматически, если файла нет);
- `app/data/cbpr.db` — SQLite в WAL-режиме, создаётся при первом старте (в git не хранится);
- критические операции Crew/Market/IP/Aftermath выполняются через `BEGIN IMMEDIATE` и откатываются целиком при ошибке;
- Dossier содержит `revision`: устаревшая вкладка не может молча перезаписать более новое сохранение;
- новый аккаунт всегда получает роль **Player**;
- пароль нового аккаунта должен содержать минимум 8 символов;
- регистрация по умолчанию требует invite-код, созданный в Admin Console;
- `CBPR_REGISTRATION_MODE=invite|open|closed` управляет режимом регистрации (`invite` по умолчанию);
- invite-коды хранятся только как SHA-256 hash, а исходный код показывается Admin один раз;
- в Profile можно сменить пароль, просмотреть активные сеансы, завершить отдельный сеанс или выйти везде;
- Admin может отключить аккаунт с обязательной причиной; все его сеансы сразу отзываются, действие попадает в Security Audit;
- **GM** и **Admin** назначаются только через Admin Console;
- перед первой выдачей прав существующий аккаунт явно указывается в `CBPR_ADMIN_USERS` и сервер перезапускается;
- альтернативный путь БД для smoke/tests задаётся через `CBPR_DB_PATH`.

Для самого первого аккаунта на новой базе временно запустите открытую регистрацию и одновременно укажите будущего Admin:

```bash
CBPR_REGISTRATION_MODE=open CBPR_ADMIN_USERS=operator python3 app/server.py
```

Зарегистрируйте `operator`, остановите сервер и запустите его снова без `CBPR_REGISTRATION_MODE=open`. При следующем старте `CBPR_ADMIN_USERS` назначит существующему `operator` роль Admin. После этого новые приглашения создаются в Admin Console.

Для systemd переменные задаются в drop-in конфигурации службы, после чего сервис перезапускается. Не добавляйте invite-коды, пароли или токены в Git.

Опциональная интеграция с общей беседой VK и OAuth-привязка пользователей включаются только серверными переменными:

```bash
VK_COMMUNITY_TOKEN=...          # токен сообщества
VK_PEER_ID=...                  # peer_id общей беседы
VK_CLIENT_ID=...                # VK OAuth app
VK_CLIENT_SECRET=...
VK_REDIRECT_URI=https://example.com/api/vk/oauth/callback
NCNET_PUBLIC_URL=https://example.com
CBPR_SECURE_COOKIES=1           # install.sh включает автоматически
CBPR_TRUST_PROXY=1              # только за доверенным nginx/Cloudflare proxy
```

Секреты не сохраняются в SQLite, frontend или Git. Без VK-переменных NC//NET работает полностью, а VK outbox остаётся в состоянии pending. `CBPR_TRUST_PROXY=1` разрешает использовать `CF-Connecting-IP`/`X-Forwarded-For` для rate limits и session history; включайте его только когда backend слушает loopback и запросы приходят через ваш доверенный reverse proxy. В LAN-режиме с прямым доступом к Python-серверу оставляйте значение выключенным.

Проверка правил и каталога:

```bash
python3 -m unittest discover -s tests -v
node --check app/static/creation-data.js
node --check app/static/ncnet.js
node --check app/static/app.js
```

Готовый workflow для CI лежит в `docs/ci-tests-workflow.yml` — чтобы включить GitHub Actions, скопируйте его в `.github/workflows/tests.yml` через веб-интерфейс GitHub (боту не хватает scope `workflows` для такого push).

## Книги-источники и извлечение текста

PDF правил лежат в корне репозитория как Git LFS-указатели (сами файлы — в LFS-хранилище). Для работы с их содержимым:

- `tools/extract_books.py` — извлекает весь текст постранично (`extracted/text/<книга>.md` + сводный `extracted/ALL_TEXT.md`), встроенные картинки (`extracted/images/<книга>/`, в git не попадают) и опционально OCR страниц без текстового слоя (`--ocr`, нужен `rapidocr-onnxruntime`);
- `tools/merge_books.py` — склеивает книги, разрезанные онлайн-сплиттером на части `*-страницы-N.pdf` в `uploads/` (обход лимита веб-загрузки GitHub в 25 МБ);
- `tools/classify_books.py` — разбивает все страницы по категориям (правила/бой/нетраннинг/лор/предметы/…) по карте глав оглавления; отчёт — `extracted/analysis/CATEGORIES.md`, постраничный индекс — `page_index.csv` + `categories.json`;
- `uploads/` — зона ручной заливки новых книг через веб-интерфейс GitHub (см. `uploads/README.md`; папка исключена из LFS в `.gitattributes`).

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

После установки backend **переживает перезагрузку сервера**, но слушает только
`127.0.0.1:8000` и устанавливает только Secure session cookies. Порт приложения не
следует открывать наружу: публичный доступ настраивается через домен и HTTPS reverse
proxy по инструкции ниже.

Полезные команды:

```bash
journalctl -u cbpr -f                # смотреть логи вживую
systemctl restart cbpr               # перезапустить сайт
cd CBPR-helper && git pull && systemctl restart cbpr   # обновить до новой версии
```

Не добавляйте порт 8000 в `ufw` или security group: снаружи должны быть доступны только 80/443 для nginx.

### Резервные копии

`install.sh` устанавливает `cbpr-backup.timer`: каждый день около 04:00 он создаёт online SQLite snapshot, добавляет uploads и checksummed manifest в `app/data/backups/`. Останавливать сайт не требуется. По умолчанию хранятся последние 14 bundle-файлов.

```bash
systemctl status cbpr-backup.timer          # расписание
systemctl start cbpr-backup.service         # создать backup сейчас
journalctl -u cbpr-backup.service -n 50     # результат последнего запуска
python3 app/backup.py list                   # список копий
python3 app/backup.py verify ИМЯ.tar.gz      # integrity + SHA-256 каждого файла
```

Admin также может создавать, проверять и скачивать bundle в Admin Console. Bundle содержит приватные данные, password hashes и media — храните его как секрет. Для другой директории/retention используются `CBPR_BACKUP_DIR` и `CBPR_BACKUP_RETENTION`. Пошаговое безопасное восстановление и перенос на VPS описаны в [`docs/backup-restore.md`](docs/backup-restore.md).

Ручное создание без systemd:

```bash
python3 app/backup.py create --retention 14 --reason manual
```

### Домен и HTTPS (обязательно для production)

1. Привяжите A/AAAA-запись домена к серверу.
2. Остановите nginx и получите сертификат (замените `ncnet.example.ru`):

```bash
apt install -y nginx certbot
systemctl stop nginx
certbot certonly --standalone -d ncnet.example.ru
```

3. Во всех местах `deploy/nginx-cbpr.conf` замените `YOUR_DOMAIN` на домен, затем включите конфигурацию:

```bash
cp deploy/nginx-cbpr.conf /etc/nginx/sites-available/cbpr
sed -i 's/YOUR_DOMAIN/ncnet.example.ru/g' /etc/nginx/sites-available/cbpr
ln -sf /etc/nginx/sites-available/cbpr /etc/nginx/sites-enabled/cbpr
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl enable --now nginx
```

Конфигурация перенаправляет HTTP на HTTPS, добавляет HSTS и проксирует запросы на
локальный Python backend. Так как сертификат получен через standalone challenge,
продлевайте его с освобождением порта 80:

```bash
certbot renew --pre-hook 'systemctl stop nginx' --post-hook 'systemctl start nginx'
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

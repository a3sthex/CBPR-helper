# Архитектура NC//NET (после декомпозиции P1, 28.08.2026)

## Слои и направление зависимостей

```
                ┌──────────────────────────────────────┐
   HTTP         │ server.py: Handler (dispatch ядро)   │
   слой         │  + миксины: account/feed/personas/   │
                │   world/sessions/characters/admin/   │
                │   misc (+ MediaHandlers из media.py) │
                └──────────────┬───────────────────────┘
                               │ только вниз
   домены     campaign · locations · memorial · crew · night_market
              recap · inventory · charbuild · mod_engine
                               │
   базы          rules · catalog · db · auth · httpkit
                               │
   фундамент                 core
```

Запрещены рёбра в обратную сторону. Единственное допущение — `bind()`/`_LATE`
(вызвано дисциплиной анти-циклов и зафиксировано в аудите):

- `night_market` ← `crew_reputation_map` (crew импортирует рынок — цикл отброшен);
- `charbuild` ↔ `inventory` (взаимные ссылки по цепочке валидации);
- `catalog`/`rules`/`mod_engine` ← `catalog_item_id_for_entry` (owner — inventory).

## Контракты кода

1. **Модули чисты**: каждый импортирует только то, что использует сам
   (мёртвые re-export'ы в server.py удалены; 268 имён было шумом эпохи монолита).
2. **db.py** — единственный владелец `DB_PATH`/`BACKUP_DIR` глобалов на запуске;
   core считает их из env при импорте.
3. **Тест-монопатчи** — на модуль-владелец имени (`importlib.import_module('<mod>')`),
   не на `server.<name>`; `server.*` остаётся видимым только для ROUTES/ядра.
4. **Некоторые серверные имена осознанно остаются** (тесты их патчат):
   актуальный список проверяется `grep -ho 'server\.\w*' tests/*.py | sort -u`.

## Безопасность/запуск

- auth: PBKDF2-HMAC-SHA256 (120k итераций), токены sessions, HttpOnly SameSite=Lax.
- `atomic_endpoint` (httpkit): BEGIN IMMEDIATE / COMMIT / rollback по исключению.
- Rate limits — в db (SQLite, без внешних стореджей).
- Весь рантайм-стейт: `app/data/` (WAL), бэкапы — `data/backups`.

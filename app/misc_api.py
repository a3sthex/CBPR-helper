"""Прочие API NC//NET: покупки/продажи, каталог, ночной рынок, расчётная ведомость, календарь, фиксер, meta/stats/roster, импорт PDF (миксин Handler; P1, логика не менялась)."""


import base64
import copy
import json
import math
import time

from auth import registration_mode
from catalog import (ITEM_MODIFICATION_FIELDS, catalog, catalog_interaction_data,
                     catalog_item_payload, item_by_id, item_effect_coverage,
                     load_effect_rules)
from charbuild import ensure_progression
from core import (BASE, CHARACTER_VISIBILITY_DEFAULTS, MOSCOW, STATS, ApiError,
                  parse_json_object, user_is_gm)
from crew import active_loan_for_instance
from httpkit import atomic_endpoint, q1
from inventory import (catalog_item_id_for_entry, ensure_character_item_instances,
                       item_entry_stackable, new_item_instance_id,
                       persist_character_item_instances)
from mod_engine import ammo_pack_size, ammo_rounds
from night_market import (NIGHT_MARKET_VENDORS, ensure_market_stock,
                          market_permanent_rows, market_stock_rows, night_market,
                          nm_day, nm_price_map)
from recap import record_character_changes
from rules import (CRIT_BODY, CRIT_BODY_EN, CRIT_HEAD, CRIT_HEAD_EN, GENERAL_DV,
                   MUST_SKILLS, ROLE_DESC, ROLE_DESC_EN, ROLE_RU, ROLES,
                   RULE_SOURCES, SKILL_MAX_CREATION, SKILL_POINTS, SKILLS,
                   START_CASH_FASHION, START_CASH_GEAR, STAT_POINTS,
                   WOUND_STATES, WOUND_STATES_EN, _num)


class MiscMixin:

    @atomic_endpoint
    def api_buy(self, conn, qs, m, body):
        u = self.require_user(conn)
        row = self.get_char(conn, body.get('char_id'))
        if row['owner_id'] != u['id']:
            raise ApiError(403, 'Это не ваш персонаж')
        if parse_json_object(row['data']).get('archived'):
            raise ApiError(409, 'Архивное досье доступно только для чтения')
        before_data = json.loads(row['data'])
        data = copy.deepcopy(before_data)
        ensure_character_item_instances(data)
        ensure_progression(data)
        cart = body.get('items') or []
        if not cart or not isinstance(cart, list):
            raise ApiError(400, 'Пустая корзина')
        nm = nm_price_map()
        ensure_market_stock(conn)
        day = nm_day()
        stock_rows = market_stock_rows(conn, day)
        pm = {item_id: item_by_id(item_id)['price']
              for item_ids in market_permanent_rows(conn).values()
              for item_id in item_ids if item_by_id(item_id)}
        total = 0.0
        bought = []
        wanted = {}
        for entry in cart[:50]:
            it = item_by_id(str(entry.get('id') or ''))
            if not it or not it.get('price'):
                continue
            qty = max(1, min(99, int(entry.get('qty') or 1)))
            is_permanent = bool(entry.get('permanent')) and it['id'] in pm
            if entry.get('mode') != 'nm':
                raise ApiError(400, 'Покупка доступна только из текущего Night Market')
            if is_permanent:
                price = pm[it['id']]
            elif it['id'] in nm:
                price = nm[it['id']]
            else:
                raise ApiError(400, 'Покупка доступна только из текущего Night Market')
            if not is_permanent:
                wanted[it['id']] = wanted.get(it['id'], 0) + qty
            total += price * qty
            bought.append((it, qty, price))
        if not bought:
            raise ApiError(400, 'В корзине нет известных товаров')
        # Finite stock and reservations only apply to offers actually seeded today.
        for item_id, qty in wanted.items():
            state_row = stock_rows.get(item_id)
            if state_row is None:
                continue
            name = item_by_id(item_id)['name']
            remaining = max(0, int(state_row['stock_remaining'] or 0))
            if remaining <= 0:
                raise ApiError(400, f'Распродано: {name}')
            if (state_row.get('reserved_character_id') and
                    int(state_row['reserved_character_id']) != int(row['id'])):
                raise ApiError(400, f'Зарезервировано для другого персонажа: {name}')
            if qty > remaining:
                raise ApiError(400, f'Недостаточно единиц: {name} (доступно {remaining})')
        cash = float(data.get('cash') or 0)
        if total > cash + 1e-9:
            raise ApiError(400, f'Не хватает €$: нужно {total:,.0f}, есть {cash:,.0f}')
        inv = data.setdefault('inventory', [])
        chrome = data.setdefault('cyberware', [])
        purchased_weapon_ids = []
        for it, qty, price in bought:
            target_bucket = chrome if it['cat'] == 'cyberware' else inv
            owned = {
                'key': it['id'], 'catalog_item_id': it['id'], 'cat': it['cat'],
                'name': it['name'], 'price': price, 'qty': 1, 'state': 'carried',
                'damage': it.get('damage'), 'sp': it.get('sp'), 'hl': it.get('hl'),
                'fields': copy.deepcopy(it.get('fields') or {}),
                'mechanics': copy.deepcopy(it.get('mechanics') or {}),
                'source': it.get('source'),
            }
            owned.update(catalog_interaction_data(it))
            owned.update({key: copy.deepcopy(it[key]) for key in ITEM_MODIFICATION_FIELDS if key in it})
            coverage = item_effect_coverage(it.get('id'))
            if coverage:
                owned['effect_coverage'] = coverage
            if item_entry_stackable(owned):
                found = next((entry for entry in target_bucket if isinstance(entry, dict) and
                              catalog_item_id_for_entry(entry) == it['id'] and
                              item_entry_stackable(entry) and
                              str(entry.get('state') or 'carried') == 'carried' and
                              not entry.get('custom_name')), None)
                if found:
                    current_rounds = ammo_rounds(found) if it['cat'] == 'ammo' else 0
                    found['qty'] = int(found.get('qty') or 1) + qty
                    if it['cat'] == 'ammo':
                        found['ammo_rounds'] = current_rounds + qty * ammo_pack_size(found)
                else:
                    owned['instance_id'] = new_item_instance_id()
                    owned['qty'] = qty
                    if it['cat'] == 'ammo':
                        owned['ammo_rounds'] = qty * ammo_pack_size(owned)
                    target_bucket.append(owned)
            else:
                if len(inv) + len(chrome) + qty > 500:
                    raise ApiError(400, 'Инвентарь не может содержать больше 500 экземпляров')
                for _ in range(qty):
                    instance = copy.deepcopy(owned)
                    instance['instance_id'] = new_item_instance_id()
                    target_bucket.append(instance)
                    if it['cat'] == 'guns':
                        purchased_weapon_ids.append(instance['instance_id'])
        for item_id, qty in wanted.items():
            state_row = stock_rows.get(item_id)
            if state_row is not None:
                conn.execute(
                    'UPDATE market_stock SET stock_remaining=stock_remaining-?,updated=? '
                    'WHERE market_day=? AND item_id=?',
                    (qty, time.time(), day, item_id))
        data['cash'] = round(cash - total, 2)
        ensure_progression(data)
        for instance_id in purchased_weapon_ids:
            state = (data.get('weapon_state') or {}).get(instance_id)
            if state:
                state['magazine'] = 0
        persist_character_item_instances(
            conn, row['id'], data, 'night_market', source_ref=nm_day())
        record_character_changes(conn, row['id'], u['id'], before_data, data,
                                 'Night Market purchase')
        conn.execute('UPDATE characters SET data=?,updated=?,revision=revision+1 WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), time.time(), row['id']))
        conn.commit()
        receipt = [{'name': it['name'], 'qty': qty, 'price': price}
                   for it, qty, price in bought]
        self.send_json({'ok': True, 'total': round(total, 2), 'cash': data['cash'],
                        'receipt': receipt})

    @atomic_endpoint
    def api_sell(self, conn, qs, m, body):
        u = self.require_user(conn)
        row = self.get_char(conn, body.get('char_id'))
        if row['owner_id'] != u['id']:
            raise ApiError(403, 'Это не ваш персонаж')
        if parse_json_object(row['data']).get('archived'):
            raise ApiError(409, 'Архивное досье доступно только для чтения')
        before_data = json.loads(row['data'])
        data = copy.deepcopy(before_data)
        ensure_character_item_instances(data)
        ensure_progression(data)
        key = str(body.get('key') or '')
        instance_id = str(body.get('instance_id') or '').lower()
        try:
            qty = max(1, int(body.get('qty') or 1))
        except (TypeError, ValueError):
            raise ApiError(400, 'Некорректное количество')
        inv = data.get('inventory') or []
        chrome = data.get('cyberware') or []
        bucket = inv
        index = next((position for position, entry in enumerate(bucket)
                      if isinstance(entry, dict) and instance_id and
                      entry.get('instance_id') == instance_id), None)
        if index is None:
            index = next((position for position, entry in enumerate(bucket)
                          if isinstance(entry, dict) and key and entry.get('key') == key), None)
        if index is None:
            bucket = chrome
            index = next((position for position, entry in enumerate(bucket)
                          if isinstance(entry, dict) and instance_id and
                          entry.get('instance_id') == instance_id), None)
        if index is None:
            index = next((position for position, entry in enumerate(bucket)
                          if isinstance(entry, dict) and key and entry.get('key') == key), None)
        if index is None:
            raise ApiError(404, 'Предмет не найден в инвентаре')
        ent = bucket[index]
        if ent.get('instance_id'):
            loan = active_loan_for_instance(conn, ent.get('instance_id'))
            if loan and loan['borrower_character_id'] == row['id']:
                raise ApiError(409, 'Предмет взят в долг — сначала верните владельцу')
        linked = conn.execute(
            'SELECT 1 FROM item_modifications WHERE character_id=? AND active=1 '
            'AND (host_instance_id=? OR upgrade_instance_id=?)',
            (row['id'], ent.get('instance_id'), ent.get('instance_id'))).fetchone()
        if linked:
            raise ApiError(409, 'Сначала снимите установленные модификации')
        cyber_states = data.get('cyberware_state') if isinstance(
            data.get('cyberware_state'), dict) else {}
        ent_cyber_state = cyber_states.get(ent.get('instance_id'))
        if (ent.get('installed_cyberware_instance_id') or
                (isinstance(ent_cyber_state, dict) and
                 ent_cyber_state.get('bound_weapon_instance_id'))):
            raise ApiError(409, 'Permanent Popup Weapon binding нельзя продать отдельно')
        if (ent.get('installed_popup_shield_instance_id') or
                (isinstance(ent_cyber_state, dict) and
                 isinstance(ent_cyber_state.get('popup_shield'), dict) and
                 ent_cyber_state['popup_shield'].get('shield_instance_id'))):
            raise ApiError(409, 'Сначала извлеките concrete Popup Shield')
        armor_tech = data.get('armor_tech_state') if isinstance(
            data.get('armor_tech_state'), dict) else {}
        if isinstance(armor_tech.get(ent.get('instance_id')), dict):
            raise ApiError(409, 'Permanent Armor Tech Upgrade нельзя продать отдельно')
        if str(ent.get('state') or 'carried') in ('equipped', 'installed'):
            raise ApiError(409, 'Сначала снимите или извлеките предмет')
        ammo_units_before = ammo_rounds(ent) if ent.get('cat') == 'ammo' else None
        if ammo_units_before is not None:
            full_packs = ammo_units_before // ammo_pack_size(ent)
            if full_packs <= 0:
                raise ApiError(409, 'Частично использованный ammo stack нельзя продать')
            qty = min(qty, int(ent.get('qty') or 1), full_packs)
        else:
            qty = min(qty, int(ent.get('qty') or 1))
        back = round(float(ent.get('price') or 0) * 0.5 * qty, 2)
        ent['qty'] = int(ent.get('qty') or 1) - qty
        if ammo_units_before is not None:
            ent['ammo_rounds'] = ammo_units_before - qty * ammo_pack_size(ent)
            ent['qty'] = math.ceil(ent['ammo_rounds'] / ammo_pack_size(ent)) \
                if ent['ammo_rounds'] > 0 else 0
        if ent['qty'] <= 0:
            bucket.pop(index)
            (data.get('weapon_state') or {}).pop(str(ent.get('instance_id') or ''), None)
        data['cash'] = round(float(data.get('cash') or 0) + back, 2)
        persist_character_item_instances(
            conn, row['id'], data, 'night_market_resale', prune=True)
        record_character_changes(conn, row['id'], u['id'], before_data, data,
                                 f'Night Market resale: {ent.get("name") or key}')
        conn.execute('UPDATE characters SET data=?,updated=?,revision=revision+1 WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), time.time(), row['id']))
        conn.commit()
        self.send_json({'ok': True, 'cash': data['cash'], 'got': back,
                        'name': ent.get('name'), 'qty': qty,
                        'instance_id': ent.get('instance_id')})

    def api_item(self, conn, qs, m, body):
        it = item_by_id(m.group(1))
        if not it:
            raise ApiError(404, 'Предмет не найден')
        self.send_json(catalog_item_payload(it))

    def api_items(self, conn, qs, m, body):
        cat = catalog()
        q = (q1(qs.get('q')) or '').strip().lower()
        cat_id = q1(qs.get('cat'))
        try:
            limit = min(500, max(1, int(q1(qs.get('limit'), '30'))))
            offset = max(0, int(q1(qs.get('offset'), '0')))
        except ValueError:
            limit, offset = 30, 0
        items = cat['items']
        if cat_id:
            items = [i for i in items if i['cat'] == cat_id]
        if q:
            terms = q.split()
            items = [i for i in items if all(t in i['search'] for t in terms)]
        total = len(items)
        items = [catalog_item_payload(item) for item in items[offset:offset + limit]]
        self.send_json({'total': total, 'items': items, 'offset': offset, 'limit': limit})

    def api_nightmarket(self, conn, qs, m, body):
        ensure_market_stock(conn)
        payload = night_market(conn=conn)
        persona_rows = conn.execute(
            "SELECT id,handle FROM personas WHERE handle IN (%s)" %
            ','.join('?' for _ in NIGHT_MARKET_VENDORS),
            tuple(vendor['handle'] for vendor in NIGHT_MARKET_VENDORS)).fetchall()
        persona_ids = {row['handle']: row['id'] for row in persona_rows}
        for vendor in payload['vendors']:
            vendor['persona_id'] = persona_ids.get(vendor.get('handle'))
        self.send_json(payload)

    @atomic_endpoint
    def api_nightmarket_reserve(self, conn, qs, m, body):
        user = self.require_gm(conn)
        allowed = {'item_id', 'character_id', 'note'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Market reserve содержит неподдерживаемые поля')
        item_id = str((body or {}).get('item_id') or '').strip()
        character_id = _num((body or {}).get('character_id'))
        note = str((body or {}).get('note') or '').strip()[:200]
        if not item_by_id(item_id):
            raise ApiError(400, 'Неизвестный предмет Night Market')
        ensure_market_stock(conn)
        day = nm_day()
        state_row = conn.execute(
            'SELECT * FROM market_stock WHERE market_day=? AND item_id=?',
            (day, item_id)).fetchone()
        if not state_row:
            raise ApiError(400, 'Предмет не в текущем Night Market')
        if character_id:
            target = self.get_char(conn, character_id)
            if parse_json_object(target['data']).get('archived'):
                raise ApiError(409, 'Досье зарезервированного персонажа заархивировано')
            conn.execute(
                'UPDATE market_stock SET reserved_character_id=?,reserved_note=?,updated=? '
                'WHERE market_day=? AND item_id=?',
                (target['id'], note, time.time(), day, item_id))
        else:
            conn.execute(
                'UPDATE market_stock SET reserved_character_id=NULL,reserved_note=?,updated=? '
                'WHERE market_day=? AND item_id=?',
                (note, time.time(), day, item_id))
        conn.commit()
        self.send_json({'ok': True, 'item_id': item_id,
                        'reserved_character_id': character_id})

    @atomic_endpoint
    def api_payroll(self, conn, qs, m, body):
        u = self.require_gm(conn)
        row = self.get_char(conn, body.get('char_id'))
        if parse_json_object(row['data']).get('archived'):
            raise ApiError(409, 'Архивное досье доступно только для чтения')
        try:
            amount = float(body.get('amount') or 0)
        except (TypeError, ValueError):
            raise ApiError(400, 'Некорректная сумма')
        if not math.isfinite(amount) or abs(amount) > 1e7:
            raise ApiError(400, 'Слишком большая сумма')
        before_data = json.loads(row['data'])
        data = json.loads(row['data'])
        data['cash'] = max(0.0, round(float(data.get('cash') or 0) + amount, 2))
        record_character_changes(conn, row['id'], u['id'], before_data, data,
                                 str((body or {}).get('reason') or 'GM payout'))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=revision+1 WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), time.time(), row['id']))
        conn.commit()
        self.send_json({'ok': True, 'cash': data['cash'], 'by': u['display_name']})

    def api_calendar_ics(self, conn, qs, m, body):
        user = self.current_user(conn)
        contracts = conn.execute(
            'SELECT id,title,district_id,scheduled_at,crew_capacity FROM contracts '
            "WHERE status IN ('open','crew_full','in_progress') AND scheduled_at IS NOT NULL "
            'ORDER BY scheduled_at').fetchall()
        lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//NC//NET//Cyberpunk RED//EN',
                 'CALSCALE:GREGORIAN', 'X-WR-CALNAME:NC//NET Contracts']
        for c in contracts:
            if not c['scheduled_at']:
                continue
            dt = datetime.fromtimestamp(c['scheduled_at'], tz=MOSCOW)
            dt_end = dt + timedelta(hours=3)
            lines.extend([
                'BEGIN:VEVENT',
                f'UID:contract-{c["id"]}@ncnet',
                f'DTSTAMP:{dt.strftime("%Y%m%dT%H%M%S")}',
                f'DTSTART:{dt.strftime("%Y%m%dT%H%M%S")}',
                f'DTEND:{dt_end.strftime("%Y%m%dT%H%M%S")}',
                f'SUMMARY:{str(c["title"] or "Contract")[:100]}',
                f'DESCRIPTION:NC//NET Contract #{c["id"]}',
                'END:VEVENT',
            ])
        lines.append('END:VCALENDAR')
        ics = '\r\n'.join(lines)
        body_bytes = ics.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/calendar; charset=utf-8')
        self.send_header('Content-Disposition', 'attachment; filename="ncnet-contracts.ics"')
        self.send_header('Content-Length', str(len(body_bytes)))
        self.send_security_headers()
        self.end_headers()
        self.wfile.write(body_bytes)

    @atomic_endpoint
    def api_fixer_request_create(self, conn, qs, m, body):
        user = self.require_user(conn)
        allowed = {'char_id', 'item_id', 'item_name', 'note'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Fixer request содержит неподдерживаемые поля')
        row = self.get_char(conn, (body or {}).get('char_id'))
        if row['owner_id'] != user['id'] and not user_is_gm(user):
            raise ApiError(403, 'Это не ваш персонаж')
        if parse_json_object(row['data']).get('archived'):
            raise ApiError(409, 'Архивное досье доступно только для чтения')
        item_id = str((body or {}).get('item_id') or '').strip()
        item_name = str((body or {}).get('item_name') or '').strip()[:160]
        note = str((body or {}).get('note') or '').strip()[:1000]
        if not item_id and len(item_name) < 2:
            raise ApiError(400, 'Укажите предмет или название запроса')
        if item_id and not item_by_id(item_id):
            raise ApiError(400, 'Неизвестный предмет для запроса')
        if item_id:
            item_name = item_by_id(item_id)['name']
        now = time.time()
        cur = conn.execute(
            'INSERT INTO fixer_requests(character_id,requested_by,item_id,item_name,'
            'note,status,created,updated) VALUES(?,?,?,?,?,?,?,?)',
            (row['id'], user['id'], item_id or None, item_name, note, 'pending', now, now))
        conn.commit()
        self.send_json({'ok': True, 'request_id': cur.lastrowid}, status=201)

    @atomic_endpoint
    def api_fixer_request_resolve(self, conn, qs, m, body):
        user = self.require_gm(conn)
        request = conn.execute('SELECT * FROM fixer_requests WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not request:
            raise ApiError(404, 'Запрос Fixer не найден')
        if request['status'] != 'pending':
            raise ApiError(409, 'Запрос Fixer уже обработан')
        action = str((body or {}).get('action') or '').strip().lower()
        if action not in ('fulfill', 'decline'):
            raise ApiError(400, 'Fixer resolve action: fulfill/decline')
        note = str((body or {}).get('note') or '').strip()[:1000]
        now = time.time()
        if action == 'decline':
            conn.execute('UPDATE fixer_requests SET status=?,resolved_by=?,resolved_at=?,'
                         'resolution_note=?,updated=? WHERE id=?',
                         ('declined', user['id'], now, note, now, request['id']))
            conn.commit()
            self.send_json({'ok': True, 'action': action})
            return
        row = self.get_char(conn, request['character_id'])
        if parse_json_object(row['data']).get('archived'):
            raise ApiError(409, 'Досье заказчика заархивировано')
        before = json.loads(row['data'])
        data = copy.deepcopy(before)
        ensure_character_item_instances(data)
        ensure_progression(data)
        try:
            qty = max(1, min(99, int((body or {}).get('qty') or 1)))
        except (TypeError, ValueError):
            raise ApiError(400, 'Некорректное количество')
        raw_price = (body or {}).get('price')
        item_id = str((body or {}).get('grant_item_id') or request['item_id'] or '').strip()
        if item_id and item_by_id(item_id):
            it = item_by_id(item_id)
            if raw_price is None:
                price = it.get('price') or 0
            else:
                try:
                    price = float(raw_price)
                except (TypeError, ValueError):
                    raise ApiError(400, 'Некорректная цена Fixer')
            price = max(0.0, min(9_999_999.0, price))
            if price * qty > float(data.get('cash') or 0) + 1e-9:
                raise ApiError(400, f'Не хватает €$: нужно {price * qty:,.0f}, '
                                    f'есть {float(data.get("cash") or 0):,.0f}')
            owned = {
                'key': it['id'], 'catalog_item_id': it['id'], 'cat': it['cat'],
                'name': it['name'], 'price': price, 'qty': 1, 'state': 'carried',
                'damage': it.get('damage'), 'sp': it.get('sp'), 'hl': it.get('hl'),
                'fields': copy.deepcopy(it.get('fields') or {}),
                'mechanics': copy.deepcopy(it.get('mechanics') or {}),
                'source': it.get('source'), 'acquisition_source': 'fixer',
            }
            owned.update(catalog_interaction_data(it))
            owned.update({key: copy.deepcopy(it[key]) for key in ITEM_MODIFICATION_FIELDS if key in it})
            coverage = item_effect_coverage(it.get('id'))
            if coverage:
                owned['effect_coverage'] = coverage
            inv = data.setdefault('inventory', [])
            if item_entry_stackable(owned):
                owned['instance_id'] = new_item_instance_id()
                owned['qty'] = qty
                if it['cat'] == 'ammo':
                    owned['ammo_rounds'] = qty * ammo_pack_size(owned)
                inv.append(owned)
            else:
                if len(inv) + qty > 500:
                    raise ApiError(400, 'Инвентарь не может содержать больше 500 экземпляров')
                for _ in range(qty):
                    instance = copy.deepcopy(owned)
                    instance['instance_id'] = new_item_instance_id()
                    inv.append(instance)
        else:
            name = str(request['item_name'] or (body or {}).get('item_name') or '').strip()[:120]
            if len(name) < 2:
                raise ApiError(400, 'Укажите название выдаваемого предмета')
            if raw_price is None:
                price = 0.0
            else:
                try:
                    price = float(raw_price)
                except (TypeError, ValueError):
                    raise ApiError(400, 'Некорректная цена Fixer')
            price = max(0.0, min(9_999_999.0, price))
            if price * qty > float(data.get('cash') or 0) + 1e-9:
                raise ApiError(400, f'Не хватает €$: нужно {price * qty:,.0f}, '
                                    f'есть {float(data.get("cash") or 0):,.0f}')
            owned = {
                'is_custom': True, 'key': 'custom', 'cat': 'custom', 'name': name,
                'custom_name': name, 'price': price, 'qty': qty, 'state': 'carried',
                'stackable': False, 'desc': '', 'source': 'Fixer Request',
                'manual_resolution_required': True, 'acquisition_source': 'fixer',
                'acquisition_note': str(note or '')[:160],
            }
            owned['instance_id'] = new_item_instance_id()
            data.setdefault('inventory', []).append(owned)
        data['cash'] = round(float(data.get('cash') or 0) - price * qty, 2)
        persist_character_item_instances(
            conn, row['id'], data, 'fixer_request', source_ref=f'fixer:{request["id"]}')
        record_character_changes(conn, row['id'], user['id'], before, data,
                                 f'Fixer request #{request["id"]}: {request["item_name"]}')
        conn.execute('UPDATE characters SET data=?,updated=?,revision=revision+1 WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now, row['id']))
        conn.execute('UPDATE fixer_requests SET status=?,resolved_by=?,resolved_at=?,'
                     'resolution_note=?,updated=? WHERE id=?',
                     ('fulfilled', user['id'], now, note, now, request['id']))
        conn.commit()
        self.send_json({'ok': True, 'action': action})

    def api_fixer_requests(self, conn, qs, m, body):
        user = self.require_user(conn)
        base = ('SELECT f.*,u.display_name requester,c.data character_data '
                'FROM fixer_requests f JOIN users u ON u.id=f.requested_by '
                'JOIN characters c ON c.id=f.character_id ')
        if user_is_gm(user):
            rows = conn.execute(
                base + "ORDER BY (f.status='pending') DESC,f.created DESC,f.id DESC LIMIT 300").fetchall()
        else:
            rows = conn.execute(
                base + 'WHERE f.requested_by=? '
                'ORDER BY f.created DESC,f.id DESC LIMIT 300', (user['id'],)).fetchall()
        payload = []
        for row in rows:
            item = dict(row)
            character_data = parse_json_object(item.pop('character_data'))
            item['character_name'] = character_data.get('handle') or 'Unknown Edgerunner'
            payload.append(item)
        self.send_json({'requests': payload})

    def api_meta(self, conn, qs, m, body):
        cat = catalog()
        is_ru = (self.headers.get('Accept-Language') or 'en').lower().startswith('ru')
        self.send_json({
            'stats': STATS, 'roles': ROLES, 'role_ru': ROLE_RU, 'role_desc': ROLE_DESC, 'role_desc_en': ROLE_DESC_EN,
            'skills': SKILLS, 'must_skills': MUST_SKILLS,
            'stat_points': STAT_POINTS, 'skill_points': SKILL_POINTS,
            'skill_max': SKILL_MAX_CREATION,
            'start_cash_gear': START_CASH_GEAR, 'start_cash_fashion': START_CASH_FASHION,
            'wound_states': WOUND_STATES if is_ru else WOUND_STATES_EN,
            'crit_body': CRIT_BODY if is_ru else CRIT_BODY_EN,
            'crit_head': CRIT_HEAD if is_ru else CRIT_HEAD_EN,
            'cats': cat['cats'],
            'range_table': cat['range_table'],
            'autofire_table': cat['autofire_table'],
            'general_dv': GENERAL_DV,
            'rule_sources': RULE_SOURCES,
            'effects_rules_version': load_effect_rules().get('rules_version'),
            'registration_mode': registration_mode(),
            'character_visibility_defaults': CHARACTER_VISIBILITY_DEFAULTS,
        })

    def api_stats(self, conn, qs, m, body):
        cat = catalog()
        c = conn.execute('SELECT COUNT(*) n FROM characters').fetchone()['n']
        u = conn.execute('SELECT COUNT(*) n FROM users WHERE id > 1').fetchone()['n']
        nw = conn.execute('SELECT COUNT(*) n FROM news').fetchone()['n']
        jb = conn.execute("SELECT COUNT(*) n FROM jobs WHERE status='open'").fetchone()['n']
        feed = conn.execute("SELECT COUNT(*) n FROM feed_posts WHERE status='published'").fetchone()['n']
        contracts = conn.execute("SELECT COUNT(*) n FROM contracts WHERE status IN ('open','crew_full')").fetchone()['n']
        self.send_json({'items': len(cat['items']), 'characters': c, 'users': u,
                        'news': nw, 'open_jobs': jb,
                        'feed_posts': feed, 'open_contracts': contracts})

    def api_roster(self, conn, qs, m, body):
        user = self.current_user(conn)
        privileged = user_is_gm(user)
        rows = conn.execute(
            'SELECT c.*,u.display_name owner,u.show_display_name owner_show_name '
            'FROM characters c JOIN users u ON u.id=c.owner_id WHERE c.public=1 '
            'ORDER BY u.id,c.id').fetchall()
        q = (q1(qs.get('q')) or '').strip().lower()
        out = []
        for row in rows:
            owner_name = row['owner'] if (privileged or row['owner_show_name']) else None
            payload = self.char_payload(row, owner_name, public_view=not privileged, conn=conn)
            data = payload['data']
            hay = ' '.join(filter(None, [data.get('handle'), data.get('role'),
                                         data.get('player'), owner_name])).lower()
            if q and q not in hay:
                continue
            out.append(payload)
        self.send_json({'characters': out})

    def api_pdf_import(self, conn, qs, m, body):
        """Parse a fillable PDF character sheet and return draft character data."""
        user = self.require_user(conn)
        pdf_b64 = str((body or {}).get('pdf') or '')
        if not pdf_b64:
            raise ApiError(400, 'PDF обязателен (base64)')
        try:
            pdf_bytes = base64.b64decode(pdf_b64)
        except Exception:
            raise ApiError(400, 'Некорректный base64')
        if len(pdf_bytes) < 100 or not pdf_bytes[:5].startswith(b'%PDF'):
            raise ApiError(400, 'Файл не является PDF')
        if len(pdf_bytes) > 5_000_000:
            raise ApiError(413, 'PDF слишком большой (макс 5 МБ)')
        try:
            sys.path.insert(0, BASE)
            import pdf_import
            result = pdf_import.import_pdf(pdf_bytes)
        except ValueError as e:
            raise ApiError(400, str(e))
        except Exception as e:
            raise ApiError(500, 'Ошибка парсинга PDF')
        self.send_json(result)

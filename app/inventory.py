"""Инвентарь NC//NET: экземпляры предметов и их модификации (P1-6).

Выделено из зоны «бд» app/server.py: генерация/нормализация
instance_id, разрешение legacy-ссылок на каталог, стекуемость,
persist/read экземпляров и модификаций, вместимость слотов оружия.
Логика не менялась (docs/repo-audit-2026-08.md).
"""
import copy
import json
import secrets
import time

from core import INSTANCE_ID_RE, ITEM_INSTANCE_STATES, parse_json_object
from rules import _num
from catalog import item_by_id
from mod_engine import weapon_modification_configuration_schema
from charbuild import cyberware_secondary_host_id


ITEM_INSTANCE_BUCKETS = {'inventory', 'cyberware'}
# INSTANCE_ID_RE переехал в core.py (P1-4) — импортирован сверху


def new_item_instance_id():
    return secrets.token_hex(16)


def catalog_item_id_for_entry(entry):
    """Resolve a legacy owned-item row to a stable Data Pool identifier."""
    if not isinstance(entry, dict):
        return None
    raw = str(entry.get('catalog_item_id') or entry.get('source_key') or
              entry.get('key') or '').split('@', 1)[0]
    return raw if raw and item_by_id(raw) else None


def item_entry_stackable(entry):
    """Use explicit instance/catalog metadata; only ammunition stacks by default."""
    if isinstance(entry, dict) and isinstance(entry.get('stackable'), bool):
        return entry['stackable']
    item = item_by_id(catalog_item_id_for_entry(entry)) if isinstance(entry, dict) else None
    explicit = (item or {}).get('stackable')
    if isinstance(explicit, bool):
        return explicit
    return str((item or entry or {}).get('cat') or '') == 'ammo'


def ensure_character_item_instances(data, regenerate=False):
    """Add stable IDs and split durable legacy stacks without losing quantities.

    The Character JSON remains a compatibility projection while ``item_instances``
    becomes the relational foundation for modifications, transfers and consumables.
    """
    changed = False
    seen = set()
    legacy_instance_ids = {}
    legacy_weapon_state = copy.deepcopy(data.get('weapon_state') or {})
    legacy_weapon_keys = set()
    for bucket in ('inventory', 'cyberware'):
        source = data.get(bucket) if isinstance(data.get(bucket), list) else []
        normalized = []
        for raw_entry in source:
            if not isinstance(raw_entry, dict):
                normalized.append(raw_entry)
                continue
            entry = dict(raw_entry)
            try:
                quantity = max(1, int(entry.get('qty') or entry.get('quantity') or 1))
            except (TypeError, ValueError):
                quantity = 1
            stackable = bucket == 'inventory' and item_entry_stackable(entry)
            copies = 1 if stackable else quantity
            per_copy_quantity = quantity if stackable else 1
            if copies != 1 or quantity != per_copy_quantity:
                changed = True
            for index in range(copies):
                owned = dict(entry)
                original_instance_id = str(entry.get('instance_id') or '').lower() \
                    if index == 0 else ''
                candidate = original_instance_id
                if regenerate or not INSTANCE_ID_RE.fullmatch(candidate) or candidate in seen:
                    candidate = new_item_instance_id()
                    changed = True
                if original_instance_id and original_instance_id != candidate:
                    legacy_instance_ids.setdefault(original_instance_id, candidate)
                seen.add(candidate)
                if owned.get('instance_id') != candidate or owned.get('qty') != per_copy_quantity:
                    changed = True
                owned['instance_id'] = candidate
                owned['qty'] = per_copy_quantity
                if owned.get('is_custom'):
                    custom_key = f'custom-{candidate}'
                    if owned.get('key') != custom_key:
                        owned['key'] = custom_key
                        changed = True
                owned.pop('quantity', None)
                state = str(owned.get('state') or
                            ('installed' if bucket == 'cyberware' else 'carried'))
                if state not in ITEM_INSTANCE_STATES:
                    state = 'installed' if bucket == 'cyberware' else 'carried'
                    changed = True
                owned['state'] = state
                catalog_id = catalog_item_id_for_entry(owned)
                if catalog_id and owned.get('catalog_item_id') != catalog_id:
                    owned['catalog_item_id'] = catalog_id
                    changed = True
                normalized.append(owned)
                if bucket == 'inventory' and owned.get('cat') in ('guns', 'melee'):
                    legacy_key = str(entry.get('key') or entry.get('source_key') or
                                     entry.get('name') or '')
                    legacy_weapon_keys.add(legacy_key)
                    if candidate not in legacy_weapon_state and legacy_key in legacy_weapon_state:
                        legacy_weapon_state[candidate] = copy.deepcopy(legacy_weapon_state[legacy_key])
                        changed = True
        if source != normalized:
            changed = True
        data[bucket] = normalized

    # Cyberware creation assigns options to concrete temporary foundation IDs.
    # When server-owned IDs are regenerated, remap those links in the same pass.
    free_neuroport = next((
        item for item in data.get('cyberware') or []
        if isinstance(item, dict) and item.get('creation_free') and
        item.get('key') == 'creation-neuroport'), None)
    if free_neuroport:
        legacy_instance_ids.setdefault(
            'creation-neuroport', free_neuroport.get('instance_id'))
    for old_id, new_id in list(legacy_instance_ids.items()):
        if old_id and INSTANCE_ID_RE.fullmatch(str(new_id or '')):
            legacy_instance_ids.setdefault(
                cyberware_secondary_host_id(old_id),
                cyberware_secondary_host_id(new_id))
    for chrome in data.get('cyberware') or []:
        if not isinstance(chrome, dict):
            continue
        old_host = str(chrome.get('host_instance') or '')
        if old_host and legacy_instance_ids.get(old_host):
            chrome['host_instance'] = legacy_instance_ids[old_host]
            changed = True
        old_hosts = chrome.get('host_instances')
        if isinstance(old_hosts, list):
            remapped = [legacy_instance_ids.get(str(host), str(host))
                        for host in old_hosts]
            if remapped != old_hosts:
                chrome['host_instances'] = remapped
                changed = True

    # Existing equipped armor pointed at a catalog key. Preserve that projection,
    # but also bind it to one concrete owned item whenever a match is available.
    armor = data.get('armor') if isinstance(data.get('armor'), dict) else {}
    inventory = [entry for entry in data.get('inventory') or [] if isinstance(entry, dict)]
    claimed = set()
    for location in ('head', 'body', 'shield'):
        piece = armor.get(location)
        if not isinstance(piece, dict):
            continue
        current = str(piece.get('instance_id') or '')
        if INSTANCE_ID_RE.fullmatch(current) and current in seen:
            claimed.add(current)
            equipped = next((entry for entry in inventory
                             if entry.get('instance_id') == current), None)
            if equipped and equipped.get('state') != 'equipped':
                equipped['state'] = 'equipped'
                changed = True
            continue
        piece_key = str(piece.get('key') or piece.get('source_key') or '').split('@', 1)[0]
        bundled = bool(piece.get('bundled'))
        match = next((entry for entry in inventory
                      if (entry.get('instance_id') not in claimed or bundled) and
                      str(entry.get('catalog_item_id') or entry.get('key') or
                          entry.get('source_key') or '').split('@', 1)[0] == piece_key), None)
        if match:
            piece['instance_id'] = match['instance_id']
            if match.get('state') != 'equipped':
                match['state'] = 'equipped'
            claimed.add(match['instance_id'])
            changed = True

    for key in legacy_weapon_keys:
        if key in legacy_weapon_state and any(
                isinstance(entry, dict) and entry.get('instance_id') != key and
                str(entry.get('key') or entry.get('source_key') or entry.get('name') or '') == key
                for entry in data.get('inventory') or []):
            legacy_weapon_state.pop(key, None)
            changed = True
    if data.get('weapon_state') != legacy_weapon_state:
        data['weapon_state'] = legacy_weapon_state
    if (_num(data.get('schema_version')) or 0) < 5:
        data['schema_version'] = 5
        changed = True
    return changed


def persist_character_item_instances(conn, character_id, data, source_type,
                                     source_ref=None, acquired_at=None, prune=False):
    """Upsert the compatibility projection into the relational instance store."""
    now = time.time()
    acquired_at = float(acquired_at or now)
    present = set()
    for bucket in ('inventory', 'cyberware'):
        for entry in data.get(bucket) or []:
            if not isinstance(entry, dict):
                continue
            instance_id = str(entry.get('instance_id') or '').lower()
            occupied = conn.execute(
                'SELECT character_id FROM item_instances WHERE instance_id=?',
                (instance_id,)).fetchone() if INSTANCE_ID_RE.fullmatch(instance_id) else None
            if (not INSTANCE_ID_RE.fullmatch(instance_id) or
                    (occupied and occupied['character_id'] != int(character_id))):
                old_instance_id = instance_id
                instance_id = new_item_instance_id()
                entry['instance_id'] = instance_id
                for piece in (data.get('armor') or {}).values():
                    if isinstance(piece, dict) and piece.get('instance_id') == old_instance_id:
                        piece['instance_id'] = instance_id
                states = data.get('weapon_state') or {}
                if old_instance_id in states:
                    states[instance_id] = states.pop(old_instance_id)
            present.add(instance_id)
            catalog_id = catalog_item_id_for_entry(entry)
            state = str(entry.get('state') or
                        ('installed' if bucket == 'cyberware' else 'carried'))
            if state not in ITEM_INSTANCE_STATES:
                state = 'installed' if bucket == 'cyberware' else 'carried'
                entry['state'] = state
            try:
                quantity = max(1, int(entry.get('qty') or 1))
            except (TypeError, ValueError):
                quantity = 1
            condition_current = _num(entry.get('condition_current'))
            condition_max = _num(entry.get('condition_max'))
            acquisition_source = str(entry.get('acquisition_source') or '').strip()[:40]
            acquisition_note = str(entry.get('acquisition_note') or '').strip()[:160]
            stored_source = acquisition_source or str(source_type or 'unknown')[:40]
            stored_ref = acquisition_note or str(source_ref or '')[:160] or None
            conn.execute(
                'INSERT INTO item_instances(instance_id,character_id,catalog_item_id,bucket,'
                'custom_name,state,quantity,condition_current,condition_max,notes,acquired_at,'
                'source_type,source_ref,data_json,created,updated) '
                'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) '
                'ON CONFLICT(instance_id) DO UPDATE SET '
                'catalog_item_id=excluded.catalog_item_id,bucket=excluded.bucket,'
                'custom_name=excluded.custom_name,state=excluded.state,quantity=excluded.quantity,'
                'condition_current=excluded.condition_current,condition_max=excluded.condition_max,'
                'notes=excluded.notes,data_json=excluded.data_json,updated=excluded.updated',
                (instance_id, int(character_id), catalog_id, bucket,
                 str(entry.get('custom_name') or '')[:120] or None, state, quantity,
                 condition_current, condition_max, str(entry.get('notes') or '')[:2000],
                 acquired_at, stored_source, stored_ref,
                 json.dumps(entry, ensure_ascii=False), acquired_at, now))
            if acquisition_source:
                conn.execute(
                    'UPDATE item_instances SET source_type=?,source_ref=? WHERE instance_id=?',
                    (acquisition_source, acquisition_note or None, instance_id))
    if prune:
        if present:
            marks = ','.join('?' for _ in present)
            conn.execute(
                f'DELETE FROM item_instances WHERE character_id=? AND instance_id NOT IN ({marks})',
                (int(character_id), *sorted(present)))
        else:
            conn.execute('DELETE FROM item_instances WHERE character_id=?', (int(character_id),))


def item_modification_payload(row):
    item = dict(row)
    item['active'] = bool(item.get('active'))
    item['permanent'] = bool(item.get('permanent'))
    item['configuration'] = parse_json_object(item.pop('configuration_json', '{}'))
    return item


def character_modifications(conn, character_id, include_inactive=False):
    where = '' if include_inactive else 'AND m.active=1'
    rows = conn.execute(
        'SELECT m.*,u.display_name installer FROM item_modifications m '
        'JOIN users u ON u.id=m.installed_by WHERE m.character_id=? ' + where +
        ' ORDER BY m.installed_at,m.modification_id', (int(character_id),)).fetchall()
    return [item_modification_payload(row) for row in rows]


def weapon_is_exotic(entry):
    item = item_by_id(catalog_item_id_for_entry(entry))
    text = ' '.join((
        str((item or {}).get('name') or ''), str((item or {}).get('desc') or ''),
        str(((item or {}).get('mechanics') or {}).get('quality') or ''),
    )).lower()
    return 'exotic weapon' in text or 'exotic ranged weapon' in text


def weapon_slot_capacity(host, active_modifications=None, owned_by_id=None):
    active_modifications = active_modifications or []
    owned_by_id = owned_by_id or {}
    pools = {
        'attachment': {'total': 0 if weapon_is_exotic(host) else 3, 'used': 0},
        'scope': {'total': 0, 'used': 0},
    }
    for modification in active_modifications:
        if not modification.get('active', True):
            continue
        upgrade = owned_by_id.get(modification.get('upgrade_instance_id')) or {}
        for pool, amount in (upgrade.get('grants_slots') or {}).items():
            if pool in pools:
                pools[pool]['total'] += max(0, int(amount or 0))
    for modification in active_modifications:
        if not modification.get('active', True):
            continue
        upgrade = owned_by_id.get(modification.get('upgrade_instance_id')) or {}
        required = max(0, int(modification.get('slots_used') or 0))
        configured_pool = (modification.get('configuration') or {}).get('slot_pool')
        pool = configured_pool if configured_pool in pools else 'attachment'
        if not configured_pool and upgrade.get('slot_type') == 'scope' and weapon_is_exotic(host):
            pool = 'scope'
        pools[pool]['used'] += required
    return pools


def weapon_upgrade_compatibility(host, upgrade, active_modifications=None,
                                 owned_by_id=None):
    active_modifications = active_modifications or []
    owned_by_id = owned_by_id or {}
    reasons = []
    manual = bool(upgrade.get('compatibility_manual'))
    if host.get('cat') != 'guns':
        reasons.append('Host is not a ranged weapon')
    if upgrade.get('cat') != 'gun_upgrades' or upgrade.get('host_type') != 'weapon':
        reasons.append('Item is not a weapon upgrade')
    host_catalog = item_by_id(catalog_item_id_for_entry(host)) or {}
    upgrade_catalog = item_by_id(catalog_item_id_for_entry(upgrade)) or {}
    mechanics = host_catalog.get('mechanics') or host.get('mechanics') or {}
    weapon_type = str(mechanics.get('type') or '').lower()
    skill = str(mechanics.get('skill') or '').lower()
    text = str(upgrade.get('compatibility_text') or
               (upgrade_catalog.get('mechanics') or {}).get('compatible_weapons') or '').lower()
    exotic = weapon_is_exotic(host)
    installed_upgrades = [owned_by_id.get(modification.get('upgrade_instance_id')) or {}
                          for modification in active_modifications]
    has_scope_rail = any(item.get('name') == 'Compatibility Rail'
                         for item in installed_upgrades)
    scope_upgrade = upgrade.get('slot_type') == 'scope'
    if 'non-exotic' in text and exotic and not (scope_upgrade and has_scope_rail):
        reasons.append('Requires a Non-Exotic weapon or Compatibility Rail')
    if 'all exotic ranged weapons' in text and not exotic:
        reasons.append('Requires an Exotic weapon')
    if 'shoulder arms' in text and skill != 'shoulder arms':
        reasons.append('Requires a Shoulder Arms weapon')
    is_bow = 'bow' in weapon_type or 'crossbow' in weapon_type
    if text.strip().startswith('bows, crossbows') and not is_bow:
        reasons.append('Requires a Bow or Crossbow')
    if ('except bows' in text or 'excluding bows' in text or 'excluding bows & crossbows' in text) and is_bow:
        reasons.append('Cannot be installed on Bows/Crossbows')
    if 'sniper rifles' in text and 'all ranged' not in text and 'sniper rifle' not in weapon_type:
        reasons.append('Requires a Sniper Rifle')
    if text.startswith('all pistols') and 'pistol' not in weapon_type:
        reasons.append('Requires a Pistol')
    host_feature_text = ' '.join(str(value) for value in (host_catalog.get('fields') or {}).values()).lower()
    if 'autofire (smg 3)' in text and 'autofire (3)' not in host_feature_text:
        reasons.append('Requires a weapon with Autofire (SMG 3)')
    if 'except grenade launchers and rocket launchers' in text and any(
            token in weapon_type for token in ('grenade launcher', 'rocket launcher')):
        reasons.append('Cannot be installed on Grenade/Rocket Launchers')
    configuration_schemas = weapon_modification_configuration_schema(
        catalog_item_id_for_entry(upgrade), host)
    if any(schema.get('required') and not schema.get('choices')
           for schema in configuration_schemas):
        reasons.append('No compatible configuration choices for this weapon type')

    pools = weapon_slot_capacity(host, active_modifications, owned_by_id)
    required = max(0, int(upgrade.get('slots_used') or 0))
    preferred_pool = 'scope' if scope_upgrade and exotic else 'attachment'
    if required and pools[preferred_pool]['used'] + required > pools[preferred_pool]['total']:
        # A non-Exotic scope normally consumes a general attachment slot. An Exotic
        # scope may only consume the dedicated slot granted by Compatibility Rail.
        reasons.append(
            f'Not enough {preferred_pool} slots '
            f'({pools[preferred_pool]["used"]}/{pools[preferred_pool]["total"]}, needs {required})')
    slots_total = sum(pool['total'] for pool in pools.values())
    slots_used = sum(pool['used'] for pool in pools.values())
    catalog_id = catalog_item_id_for_entry(upgrade)
    group = upgrade.get('modification_group')
    for modification in active_modifications:
        installed = owned_by_id.get(modification.get('upgrade_instance_id')) or {}
        if upgrade.get('unique_per_host') and catalog_item_id_for_entry(installed) == catalog_id:
            reasons.append('Only one copy may be installed on this host')
        if group and installed.get('modification_group') == group:
            reasons.append(f'Conflicts with installed {installed.get("name") or "upgrade"}')
        names = {str(upgrade.get('name') or ''), str(installed.get('name') or '')}
        if names == {'Smart Rebuild', 'Smartgun Link'}:
            reasons.append('Smart Rebuild conflicts with Smartgun Link')
    return {
        'allowed': not reasons, 'manual_resolution_required': manual,
        'reasons': reasons, 'slots_total': slots_total, 'slots_used': slots_used,
        'slot_pools': pools, 'slot_pool': preferred_pool if required else None,
        'slot_pool_after': pools[preferred_pool]['used'] + required,
        'slot_pool_total': pools[preferred_pool]['total'],
        'slots_required': required, 'slots_after': slots_used + required,
        'grants_slots': copy.deepcopy(upgrade.get('grants_slots') or {}),
        'compatibility_text': upgrade.get('compatibility_text') or '',
    }

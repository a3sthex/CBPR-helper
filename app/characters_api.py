"""Персонажи NC//NET: листы, инвентарь, схроны, Tech Maker, терапия, IP-механика (миксин Handler; P1, логика не менялась)."""


import copy
import json
import math
import os
import re
import secrets
import sqlite3
import time

from campaign import (CAMPAIGN_DURATION_LABELS, DOWNTIME_ACTIVITY_BY_ID,
                      campaign_duration_seconds, campaign_now,
                      character_campaign_services, clean_downtime_activities,
                      downtime_payload, downtime_state)
from catalog import (ITEM_MODIFICATION_FIELDS, catalog,
                     catalog_interaction_data, enrich_owned_item_interactions,
                     item_by_id, item_effect_coverage, load_effect_rules,
                     vehicle_modification_rules_for_catalog,
                     weapon_modification_rules_for_catalog)
from charbuild import (TECH_MAKER_FABRICATION_SPECIALTIES, TECH_MAKER_SPECIALTIES,
                       TECH_MAKER_SPECIALTY_LABELS, THERAPY_PROFILES,
                       armor_shield_hp, bound_popup_weapon_profile,
                       canonical_import_character, character_maker_ranks,
                       clean_character, clean_character_profile_patch,
                       clean_character_trust_update, clean_custom_effect,
                       clean_tech_maker_effect, cyberware_capacity,
                       cyberware_host_assignments, cyberware_host_kind,
                       cyberware_installation_profile, cyberware_is_installed,
                       cyberware_is_paired_leg_foundation,
                       cyberware_option_compatibility, cyberware_side_required,
                       cyberware_weapon_profile, effective_armor_hosts,
                       effective_cyberware_loadout, ensure_progression,
                       popup_weapon_binding_compatibility,
                       popup_weapon_binding_kind, public_character_data,
                       skill_base, tech_maker_fabricable_item,
                       tech_maker_host_type, tech_maker_payload, trust_number,
                       validate_armor_repair_references,
                       validate_armor_tech_references,
                       validate_bound_popup_weapon_references,
                       validate_creation, validate_cyberware_payload_conflicts,
                       validate_cyberware_requirements, validate_cyberware_sides,
                       validate_cyberware_slots, validate_cyberware_trust_lifecycle,
                       validate_popup_shield_references, validate_role_rank_setup,
                       validate_tech_maker_references)
from core import (INSTANCE_ID_RE, UPLOAD_DIR, ApiError, _row_value,
                  ensure_character_visibility, parse_json_object, user_is_admin,
                  user_is_gm)
from crew import (TRANSFER_KINDS, _attach_runtime_state,
                  _attach_tech_maker_modifications, _character_item_name,
                  _detach_runtime_state, _detach_tech_maker_modifications,
                  _inventory_entry, _persist_transfer_side,
                  _prepare_entry_for_holder, _record_item_transfer,
                  _record_transfer_ledger, _split_stack,
                  _transferable_item_error, active_loan_for_instance,
                  character_open_loans, crew_stash_payload, transfer_targets)
from db import (VEHICLE_REPAIR_RULES, active_black_ice_entity,
                character_effective_cyberdecks, cyberdeck_item_compatibility,
                cyberdeck_program_category, cyberdeck_slot_usage,
                initial_black_ice_entity, initial_program_runtime_state,
                queue_defense_sequencer_trigger,
                resolve_defense_sequencer_trigger, roll_dice, session_net_state,
                sync_vehicle_states_with_modifications,
                sync_weapon_states_with_modifications,
                validate_active_modification_references,
                vehicle_classification, vehicle_repair_severity,
                vehicle_repair_skill, vehicle_upgrade_compatibility)
from httpkit import atomic_endpoint
from inventory import (catalog_item_id_for_entry, character_modifications,
                       ensure_character_item_instances, item_entry_stackable,
                       item_modification_payload, new_item_instance_id,
                       persist_character_item_instances, weapon_is_exotic,
                       weapon_slot_capacity, weapon_upgrade_compatibility)
from media import attach_character_media
from memorial import (MEMORIAL_STATUSES, clean_memorial_input,
                      clean_reputation_input, memorial_payload)
from mod_engine import (ammo_kind_for_modification_profile,
                        ammo_matches_requirement, ammo_pack_size, ammo_rounds,
                        bound_vehicle_weapon_profile,
                        character_effective_vehicles, character_effective_weapons,
                        clean_vehicle_modification_choices,
                        clean_weapon_modification_choices,
                        clear_loaded_ammo_if_empty, consume_shared_ammo,
                        evaluate_effective_vehicle, evaluate_effective_weapon,
                        initial_vehicle_modification_state,
                        normalize_vehicle_modification_state, vehicle_base_interior,
                        vehicle_modification_configuration_schema,
                        weapon_modification_configuration_schema,
                        weapon_profiles_from_rules)
from recap import (add_notification, readable_change_value,
                   record_character_change_set, record_character_changes,
                   record_effect_change)
from rules import (ACTIVE_EFFECT_ACTIONS, ROLES, SKILL_BY_NAME,
                   SPECIALIZED_SKILLS, _num, character_effect_instances, derive,
                   effect_instance_payload, instantiate_consumable_effects)


class CharactersMixin:

    def _reputation_for(self, character_id, conn, public_view):
        if conn is None:
            return []
        try:
            rows = conn.execute(
                'SELECT cr.*,p.display_name org_name,p.handle org_handle '
                'FROM character_reputation cr JOIN personas p ON p.id=cr.organization_persona_id '
                'WHERE cr.character_id=? ORDER BY cr.updated DESC', (int(character_id),)).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            return []

    def add_ip_ledger(self, conn, character_id, actor_id, amount, before, after,
                      kind, subject, reason):
        conn.execute('INSERT INTO ip_ledger(character_id,actor_id,amount,balance_before,balance_after,kind,subject,reason,created) VALUES(?,?,?,?,?,?,?,?,?)',
                     (character_id, actor_id, amount, before, after, kind,
                      str(subject or '')[:120] or None, str(reason or '')[:500], time.time()))

    @atomic_endpoint
    def api_character_armor_repair_action(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {
            'revision', 'action', 'method', 'technician', 'jeeves_instance_id',
            'manual_resolution_confirmed', 'no_sp_loss_confirmed',
            'service_cost', 'payment_confirmed', 'reason',
        }
        if set(body or {}) - allowed:
            raise ApiError(400, 'Armor Repair action содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        reason_detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason_detail) < 3:
            raise ApiError(400, 'Укажите причину Armor Repair action')
        instance_id = str(m.group(2)).lower()
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        host = next((item for item in effective_armor_hosts(data)['hosts']
                     if item['instance_id'] == instance_id), None)
        if not host:
            raise ApiError(404, 'Concrete Armor instance не найден')
        if host['host_kind'] == 'shield':
            raise ApiError(409, 'Bulletproof Shields не подлежат ремонту')
        if host['unrepairable']:
            raise ApiError(409, 'Эта Armor не может восстанавливать SP')
        states = data.setdefault('armor_repair_state', {})
        workflow = states.setdefault(instance_id, {'active': None, 'history': []})
        if not isinstance(workflow.get('history'), list):
            workflow['history'] = []
        active = workflow.get('active') if isinstance(workflow.get('active'), dict) else None
        action = str((body or {}).get('action') or '').lower()
        now = time.time()
        result = {'action': action}
        if action == 'start':
            if active:
                raise ApiError(409, 'Armor Repair уже активен')
            if not host['damaged'] or not host['equipped_locations']:
                raise ApiError(409, 'Armor должна быть экипирована и повреждена')
            method = str((body or {}).get('method') or '').lower()
            if method not in ('manual_tech', 'jeeves', 'paid_service'):
                raise ApiError(400, 'Armor Repair method: manual_tech/jeeves/paid_service')
            technician = str((body or {}).get('technician') or '').strip()[:120]
            if len(technician) < 2:
                raise ApiError(400, 'Укажите Armor repair technician')
            duration_label = 'MANUAL TECH TIME'
            duration_key = None
            jeeves_id = None
            if method == 'jeeves':
                jeeves_id = str((body or {}).get('jeeves_instance_id') or '').lower()
                jeeves = next((item for item in data.get('inventory') or []
                               if isinstance(item, dict) and item.get('instance_id') == jeeves_id and
                               catalog_item_id_for_entry(item) == 'gear-39' and
                               item.get('state') in ('carried', 'stored')), None)
                if not jeeves:
                    raise ApiError(409, 'Jeeves Executive Garment Bag недоступен')
                price = float((item_by_id(host['catalog_item_id']) or {}).get('price') or 0)
                if price > 1000:
                    raise ApiError(409, 'Jeeves не ремонтирует Luxury/Super Luxury Armor')
                duration_label = ('1 Hour' if price <= 20 else '6 Hours' if price <= 50 else
                                  '1 Day' if price <= 100 else '1 Week' if price <= 500 else
                                  '2 Weeks')
                duration_key = ('1_hour' if price <= 20 else '6_hours' if price <= 50 else
                                '1_day' if price <= 100 else '1_week' if price <= 500 else
                                '2_weeks')
            service_cost = 0
            if method == 'paid_service':
                service_cost = _num((body or {}).get('service_cost'))
                if service_cost is None or not 0 <= service_cost <= 1_000_000:
                    raise ApiError(400, 'Укажите bounded Armor Repair service cost')
                if (body or {}).get('payment_confirmed') is not True:
                    raise ApiError(400, 'Подтвердите оплату Armor Repair service')
                cash = float(data.get('cash') or 0)
                if cash < service_cost:
                    raise ApiError(409, 'Недостаточно средств для Armor Repair service')
                data['cash'] = round(cash - service_cost, 2)
                duration_label = 'MANUAL PAID SERVICE TIME'
            campaign_started = campaign_now(conn)
            active = {
                'repair_id': secrets.token_hex(16), 'method': method,
                'technician': technician, 'jeeves_instance_id': jeeves_id,
                'service_cost': service_cost,
                'payment_refundable': False if service_cost else None,
                'duration_label': duration_label,
                'target_locations': host['equipped_locations'],
                'before': copy.deepcopy(host['current_by_location']),
                'target_maximum': host['effective_sp'], 'started_at': now,
                'status': 'active', 'source': 'CP:R 140 / BC 43',
                'manual_resolution_required': True,
                'campaign_started_at': campaign_started,
                'campaign_due_at': (
                    campaign_started + campaign_duration_seconds(duration_key)
                    if duration_key else None),
            }
            workflow['active'] = active
            result['repair'] = copy.deepcopy(active)
            reason = f'Start Armor Repair {host["name"]}: {reason_detail}'
        elif action in ('resolve', 'cancel'):
            if not active:
                raise ApiError(409, 'Нет активного Armor Repair')
            completed = action == 'resolve'
            if completed and (body or {}).get('manual_resolution_confirmed') is not True:
                raise ApiError(400, 'Подтвердите завершение Armor Repair')
            history = copy.deepcopy(active)
            history['status'] = 'completed' if completed else 'canceled'
            history['resolved_at'] = now
            history['reason'] = reason_detail
            if completed:
                after_values = {}
                for location in active.get('target_locations') or []:
                    piece = (data.get('armor') or {}).get(location)
                    if isinstance(piece, dict) and piece.get('instance_id') == instance_id:
                        maximum = int(_num(piece.get('maximum')) or
                                      _num(active.get('target_maximum')) or 0)
                        piece['current'] = maximum
                        after_values[location] = maximum
                history['after'] = after_values
                result['restored'] = after_values
            workflow['history'].append(history)
            workflow['history'] = workflow['history'][-30:]
            workflow['active'] = None
            result['repair'] = history
            reason = f'{"Resolve" if completed else "Cancel"} Armor Repair {host["name"]}: {reason_detail}'
        elif action == 'self_repair_tick':
            if host.get('self_repair') != 'executive_armor_daily':
                raise ApiError(409, 'Armor не имеет daily self-repair')
            if (body or {}).get('no_sp_loss_confirmed') is not True:
                raise ApiError(400, 'Подтвердите день без потери SP')
            restored = {}
            for location in host['equipped_locations']:
                piece = (data.get('armor') or {}).get(location)
                if isinstance(piece, dict):
                    maximum = int(_num(piece.get('maximum')) or host['effective_sp'] or 0)
                    current = int(_num(piece.get('current')) or 0)
                    piece['current'] = min(maximum, current + 1)
                    restored[location] = piece['current']
            result['restored'] = restored
            workflow['history'].append({
                'action': action, 'status': 'completed', 'resolved_at': now,
                'after': restored, 'reason': reason_detail, 'source': 'BC 34'})
            workflow['history'] = workflow['history'][-30:]
            reason = f'Executive Armor daily self-repair {host["name"]}: {reason_detail}'
        else:
            raise ApiError(400, 'Armor Repair action: start/resolve/cancel/self_repair_tick')
        validate_armor_repair_references(data)
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='item_action')
        ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                  (ledger_id,)).fetchone()
        delta = parse_json_object(ledger_row['delta_json'])
        delta['armor_repair_lifecycle'] = copy.deepcopy(result)
        conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                     (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id, 'result': result,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    @atomic_endpoint
    def api_character_armor_tech_upgrade(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {'revision', 'tech_name', 'manual_confirm', 'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Armor Tech Upgrade содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        if (body or {}).get('manual_confirm') is not True:
            raise ApiError(400, 'Подтвердите успешный Tech Upgrade Check')
        tech_name = str((body or {}).get('tech_name') or '').strip()[:120]
        reason_detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(tech_name) < 2 or len(reason_detail) < 3:
            raise ApiError(400, 'Укажите Tech и причину Armor Upgrade')
        instance_id = str(m.group(2)).lower()
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        armor_item = next((item for item in data.get('inventory') or []
                           if isinstance(item, dict) and item.get('instance_id') == instance_id and
                           item.get('cat') == 'armor'), None)
        if not armor_item:
            raise ApiError(404, 'Concrete Armor/Shield instance не найден')
        states = data.setdefault('armor_tech_state', {})
        if isinstance(states.get(instance_id), dict) and states[instance_id].get('active'):
            raise ApiError(409, 'Armor/Shield уже имеет Tech Upgrade')
        catalog_item = item_by_id(catalog_item_id_for_entry(armor_item)) or armor_item
        locations = catalog_item.get('armor_locations') or []
        shield = 'shield' in locations
        base_sp = _num(catalog_item.get('sp'))
        if not shield and base_sp is None:
            raise ApiError(409, 'Armor instance не имеет upgradeable SP')
        mode = 'manual_shield_upgrade' if shield else 'sp_plus_one'
        now = time.time()
        state = {
            'active': True, 'mode': mode, 'permanent': True,
            'tech_name': tech_name, 'installed_by': user['id'],
            'installed_at': now, 'source': 'CP:R 148 · Upgrade Expertise',
            'manual_resolution_required': shield,
            'reason': reason_detail,
        }
        states[instance_id] = state
        if not shield:
            for location in ('head', 'body'):
                piece = (data.get('armor') or {}).get(location)
                if isinstance(piece, dict) and piece.get('instance_id') == instance_id:
                    previous_max = _num(piece.get('maximum'))
                    previous_max = previous_max if previous_max is not None else base_sp
                    previous_current = _num(piece.get('current'))
                    previous_current = previous_current if previous_current is not None else previous_max
                    piece['sp'] = base_sp + 1
                    piece['maximum'] = base_sp + 1
                    piece['current'] = min(base_sp + 1, previous_current + 1)
        validate_armor_tech_references(data)
        persist_character_item_instances(
            conn, row['id'], data, 'armor_tech_upgrade',
            source_ref=reason_detail, prune=True)
        revision_after = current_revision + 1
        reason = (f'Tech Upgrade {armor_item.get("name")} '
                  f'({"SP +1" if not shield else "MANUAL SHIELD"}): {reason_detail}')
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='modification')
        ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                  (ledger_id,)).fetchone()
        delta = parse_json_object(ledger_row['delta_json'])
        delta['armor_tech_upgrade'] = {
            'instance_id': instance_id, 'mode': mode, 'permanent': True,
            'tech_name': tech_name, 'manual_resolution_required': shield,
        }
        conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                     (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id, 'upgrade': state,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    @atomic_endpoint
    def api_character_backup_restore(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        if set(body or {}) - {'revision', 'reason'}:
            raise ApiError(400, 'Backup restore содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        deck_id, hardware_id = str(m.group(2)).lower(), str(m.group(3)).lower()
        modifications = character_modifications(conn, row['id'])
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        owned = {item.get('instance_id'): item for item in data.get('inventory') or []
                 if isinstance(item, dict) and item.get('instance_id')}
        backup_modification = next((item for item in modifications
                                    if item.get('host_instance_id') == deck_id and
                                    item.get('upgrade_instance_id') == hardware_id and
                                    (owned.get(hardware_id) or {}).get('name') == 'Backup Drive'), None)
        if not backup_modification:
            raise ApiError(404, 'Installed Backup Drive не найден')
        backup_state = (data.get('modification_state') or {}).get(
            backup_modification['modification_id']) or {}
        saved = backup_state.get('saved_programs') or []
        if not saved:
            raise ApiError(409, 'Backup Drive не содержит Programs')
        detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(detail) < 3:
            raise ApiError(400, 'Укажите причину Backup restore')
        active_deck = [item for item in modifications
                       if item.get('host_instance_id') == deck_id]
        restored_rows = []
        for snapshot in saved:
            program_id = str(snapshot.get('program_instance_id') or '')
            program = owned.get(program_id)
            inactive = conn.execute(
                'SELECT * FROM item_modifications WHERE modification_id=? '
                'AND character_id=? AND host_instance_id=? AND upgrade_instance_id=? AND active=0',
                (snapshot.get('modification_id'), row['id'], deck_id, program_id)).fetchone()
            if not program or program.get('state') != 'broken' or not inactive:
                raise ApiError(409, 'Saved Program instance недоступен для восстановления')
            compatibility = cyberdeck_item_compatibility(
                owned.get(deck_id) or {}, program, active_deck, owned)
            if not compatibility['allowed']:
                raise ApiError(409, 'Недостаточно Cyberdeck slots для Backup restore')
            restored_modification = item_modification_payload(inactive)
            restored_modification['active'] = True
            active_deck.append(restored_modification)
            restored_rows.append((snapshot, program, restored_modification))
        now = time.time()
        restored_ids = []
        for snapshot, program, restored_modification in restored_rows:
            modification_id = restored_modification['modification_id']
            conn.execute(
                'UPDATE item_modifications SET active=1,removed_by=NULL,removed_at=NULL,updated=? '
                'WHERE modification_id=?', (now, modification_id))
            program['state'] = 'installed'
            program['host_instance_id'] = deck_id
            data.setdefault('program_state', {})[program['instance_id']] = \
                initial_program_runtime_state(
                    program, deck_id, modification_id,
                    snapshot.get('runtime_before'))
            restored_ids.append(modification_id)
        backup_state['saved_programs'] = []
        validate_active_modification_references(conn, row['id'], data)
        persist_character_item_instances(
            conn, row['id'], data, 'backup_restore', source_ref=detail, prune=True)
        revision_after = current_revision + 1
        reason = f'Restore {len(restored_ids)} Programs from Backup Drive: {detail}'
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='modification')
        ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                  (ledger_id,)).fetchone()
        delta = parse_json_object(ledger_row['delta_json'])
        delta['created_modification_ids'] = restored_ids
        conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                     (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id,
            'restored': len(restored_ids),
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    @atomic_endpoint
    def api_character_black_ice_deploy(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {
            'revision', 'mode', 'floor_label', 'target_label', 'reason',
            'session_id', 'session_floor_id', 'session_node_id',
            'target_combatant_id'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Black ICE deployment содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        deck_id, program_id = str(m.group(2)).lower(), str(m.group(3)).lower()
        modifications = character_modifications(conn, row['id'])
        modification = next((item for item in modifications
                             if item.get('host_instance_id') == deck_id and
                             item.get('upgrade_instance_id') == program_id and
                             item.get('host_type') == 'cyberdeck'), None)
        if not modification:
            raise ApiError(404, 'Installed Black ICE instance не найден')
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        owned = {item.get('instance_id'): item for item in data.get('inventory') or []
                 if isinstance(item, dict) and item.get('instance_id')}
        program = owned.get(program_id)
        if not program or cyberdeck_program_category(program) != 'black_ice':
            raise ApiError(400, 'Выбранная Program не является Black ICE')
        if active_black_ice_entity(data, program_id):
            raise ApiError(409, 'Для этой Black ICE уже существует active NET entity')
        runtime = initial_program_runtime_state(
            program, deck_id, modification['modification_id'],
            (data.get('program_state') or {}).get(program_id))
        if runtime['status'] != 'inactive':
            raise ApiError(409, 'Black ICE необходимо сначала Deactivate')
        mode = str((body or {}).get('mode') or '')
        if mode not in ('lie_in_wait', 'deploy_combat'):
            raise ApiError(400, 'Black ICE mode: lie_in_wait/deploy_combat')
        session = None
        net_state = None
        net_state_before = None
        session_floor_id = None
        session_node_id = None
        session_node_label = None
        target_combatant_id = None
        session_id = _num((body or {}).get('session_id'))
        floor_label = str((body or {}).get('floor_label') or '').strip()[:120]
        target_label = str((body or {}).get('target_label') or '').strip()[:120]
        if session_id is not None:
            if int(session_id) != session_id:
                raise ApiError(400, 'Некорректная Live Session')
            session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                                   (int(session_id),)).fetchone()
            role, capabilities = self.session_capabilities(conn, user, session)
            if (not session or not role or
                    session['status'] not in ('preparing', 'active', 'paused')):
                raise ApiError(403, 'Нет доступа к Live NET Session')
            if ('view_gm' not in capabilities and not conn.execute(
                    'SELECT 1 FROM session_combatants WHERE session_id=? AND character_id=?',
                    (session['id'], row['id'])).fetchone()):
                raise ApiError(403, 'Character не участвует в этой Session')
            net_state = session_net_state(_row_value(session, 'net_state_json', '{}'))
            net_state_before = copy.deepcopy(net_state)
            session_floor_id = str((body or {}).get('session_floor_id') or '').lower()
            floor = next((item for item in net_state['floors']
                          if item['floor_id'] == session_floor_id), None)
            if not floor:
                raise ApiError(400, 'Выберите validated Session NET Floor')
            floor_label = floor['label']
            floor_nodes = [item for item in net_state['nodes']
                           if item['floor_id'] == session_floor_id]
            session_node_id = str((body or {}).get('session_node_id') or '').lower()
            node = None
            if floor_nodes:
                node = next((item for item in floor_nodes
                             if item['node_id'] == session_node_id), None)
                if not node:
                    raise ApiError(400, 'Выберите validated Session NET node')
                session_node_label = node['label']
            else:
                session_node_id = None
            if mode == 'deploy_combat':
                target_combatant_id = _num((body or {}).get('target_combatant_id'))
                if (target_combatant_id is None or int(target_combatant_id) != target_combatant_id):
                    raise ApiError(400, 'Выберите Session target combatant')
                target = conn.execute(
                    'SELECT * FROM session_combatants WHERE session_id=? AND id=?',
                    (session['id'], int(target_combatant_id))).fetchone()
                if not target or target['character_id'] == row['id']:
                    raise ApiError(400, 'Некорректный Session target для Black ICE')
                target_combatant_id = target['id']
                target_label = target['name']
                if node:
                    node['visible'] = True
        reason_detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(floor_label) < 1:
            raise ApiError(400, 'Укажите Floor для Black ICE')
        if mode == 'deploy_combat' and len(target_label) < 2:
            raise ApiError(400, 'Укажите target для deployed Black ICE')
        if len(reason_detail) < 3:
            raise ApiError(400, 'Укажите причину Black ICE deployment')
        entity = initial_black_ice_entity(
            program, deck_id, row['id'], mode, floor_label, target_label)
        if session:
            entity.update({
                'session_id': session['id'], 'session_floor_id': session_floor_id,
                'session_node_id': session_node_id,
                'session_node_label': session_node_label,
                'target_combatant_id': target_combatant_id,
            })
        entities = data.setdefault('net_entities', {})
        entities[entity['net_entity_id']] = entity
        if len(entities) > 200:
            archived = sorted(
                (item for item in entities.values()
                 if item.get('status') in ('deactivated', 'destroyed')),
                key=lambda item: item.get('archived_at') or 0)
            for old in archived[:max(0, len(entities) - 200)]:
                entities.pop(old.get('net_entity_id'), None)
        runtime['status'] = 'rezzed'
        runtime['rez_current'] = runtime['rez_max']
        data.setdefault('program_state', {})[program_id] = runtime
        reason = (
            f'Deploy Black ICE {program.get("name")} as {entity["status"]} '
            f'on {floor_label}: {reason_detail}')
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='item_action')
        now = time.time()
        if session:
            net_state['links'].append({
                'net_entity_id': entity['net_entity_id'],
                'character_id': row['id'], 'floor_id': session_floor_id,
                'node_id': session_node_id,
                'target_combatant_id': target_combatant_id,
                'initiative': entity.get('initiative') or 0,
                'active': True, 'visible': mode == 'deploy_combat',
                'linked_at': now,
            })
            conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                         (json.dumps(net_state, ensure_ascii=False), now, session['id']))
            conn.execute(
                'INSERT INTO session_activity(session_id,actor_user_id,event_type,after_json,note,created) '
                'VALUES(?,?,?,?,?,?)',
                (session['id'], user['id'], 'net_entity_deploy',
                 json.dumps(entity, ensure_ascii=False), reason_detail, now))
            ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                      (ledger_id,)).fetchone()
            delta = parse_json_object(ledger_row['delta_json'])
            delta['session_net_change'] = {
                'session_id': session['id'], 'before': net_state_before,
                'after': copy.deepcopy(net_state),
            }
            conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                         (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id, 'net_entity': entity,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        }, status=201)

    @atomic_endpoint
    def api_character_cyberware_action(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {
            'revision', 'action', 'host_instance_ids', 'installation_side',
            'installation_site', 'technician', 'manual_resolution_confirmed',
            'biosystem_confirmed', 'reason',
        }
        if set(body or {}) - allowed:
            raise ApiError(400, 'Cyberware action содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        reason_detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason_detail) < 3:
            raise ApiError(400, 'Укажите причину Cyberware lifecycle action')
        instance_id = str(m.group(2)).lower()
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        chrome = next((item for item in data.get('cyberware') or []
                       if isinstance(item, dict) and
                       item.get('instance_id') == instance_id), None)
        if not chrome:
            raise ApiError(404, 'Cyberware instance не найден')
        catalog_item = item_by_id(catalog_item_id_for_entry(chrome))
        if not catalog_item or catalog_item.get('cat') != 'cyberware':
            raise ApiError(409, 'Cyberware instance не связан с Data Pool')
        action = str((body or {}).get('action') or '').lower()
        if action not in ('install', 'uninstall', 'rebind', 'configure',
                          'quick_detach', 'quick_attach'):
            raise ApiError(
                400, 'Cyberware action: install/uninstall/rebind/configure/'
                     'quick_detach/quick_attach')
        raw_host_ids = (body or {}).get('host_instance_ids') or []
        if not isinstance(raw_host_ids, list) or len(raw_host_ids) > 4:
            raise ApiError(400, 'host_instance_ids должен быть коротким списком')
        host_ids = []
        for value in raw_host_ids:
            value = str(value or '').lower()
            if not INSTANCE_ID_RE.fullmatch(value):
                raise ApiError(400, 'Некорректный concrete Cyberware host')
            if value not in host_ids:
                host_ids.append(value)
        capacity = cyberware_capacity(chrome)
        expected_host = capacity.get('host')
        installed_before = cyberware_is_installed(chrome)
        humanity_before = derive(data)
        before_current = humanity_before.get('humanity_cur')
        before_maximum = humanity_before.get('humanity_max')
        now = time.time()
        installation_side = str((body or {}).get('installation_side') or '').lower()
        installation_site = str((body or {}).get('installation_site') or '').title() \
            if action in ('install', 'uninstall') else ''
        technician = str((body or {}).get('technician') or '').strip()[:120] \
            if action in ('install', 'uninstall') else ''
        profile = cyberware_installation_profile(chrome)
        runtime_states = data.setdefault('cyberware_state', {})
        if not isinstance(runtime_states, dict):
            runtime_states = {}
            data['cyberware_state'] = runtime_states
        runtime = runtime_states.get(instance_id)
        if not isinstance(runtime, dict):
            runtime = {'installation_count': 0, 'humanity_loss_events': 0,
                       'history': []}
            runtime_states[instance_id] = runtime
        if not isinstance(runtime.get('history'), list):
            runtime['history'] = []

        def append_history(event_action, *, affected_ids=None, humanity_loss=0):
            runtime['history'].append({
                'action': event_action, 'created': now,
                'installation_side': chrome.get('installation_side') or
                    runtime.get('installation_side'),
                'installation_site': installation_site or None,
                'technician': technician or None,
                'affected_instance_ids': affected_ids or [instance_id],
                'humanity_loss': humanity_loss,
                'reason': reason_detail,
                'manual_resolution_confirmed': bool(
                    event_action in ('install', 'uninstall') and
                    (body or {}).get('manual_resolution_confirmed') is True),
            })
            runtime['history'] = runtime['history'][-30:]
            runtime['last_action'] = event_action
            runtime['last_action_at'] = now

        def validate_installation_context():
            if (body or {}).get('manual_resolution_confirmed') is not True:
                raise ApiError(400, 'Подтвердите manual surgery/service resolution')
            if installation_site != profile['required_site']:
                raise ApiError(
                    400, f'{chrome.get("name")}: требуется installation site '
                         f'{profile["required_site"]}')
            if len(technician) < 2:
                raise ApiError(400, 'Укажите clinic, surgeon или technician')
            if profile['biosystem_required'] and \
                    (body or {}).get('biosystem_confirmed') is not True:
                raise ApiError(400, 'Подтвердите required Biosystem')

        def assign_side(required=True):
            if cyberware_is_paired_leg_foundation(chrome):
                chrome['installation_side'] = 'paired'
            elif cyberware_side_required(chrome):
                if installation_side not in ('left', 'right'):
                    if required:
                        raise ApiError(400, 'Выберите installation side: left/right')
                else:
                    chrome['installation_side'] = installation_side
            elif installation_side:
                raise ApiError(400, 'Эта Cyberware не использует left/right side')

        def assign_hosts():
            compatibility = cyberware_option_compatibility(
                data, instance_id, host_ids)
            if not compatibility['allowed']:
                raise ApiError(400, '; '.join(compatibility['reasons']))
            chrome['host_instance'] = host_ids[0]
            chrome['host_instances'] = host_ids
            return compatibility

        compatibility = None
        affected_ids = [instance_id]
        if action == 'install':
            if installed_before:
                raise ApiError(409, 'Cyberware уже установлена')
            if chrome.get('state') == 'broken':
                raise ApiError(409, 'Сломанную Cyberware нельзя установить')
            validate_installation_context()
            assign_side()
            if expected_host:
                compatibility = assign_hosts()
            elif host_ids:
                raise ApiError(400, 'Эта Cyberware не использует Option host')
            catalog_id = catalog_item_id_for_entry(chrome)
            other_installed = [
                item for item in data.get('cyberware') or []
                if isinstance(item, dict) and item.get('instance_id') != instance_id and
                cyberware_is_installed(item)]
            if capacity.get('unique') and any(
                    catalog_item_id_for_entry(item) == catalog_id
                    for item in other_installed):
                raise ApiError(409, 'Допустима только одна установленная копия Cyberware')
            chrome_name = str(chrome.get('name') or '').lower()
            if chrome_name == 'neuroport' and any(
                    str(item.get('name') or '').lower() == 'neuroport'
                    for item in other_installed):
                raise ApiError(409, 'Одновременно допустим только один Neuroport')
            if cyberware_host_kind(chrome) == 'Cyberaudio Suite' and any(
                    cyberware_host_kind(item) == 'Cyberaudio Suite'
                    for item in other_installed):
                raise ApiError(409, 'Одновременно допустим только один Cyberaudio Suite')
            chrome['state'] = 'installed'
            validate_cyberware_requirements(data)
            validate_cyberware_sides(data, allow_unassigned=True)
            validate_cyberware_payload_conflicts(data)
            if expected_host:
                compatibility = cyberware_option_compatibility(data, instance_id, host_ids)
                if not compatibility['allowed']:
                    raise ApiError(400, '; '.join(compatibility['reasons']))
            loss = max(0, int(_num(chrome.get('hl')) or 0))
            if before_current is not None:
                if before_current - loss < 0:
                    raise ApiError(409, 'Недостаточно Humanity для установки Cyberware')
                data['humanity_cur'] = before_current - loss
            runtime['installation_count'] = max(
                0, int(_num(runtime.get('installation_count')) or 0)) + 1
            runtime['humanity_loss_events'] = max(
                0, int(_num(runtime.get('humanity_loss_events')) or 0)) + 1
            runtime['first_installed_at'] = runtime.get('first_installed_at') or now
            runtime['installation_side'] = chrome.get('installation_side')
            runtime['last_installation_site'] = installation_site
            runtime['last_technician'] = technician
            runtime['quick_change_detached'] = False
            append_history('install', humanity_loss=loss)
            reason = f'Install Cyberware {chrome.get("name")}: {reason_detail}'
        elif action == 'rebind':
            if not installed_before or not expected_host:
                raise ApiError(409, 'Rebind требует установленную Cyberware Option')
            compatibility = assign_hosts()
            append_history('rebind')
            reason = f'Rebind Cyberware Option {chrome.get("name")}: {reason_detail}'
        elif action == 'configure':
            if not installed_before or not cyberware_side_required(chrome):
                raise ApiError(409, 'Configure side требует установленный sided foundation')
            assign_side()
            validate_cyberware_sides(data, allow_unassigned=True)
            runtime['installation_side'] = chrome.get('installation_side')
            append_history('configure')
            reason = f'Configure Cyberware side {chrome.get("name")}: {reason_detail}'
        elif action == 'quick_detach':
            if not installed_before or cyberware_host_kind(chrome) != 'Cyberarm':
                raise ApiError(409, 'Quick Detach требует установленный Cyberarm')
            loadout = effective_cyberware_loadout(data)
            foundation_host_ids = {
                host['instance_id'] for host in loadout['hosts']
                if host.get('foundation_instance_id') == instance_id}
            dependents = [
                item for item in data.get('cyberware') or []
                if isinstance(item, dict) and cyberware_is_installed(item) and
                foundation_host_ids.intersection(cyberware_host_assignments(item))]
            if not any(item.get('name') == 'Quick Change Mount' for item in dependents):
                raise ApiError(409, 'Cyberarm не имеет установленный Quick Change Mount')
            affected_ids = [instance_id] + [item['instance_id'] for item in dependents]
            for item in [chrome, *dependents]:
                item['state'] = 'carried'
            runtime['quick_change_detached'] = True
            runtime['quick_change_bundle_instance_ids'] = affected_ids[1:]
            runtime['installation_side'] = chrome.get('installation_side')
            if before_current is not None:
                data['humanity_cur'] = before_current
            append_history('quick_detach', affected_ids=affected_ids)
            reason = f'Quick Detach Cyberarm {chrome.get("name")}: {reason_detail}'
        elif action == 'quick_attach':
            if installed_before or cyberware_host_kind(chrome) != 'Cyberarm' or \
                    not runtime.get('quick_change_detached'):
                raise ApiError(409, 'Quick Attach требует detached Quick Change Cyberarm')
            bundle_ids = [str(value) for value in
                          runtime.get('quick_change_bundle_instance_ids') or []]
            bundle = [
                item for item in data.get('cyberware') or []
                if isinstance(item, dict) and item.get('instance_id') in bundle_ids]
            if len(bundle) != len(set(bundle_ids)) or not any(
                    item.get('name') == 'Quick Change Mount' for item in bundle):
                raise ApiError(409, 'Quick Change Cyberarm bundle повреждён')
            assign_side()
            chrome['state'] = 'installed'
            for item in bundle:
                item['state'] = 'installed'
            validate_cyberware_requirements(data)
            validate_cyberware_sides(data, allow_unassigned=True)
            validate_cyberware_payload_conflicts(data)
            validate_cyberware_slots(data, allow_unbound=True)
            affected_ids = [instance_id, *bundle_ids]
            runtime['quick_change_detached'] = False
            runtime['installation_side'] = chrome.get('installation_side')
            if before_current is not None:
                data['humanity_cur'] = before_current
            append_history('quick_attach', affected_ids=affected_ids, humanity_loss=0)
            reason = f'Quick Attach Cyberarm {chrome.get("name")}: {reason_detail}'
        else:
            if not installed_before:
                raise ApiError(409, 'Cyberware уже не установлена')
            if chrome.get('creation_free') and chrome.get('key') == 'creation-neuroport':
                raise ApiError(409, 'Стартовый Neuroport нельзя извлечь этим действием')
            validate_installation_context()
            foundation_host_ids = {
                host['instance_id'] for host in
                effective_cyberware_loadout(data)['hosts']
                if host.get('foundation_instance_id') == instance_id}
            dependents = [
                item for item in data.get('cyberware') or []
                if isinstance(item, dict) and item.get('instance_id') != instance_id and
                cyberware_is_installed(item) and
                foundation_host_ids.intersection(cyberware_host_assignments(item))]
            if dependents:
                names = ', '.join(str(item.get('name') or 'Option') for item in dependents[:5])
                raise ApiError(409, f'Сначала извлеките зависимые Cyberware Options: {names}')
            runtime['installation_side'] = chrome.get('installation_side')
            chrome['state'] = 'carried'
            chrome.pop('host_instance', None)
            chrome.pop('host_instances', None)
            chrome.pop('installation_side', None)
            validate_cyberware_requirements(data)
            post_remove_loadout = effective_cyberware_loadout(data)
            if any(host['overloaded'] for host in post_remove_loadout['hosts']):
                raise ApiError(409, 'Сначала освободите зависимые Cyberware Option Slots')
            if before_current is not None:
                data['humanity_cur'] = before_current
            append_history('uninstall')
            reason = f'Uninstall Cyberware {chrome.get("name")}: {reason_detail}'

        bound_weapon_id = str(runtime.get('bound_weapon_instance_id') or '')
        if bound_weapon_id:
            bound_weapon = next((item for item in data.get('inventory') or []
                                 if isinstance(item, dict) and
                                 item.get('instance_id') == bound_weapon_id), None)
            if bound_weapon:
                current_hosts = cyberware_host_assignments(chrome)
                bound_weapon['installed_cyberarm_host_id'] = (
                    current_hosts[0] if current_hosts else None)
        humanity_after = derive(data)
        validate_bound_popup_weapon_references(data)
        validate_popup_shield_references(data)
        validate_active_modification_references(conn, row['id'], data)
        persist_character_item_instances(
            conn, row['id'], data, 'cyberware_lifecycle', source_ref=reason, prune=True)
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='modification')
        ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                  (ledger_id,)).fetchone()
        delta = parse_json_object(ledger_row['delta_json'])
        delta['cyberware_lifecycle'] = {
            'action': action, 'instance_id': instance_id,
            'affected_instance_ids': affected_ids,
            'host_instance_ids': host_ids,
            'installation_side': chrome.get('installation_side') or
                runtime.get('installation_side'),
            'installation_site': installation_site or None,
            'technician': technician or None,
            'manual_resolution_confirmed': bool(
                action in ('install', 'uninstall') and
                (body or {}).get('manual_resolution_confirmed') is True),
            'humanity_current_before': before_current,
            'humanity_current_after': humanity_after.get('humanity_cur'),
            'humanity_maximum_before': before_maximum,
            'humanity_maximum_after': humanity_after.get('humanity_max'),
            'humanity_restored_on_uninstall': 0,
            'quick_change_no_humanity_loss': action == 'quick_attach',
        }
        conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                     (json.dumps(delta, ensure_ascii=False), ledger_id))
        now = time.time()
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id, 'action': action,
            'humanity': delta['cyberware_lifecycle'],
            'compatibility': compatibility,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    @atomic_endpoint
    def api_character_cyberware_weapon_action(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {'revision', 'action', 'ammo_instance_id', 'payload_type', 'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Cyberweapon action содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        reason_detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason_detail) < 3:
            raise ApiError(400, 'Укажите причину Cyberweapon action')
        instance_id = str(m.group(2)).lower()
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        chrome = next((item for item in data.get('cyberware') or []
                       if isinstance(item, dict) and item.get('instance_id') == instance_id), None)
        profile = cyberware_weapon_profile(chrome) or bound_popup_weapon_profile(data, chrome)
        if not chrome or not cyberware_is_installed(chrome) or not profile:
            raise ApiError(404, 'Installed curated Cyberweapon не найден')
        runtime_states = data.setdefault('cyberware_state', {})
        runtime = runtime_states.setdefault(instance_id, {})
        bound_weapon = next((item for item in data.get('inventory') or []
                             if isinstance(item, dict) and item.get('instance_id') ==
                             profile.get('bound_weapon_instance_id')), None)
        if bound_weapon:
            weapon_state = data.setdefault('weapon_state', {}).setdefault(
                bound_weapon['instance_id'], {
                    'magazine': int(profile.get('magazine') or 0),
                    'magazine_max': int(profile.get('magazine') or 0), 'reserve': 0,
                })
            weapon_state.setdefault('deployed', False)
            weapon_state.setdefault('revved', False)
        else:
            weapon_state = runtime.setdefault('weapon', {
                'deployed': not profile.get('deployable'), 'revved': False,
                'magazine': 0, 'magazine_max': int(profile.get('magazine') or 0),
            })
        maximum = max(0, int(_num(profile.get('magazine')) or 0))
        weapon_state['magazine_max'] = maximum
        weapon_state['magazine'] = max(
            0, min(maximum, int(_num(weapon_state.get('magazine')) or 0)))
        action = str((body or {}).get('action') or '').lower()
        result = {'action': action, 'profile_id': profile['id']}
        if action in ('deploy', 'stow'):
            if not profile.get('deployable'):
                raise ApiError(409, 'Cyberweapon не имеет deploy/stow state')
            weapon_state['deployed'] = action == 'deploy'
            if action == 'stow':
                weapon_state['revved'] = False
            reason = f'{action.title()} Cyberweapon {chrome.get("name")}: {reason_detail}'
        elif action in ('rev', 'rev_down'):
            if not profile.get('rev_action'):
                raise ApiError(409, 'Cyberweapon не имеет rev action')
            if profile.get('deployable') and not weapon_state.get('deployed'):
                raise ApiError(409, 'Сначала deploy Cyberweapon')
            weapon_state['revved'] = action == 'rev'
            reason = f'{action} Cyberweapon {chrome.get("name")}: {reason_detail}'
        elif action == 'fire':
            if profile.get('kind') not in ('ranged', 'ranged_dual'):
                raise ApiError(409, 'Fire доступен только ranged Cyberweapon')
            if profile.get('deployable') and not weapon_state.get('deployed'):
                raise ApiError(409, 'Сначала deploy Cyberweapon')
            current = weapon_state['magazine']
            if current < 1:
                raise ApiError(409, 'Cyberweapon magazine пуст')
            weapon_state['magazine'] = current - 1
            clear_loaded_ammo_if_empty(weapon_state)
            # Special payload drains entirely on fire (Gas Jet)
            if profile.get('special_ammo') and weapon_state.get('magazine', 0) == 0:
                weapon_state.pop('loaded_payload', None)
                weapon_state.pop('loaded_ammo_kind', None)
            result.update({'magazine_before': current,
                           'magazine_after': weapon_state['magazine']})
            # Manual effect hint for special weapons
            if profile.get('special_ammo') and profile.get('manual_effect'):
                result['manual_effect'] = profile['manual_effect']
                result['manual_resolution_required'] = True
            reason = f'Fire Cyberweapon {chrome.get("name")}: {reason_detail}'
        elif action == 'reload':
            if maximum <= 0:
                raise ApiError(409, 'Cyberweapon не использует tracked ammo')
            if profile.get('special_ammo'):
                if weapon_state.get('magazine', 0) >= maximum:
                    raise ApiError(409, 'Магазин уже заполнен')
                payload = None
                if profile['id'] == 'gas-jet':
                    payload_raw = str((body or {}).get('payload_type') or '').strip().lower()
                    allowed = set(profile.get('payload_options') or ['street_drug', 'poison', 'biotoxin'])
                    if payload_raw not in allowed:
                        raise ApiError(400, 'Выберите payload для Gas Jet: street_drug / poison / biotoxin')
                    payload = payload_raw
                    weapon_state['loaded_payload'] = payload
                elif profile['id'] == 'popup-net-launcher':
                    weapon_state['loaded_payload'] = 'net'
                elif profile['id'] in ('dartgun', 'dartgun-cyberfinger'):
                    weapon_state['loaded_payload'] = 'dart'
                    weapon_state.pop('loaded_ammo_kind', None)
                weapon_state['magazine'] = maximum
                weapon_state.pop('loaded_ammo_catalog_id', None)
                weapon_state.pop('loaded_ammo_name', None)
                if payload != 'street_drug' and payload is not None:
                    weapon_state.pop('loaded_ammo_kind', None)
                result['special_reload'] = True
                result['loaded_payload'] = weapon_state.get('loaded_payload')
                result['magazine_after'] = maximum
                if payload:
                    reason = f'Reload Cyberweapon {chrome.get("name")} [{payload}]: {reason_detail}'
                else:
                    reason = f'Reload Cyberweapon {chrome.get("name")} [special ammo]: {reason_detail}'
            else:
                ammo_id = str((body or {}).get('ammo_instance_id') or '').lower()
                ammo = next((item for item in data.get('inventory') or []
                             if isinstance(item, dict) and item.get('instance_id') == ammo_id), None)
                ammo_kinds = profile.get('ammo_kinds') or ([profile.get('ammo_kind')]
                                                           if profile.get('ammo_kind') else [])
                if bound_weapon:
                    if not ammo_matches_requirement(ammo, weapon=bound_weapon):
                        raise ApiError(400, 'Ammo stack несовместим с Cyberweapon')
                    transfer = consume_shared_ammo(
                        data, weapon_state, ammo_id, weapon=bound_weapon)
                    ammo_kind = None
                else:
                    ammo_kind = next((kind for kind in ammo_kinds
                                      if ammo_matches_requirement(ammo, kind)), None)
                    if not ammo_kind:
                        raise ApiError(400, 'Ammo stack несовместим с Cyberweapon')
                    transfer = consume_shared_ammo(
                        data, weapon_state, ammo_id, ammo_kind=ammo_kind)
                if ammo_kind:
                    weapon_state['loaded_ammo_kind'] = ammo_kind
                result['transfer'] = transfer
                reason = (f'Reload Cyberweapon {chrome.get("name")} with '
                          f'{transfer["ammo_name"]} ×{transfer["moved"]}: {reason_detail}')
        else:
            raise ApiError(400, 'Cyberweapon action: deploy/stow/rev/rev_down/fire/reload')
        if not bound_weapon:
            runtime['weapon'] = weapon_state
        validate_bound_popup_weapon_references(data)
        validate_active_modification_references(conn, row['id'], data)
        persist_character_item_instances(
            conn, row['id'], data, 'cyberweapon_action', source_ref=reason, prune=True)
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='item_action')
        now = time.time()
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id, 'result': result,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    @atomic_endpoint
    def api_character_defense_sequencer_resolve(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {'revision', 'armor_instance_id', 'not_used_in_netrun_confirmed',
                   'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Defense Sequencer resolution содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        if (body or {}).get('not_used_in_netrun_confirmed') is not True:
            raise ApiError(
                400, 'Подтвердите, что выбранная Armor не использовалась в этом Netrun')
        deck_id, hardware_id = str(m.group(2)).lower(), str(m.group(3)).lower()
        armor_id = str((body or {}).get('armor_instance_id') or '').lower()
        if not INSTANCE_ID_RE.fullmatch(armor_id):
            raise ApiError(400, 'Выберите concrete Armor Program instance')
        detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(detail) < 3:
            raise ApiError(400, 'Укажите причину Defense Sequencer resolution')
        modifications = character_modifications(conn, row['id'])
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        now = time.time()
        resolved = resolve_defense_sequencer_trigger(
            data, modifications, deck_id, hardware_id, armor_id, now=now)
        validate_active_modification_references(conn, row['id'], data)
        reason = (f'Defense Sequencer Rez {resolved["armor_name"]} at REZ '
                  f'{resolved["rez_current"]}: {detail}; '
                  'not-used-in-this-Netrun eligibility confirmed manually')
        persist_character_item_instances(
            conn, row['id'], data, 'defense_sequencer', source_ref=reason, prune=True)
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='item_action')
        ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                  (ledger_id,)).fetchone()
        delta = parse_json_object(ledger_row['delta_json'])
        delta.update({
            'defense_sequencer_resolution': True,
            'manual_eligibility_confirmed': True,
            'resolved_armor_instance_id': armor_id,
        })
        conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                     (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id, 'resolved': resolved,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    def api_character_downtime(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1), allow_gm=True)
        data = ensure_progression(json.loads(row['data']))
        self.send_json(downtime_payload(data, conn=conn))

    @atomic_endpoint
    def api_character_downtime_action(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1), allow_gm=True)
        allowed = {'revision', 'action', 'activity_id', 'earned', 'hp', 'note'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Downtime action содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        action = str((body or {}).get('action') or '').strip().lower()
        if action not in ('resolve', 'complete', 'abandon'):
            raise ApiError(400, 'Downtime action: resolve/complete/abandon')
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        state = downtime_state(data)
        active = state.get('active') if isinstance(state.get('active'), dict) else None
        if not active:
            raise ApiError(409, 'Нет активного Downtime')
        note = str((body or {}).get('note') or '').strip()[:1000]
        reason = None
        if action == 'resolve':
            activity_id = str((body or {}).get('activity_id') or '').strip().lower()
            activity = next((item for item in active.get('activities') or []
                             if item.get('id') == activity_id), None)
            if not activity:
                raise ApiError(404, 'Downtime activity не найдена')
            if activity.get('resolved'):
                raise ApiError(409, 'Downtime activity уже отмечена выполненной')
            catalog = DOWNTIME_ACTIVITY_BY_ID[activity_id]
            kind = catalog['kind']
            if kind == 'hustle':
                try:
                    earned = max(0.0, min(9_999_999.0, float((body or {}).get('earned') or 0)))
                except (TypeError, ValueError):
                    raise ApiError(400, 'Некорректная сумма Hustle')
                cash = float(data.get('cash') or 0)
                if not math.isfinite(cash) or cash + earned > 9_999_999:
                    raise ApiError(400, 'Слишком большая сумма')
                data['cash'] = round(cash + earned, 2)
                resolution_note = note or f'Hustle: +€$ {earned:,.0f} (manual roll)'
                reason = f'Downtime Hustle: +€$ {earned:,.0f}'
            elif kind == 'recover_hp':
                try:
                    hp = max(0, min(1000, int((body or {}).get('hp') or 0)))
                except (TypeError, ValueError):
                    raise ApiError(400, 'Некорректное восстановление HP')
                derived = derive(data)
                hp_max = _num(derived.get('hp_max')) or _num(data.get('hp_cur')) or 0
                hp_cur = _num(data.get('hp_cur'))
                if hp_cur is not None and hp_max:
                    data['hp_cur'] = min(hp_max, hp_cur + hp)
                elif hp_cur is not None:
                    data['hp_cur'] = hp_cur + hp
                else:
                    data['hp_cur'] = hp
                resolution_note = note or f'Recover HP: +{hp}'
                reason = f'Downtime Recover HP: +{hp}'
            else:
                resolution_note = note or 'Resolved at the table'
                reason = f'Downtime activity resolved: {catalog["label_ru"]}'
            activity['resolved'] = True
            activity['resolution_note'] = resolution_note
            revision_after = current_revision + 1
            persist_character_item_instances(conn, row['id'], data, 'downtime_resolve',
                                             source_ref=reason)
            ledger_id = record_character_change_set(
                conn, row['id'], user['id'], before, data, reason,
                current_revision, revision_after, category='downtime')
            ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                      (ledger_id,)).fetchone()
            delta = parse_json_object(ledger_row['delta_json'])
            delta['revertible'] = False
            conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                         (json.dumps(delta, ensure_ascii=False), ledger_id))
        elif action == 'complete':
            summary = str(note or 'Downtime completed').strip()[:1000]
            active['completed_at'] = time.time()
            active['summary'] = summary
            state['history'].append(active)
            state['history'] = state['history'][-50:]
            state['active'] = None
            reason = f'Downtime completed: {summary}'
            revision_after = current_revision + 1
            persist_character_item_instances(conn, row['id'], data, 'downtime_complete',
                                             source_ref=reason)
            ledger_id = record_character_change_set(
                conn, row['id'], user['id'], before, data, reason,
                current_revision, revision_after, category='downtime')
            ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                      (ledger_id,)).fetchone()
            delta = parse_json_object(ledger_row['delta_json'])
            delta['revertible'] = False
            conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                         (json.dumps(delta, ensure_ascii=False), ledger_id))
        else:  # abandon
            summary = str(note or 'Downtime abandoned').strip()[:1000]
            active['completed_at'] = time.time()
            active['summary'] = summary
            state['history'].append(active)
            state['history'] = state['history'][-50:]
            state['active'] = None
            reason = f'Downtime abandoned: {summary}'
            revision_after = current_revision + 1
            persist_character_item_instances(conn, row['id'], data, 'downtime_abandon',
                                             source_ref=reason)
            ledger_id = record_character_change_set(
                conn, row['id'], user['id'], before, data, reason,
                current_revision, revision_after, category='downtime')
            ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                      (ledger_id,)).fetchone()
            delta = parse_json_object(ledger_row['delta_json'])
            delta['revertible'] = False
            conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                         (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), time.time(),
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({'ok': True, 'action': action,
                        'downtime': downtime_payload(
                            ensure_progression(json.loads(fresh['data'])), conn=conn)})

    @atomic_endpoint
    def api_character_downtime_start(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1), allow_gm=True)
        allowed = {'revision', 'duration_key', 'activities', 'note'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Downtime start содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        state = downtime_state(data)
        if isinstance(state.get('active'), dict):
            raise ApiError(409, 'Downtime уже активен')
        duration_key = str((body or {}).get('duration_key') or '') or None
        duration_label = None
        if duration_key:
            duration = campaign_duration_seconds(duration_key)
            if duration is None:
                raise ApiError(400, 'Неизвестная длительность Downtime')
            duration_label = CAMPAIGN_DURATION_LABELS.get(duration_key)
        activities = clean_downtime_activities((body or {}).get('activities'))
        note = str((body or {}).get('note') or '').strip()[:1000]
        now = time.time()
        campaign_started = campaign_now(conn)
        active = {
            'downtime_id': secrets.token_hex(16),
            'started_at': now,
            'campaign_started_at': campaign_started,
            'campaign_due_at': campaign_started + duration if duration_key else None,
            'duration_key': duration_key,
            'duration_label': duration_label,
            'note': note,
            'created_by': user['id'],
            'activities': activities,
        }
        state['active'] = active
        reason = f'Downtime started: {note or duration_key or "manual"}'
        persist_character_item_instances(conn, row['id'], data, 'downtime_start',
                                         source_ref=reason)
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='downtime')
        ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                  (ledger_id,)).fetchone()
        delta = parse_json_object(ledger_row['delta_json'])
        delta['revertible'] = False
        conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                     (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now, revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({'ok': True, 'downtime': downtime_payload(
            ensure_progression(json.loads(fresh['data'])), conn=conn)}, status=201)

    @atomic_endpoint
    def api_character_effect_action(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1), allow_gm=True)
        if set(body or {}) - {'revision', 'action'}:
            raise ApiError(400, 'Effect action содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        expected_revision = _num((body or {}).get('revision'))
        if expected_revision is None or expected_revision != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        effect_id = str(m.group(2)).lower()
        raw = conn.execute(
            'SELECT e.*,u.display_name actor FROM active_effect_instances e '
            'JOIN users u ON u.id=e.created_by WHERE e.effect_id=? AND e.character_id=?',
            (effect_id, row['id'])).fetchone()
        if not raw:
            raise ApiError(404, 'Effect instance не найден')
        before = effect_instance_payload(raw)
        if before.get('archived_at'):
            raise ApiError(409, 'Effect instance уже архивирован')
        action = str((body or {}).get('action') or '').strip().lower()
        if action not in ACTIVE_EFFECT_ACTIONS | {'archive'}:
            raise ApiError(400, 'Неизвестное действие с эффектом')
        now = time.time()
        if action == 'disable':
            if not before['active']:
                raise ApiError(409, 'Эффект уже отключён')
            conn.execute('UPDATE active_effect_instances SET active=0,updated=? WHERE effect_id=?',
                         (now, effect_id))
            reason = f'Disable effect {before["label"]}'
        elif action == 'enable':
            if before['duration_type'] == 'real_time' and before.get('expires_at', 0) <= now:
                raise ApiError(409, 'Истёкший real-time эффект нельзя включить повторно')
            if before['duration_type'] == 'rounds' and (_num(before.get('remaining_rounds')) or 0) <= 0:
                raise ApiError(409, 'Завершённый round effect нельзя включить повторно')
            if before['active']:
                raise ApiError(409, 'Эффект уже включён')
            conn.execute('UPDATE active_effect_instances SET active=1,updated=? WHERE effect_id=?',
                         (now, effect_id))
            reason = f'Enable effect {before["label"]}'
        elif action == 'tick':
            if before['duration_type'] != 'rounds':
                raise ApiError(400, 'Tick доступен только для round effect')
            if before['status'] != 'active':
                raise ApiError(409, 'Round effect сейчас не активен')
            remaining = max(0, (_num(before.get('remaining_rounds')) or 0) - 1)
            conn.execute(
                'UPDATE active_effect_instances SET remaining_rounds=?,active=?,updated=? '
                'WHERE effect_id=?', (remaining, 1 if remaining else 0, now, effect_id))
            reason = f'Advance effect round {before["label"]}: {remaining} remaining'
        else:
            conn.execute(
                'UPDATE active_effect_instances SET active=0,archived_at=?,updated=? '
                'WHERE effect_id=?', (now, now, effect_id))
            reason = f'Archive effect {before["label"]}'
        after_row = conn.execute(
            'SELECT e.*,u.display_name actor FROM active_effect_instances e '
            'JOIN users u ON u.id=e.created_by WHERE e.effect_id=?',
            (effect_id,)).fetchone()
        after = effect_instance_payload(after_row, now)
        revision_after = current_revision + 1
        record_effect_change(
            conn, row['id'], user['id'], effect_id, before['label'], before, after,
            reason, current_revision, revision_after)
        conn.execute('UPDATE characters SET updated=?,revision=? WHERE id=?',
                     (now, revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'effect': after,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    @atomic_endpoint
    def api_character_effect_create(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        current_revision = _row_value(row, 'revision', 0) or 0
        expected_revision = _num((body or {}).get('revision'))
        if expected_revision is None or expected_revision != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        effect_id = secrets.token_hex(16)
        clean = clean_custom_effect(body or {}, effect_id)
        now = time.time()
        conn.execute(
            'INSERT INTO active_effect_instances(effect_id,character_id,source_type,label,'
            'definition_json,duration_type,started_at,expires_at,remaining_rounds,active,'
            'created_by,reason,created,updated) VALUES(?,?,?,?,?,?,?,?,?,1,?,?,?,?)',
            (effect_id, row['id'], 'custom', clean['label'],
             json.dumps(clean['definition'], ensure_ascii=False), clean['duration_type'],
             now, clean['expires_at'], clean['remaining_rounds'], user['id'],
             clean['reason'], now, now))
        created_row = conn.execute(
            'SELECT e.*,u.display_name actor FROM active_effect_instances e '
            'JOIN users u ON u.id=e.created_by WHERE e.effect_id=?',
            (effect_id,)).fetchone()
        created = effect_instance_payload(created_row, now)
        revision_after = current_revision + 1
        record_effect_change(
            conn, row['id'], user['id'], effect_id, clean['label'], None, created,
            clean['reason'], current_revision, revision_after)
        conn.execute('UPDATE characters SET updated=?,revision=? WHERE id=?',
                     (now, revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'effect': created,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        }, status=201)

    def api_character_effects(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1), allow_gm=True)
        self.send_json({
            'character_id': row['id'], 'revision': _row_value(row, 'revision', 0) or 0,
            'effects': character_effect_instances(conn, row['id']),
        })

    @atomic_endpoint
    def api_character_import(self, conn, qs, m, body):
        u = self.require_user(conn)
        raw = (body or {}).get('data')
        if raw is None:
            raw = (body or {})
        data = canonical_import_character(raw)
        owned_rows = conn.execute('SELECT data FROM characters WHERE owner_id=?',
                                  (u['id'],)).fetchall()
        count = sum(1 for item in owned_rows if not parse_json_object(item['data']).get('archived'))
        if count >= 50:
            raise ApiError(400, 'Слишком много персонажей (максимум 50)')
        now = time.time()
        cur = conn.execute(
            'INSERT INTO characters(owner_id, public, data, created, updated) VALUES(?,?,?,?,?)',
            (u['id'], 0, json.dumps(data, ensure_ascii=False), now, now))
        persist_character_item_instances(
            conn, cur.lastrowid, data, 'character_import', acquired_at=now, prune=True)
        record_character_changes(conn, cur.lastrowid, u['id'], {}, data,
                                 'Character imported from JSON')
        conn.commit()
        row = conn.execute('SELECT * FROM characters WHERE id=?', (cur.lastrowid,)).fetchone()
        self.send_json(self.char_payload(row, u['display_name'], conn=conn), status=201)

    @atomic_endpoint
    def api_character_improve(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        data = ensure_progression(json.loads(row['data']))
        kind = str((body or {}).get('kind') or '')
        subject = str((body or {}).get('subject') or '').strip()
        before = data['ip_available']; cost = 0; reason = ''
        if kind == 'skill':
            base = skill_base(subject)
            if not base or base in SPECIALIZED_SKILLS or subject != base:
                raise ApiError(400, 'Для специализированного навыка повышайте parent-pool')
            current = _num((data.get('skills') or {}).get(subject)) or 0
            if current >= 10: raise ApiError(400, 'Skill уже достиг Level 10')
            target = current + 1; cost = target * (40 if SKILL_BY_NAME[base][3] else 20)
            data.setdefault('skills', {})[subject] = target
            reason = f'{subject} {current} → {target}'
        elif kind == 'parent':
            if subject not in SPECIALIZED_SKILLS:
                raise ApiError(400, 'Неизвестный parent Skill')
            pools = data.setdefault('skill_pools', {})
            current = _num(pools.get(subject)) or 0; target = current + 1
            cost = target * (40 if SKILL_BY_NAME[subject][3] else 20)
            pools[subject] = target; reason = f'{subject} Pool {current} → {target}'
        elif kind == 'activate_role':
            if subject not in ROLES or not any(item.get('name') == subject for item in data['roles']):
                raise ApiError(400, 'Role не принадлежит персонажу')
            active = next((item for item in data['roles'] if item.get('name') == data.get('active_role')), None)
            if active and (_num(active.get('rank')) or 0) < 4:
                raise ApiError(400, 'Active Role должна достичь Rank 4 перед переключением')
            previous = data.get('active_role'); data['active_role'] = subject
            reason = f'Active Role: {previous} → {subject}'
        elif kind == 'role':
            if subject not in ROLES: raise ApiError(400, 'Неизвестная Role')
            roles = data['roles']; existing = next((item for item in roles if item.get('name') == subject), None)
            active = next((item for item in roles if item.get('name') == data.get('active_role')), None)
            if existing:
                if subject != data.get('active_role'): raise ApiError(400, 'Повышать можно только active Role')
                current = _num(existing.get('rank')) or 0
                if current >= 10: raise ApiError(400, 'Role Ability уже достигла Rank 10')
                target = current + 1; cost = target * 60; existing['rank'] = target
                if isinstance((body or {}).get('setup'), dict): existing['setup'] = body['setup']
                validate_role_rank_setup(subject, target, existing.get('setup') or {})
                reason = f'{subject} {current} → {target}'
            else:
                if active and (_num(active.get('rank')) or 0) < 4:
                    raise ApiError(400, 'Active Role должна достичь Rank 4 перед multiclass')
                cost = 60
                setup = dict((body or {}).get('setup') or {})
                validate_role_rank_setup(subject, 1, setup)
                roles.append({'name': subject, 'rank': 1, 'setup': setup, 'primary': False})
                data['active_role'] = subject; reason = f'New Role: {subject} 1'
        else:
            raise ApiError(400, 'Неизвестный тип улучшения')
        if before < cost: raise ApiError(400, f'Недостаточно IP: требуется {cost}')
        data['ip_available'] = before - cost; data['ip_total_spent'] += cost
        self.add_ip_ledger(conn, row['id'], user['id'], -cost, before,
                           data['ip_available'], 'improvement', subject, reason)
        self.send_json(self.save_character_data(conn, row, data, user['id'], reason))

    @atomic_endpoint
    def api_character_ip(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = self.get_char(conn, m.group(1))
        if parse_json_object(row['data']).get('archived'):
            raise ApiError(409, 'Архивное досье доступно только для чтения')
        data = ensure_progression(json.loads(row['data']))
        amount = _num((body or {}).get('amount')) or 0
        reason = str((body or {}).get('reason') or '').strip()
        if not amount or abs(amount) > 10_000 or not reason:
            raise ApiError(400, 'Укажите ненулевое изменение IP и причину')
        before = data['ip_available']; after = before + amount
        if after < 0:
            raise ApiError(400, 'Баланс IP не может быть отрицательным')
        data['ip_available'] = after
        if amount > 0: data['ip_total_earned'] += amount
        self.add_ip_ledger(conn, row['id'], user['id'], amount, before, after,
                           'adjustment', None, reason)
        self.send_json(self.save_character_data(conn, row, data, user['id'], reason))

    def api_character_ip_history(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1), allow_gm=True)
        rows = conn.execute('SELECT l.*,u.display_name actor FROM ip_ledger l JOIN users u ON u.id=l.actor_id WHERE character_id=? ORDER BY id DESC LIMIT 500',
                            (row['id'],)).fetchall()
        self.send_json({'entries': [dict(item) for item in rows]})

    @atomic_endpoint
    def api_character_item_action(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        expected_revision = _num((body or {}).get('revision'))
        current_revision = _row_value(row, 'revision', 0) or 0
        if expected_revision is None or expected_revision != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        instance_id = str(m.group(2)).lower()
        index = next((position for position, entry in enumerate(data.get('inventory') or [])
                      if isinstance(entry, dict) and entry.get('instance_id') == instance_id), None)
        if index is None:
            raise ApiError(404, 'Экземпляр предмета не найден')
        entry = data['inventory'][index]
        catalog_item = item_by_id(catalog_item_id_for_entry(entry))
        interaction = catalog_interaction_data(catalog_item)
        action = str((body or {}).get('action') or '').strip().lower()
        display_name = str(entry.get('custom_name') or entry.get('name') or 'Item')
        effect = None
        use_effect_result = {'created': [], 'replaced_effect_ids': [], 'manual_rules': []}

        if action == 'use':
            if not interaction.get('consumable'):
                raise ApiError(400, 'Этот предмет не является расходником')
            if entry.get('state') in ('stored', 'broken', 'consumed'):
                raise ApiError(409, 'Расходник должен быть исправен и находиться при персонаже')
            try:
                uses = max(1, min(99, int((body or {}).get('amount') or 1)))
            except (TypeError, ValueError):
                raise ApiError(400, 'Некорректное количество')
            consume_amount = max(1, int(interaction.get('consume_amount') or 1))
            spent = uses * consume_amount
            quantity = max(1, int(entry.get('qty') or 1))
            if spent > quantity:
                raise ApiError(400, 'Недостаточно единиц расходника')
            remaining = quantity - spent
            if remaining:
                entry['qty'] = remaining
            else:
                data['inventory'].pop(index)
            effect = copy.deepcopy(interaction.get('use_effect'))
            reason = f'Use {display_name} ×{spent}'
            use_effect_result = instantiate_consumable_effects(
                conn, row['id'], user['id'], entry)
        elif action == 'equip':
            if not interaction.get('equippable'):
                raise ApiError(400, 'Этот предмет нельзя экипировать')
            if entry.get('state') != 'carried':
                raise ApiError(409, 'Экипировать можно только carried предмет')
            modes = interaction.get('equip_modes') or ['ready']
            mode = str((body or {}).get('mode') or modes[0])
            if mode not in modes:
                raise ApiError(400, 'Недопустимый режим экипировки')
            hands_required = max(0, int(interaction.get('hands_required') or 0)) if mode == 'held' else 0
            occupied_hands = 0
            for equipped in data.get('inventory') or []:
                if (not isinstance(equipped, dict) or equipped.get('state') != 'equipped' or
                        equipped.get('equipped_mode') != 'held'):
                    continue
                equipped_item = item_by_id(catalog_item_id_for_entry(equipped))
                occupied_hands += max(0, int((equipped_item or {}).get('hands_required') or 0))
            shoulder_mounts = sum(
                1 for chrome in data.get('cyberware') or []
                if isinstance(chrome, dict) and chrome.get('state') == 'installed' and
                str(chrome.get('name') or '').lower() == 'artificial shoulder mount')
            available_hands = 2 + shoulder_mounts * 2
            if occupied_hands + hands_required > available_hands:
                raise ApiError(409, 'Недостаточно свободных рук для экипировки')
            limit = _num(interaction.get('equip_limit'))
            if limit is not None:
                equipped_count = sum(
                    1 for owned in data.get('inventory') or []
                    if isinstance(owned, dict) and owned.get('state') == 'equipped' and
                    catalog_item_id_for_entry(owned) == catalog_item_id_for_entry(entry))
                if equipped_count >= limit:
                    raise ApiError(409, 'Достигнут лимит экипированных копий')
            slots = interaction.get('equip_slots') or []
            slot_defaults = {'held': 'hand', 'worn': 'ear', 'ready': 'belt',
                             'workspace': 'workspace', 'mounted': 'weapon'}
            slot = str((body or {}).get('slot') or slot_defaults.get(mode) or (slots[0] if slots else 'other'))
            if slots and slot not in slots:
                raise ApiError(400, 'Недопустимый слот экипировки')
            entry.update({
                'state': 'equipped', 'equipped_mode': mode, 'equipped_slot': slot,
                'active': not bool(interaction.get('activation_required')),
            })
            reason = f'Equip {display_name} ({mode})'
        elif action == 'unequip':
            if entry.get('state') != 'equipped':
                raise ApiError(409, 'Предмет не экипирован')
            entry['state'] = 'carried'
            for key in ('active', 'equipped_mode', 'equipped_slot', 'host_instance_id'):
                entry.pop(key, None)
            reason = f'Unequip {display_name}'
        elif action in ('activate', 'deactivate'):
            if not interaction.get('equippable') or not interaction.get('activation_required'):
                raise ApiError(400, 'Предмет не поддерживает включение и выключение')
            if entry.get('state') != 'equipped':
                raise ApiError(409, 'Сначала экипируйте предмет')
            active = action == 'activate'
            if bool(entry.get('active')) == active:
                raise ApiError(409, 'Предмет уже находится в выбранном состоянии')
            entry['active'] = active
            reason = f'{"Activate" if active else "Deactivate"} {display_name}'
        else:
            raise ApiError(400, 'Неизвестное действие с предметом')

        revision_after = current_revision + 1
        persist_character_item_instances(
            conn, row['id'], data, 'item_action', source_ref=reason, prune=True)
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='item_action')
        if use_effect_result['created']:
            ledger_row = conn.execute(
                'SELECT delta_json FROM character_ledger WHERE id=?', (ledger_id,)).fetchone()
            delta = parse_json_object(ledger_row['delta_json'])
            delta['created_effect_ids'] = [item['effect_id'] for item in use_effect_result['created']]
            delta['replaced_effect_ids'] = use_effect_result['replaced_effect_ids']
            delta['manual_rules'] = use_effect_result['manual_rules']
            for created_effect in use_effect_result['created']:
                definition = created_effect.get('definition') or {}
                delta.setdefault('changes', []).append({
                    'path': f'effects.instances.{created_effect["effect_id"]}',
                    'label': f'Effect: {created_effect["label"]}', 'kind': 'added',
                    'before': '—',
                    'after': readable_change_value({
                        'status': created_effect.get('status'),
                        'target': definition.get('target'),
                        'operation': definition.get('operation'),
                        'value': definition.get('value'),
                        'duration': created_effect.get('duration_type'),
                    }),
                })
            delta['change_count'] = len(delta.get('changes') or [])
            conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                         (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute(
            'UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
            (json.dumps(data, ensure_ascii=False), time.time(), revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ok': True, 'action': action, 'message': reason, 'effect': effect,
            'created_effects': use_effect_result['created'],
            'manual_rules': use_effect_result['manual_rules'],
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    @atomic_endpoint
    def api_character_item_transfer(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1), allow_gm=True)
        allowed = {'revision', 'action', 'to_char_id', 'to_instance_id',
                   'to_revision', 'quantity', 'notes'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Item transfer содержит неподдерживаемые поля')
        action = str((body or {}).get('action') or '').strip().lower()
        if action not in TRANSFER_KINDS:
            raise ApiError(400, 'Неизвестный тип передачи предмета')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        instance_id = str(m.group(2)).lower()
        if not INSTANCE_ID_RE.fullmatch(instance_id):
            raise ApiError(400, 'Некорректный идентификатор предмета')
        notes = str((body or {}).get('notes') or '').strip()[:500]
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        sides = []

        def load_side(target_row):
            target_before = enrich_owned_item_interactions(
                ensure_progression(json.loads(target_row['data'])))
            return target_before, copy.deepcopy(target_before)

        def parse_qty():
            raw = (body or {}).get('quantity')
            if raw is None:
                return None
            try:
                return max(1, int(raw))
            except (TypeError, ValueError):
                raise ApiError(400, 'Некорректное количество')

        def move(source_data, source_row_id, target_instance_id, qty, dest,
                 loan_ok=False, force_unequip=False):
            """Move one instance out of ``source_data`` into stash or a character.

            ``dest`` is ``('stash',)`` or ``('char', target_data, target_char_id)``.
            Returns ``(moved_instance_id, moved_qty, name)``.
            """
            index, entry = _inventory_entry(source_data, target_instance_id)
            if index is None:
                raise ApiError(404, 'Экземпляр предмета не найден')
            if force_unequip and entry.get('state') in ('equipped', 'installed'):
                entry['state'] = 'carried'
                for key in ('equipped_mode', 'equipped_slot', 'active',
                            'host_instance_id', 'host_instances'):
                    entry.pop(key, None)
            loan = active_loan_for_instance(conn, target_instance_id)
            _transferable_item_error(conn, source_row_id, entry, source_data,
                                     loan, loan_ok=loan_ok)
            full_qty = max(1, int(entry.get('qty') or 1))
            qty = full_qty if qty is None else int(qty)
            if qty <= 0 or qty > full_qty:
                raise ApiError(400, 'Некорректное количество для передачи')
            if not item_entry_stackable(entry) and qty > 1:
                raise ApiError(400, 'Этот предмет передаётся поштучно (не stackable)')
            name = _character_item_name(entry)
            partial = qty < full_qty
            if partial:
                remaining, taken = _split_stack(entry, qty)
                source_data['inventory'][index] = remaining
                moved_id = new_item_instance_id()
                taken['instance_id'] = moved_id
            else:
                source_data['inventory'].pop(index)
                taken = entry
                moved_id = target_instance_id
                _detach_runtime_state(source_data, taken, target_instance_id)
                _detach_tech_maker_modifications(source_data, taken, target_instance_id)
                # Rehome the relational row now so persist never regenerates the
                # stable instance_id across characters.
                if dest[0] == 'stash':
                    conn.execute('DELETE FROM item_instances WHERE instance_id=?',
                                 (moved_id,))
                else:
                    conn.execute(
                        'UPDATE item_instances SET character_id=? WHERE instance_id=?',
                        (dest[2], moved_id))
            if dest[0] == 'stash':
                cleaned = _prepare_entry_for_holder(taken, 'stash')
                cleaned['instance_id'] = moved_id
                now = time.time()
                conn.execute(
                    'INSERT INTO crew_stash(instance_id,catalog_item_id,custom_name,'
                    'state,quantity,notes,stored_at,data_json,created,updated) '
                    'VALUES(?,?,?,?,?,?,?,?,?,?)',
                    (moved_id, catalog_item_id_for_entry(taken),
                     str(cleaned.get('custom_name') or '')[:120] or None, 'stored',
                     cleaned['qty'], '', now, json.dumps(cleaned, ensure_ascii=False),
                     now, now))
            else:
                target_data = dest[1]
                if len(target_data.get('inventory') or []) + 1 > 500:
                    raise ApiError(400, 'Инвентарь получателя переполнен')
                cleaned = _prepare_entry_for_holder(taken, 'char')
                cleaned['instance_id'] = moved_id
                _attach_runtime_state(target_data, cleaned, moved_id)
                _attach_tech_maker_modifications(target_data, cleaned)
                target_data.setdefault('inventory', []).append(cleaned)
            return moved_id, qty, name

        message = ''
        if action == 'split':
            index, entry = _inventory_entry(data, instance_id)
            if index is None:
                raise ApiError(404, 'Экземпляр предмета не найден')
            if not item_entry_stackable(entry):
                raise ApiError(400, 'Делить можно только stackable предметы')
            loan = active_loan_for_instance(conn, instance_id)
            if loan is not None and loan['borrower_character_id'] == row['id']:
                raise ApiError(409, 'Предмет взят в долг — его нельзя делить')
            full_qty = max(1, int(entry.get('qty') or 1))
            try:
                take_qty = max(1, int((body or {}).get('quantity') or 0))
            except (TypeError, ValueError):
                raise ApiError(400, 'Некорректное количество')
            if take_qty >= full_qty:
                raise ApiError(400, 'Для разделения укажите количество меньше размера стека')
            remaining, taken = _split_stack(entry, take_qty)
            data['inventory'][index] = remaining
            new_id = new_item_instance_id()
            taken['instance_id'] = new_id
            data['inventory'].append(taken)
            message = f'Split {_character_item_name(entry)} ×{take_qty}'
            _record_item_transfer(
                conn, new_id, 'split', user['id'], notes,
                from_character_id=row['id'], to_character_id=row['id'],
                from_bucket='inventory', to_bucket='inventory', quantity=take_qty)
            sides.append({'id': row['id'], 'before': before, 'data': data, 'reason': message})
        elif action == 'stash':
            moved_id, qty, name = move(data, row['id'], instance_id, parse_qty(), ('stash',))
            message = f'Move {name} ×{qty} to Crew Stash'
            _record_item_transfer(
                conn, moved_id, 'stash', user['id'], notes,
                from_character_id=row['id'], to_character_id=None,
                from_bucket='inventory', to_bucket='stash', quantity=qty)
            sides.append({'id': row['id'], 'before': before, 'data': data, 'reason': message})
        elif action in ('give', 'loan'):
            to_char_id = _num((body or {}).get('to_char_id'))
            if not to_char_id:
                raise ApiError(400, 'Укажите получателя (to_char_id)')
            target_row = self.get_char(conn, to_char_id)
            if target_row['id'] == row['id']:
                raise ApiError(400, 'Нельзя передать предмет самому себе')
            if parse_json_object(target_row['data']).get('archived'):
                raise ApiError(409, 'Досье получателя заархивировано')
            target_before, target_data = load_side(target_row)
            moved_id, qty, name = move(data, row['id'], instance_id, parse_qty(),
                                       ('char', target_data, target_row['id']))
            if action == 'loan':
                conn.execute(
                    'INSERT INTO item_loans(loan_id,instance_id,owner_character_id,'
                    'borrower_character_id,quantity,loaned_by,loaned_at,notes) '
                    'VALUES(?,?,?,?,?,?,?,?)',
                    (secrets.token_hex(16), moved_id, row['id'], target_row['id'], qty,
                     user['id'], time.time(), notes))
            message = f'{"Loan" if action == "loan" else "Give"} {name} ×{qty}'
            _record_item_transfer(
                conn, moved_id, action, user['id'], notes,
                from_character_id=row['id'], to_character_id=target_row['id'],
                from_bucket='inventory', to_bucket='inventory', quantity=qty)
            sides.append({'id': row['id'], 'before': before, 'data': data, 'reason': message})
            sides.append({'id': target_row['id'], 'before': target_before,
                          'data': target_data, 'reason': message})
        elif action == 'return':
            loan = active_loan_for_instance(conn, instance_id)
            if not loan or loan['borrower_character_id'] != row['id']:
                raise ApiError(409, 'Предмет не числится за вами как долг')
            owner_row = self.get_char(conn, loan['owner_character_id'])
            if parse_json_object(owner_row['data']).get('archived'):
                raise ApiError(409, 'Досье владельца заархивировано')
            owner_before, owner_data = load_side(owner_row)
            moved_id, qty, name = move(data, row['id'], instance_id, None,
                                       ('char', owner_data, owner_row['id']), loan_ok=True)
            conn.execute('UPDATE item_loans SET returned_at=?,returned_by=? WHERE loan_id=?',
                         (time.time(), user['id'], loan['loan_id']))
            message = f'Return {name} ×{qty} to owner'
            _record_item_transfer(
                conn, moved_id, 'return', user['id'], notes,
                from_character_id=row['id'], to_character_id=owner_row['id'],
                from_bucket='inventory', to_bucket='inventory', quantity=qty)
            sides.append({'id': row['id'], 'before': before, 'data': data, 'reason': message})
            sides.append({'id': owner_row['id'], 'before': owner_before,
                          'data': owner_data, 'reason': message})
        elif action == 'recall':
            loan = active_loan_for_instance(conn, instance_id)
            if not loan or loan['owner_character_id'] != row['id']:
                raise ApiError(409, 'Предмет не числится как выданный вами в долг')
            borrower_row = self.get_char(conn, loan['borrower_character_id'])
            borrower_before, borrower_data = load_side(borrower_row)
            moved_id, qty, name = move(borrower_data, borrower_row['id'], instance_id,
                                       None, ('char', data, row['id']), loan_ok=True,
                                       force_unequip=True)
            conn.execute('UPDATE item_loans SET returned_at=?,returned_by=? WHERE loan_id=?',
                         (time.time(), user['id'], loan['loan_id']))
            message = f'Recall {name} ×{qty} from borrower'
            _record_item_transfer(
                conn, moved_id, 'recall', user['id'], notes,
                from_character_id=borrower_row['id'], to_character_id=row['id'],
                from_bucket='inventory', to_bucket='inventory', quantity=qty)
            # The losing side must persist first so the stable instance_id is freed.
            sides.append({'id': borrower_row['id'], 'before': borrower_before,
                          'data': borrower_data, 'reason': message})
            sides.append({'id': row['id'], 'before': before, 'data': data, 'reason': message})
        elif action == 'trade':
            to_char_id = _num((body or {}).get('to_char_id'))
            to_instance_id = str((body or {}).get('to_instance_id') or '').lower()
            if not to_char_id:
                raise ApiError(400, 'Укажите партнёра обмена (to_char_id)')
            if not INSTANCE_ID_RE.fullmatch(to_instance_id):
                raise ApiError(400, 'Укажите предмет партнёра (to_instance_id)')
            if to_instance_id == instance_id:
                raise ApiError(400, 'Нельзя обменять предмет на самого себя')
            target_row = self.get_char(conn, to_char_id)
            if target_row['id'] == row['id']:
                raise ApiError(400, 'Нельзя обменяться с самим собой')
            if parse_json_object(target_row['data']).get('archived'):
                raise ApiError(409, 'Досье партнёра заархивировано')
            target_revision = _row_value(target_row, 'revision', 0) or 0
            if _num((body or {}).get('to_revision')) != target_revision:
                raise ApiError(409, 'Dossier партнёра изменён в другой вкладке; обновите страницу')
            target_before, target_data = load_side(target_row)
            moved_id, qty, name = move(data, row['id'], instance_id, None,
                                       ('char', target_data, target_row['id']))
            other_id, other_qty, other_name = move(
                target_data, target_row['id'], to_instance_id, None,
                ('char', data, row['id']))
            message = f'Trade {name} ↔ {other_name}'
            _record_item_transfer(
                conn, moved_id, 'trade', user['id'], notes,
                from_character_id=row['id'], to_character_id=target_row['id'],
                from_bucket='inventory', to_bucket='inventory', quantity=qty)
            _record_item_transfer(
                conn, other_id, 'trade', user['id'], notes,
                from_character_id=target_row['id'], to_character_id=row['id'],
                from_bucket='inventory', to_bucket='inventory', quantity=other_qty)
            sides.append({'id': row['id'], 'before': before, 'data': data, 'reason': message})
            sides.append({'id': target_row['id'], 'before': target_before,
                          'data': target_data, 'reason': message})

        if not sides:
            raise ApiError(400, 'Неизвестный тип передачи предмета')
        for side in sides:
            _persist_transfer_side(conn, side['id'], side['data'],
                                   'item_transfer', side['reason'])
            side_row = self.get_char(conn, side['id'])
            revision = _row_value(side_row, 'revision', 0) or 0
            _record_transfer_ledger(conn, side['id'], user['id'], side['before'],
                                    side['data'], side['reason'], revision, revision + 1)
            conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                         (json.dumps(side['data'], ensure_ascii=False), time.time(),
                          revision + 1, side['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({'ok': True, 'action': action, 'message': message,
                        'character': self.char_payload(fresh, fresh['owner'], conn=conn)})

    def api_character_items(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1), allow_gm=True)
        instances = conn.execute(
            'SELECT * FROM item_instances WHERE character_id=? '
            'ORDER BY bucket,acquired_at,instance_id', (row['id'],)).fetchall()
        payload = []
        for instance in instances:
            item = dict(instance)
            item['item'] = parse_json_object(item.pop('data_json'))
            payload.append(item)
        self.send_json({'character_id': row['id'], 'instances': payload})

    def api_character_ledger(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1), allow_gm=True)
        current_revision = _row_value(row, 'revision', 0) or 0
        entries = conn.execute(
            'SELECT l.*,u.display_name actor FROM character_ledger l '
            'JOIN users u ON u.id=l.actor_user_id WHERE character_id=? '
            'ORDER BY l.id DESC LIMIT 500', (row['id'],)).fetchall()
        payload = []
        for raw in entries:
            item = dict(raw)
            delta = parse_json_object(item.get('delta_json'))
            item['delta'] = delta
            item['changes'] = delta.get('changes') if isinstance(delta.get('changes'), list) else []
            item['can_revert'] = bool(
                delta.get('revertible') and
                _num(delta.get('revision_after')) == current_revision and
                item['category'] in (
                    'sheet_update', 'sheet_revert', 'item_action', 'modification', 'vehicle'))
            item['has_snapshot'] = bool(item.get('before_json'))
            item.pop('before_json', None)
            item.pop('after_json', None)
            item.pop('delta_json', None)
            payload.append(item)
        self.send_json({'entries': payload, 'current_revision': current_revision})

    @atomic_endpoint
    def api_character_ledger_revert(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1), allow_gm=True)
        expected_revision = _num((body or {}).get('revision'))
        current_revision = _row_value(row, 'revision', 0) or 0
        if expected_revision is None or expected_revision != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        entry = conn.execute(
            'SELECT * FROM character_ledger WHERE id=? AND character_id=?',
            (int(m.group(2)), row['id'])).fetchone()
        if not entry or entry['category'] not in (
                'sheet_update', 'sheet_revert', 'item_action', 'modification', 'vehicle'):
            raise ApiError(404, 'Изменение Character Sheet не найдено')
        delta = parse_json_object(entry['delta_json'])
        if (not delta.get('revertible') or
                _num(delta.get('revision_after')) != current_revision):
            raise ApiError(409, 'Откат доступен только до следующего изменения Dossier')
        try:
            target = json.loads(entry['before_json'])
        except (TypeError, ValueError, json.JSONDecodeError):
            raise ApiError(409, 'Snapshot для отката повреждён')
        if not isinstance(target, dict):
            raise ApiError(409, 'Snapshot для отката повреждён')
        before = json.loads(row['data'])
        now = time.time()
        session_net_change = delta.get('session_net_change')
        if isinstance(session_net_change, dict):
            session_id = _num(session_net_change.get('session_id'))
            session_before = session_net_change.get('before')
            session_after = session_net_change.get('after')
            session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                                   (session_id,)).fetchone() if session_id else None
            if (not session or not isinstance(session_before, dict) or
                    not isinstance(session_after, dict)):
                raise ApiError(409, 'Session NET snapshot для отката повреждён')
            clean_session_before = session_net_state(session_before)
            clean_session_after = session_net_state(session_after)
            current_session_net = session_net_state(
                _row_value(session, 'net_state_json', '{}'))
            if current_session_net != clean_session_after:
                raise ApiError(409, 'Session NET context изменён после Character action')
            conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                         (json.dumps(clean_session_before, ensure_ascii=False), now,
                          session['id']))
            conn.execute(
                'INSERT INTO session_activity(session_id,actor_user_id,event_type,note,created) '
                'VALUES(?,?,?,?,?)',
                (session['id'], user['id'], 'net_entity_revert',
                 f'Revert character ledger #{entry["id"]}', now))
        for effect_id in delta.get('created_effect_ids') or []:
            conn.execute(
                'UPDATE active_effect_instances SET active=0,archived_at=?,updated=? '
                'WHERE effect_id=? AND character_id=?',
                (now, now, str(effect_id), row['id']))
        for effect_id in delta.get('replaced_effect_ids') or []:
            replaced = conn.execute(
                'SELECT * FROM active_effect_instances WHERE effect_id=? AND character_id=?',
                (str(effect_id), row['id'])).fetchone()
            if not replaced or replaced['archived_at']:
                continue
            if replaced['duration_type'] == 'real_time' and replaced['expires_at'] is not None and replaced['expires_at'] <= now:
                continue
            if replaced['duration_type'] == 'rounds' and (_num(replaced['remaining_rounds']) or 0) <= 0:
                continue
            conn.execute('UPDATE active_effect_instances SET active=1,updated=? WHERE effect_id=?',
                         (now, str(effect_id)))
        for modification_id in delta.get('created_modification_ids') or []:
            conn.execute(
                'UPDATE item_modifications SET active=0,removed_by=?,removed_at=?,updated=? '
                'WHERE modification_id=? AND character_id=?',
                (user['id'], now, now, str(modification_id), row['id']))
        for modification_id in delta.get('removed_modification_ids') or []:
            conn.execute(
                'UPDATE item_modifications SET active=1,removed_by=NULL,removed_at=NULL,updated=? '
                'WHERE modification_id=? AND character_id=?',
                (now, str(modification_id), row['id']))
        ensure_character_item_instances(target)
        ensure_progression(target)
        validate_armor_tech_references(target)
        validate_armor_repair_references(target)
        validate_tech_maker_references(target)
        validate_bound_popup_weapon_references(target)
        validate_popup_shield_references(target)
        validate_active_modification_references(conn, row['id'], target)
        sync_weapon_states_with_modifications(conn, row['id'], target)
        sync_vehicle_states_with_modifications(conn, row['id'], target)
        persist_character_item_instances(
            conn, row['id'], target, 'ledger_revert',
            source_ref=f'ledger:{entry["id"]}', prune=True)
        revision_after = current_revision + 1
        reason = str((body or {}).get('reason') or '').strip()
        reason = reason[:500] or f'Revert ledger entry #{entry["id"]}'
        revert_ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, target, reason,
            current_revision, revision_after, category='sheet_revert',
            reverts_ledger_id=entry['id'])
        if (delta.get('created_effect_ids') or delta.get('replaced_effect_ids') or
                delta.get('created_modification_ids') or delta.get('removed_modification_ids') or
                session_net_change):
            revert_delta_row = conn.execute(
                'SELECT delta_json FROM character_ledger WHERE id=?',
                (revert_ledger_id,)).fetchone()
            revert_delta = parse_json_object(revert_delta_row['delta_json'])
            revert_delta['revertible'] = False
            revert_delta['effect_linked_revert'] = True
            conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                         (json.dumps(revert_delta, ensure_ascii=False), revert_ledger_id))
        conn.execute(
            'UPDATE characters SET data=?,public=?,updated=?,revision=? WHERE id=?',
            (json.dumps(target, ensure_ascii=False), 1 if target.get('public') else 0,
             time.time(), revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json(self.char_payload(fresh, fresh['owner'], conn=conn))

    @atomic_endpoint
    def api_character_memorialize(self, conn, qs, m, body):
        """Mark a Character as fallen (deceased/retired/missing)."""
        user = self.require_gm(conn)
        row = self.get_char(conn, m.group(1))
        data = ensure_progression(json.loads(row['data']))
        status = str((body or {}).get('status') or 'deceased').lower()
        if status not in MEMORIAL_STATUSES:
            raise ApiError(400, 'Неизвестный статус memorial')
        if data.get('status') in MEMORIAL_STATUSES:
            raise ApiError(409, 'Персонаж уже помечен memorial')
        existing = conn.execute('SELECT * FROM memorials WHERE character_id=?',
                                (row['id'],)).fetchone()
        if existing:
            raise ApiError(409, 'Memorial для персонажа уже существует')
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину memorial')
        collaborative = bool((body or {}).get('collaborative'))
        # Identity fields are always taken from the Dossier for a memorial.
        source = dict(body or {})
        source.setdefault('handle', data.get('handle'))
        source.setdefault('role', data.get('role'))
        source.setdefault('role_rank', _num(data.get('role_rank')) or 0)
        cleaned = clean_memorial_input(source)
        now = time.time()
        draft_state = 'pending_owner' if collaborative else 'published'
        cur = conn.execute(
            'INSERT INTO memorials(character_id,handle,role,role_rank,portrait_media_id,status,'
            'death_date,location,cause,epitaph,last_words,obituary,gm_notes,visibility,'
            'created_by,created,updated,draft_state) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (row['id'], cleaned['handle'], cleaned['role'], cleaned['role_rank'],
             str(data.get('portrait_media_id') or '')[:64] or None, cleaned['status'],
             cleaned['death_date'], cleaned['location'], cleaned['cause'],
             cleaned['epitaph'], cleaned['last_words'], cleaned['obituary'],
             cleaned['gm_notes'], cleaned['visibility'], user['id'], now, now, draft_state))
        memorial_id = cur.lastrowid
        if collaborative:
            # Owner fills the narrative; the Dossier is frozen only at publish.
            if row['owner_id']:
                add_notification(conn, row['owner_id'], 'memorial_draft',
                                 'Memorial draft awaiting your input',
                                 data.get('handle') or 'Edgerunner',
                                 f'#/memorial/{memorial_id}')
        else:
            feed_post_id = None
            if (body or {}).get('publish_obituary') and cleaned['obituary']:
                cur_feed = conn.execute(
                    'INSERT INTO feed_posts(format,status,creator_user_id,headline,body,'
                    'truth_status,event_at,created,updated) '
                    "VALUES('article','draft',?,?,?,'unknown',?,?,?)",
                    (user['id'], f'In Memoriam: {cleaned["handle"]}', cleaned['obituary'],
                     cleaned['death_date'] or now, now, now))
                feed_post_id = cur_feed.lastrowid
            conn.execute('UPDATE memorials SET feed_post_id=? WHERE id=?',
                         (feed_post_id, memorial_id))
            before = json.loads(row['data'])
            after = copy.deepcopy(before)
            after['status'] = status
            after['archived'] = True
            after['public'] = False
            after['archive_reason'] = reason
            conn.execute('UPDATE characters SET data=?,public=0,updated=?,revision=revision+1 WHERE id=?',
                         (json.dumps(after, ensure_ascii=False), now, row['id']))
            record_character_changes(conn, row['id'], user['id'], before, after,
                                     f'Memorialized as {status}: {reason}')
        conn.commit()
        fresh = conn.execute('SELECT * FROM memorials WHERE id=?', (memorial_id,)).fetchone()
        self.send_json(memorial_payload(fresh, user, full=True), status=201)

    @atomic_endpoint
    def api_character_modification_action(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        if set(body or {}) - {
                'revision', 'action', 'reason', 'weapon_instance_id', 'ammo_instance_id'}:
            raise ApiError(400, 'Modification action содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        modification_id = str(m.group(2)).lower()
        modification_row = conn.execute(
            'SELECT * FROM item_modifications WHERE modification_id=? AND character_id=?',
            (modification_id, row['id'])).fetchone()
        if not modification_row:
            raise ApiError(404, 'Modification не найдена')
        modification = item_modification_payload(modification_row)
        if not modification['active']:
            raise ApiError(409, 'Modification уже снята')
        action = str((body or {}).get('action') or '').lower()
        if 'weapon_instance_id' in (body or {}) and action != 'mount_weapon':
            raise ApiError(400, 'weapon_instance_id допустим только для mount_weapon')
        if 'ammo_instance_id' in (body or {}) and action != 'reload':
            raise ApiError(400, 'ammo_instance_id допустим только для Reload')
        if action in ('fire', 'reload', 'use_nos', 'reset_nos',
                      'mount_weapon', 'unmount_weapon'):
            before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
            data = copy.deepcopy(before)
            state = (data.get('modification_state') or {}).get(modification_id)
            config = modification.get('configuration') or {}
            owned = {entry.get('instance_id'): entry for entry in data.get('inventory') or []
                     if isinstance(entry, dict) and entry.get('instance_id')}
            upgrade = owned.get(modification['upgrade_instance_id']) or {}
            resource_rules = config.get('effect_rules')
            if not isinstance(resource_rules, list) or not resource_rules:
                rule_loader = (vehicle_modification_rules_for_catalog
                               if modification.get('host_type') == 'vehicle'
                               else weapon_modification_rules_for_catalog)
                resource_rules = rule_loader(
                    catalog_item_id_for_entry(upgrade) or
                    config.get('upgrade_catalog_item_id'))
            if modification.get('host_type') == 'vehicle':
                authoritative = initial_vehicle_modification_state(
                    resource_rules, data, config.get('choices') or {})
                state = normalize_vehicle_modification_state(state, authoritative)
                if state:
                    data.setdefault('modification_state', {})[modification_id] = state
            if not isinstance(state, dict) or not state.get('profile_id'):
                raise ApiError(400, 'Modification не имеет action resource profile')
            profile_label = config.get('upgrade_name') or state.get('profile_id')
            action_state = state
            reload_weapon = None
            action_reason = str((body or {}).get('reason') or '').strip()[:500]

            if action in ('mount_weapon', 'unmount_weapon'):
                if state.get('resource_type') != 'heavy_weapon_mount':
                    raise ApiError(400, 'Modification не является Vehicle Heavy Weapon Mount')
                if len(action_reason) < 3:
                    raise ApiError(400, 'Укажите причину изменения mounted weapon')
                if action == 'mount_weapon':
                    if state.get('weapon_instance_id'):
                        raise ApiError(409, 'Сначала снимите текущее mounted weapon')
                    weapon_instance_id = str(
                        (body or {}).get('weapon_instance_id') or '').lower()
                    if not INSTANCE_ID_RE.fullmatch(weapon_instance_id):
                        raise ApiError(400, 'Выберите конкретный экземпляр оружия')
                    weapon = owned.get(weapon_instance_id)
                    catalog_weapon = item_by_id(catalog_item_id_for_entry(weapon)) or {}
                    mechanics = catalog_weapon.get('mechanics') or {}
                    if not weapon or weapon.get('cat') != 'guns' or _num(mechanics.get('hands')) != 2:
                        raise ApiError(400, 'Крепление принимает только двуручное дальнобойное оружие')
                    if weapon.get('state') != 'carried' or weapon.get('mounted_modification_id'):
                        raise ApiError(409, 'Оружие должно быть свободным и находиться в carried')
                    state['weapon_instance_id'] = weapon_instance_id
                    weapon.update({
                        'state': 'installed',
                        'mounted_modification_id': modification_id,
                        'mounted_vehicle_id': modification['host_instance_id'],
                    })
                    sync_weapon_states_with_modifications(conn, row['id'], data)
                    profile_label = weapon.get('custom_name') or weapon.get('name') or 'Weapon'
                    reason = f'Mount {profile_label} on Vehicle Heavy Weapon Mount: {action_reason}'
                else:
                    weapon_instance_id = str(state.get('weapon_instance_id') or '')
                    weapon = owned.get(weapon_instance_id)
                    if not weapon:
                        raise ApiError(409, 'Mounted weapon instance отсутствует')
                    profile_label = weapon.get('custom_name') or weapon.get('name') or 'Weapon'
                    state['weapon_instance_id'] = None
                    weapon['state'] = 'carried'
                    weapon.pop('mounted_modification_id', None)
                    weapon.pop('mounted_vehicle_id', None)
                    reason = f'Unmount {profile_label} from Vehicle Heavy Weapon Mount: {action_reason}'
            elif action in ('use_nos', 'reset_nos'):
                if state.get('resource_type') != 'nos_tank':
                    raise ApiError(400, 'Modification не является баллоном NOS')
                current = max(0, int(_num(state.get('uses_remaining')) or 0))
                maximum = max(1, int(_num(state.get('uses_max')) or 1))
                if action == 'use_nos':
                    if current <= 0:
                        raise ApiError(409, 'Баллон NOS уже использован в этот игровой день')
                    state['uses_remaining'] = current - 1
                    reason = f'Use {profile_label}: {current} → {state["uses_remaining"]}'
                else:
                    if len(action_reason) < 3:
                        raise ApiError(400, 'Укажите причину сброса NOS')
                    if current >= maximum:
                        raise ApiError(409, 'Баллон NOS уже готов к использованию')
                    state['uses_remaining'] = maximum
                    reason = f'Reset {profile_label}: {current} → {maximum}; {action_reason}'
            else:
                if state.get('resource_type') == 'nos_tank':
                    raise ApiError(400, 'Баллон NOS не является оружием')
                if state.get('resource_type') == 'heavy_weapon_mount':
                    weapon_instance_id = str(state.get('weapon_instance_id') or '')
                    weapon = owned.get(weapon_instance_id)
                    if not weapon:
                        raise ApiError(409, 'Сначала установите оружие в Vehicle Heavy Weapon Mount')
                    sync_weapon_states_with_modifications(conn, row['id'], data)
                    all_modifications = character_modifications(conn, row['id'])
                    weapon_modifications = [
                        item for item in all_modifications
                        if item.get('host_instance_id') == weapon_instance_id]
                    effective_weapon = evaluate_effective_weapon(
                        weapon, weapon_modifications, owned, data)
                    bound_profile = bound_vehicle_weapon_profile(
                        weapon, effective_weapon, data)
                    action_state = (data.get('weapon_state') or {}).get(weapon_instance_id) or {}
                    profile_label = weapon.get('custom_name') or weapon.get('name') or 'Weapon'
                    reload_weapon = weapon
                    ammo_cost = max(1, int(bound_profile.get('ammo_cost') or 1))
                else:
                    ammo_cost = max(1, int(_num(state.get('ammo_cost')) or 1))
                if action == 'fire':
                    maximum = max(0, int(_num(action_state.get('magazine_max')) or 0))
                    if maximum <= 0:
                        raise ApiError(409, 'Оружие не имеет отслеживаемого магазина')
                    current = max(0, int(_num(action_state.get('magazine')) or 0))
                    if current < ammo_cost:
                        raise ApiError(409, f'Для атаки требуется {ammo_cost} патронов')
                    action_state['magazine'] = current - ammo_cost
                    clear_loaded_ammo_if_empty(action_state)
                    reason = f'Fire {profile_label}: magazine {current} → {action_state["magazine"]}'
                else:
                    reload_ammo_kind = None if reload_weapon else \
                        ammo_kind_for_modification_profile(
                            resource_rules, state.get('profile_id'))
                    transfer = consume_shared_ammo(
                        data, action_state, (body or {}).get('ammo_instance_id'),
                        ammo_kind=reload_ammo_kind, weapon=reload_weapon)
                    reason = (
                        f'Reload {profile_label} with {transfer["ammo_name"]} '
                        f'×{transfer["moved"]}: magazine {action_state["magazine"]}')

            validate_active_modification_references(conn, row['id'], data)
            persist_character_item_instances(
                conn, row['id'], data, 'vehicle_action', source_ref=reason,
                prune=True)
            now = time.time()
            revision_after = current_revision + 1
            ledger_id = record_character_change_set(
                conn, row['id'], user['id'], before, data, reason,
                current_revision, revision_after,
                category='vehicle' if modification.get('host_type') == 'vehicle'
                else 'modification')
            conn.execute('UPDATE item_modifications SET updated=? WHERE modification_id=?',
                         (now, modification_id))
            conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                         (json.dumps(data, ensure_ascii=False), now, revision_after, row['id']))
            conn.commit()
            fresh = self.get_char(conn, row['id'])
            self.send_json({
                'ledger_id': ledger_id,
                'character': self.char_payload(fresh, fresh['owner'], conn=conn),
                'management': self.modification_management_payload(conn, fresh),
            })
            return
        if modification['permanent']:
            raise ApiError(409, 'Эта modification не может быть снята')
        if action != 'remove':
            raise ApiError(400, 'Неизвестное действие с modification')
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину снятия modification')
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        upgrade = next((entry for entry in data.get('inventory') or []
                        if isinstance(entry, dict) and entry.get('instance_id') == modification['upgrade_instance_id']), None)
        if not upgrade:
            raise ApiError(409, 'Upgrade instance отсутствует в Inventory')
        host = next((entry for entry in data.get('inventory') or []
                     if isinstance(entry, dict) and entry.get('instance_id') == modification['host_instance_id']), None)
        if host and host.get('installed_cyberware_instance_id'):
            raise ApiError(409, 'Permanent Popup Weapon attachments нельзя изменять')
        remaining_modifications = [item for item in character_modifications(conn, row['id'])
                                   if item['modification_id'] != modification_id]
        owned = {entry.get('instance_id'): entry for entry in data.get('inventory') or []
                 if isinstance(entry, dict) and entry.get('instance_id')}
        erased_backup_count = 0
        if host and modification.get('host_type') == 'weapon':
            remaining_pools = weapon_slot_capacity(host, remaining_modifications, owned)
            overloaded = [name for name, pool in remaining_pools.items()
                          if pool['used'] > pool['total']]
            if overloaded:
                raise ApiError(409, 'Сначала снимите modifications, зависящие от granted slots')
        elif host and modification.get('host_type') == 'cyberdeck':
            remaining_deck_modifications = [
                item for item in remaining_modifications
                if item.get('host_instance_id') == host.get('instance_id')]
            remaining_usage = cyberdeck_slot_usage(
                host, remaining_deck_modifications, owned)
            if remaining_usage['overloaded']:
                raise ApiError(409, 'Сначала освободите зависимые Cyberdeck slots')
            if upgrade.get('modification_kind') == 'cyberdeck_program':
                runtime = (data.get('program_state') or {}).get(
                    upgrade.get('instance_id')) or {}
                if runtime.get('status') in ('rezzed', 'derezzed'):
                    raise ApiError(409, 'Deactivate Program before Uninstall')
            if upgrade.get('name') == 'Backup Drive':
                backup_state = (data.get('modification_state') or {}).get(
                    modification_id) or {}
                erased_backup_count = len(backup_state.get('saved_programs') or [])
        elif host and modification.get('host_type') == 'vehicle':
            removed_name = str(upgrade.get('name') or '')
            removed_state = (data.get('modification_state') or {}).get(modification_id) or {}
            if (removed_state.get('resource_type') == 'heavy_weapon_mount' and
                    removed_state.get('weapon_instance_id')):
                raise ApiError(409, 'Сначала снимите оружие с Vehicle Heavy Weapon Mount')
            if removed_name == 'Housing Capacity':
                remaining_upgrades = [owned.get(item.get('upgrade_instance_id')) or {}
                                      for item in remaining_modifications]
                remaining_names = [str(item.get('name') or '')
                                   for item in remaining_upgrades]
                base_room_count = vehicle_base_interior(host)['base_rooms']
                remaining_room_upgrades = sum(
                    name in ('Luxury Vehicle Room', 'Complex Vehicle Room')
                    for name in remaining_names)
                if remaining_room_upgrades > base_room_count:
                    raise ApiError(409, 'Сначала снимите upgrades жилых комнат')
                remaining_mounts = sum(
                    name == 'Vehicle Heavy Weapon Mount' for name in remaining_names)
                if 'groundcar' in vehicle_classification(host) and remaining_mounts > 1:
                    raise ApiError(409, 'Housing Capacity требуется для нескольких Heavy Weapon Mounts')
            for remaining in remaining_modifications:
                dependent = owned.get(remaining.get('upgrade_instance_id')) or {}
                host_names = (dependent.get('prerequisite_host_names') or {}).get(removed_name) or []
                applies = not host_names or str(host.get('name') or '') in host_names
                required_names = dependent.get('prerequisite_upgrades') or []
                removes_prerequisite = any(
                    removed_name == required or removed_name.startswith(required + ' (')
                    for required in required_names)
                if applies and removes_prerequisite:
                    raise ApiError(409, 'Сначала снимите зависимые vehicle upgrades')
            prospective_host_modifications = [
                item for item in remaining_modifications
                if item.get('host_instance_id') == host.get('instance_id')]
            prospective = evaluate_effective_vehicle(
                host, prospective_host_modifications, owned, data,
                remaining_modifications)
            prospective_seats = _num((prospective.get('effective') or {}).get('seats'))
            if prospective_seats is not None and prospective_seats < 0:
                raise ApiError(409, 'Сначала освободите места, занятые Heavy Weapon Mount')
        upgrade['state'] = 'carried'
        upgrade.pop('host_instance_id', None)
        data.setdefault('modification_state', {}).pop(modification_id, None)
        if upgrade.get('modification_kind') == 'cyberdeck_program':
            data.setdefault('program_state', {}).pop(upgrade.get('instance_id'), None)
        now = time.time()
        conn.execute(
            'UPDATE item_modifications SET active=0,removed_by=?,removed_at=?,updated=? '
            'WHERE modification_id=?', (user['id'], now, now, modification_id))
        if modification.get('host_type') == 'weapon':
            sync_weapon_states_with_modifications(conn, row['id'], data)
        elif modification.get('host_type') == 'vehicle':
            sync_vehicle_states_with_modifications(conn, row['id'], data)
        revision_after = current_revision + 1
        persist_character_item_instances(conn, row['id'], data, 'modification_remove')
        config = modification.get('configuration') or {}
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data,
            f'Remove {config.get("upgrade_name") or upgrade.get("name")}: {reason}',
            current_revision, revision_after, category='modification')
        ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                  (ledger_id,)).fetchone()
        delta = parse_json_object(ledger_row['delta_json'])
        delta['removed_modification_ids'] = [modification_id]
        if erased_backup_count:
            delta['revertible'] = False
            delta['backup_drive_erased_programs'] = erased_backup_count
        conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                     (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now, revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
            'management': self.modification_management_payload(conn, fresh),
        })

    @atomic_endpoint
    def api_character_modification_install(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        if set(body or {}) - {'revision', 'host_instance_id', 'upgrade_instance_id',
                              'manual_confirm', 'configuration', 'reason', 'notes'}:
            raise ApiError(400, 'Modification содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        host_id = str((body or {}).get('host_instance_id') or '').lower()
        upgrade_id = str((body or {}).get('upgrade_instance_id') or '').lower()
        if not INSTANCE_ID_RE.fullmatch(host_id) or not INSTANCE_ID_RE.fullmatch(upgrade_id):
            raise ApiError(400, 'Некорректный host или upgrade instance')
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину установки modification')
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        owned = {entry.get('instance_id'): entry for entry in data.get('inventory') or []
                 if isinstance(entry, dict) and entry.get('instance_id')}
        host, upgrade = owned.get(host_id), owned.get(upgrade_id)
        if not host or not upgrade:
            raise ApiError(404, 'Host или upgrade не найден в Inventory')
        if host.get('state') in ('stored', 'broken', 'consumed'):
            raise ApiError(409, 'Host должен быть исправен и находиться при персонаже')
        if host.get('installed_cyberware_instance_id'):
            raise ApiError(409, 'Permanent Popup Weapon attachments нельзя изменять')
        if upgrade.get('state') != 'carried':
            raise ApiError(409, 'Upgrade должен находиться в состоянии carried')
        host_type = str(upgrade.get('host_type') or '')
        active = [mod for mod in character_modifications(conn, row['id'])
                  if mod['host_instance_id'] == host_id]
        if host_type == 'weapon':
            choices = clean_weapon_modification_choices(
                catalog_item_id_for_entry(upgrade), (body or {}).get('configuration'), host)
            compatibility = weapon_upgrade_compatibility(host, upgrade, active, owned)
            effect_rules = weapon_modification_rules_for_catalog(
                catalog_item_id_for_entry(upgrade))
        elif host_type == 'vehicle':
            choices = clean_vehicle_modification_choices(
                catalog_item_id_for_entry(upgrade), (body or {}).get('configuration'))
            compatibility = vehicle_upgrade_compatibility(
                host, upgrade, active, owned, data)
            effect_rules = vehicle_modification_rules_for_catalog(
                catalog_item_id_for_entry(upgrade))
        elif host_type == 'cyberdeck':
            if (body or {}).get('configuration') not in (None, {}):
                raise ApiError(400, 'Cyberdeck configuration пока не поддерживается')
            choices = {}
            compatibility = cyberdeck_item_compatibility(
                host, upgrade, active, owned)
            effect_rules = []
        else:
            raise ApiError(400, 'Неподдерживаемый тип modification host')
        if not compatibility['allowed']:
            raise ApiError(400, 'Несовместимая модификация: ' + '; '.join(compatibility['reasons']))
        if compatibility['manual_resolution_required'] and not bool((body or {}).get('manual_confirm')):
            raise ApiError(409, 'Требуется ручное подтверждение сложного правила совместимости')
        modification_id = secrets.token_hex(16)
        now = time.time()
        configuration = {
            'host_catalog_item_id': catalog_item_id_for_entry(host),
            'upgrade_catalog_item_id': catalog_item_id_for_entry(upgrade),
            'host_name': host.get('custom_name') or host.get('name'),
            'upgrade_name': upgrade.get('custom_name') or upgrade.get('name'),
            'compatibility': compatibility,
            'manual_confirmed': bool((body or {}).get('manual_confirm')),
            'slot_pool': compatibility.get('slot_pool'),
            'grants_slots': copy.deepcopy(upgrade.get('grants_slots') or {}),
            'choices': choices,
            'effect_rules': effect_rules,
            'effects_rules_version': load_effect_rules().get('rules_version'),
        }
        profiles = weapon_profiles_from_rules(configuration['effect_rules'])
        if profiles:
            profile = profiles[0]
            data.setdefault('modification_state', {})[modification_id] = {
                'profile_id': profile['id'],
                'magazine': 0,
                'magazine_max': int(profile['magazine']),
                'reserve': 0,
            }
        elif host_type == 'vehicle':
            initial_state = initial_vehicle_modification_state(
                configuration['effect_rules'], data, choices)
            if initial_state:
                data.setdefault('modification_state', {})[modification_id] = initial_state
        elif host_type == 'cyberdeck':
            if upgrade.get('modification_kind') == 'cyberdeck_program':
                data.setdefault('program_state', {})[upgrade_id] = \
                    initial_program_runtime_state(
                        upgrade, host_id, modification_id)
            elif upgrade.get('name') == 'Backup Drive':
                data.setdefault('modification_state', {})[modification_id] = {
                    'resource_type': 'backup_drive', 'saved_programs': [],
                }
        conn.execute(
            'INSERT INTO item_modifications(modification_id,character_id,host_instance_id,'
            'upgrade_instance_id,host_type,slot_type,slots_used,active,permanent,'
            'configuration_json,notes,source_type,installed_by,installed_at,created,updated) '
            'VALUES(?,?,?,?,?,?,?,1,?,?,?,?,?,?,?,?)',
            (modification_id, row['id'], host_id, upgrade_id, host_type,
             compatibility.get('slot_pool') or upgrade.get('slot_type') or f'{host_type}_upgrade',
             int(upgrade.get('slots_used') or 0), 1 if upgrade.get('permanent_installation') else 0,
             json.dumps(configuration, ensure_ascii=False), str((body or {}).get('notes') or '')[:2000],
             upgrade.get('acquisition_source') or 'inventory', user['id'], now, now, now))
        upgrade['state'] = 'installed'
        upgrade['host_instance_id'] = host_id
        if host_type == 'weapon':
            sync_weapon_states_with_modifications(conn, row['id'], data)
        elif host_type == 'vehicle':
            sync_vehicle_states_with_modifications(conn, row['id'], data)
        revision_after = current_revision + 1
        persist_character_item_instances(conn, row['id'], data, 'modification_install')
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data,
            f'Install {configuration["upgrade_name"]} on {configuration["host_name"]}: {reason}',
            current_revision, revision_after, category='modification')
        ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                  (ledger_id,)).fetchone()
        delta = parse_json_object(ledger_row['delta_json'])
        delta['created_modification_ids'] = [modification_id]
        if upgrade.get('permanent_installation'):
            delta['revertible'] = False
            delta['permanent_modification'] = True
        conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                     (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now, revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'modification_id': modification_id,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
            'management': self.modification_management_payload(conn, fresh),
        }, status=201)

    def api_character_modifications(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1), allow_gm=True)
        self.send_json(self.modification_management_payload(conn, row))

    def api_character_net_contexts(self, conn, qs, m, body):
        user, character = self.require_character_editor(conn, m.group(1))
        rows = conn.execute(
            'SELECT DISTINCT s.* FROM nc_sessions s JOIN session_combatants c '
            'ON c.session_id=s.id WHERE c.character_id=? '
            "AND s.status IN ('preparing','active','paused') ORDER BY s.updated DESC",
            (character['id'],)).fetchall()
        contexts = []
        for session in rows:
            role, capabilities = self.session_capabilities(conn, user, session)
            if not role:
                continue
            state = session_net_state(_row_value(session, 'net_state_json', '{}'))
            targets = conn.execute(
                'SELECT id,kind,character_id,name FROM session_combatants '
                'WHERE session_id=? AND (character_id IS NULL OR character_id!=?) '
                'ORDER BY initiative DESC,sort_order,id',
                (session['id'], character['id'])).fetchall()
            contexts.append({
                'session_id': session['id'], 'title': session['title'],
                'status': session['status'], 'access_role': role,
                'floors': state['floors'], 'nodes': state['nodes'],
                'paths': state['paths'],
                'targets': [dict(target) for target in targets],
                'can_manage_net': 'edit_combatants' in capabilities,
            })
        self.send_json({'character_id': character['id'], 'sessions': contexts})

    @atomic_endpoint
    def api_character_net_entity_action(self, conn, qs, m, body):
        user = self.require_user(conn)
        row = self.get_char(conn, m.group(1))
        if parse_json_object(row['data']).get('archived'):
            raise ApiError(409, 'Архивное досье доступно только для чтения')
        allowed = {'revision', 'action', 'amount', 'floor_label',
                   'target_label', 'reason', 'session_floor_id', 'session_node_id',
                   'target_combatant_id'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'NET entity action содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        entity_id = str(m.group(2)).lower()
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        entity = (data.get('net_entities') or {}).get(entity_id)
        if not isinstance(entity, dict) or entity.get('type') != 'black_ice':
            raise ApiError(404, 'Black ICE NET entity не найдена')
        linked_session = None
        if entity.get('session_id'):
            linked_session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                                          (int(entity['session_id']),)).fetchone()
        if row['owner_id'] != user['id']:
            if (not linked_session or
                    'edit_combatants' not in self.session_capabilities(
                        conn, user, linked_session)[1]):
                raise ApiError(403, 'Нет права управлять Black ICE entity')
        if entity.get('status') not in ('lying_in_wait', 'hunting', 'derezzed'):
            raise ApiError(409, 'Black ICE NET entity уже завершена')
        before_entity = copy.deepcopy(entity)
        program_id = str(entity.get('source_program_instance_id') or '')
        deck_id = str(entity.get('deck_instance_id') or '')
        modifications = character_modifications(conn, row['id'])
        modification = next((item for item in modifications
                             if item.get('host_instance_id') == deck_id and
                             item.get('upgrade_instance_id') == program_id), None)
        owned = {item.get('instance_id'): item for item in data.get('inventory') or []
                 if isinstance(item, dict) and item.get('instance_id')}
        program = owned.get(program_id)
        if not modification or not program:
            raise ApiError(409, 'Source Black ICE installation отсутствует')
        runtime = initial_program_runtime_state(
            program, deck_id, modification['modification_id'],
            (data.get('program_state') or {}).get(program_id))
        linked_net_state = session_net_state(
            _row_value(linked_session, 'net_state_json', '{}')) if linked_session else None
        linked_net_link = next((item for item in linked_net_state['links']
                                if item['net_entity_id'] == entity_id), None) \
            if linked_net_state else None
        linked_net_state_before = copy.deepcopy(linked_net_state) \
            if linked_net_state else None
        if linked_session and not linked_net_link:
            raise ApiError(409, 'Session NET entity link отсутствует')
        action = str((body or {}).get('action') or '').lower()
        detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(detail) < 3:
            raise ApiError(400, 'Укажите причину NET entity action')
        now = time.time()
        removed_modification_ids = []
        if action == 'damage':
            if entity.get('status') not in ('lying_in_wait', 'hunting'):
                raise ApiError(409, 'REZ damage требует active Black ICE')
            amount = _num((body or {}).get('amount'))
            if amount is None or int(amount) != amount or not 1 <= amount <= 100:
                raise ApiError(400, 'Укажите REZ damage от 1 до 100')
            previous = int(entity.get('rez_current') or 0)
            entity['rez_current'] = max(0, previous - int(amount))
            runtime['rez_current'] = entity['rez_current']
            if entity['rez_current'] == 0:
                entity['status'] = 'derezzed'
                runtime['status'] = 'derezzed'
                if linked_net_link:
                    linked_net_link['initiative'] = 0
            reason = (f'Black ICE REZ damage {entity.get("name")}: '
                      f'{previous} → {entity["rez_current"]}; {detail}')
        elif action == 'slide':
            if entity.get('status') != 'hunting':
                raise ApiError(409, 'Slide требует hunting Black ICE')
            entity['status'] = 'lying_in_wait'
            entity['target_label'] = None
            entity['initiative'] = None
            entity['initiative_roll'] = None
            entity['target_combatant_id'] = None
            if linked_net_link:
                linked_net_link['target_combatant_id'] = None
                linked_net_link['initiative'] = 0
            reason = f'Slide from Black ICE {entity.get("name")}: {detail}'
        elif action == 'engage':
            if entity.get('status') != 'lying_in_wait':
                raise ApiError(409, 'Engage требует lying-in-wait Black ICE')
            if linked_session:
                floor_id = str((body or {}).get('session_floor_id') or
                               linked_net_link.get('floor_id') or '').lower()
                floor = next((item for item in linked_net_state['floors']
                              if item['floor_id'] == floor_id), None)
                floor_nodes = [item for item in linked_net_state['nodes']
                               if item['floor_id'] == floor_id]
                node_id = str((body or {}).get('session_node_id') or
                              linked_net_link.get('node_id') or '').lower()
                node = next((item for item in floor_nodes
                             if item['node_id'] == node_id), None) if floor_nodes else None
                target_id = _num((body or {}).get('target_combatant_id'))
                target = conn.execute(
                    'SELECT * FROM session_combatants WHERE session_id=? AND id=?',
                    (linked_session['id'], int(target_id))).fetchone() \
                    if target_id is not None and int(target_id) == target_id else None
                if (not floor or not target or target['character_id'] == row['id'] or
                        (floor_nodes and not node)):
                    raise ApiError(400, 'Выберите validated Session Floor, node и target')
                floor_label, target_label = floor['label'], target['name']
                entity['session_floor_id'] = floor_id
                entity['session_node_id'] = node_id if node else None
                entity['session_node_label'] = node['label'] if node else None
                entity['target_combatant_id'] = target['id']
                linked_net_link['floor_id'] = floor_id
                linked_net_link['node_id'] = node_id if node else None
                linked_net_link['target_combatant_id'] = target['id']
                linked_net_link['visible'] = True
                if node:
                    node['visible'] = True
            else:
                target_label = str((body or {}).get('target_label') or '').strip()[:120]
                floor_label = str((body or {}).get('floor_label') or
                                  entity.get('floor_label') or '').strip()[:120]
                if len(target_label) < 2 or not floor_label:
                    raise ApiError(400, 'Укажите Floor и target для Black ICE')
            roll = secrets.randbelow(10) + 1
            entity.update({
                'status': 'hunting', 'target_label': target_label,
                'floor_label': floor_label, 'initiative_roll': roll,
                'initiative': int(entity.get('spd') or 0) + roll,
            })
            if linked_net_link:
                linked_net_link['initiative'] = entity['initiative']
            reason = f'Engage Black ICE {entity.get("name")} vs {target_label}: {detail}'
        elif action == 'deactivate':
            entity['status'] = 'deactivated'
            entity['archived_at'] = now
            runtime['status'] = 'inactive'
            runtime['rez_current'] = runtime['rez_max']
            if linked_net_link:
                linked_net_link['active'] = False
            reason = f'Deactivate Black ICE {entity.get("name")}: {detail}'
        elif action == 'destroy':
            entity['status'] = 'destroyed'
            entity['rez_current'] = 0
            entity['archived_at'] = now
            runtime['status'] = 'destroyed'
            runtime['rez_current'] = 0
            program['state'] = 'broken'
            program.pop('host_instance_id', None)
            conn.execute(
                'UPDATE item_modifications SET active=0,removed_by=?,removed_at=?,updated=? '
                'WHERE modification_id=?',
                (user['id'], now, now, modification['modification_id']))
            removed_modification_ids.append(modification['modification_id'])
            if linked_net_link:
                linked_net_link['active'] = False
            reason = f'Destroy Black ICE entity {entity.get("name")}: {detail}'
        else:
            raise ApiError(400, 'NET entity action: damage/slide/engage/deactivate/destroy')
        entity['updated_at'] = now
        data.setdefault('program_state', {})[program_id] = runtime
        validate_active_modification_references(conn, row['id'], data)
        persist_character_item_instances(
            conn, row['id'], data, 'net_entity_action', source_ref=reason, prune=True)
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after,
            category='modification' if removed_modification_ids else 'item_action')
        if removed_modification_ids:
            ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                      (ledger_id,)).fetchone()
            delta = parse_json_object(ledger_row['delta_json'])
            delta['removed_modification_ids'] = removed_modification_ids
            conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                         (json.dumps(delta, ensure_ascii=False), ledger_id))
        if linked_session:
            queue_count = sum(1 for item in linked_net_state['links']
                              if item['active'] and (_num(item.get('initiative')) or 0) > 0)
            linked_net_state['active_turn'] = min(
                linked_net_state['active_turn'], max(0, queue_count - 1))
            conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                         (json.dumps(linked_net_state, ensure_ascii=False), now,
                          linked_session['id']))
            conn.execute(
                'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,'
                'after_json,note,created) VALUES(?,?,?,?,?,?,?)',
                (linked_session['id'], user['id'], f'net_entity_{action}',
                 json.dumps(before_entity, ensure_ascii=False),
                 json.dumps(entity, ensure_ascii=False), detail, now))
            ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                      (ledger_id,)).fetchone()
            delta = parse_json_object(ledger_row['delta_json'])
            delta['session_net_change'] = {
                'session_id': linked_session['id'],
                'before': linked_net_state_before,
                'after': copy.deepcopy(linked_net_state),
            }
            conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                         (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id, 'net_entity': copy.deepcopy(entity),
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    def api_character_network(self, conn, qs, m, body):
        row = self.get_char(conn, m.group(1))
        user = self.current_user(conn)
        if not row['public'] and (not user or (user['id'] != row['owner_id'] and not user_is_gm(user))):
            raise ApiError(403, 'Персонаж приватный')
        contracts = conn.execute(
            'SELECT c.id,c.title,c.status,c.district_id,s.status signup_status,s.joined_at '
            'FROM contract_signups s JOIN contracts c ON c.id=s.contract_id '
            'WHERE s.character_id=? ORDER BY s.joined_at DESC', (row['id'],)).fetchall()
        posts = conn.execute(
            "SELECT id,headline,body,format,published_at FROM feed_posts "
            "WHERE author_character_id=? AND status='published' ORDER BY published_at DESC",
            (row['id'],)).fetchall()
        comments = conn.execute(
            'SELECT fc.id,fc.post_id,fc.body,fc.created FROM feed_comments fc '
            'WHERE fc.author_character_id=? AND fc.hidden_at IS NULL ORDER BY fc.created DESC LIMIT 100',
            (row['id'],)).fetchall()
        self.send_json({'contracts': [dict(item) for item in contracts],
                        'posts': [dict(item) for item in posts],
                        'comments': [dict(item) for item in comments]})

    @atomic_endpoint
    def api_character_popup_shield_action(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {'revision', 'action', 'shield_instance_id', 'amount', 'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Popup Shield action содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        reason_detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason_detail) < 3:
            raise ApiError(400, 'Укажите причину Popup Shield action')
        option_id = str(m.group(2)).lower()
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        option = next((item for item in data.get('cyberware') or []
                       if isinstance(item, dict) and item.get('instance_id') == option_id), None)
        if not option or not cyberware_is_installed(option) or \
                catalog_item_id_for_entry(option) != 'cyberware-120':
            raise ApiError(404, 'Installed Popup Shield option не найден')
        runtime = data.setdefault('cyberware_state', {}).setdefault(option_id, {})
        popup = runtime.get('popup_shield') if isinstance(runtime.get('popup_shield'), dict) else {}
        action = str((body or {}).get('action') or '').lower()
        shield_id = str(popup.get('shield_instance_id') or '')
        shield = next((item for item in data.get('inventory') or []
                       if isinstance(item, dict) and item.get('instance_id') == shield_id), None)
        result = {'action': action}
        if action == 'install':
            if shield:
                raise ApiError(409, 'Popup Shield уже содержит concrete shield')
            shield_id = str((body or {}).get('shield_instance_id') or '').lower()
            shield = next((item for item in data.get('inventory') or []
                           if isinstance(item, dict) and item.get('instance_id') == shield_id), None)
            if (not shield or catalog_item_id_for_entry(shield) != 'armor-0' or
                    shield.get('state') != 'carried' or
                    shield.get('installed_popup_shield_instance_id')):
                raise ApiError(400, 'Popup Shield принимает только free Bulletproof Shield')
            maximum = armor_shield_hp(shield)
            popup = {'shield_instance_id': shield_id, 'hp_current': maximum,
                     'hp_max': maximum, 'deployed': False, 'installed_at': time.time()}
            runtime['popup_shield'] = popup
            shield['state'] = 'installed'
            shield['installed_popup_shield_instance_id'] = option_id
            reason = f'Install concrete Bulletproof Shield into Popup Shield: {reason_detail}'
        elif action == 'remove':
            if not shield:
                raise ApiError(409, 'Popup Shield не содержит concrete shield')
            current = max(0, int(_num(popup.get('hp_current')) or 0))
            shield['state'] = 'broken' if current <= 0 else 'carried'
            shield.pop('installed_popup_shield_instance_id', None)
            runtime['popup_shield'] = {}
            reason = f'Remove concrete Shield from Popup Shield: {reason_detail}'
        elif action in ('deploy', 'stow'):
            if not shield:
                raise ApiError(409, 'Popup Shield не содержит concrete shield')
            if action == 'deploy' and (_num(popup.get('hp_current')) or 0) <= 0:
                raise ApiError(409, 'Destroyed Shield нельзя deploy')
            popup['deployed'] = action == 'deploy'
            runtime['popup_shield'] = popup
            reason = f'{action.title()} Popup Shield: {reason_detail}'
        elif action == 'damage':
            if not shield:
                raise ApiError(409, 'Popup Shield не содержит concrete shield')
            amount = _num((body or {}).get('amount'))
            if amount is None or not 1 <= amount <= 100:
                raise ApiError(400, 'Укажите Popup Shield damage 1–100')
            previous = max(0, int(_num(popup.get('hp_current')) or 0))
            popup['hp_current'] = max(0, previous - int(amount))
            if popup['hp_current'] == 0:
                popup['deployed'] = False
                shield['state'] = 'broken'
            runtime['popup_shield'] = popup
            result.update({'hp_before': previous, 'hp_after': popup['hp_current']})
            reason = f'Popup Shield damage {previous} → {popup["hp_current"]}: {reason_detail}'
        else:
            raise ApiError(400, 'Popup Shield action: install/remove/deploy/stow/damage')
        validate_popup_shield_references(data)
        persist_character_item_instances(
            conn, row['id'], data, 'popup_shield_action', source_ref=reason, prune=True)
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='item_action')
        now = time.time()
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({'ledger_id': ledger_id, 'result': result,
                        'character': self.char_payload(fresh, fresh['owner'], conn=conn)})

    @atomic_endpoint
    def api_character_popup_weapon_bind(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {'revision', 'weapon_instance_id', 'permanent_confirmed', 'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Popup Weapon binding содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        if (body or {}).get('permanent_confirmed') is not True:
            raise ApiError(400, 'Подтвердите permanent Popup Weapon binding')
        reason_detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason_detail) < 3:
            raise ApiError(400, 'Укажите причину Popup Weapon binding')
        option_id = str(m.group(2)).lower()
        weapon_id = str((body or {}).get('weapon_instance_id') or '').lower()
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        option = next((item for item in data.get('cyberware') or []
                       if isinstance(item, dict) and item.get('instance_id') == option_id), None)
        if not option or not cyberware_is_installed(option) or not popup_weapon_binding_kind(option):
            raise ApiError(404, 'Installed generic Popup Weapon option не найден')
        runtime_states = data.setdefault('cyberware_state', {})
        runtime = runtime_states.setdefault(option_id, {})
        if runtime.get('bound_weapon_instance_id'):
            raise ApiError(409, 'Popup Weapon уже имеет permanent bound weapon')
        weapon = next((item for item in data.get('inventory') or []
                       if isinstance(item, dict) and item.get('instance_id') == weapon_id), None)
        compatibility = popup_weapon_binding_compatibility(option, weapon)
        if not compatibility['allowed']:
            raise ApiError(400, '; '.join(compatibility['reasons']))
        weapon['state'] = 'installed'
        weapon['installed_cyberware_instance_id'] = option_id
        host_ids = cyberware_host_assignments(option)
        weapon['installed_cyberarm_host_id'] = host_ids[0] if host_ids else None
        runtime['bound_weapon_instance_id'] = weapon_id
        runtime['bound_weapon_permanent'] = True
        runtime['bound_at'] = time.time()
        runtime['binding_reason'] = reason_detail
        validate_bound_popup_weapon_references(data)
        validate_active_modification_references(conn, row['id'], data)
        persist_character_item_instances(
            conn, row['id'], data, 'popup_weapon_binding',
            source_ref=reason_detail, prune=True)
        revision_after = current_revision + 1
        reason = (f'Permanently bind {weapon.get("name")} to '
                  f'{option.get("name")}: {reason_detail}')
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='modification')
        ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                  (ledger_id,)).fetchone()
        delta = parse_json_object(ledger_row['delta_json'])
        delta['popup_weapon_binding'] = {
            'option_instance_id': option_id, 'weapon_instance_id': weapon_id,
            'permanent': True, 'attachments_preserved': True,
        }
        conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                     (json.dumps(delta, ensure_ascii=False), ledger_id))
        now = time.time()
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id, 'compatibility': compatibility,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    @atomic_endpoint
    def api_character_program_action(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        if set(body or {}) - {'revision', 'action', 'amount', 'reason'}:
            raise ApiError(400, 'Program action содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        deck_id, program_id = str(m.group(2)).lower(), str(m.group(3)).lower()
        modifications = character_modifications(conn, row['id'])
        modification = next((item for item in modifications
                             if item.get('host_instance_id') == deck_id and
                             item.get('upgrade_instance_id') == program_id and
                             item.get('host_type') == 'cyberdeck'), None)
        if not modification:
            raise ApiError(404, 'Installed Program instance не найден')
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        owned = {item.get('instance_id'): item for item in data.get('inventory') or []
                 if isinstance(item, dict) and item.get('instance_id')}
        deck, program = owned.get(deck_id), owned.get(program_id)
        if (not deck or not program or
                program.get('modification_kind') != 'cyberdeck_program'):
            raise ApiError(409, 'Повреждена связь установленной Program')
        runtime = initial_program_runtime_state(
            program, deck_id, modification['modification_id'],
            (data.get('program_state') or {}).get(program_id))
        data.setdefault('program_state', {})[program_id] = runtime
        action = str((body or {}).get('action') or '').lower()
        detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(detail) < 3:
            raise ApiError(400, 'Укажите причину Program action')
        category = runtime['category']
        status = runtime['status']
        active_entity = active_black_ice_entity(data, program_id) \
            if category == 'black_ice' else None
        if category == 'black_ice' and action != 'destroy':
            raise ApiError(409, 'Black ICE actions require NET entity')
        if category == 'black_ice' and action == 'destroy' and active_entity:
            raise ApiError(409, 'Destroy active Black ICE through its NET entity')
        now = time.time()
        removed_modification_ids = []
        if action == 'run':
            if category != 'attacker':
                raise ApiError(409, 'Run доступен только Attacker Program')
            runtime['run_count'] += 1
            runtime['last_run_at'] = now
            reason = f'Run Attacker Program {program.get("name")}: {detail}'
        elif action == 'rez':
            if category == 'black_ice':
                raise ApiError(409, 'Black ICE требует NET entity deployment')
            if category not in ('booster', 'defender'):
                raise ApiError(409, 'Activate доступен только Booster или Defender Program')
            if status != 'inactive':
                raise ApiError(409, 'Program необходимо сначала Deactivate')
            catalog_program = item_by_id(catalog_item_id_for_entry(program)) or {}
            if re.search(r'Only 1 copy of this Program can be running',
                         str(catalog_program.get('desc') or ''), re.I):
                for other in (data.get('program_state') or {}).values():
                    if (other is not runtime and
                            other.get('catalog_item_id') == runtime['catalog_item_id'] and
                            other.get('status') == 'rezzed'):
                        raise ApiError(409, 'Только одна копия этой Program может быть Rezzed')
            runtime['status'] = 'rezzed'
            runtime['rez_current'] = runtime['rez_max']
            reason = f'Rez {program.get("name")} at REZ {runtime["rez_current"]}: {detail}'
        elif action == 'damage':
            if status != 'rezzed' or runtime['rez_max'] <= 0:
                raise ApiError(409, 'REZ damage требует Rezzed Program')
            amount = _num((body or {}).get('amount'))
            if amount is None or int(amount) != amount or not 1 <= amount <= 100:
                raise ApiError(400, 'Укажите REZ damage от 1 до 100')
            previous = runtime['rez_current']
            runtime['rez_current'] = max(0, previous - int(amount))
            if runtime['rez_current'] == 0:
                runtime['status'] = 'derezzed'
            reason = (f'Program REZ damage {program.get("name")}: '
                      f'{previous} → {runtime["rez_current"]}; {detail}')
        elif action == 'derez':
            if status != 'rezzed':
                raise ApiError(409, 'Derez требует Rezzed Program')
            runtime['status'] = 'derezzed'
            runtime['rez_current'] = 0
            reason = f'Derez Program {program.get("name")}: {detail}'
        elif action == 'deactivate':
            if status not in ('rezzed', 'derezzed'):
                raise ApiError(409, 'Deactivate требует Rezzed или Derezzed Program')
            runtime['status'] = 'inactive'
            runtime['rez_current'] = runtime['rez_max']
            reason = f'Deactivate Program {program.get("name")}: {detail}'
        elif action == 'destroy':
            backup_modification = next((item for item in modifications
                                        if item.get('host_instance_id') == deck_id and
                                        (owned.get(item.get('upgrade_instance_id')) or {}).get('name') == 'Backup Drive'), None)
            if category != 'black_ice' and backup_modification:
                backup_state = data.setdefault('modification_state', {}).setdefault(
                    backup_modification['modification_id'],
                    {'resource_type': 'backup_drive', 'saved_programs': []})
                saved = backup_state.setdefault('saved_programs', [])
                if not any(item.get('program_instance_id') == program_id for item in saved):
                    saved.append({
                        'program_instance_id': program_id,
                        'modification_id': modification['modification_id'],
                        'catalog_item_id': catalog_item_id_for_entry(program),
                        'name': program.get('custom_name') or program.get('name'),
                        'runtime_before': copy.deepcopy(runtime),
                        'saved_at': now,
                    })
            runtime['status'] = 'destroyed'
            runtime['rez_current'] = 0
            program['state'] = 'broken'
            program.pop('host_instance_id', None)
            conn.execute(
                'UPDATE item_modifications SET active=0,removed_by=?,removed_at=?,updated=? '
                'WHERE modification_id=?',
                (user['id'], now, now, modification['modification_id']))
            removed_modification_ids.append(modification['modification_id'])
            reason = f'Destroy Program {program.get("name")}: {detail}'
        else:
            raise ApiError(400, 'Program action: run/rez/damage/derez/deactivate/destroy')
        if runtime['status'] in ('derezzed', 'destroyed'):
            queue_defense_sequencer_trigger(
                data, modifications, deck_id, program_id)
        validate_active_modification_references(conn, row['id'], data)
        persist_character_item_instances(
            conn, row['id'], data, 'program_action', source_ref=reason, prune=True)
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after,
            category='modification' if removed_modification_ids else 'item_action')
        if removed_modification_ids:
            ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                      (ledger_id,)).fetchone()
            delta = parse_json_object(ledger_row['delta_json'])
            delta['removed_modification_ids'] = removed_modification_ids
            conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                         (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    def api_character_reputation(self, conn, qs, m, body):
        user = self.current_user(conn)
        gm = user_is_gm(user)
        cid = int(m.group(1))
        if not gm:
            row = conn.execute('SELECT owner_id FROM characters WHERE id=?', (cid,)).fetchone()
            if not row or row['owner_id'] != (user['id'] if user else -1):
                raise ApiError(403, 'Нет доступа к репутации персонажа')
        rows = conn.execute(
            'SELECT * FROM character_reputation WHERE character_id=? ORDER BY updated DESC', (cid,)).fetchall()
        self.send_json({'reputation': [dict(r) for r in rows]})

    @atomic_endpoint
    def api_character_reputation_delete(self, conn, qs, m, body):
        user = self.require_gm(conn)
        conn.execute('DELETE FROM character_reputation WHERE id=? AND character_id=?',
                     (int(m.group(2)), int(m.group(1))))
        conn.commit()
        self.send_json({'ok': True})

    @atomic_endpoint
    def api_character_reputation_set(self, conn, qs, m, body):
        user = self.require_gm(conn)
        cid = int(m.group(1))
        cleaned = clean_reputation_input(body or {})
        if not cleaned['organization_persona_id']:
            raise ApiError(400, 'Укажите организацию')
        now = time.time()
        conn.execute(
            'INSERT INTO character_reputation(character_id,organization_persona_id,reputation,'
            'favor,heat,standing,note,created_by,created,updated) '
            'VALUES(?,?,?,?,?,?,?,?,?,?) '
            'ON CONFLICT(character_id,organization_persona_id) DO UPDATE SET '
            'reputation=excluded.reputation,favor=excluded.favor,heat=excluded.heat,'
            'standing=excluded.standing,note=excluded.note,updated=excluded.updated',
            (cid, cleaned['organization_persona_id'], cleaned['reputation'],
             cleaned['favor'], cleaned['heat'], cleaned['standing'],
             cleaned['note'], user['id'], now, now))
        conn.commit()
        row = conn.execute(
            'SELECT * FROM character_reputation WHERE character_id=? AND organization_persona_id=?',
            (cid, cleaned['organization_persona_id'])).fetchone()
        self.send_json(dict(row))

    @atomic_endpoint
    def api_character_resource(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        data = ensure_progression(json.loads(row['data']))
        resource = str((body or {}).get('resource') or '')
        action = str((body or {}).get('action') or 'delta')
        value = _num((body or {}).get('value')) or 0
        derived = derive(data)
        if resource == 'luck':
            maximum = _num((data.get('stats') or {}).get('LUCK')) or 0
            data['luck_cur'] = maximum if action == 'reset' else max(0, min(maximum, data['luck_cur'] + value))
        elif resource == 'hp':
            maximum = derived.get('hp_max') or 0
            current = _num(data.get('hp_cur')) if _num(data.get('hp_cur')) is not None else maximum
            data['hp_cur'] = max(-maximum, min(maximum, current + value))
        elif resource == 'cash':
            raise ApiError(403, 'Деньги изменяются только через Market, Payroll или Aftermath')
        elif resource == 'reputation':
            data['reputation'] = max(0, min(10, data['reputation'] + value))
        elif resource == 'armor':
            location = str((body or {}).get('subject') or '')
            piece = (data.get('armor') or {}).get(location)
            if not isinstance(piece, dict): raise ApiError(400, 'Локация брони не экипирована')
            maximum = _num(piece.get('maximum')) or _num(piece.get('sp')) or _num(piece.get('sdp')) or 0
            piece['current'] = maximum if action == 'reset' else max(0, min(maximum, (_num(piece.get('current')) or 0) + value))
        elif resource == 'vehicle_sdp':
            if _num((body or {}).get('revision')) != (_row_value(row, 'revision', 0) or 0):
                raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
            instance_id = str((body or {}).get('subject') or '')
            sync_vehicle_states_with_modifications(conn, row['id'], data)
            state = (data.get('vehicle_state') or {}).get(instance_id)
            if not state:
                raise ApiError(400, 'Vehicle instance не найден')
            maximum = _num(state.get('sdp_max')) or 0
            current = _num(state.get('sdp_current')) or 0
            if action == 'reset' or value > 0:
                raise ApiError(409, 'Используйте Vehicle Repair Workflow')
            if action != 'delta' or value >= 0:
                raise ApiError(400, 'Vehicle SDP action поддерживает только damage')
            state['sdp_current'] = max(0, min(maximum, current + value))
            self.send_json(self.save_character_data(
                conn, row, data, user['id'],
                f'Vehicle SDP {instance_id}: {current} → {state["sdp_current"]}'))
            return
        elif resource == 'weapon':
            current_revision = _row_value(row, 'revision', 0) or 0
            if _num((body or {}).get('revision')) != current_revision:
                raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
            sync_weapon_states_with_modifications(conn, row['id'], data)
            before = copy.deepcopy(data)
            key = str((body or {}).get('subject') or '')
            weapon = next((item for item in data.get('inventory') or []
                           if isinstance(item, dict) and item.get('instance_id') == key), None)
            if weapon and weapon.get('mounted_modification_id'):
                raise ApiError(409, 'Mounted weapon управляется только через Vehicle Garage')
            state = (data.get('weapon_state') or {}).get(key)
            if not weapon or not state:
                raise ApiError(400, 'Оружие не найдено')
            if action == 'fire':
                modifications = character_modifications(conn, row['id'])
                weapon_modifications = [item for item in modifications
                                        if item.get('host_instance_id') == key]
                owned = {item.get('instance_id'): item for item in data.get('inventory') or []
                         if isinstance(item, dict) and item.get('instance_id')}
                effective_weapon = evaluate_effective_weapon(
                    weapon, weapon_modifications, owned, data)
                action_profile = bound_vehicle_weapon_profile(
                    weapon, effective_weapon, data)
                ammo_cost = max(1, int(action_profile.get('ammo_cost') or 1))
                current = max(0, int(_num(state.get('magazine')) or 0))
                if current < ammo_cost:
                    raise ApiError(409, f'Для атаки требуется {ammo_cost} патронов')
                state['magazine'] = current - ammo_cost
                clear_loaded_ammo_if_empty(state)
                reason = (f'Fire {weapon.get("custom_name") or weapon.get("name")}: '
                          f'magazine {current} → {state["magazine"]}')
            elif action == 'reload':
                transfer = consume_shared_ammo(
                    data, state, (body or {}).get('ammo_instance_id'), weapon=weapon)
                reason = (
                    f'Reload {weapon.get("custom_name") or weapon.get("name")} '
                    f'with {transfer["ammo_name"]} ×{transfer["moved"]}')
            else:
                raise ApiError(400, 'Weapon action: fire/reload')
            validate_active_modification_references(conn, row['id'], data)
            persist_character_item_instances(
                conn, row['id'], data, 'weapon_action', source_ref=reason, prune=True)
            now = time.time()
            revision_after = current_revision + 1
            ledger_id = record_character_change_set(
                conn, row['id'], user['id'], before, data, reason,
                current_revision, revision_after, category='item_action')
            conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                         (json.dumps(data, ensure_ascii=False), now,
                          revision_after, row['id']))
            conn.commit()
            fresh = self.get_char(conn, row['id'])
            self.send_json({
                'ledger_id': ledger_id,
                'character': self.char_payload(fresh, fresh['owner'], conn=conn),
            })
            return
        else:
            raise ApiError(400, 'Неизвестный ресурс')
        self.send_json(self.save_character_data(conn, row, data))

    @atomic_endpoint
    def api_character_sheet_update(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        expected_revision = _num((body or {}).get('revision'))
        current_revision = _row_value(row, 'revision', 0) or 0
        if expected_revision is None:
            raise ApiError(428, 'Укажите revision Dossier')
        if expected_revision != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        reason = str((body or {}).get('reason') or '').strip()
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину изменения Character Sheet')
        before = json.loads(row['data'])
        after = clean_character_trust_update(before, (body or {}).get('data'))
        if before == after:
            raise ApiError(400, 'В Character Sheet нет изменений')
        validate_cyberware_trust_lifecycle(before, after)
        validate_bound_popup_weapon_references(after)
        validate_popup_shield_references(after)
        validate_armor_tech_references(after)
        validate_armor_repair_references(after)
        validate_tech_maker_references(after)
        validate_active_modification_references(conn, row['id'], after)
        sync_weapon_states_with_modifications(conn, row['id'], after)
        sync_vehicle_states_with_modifications(conn, row['id'], after)
        persist_character_item_instances(
            conn, row['id'], after, 'trust_audit_edit', source_ref=reason, prune=True)
        revision_after = current_revision + 1
        record_character_change_set(
            conn, row['id'], user['id'], before, after, reason,
            current_revision, revision_after)
        conn.execute(
            'UPDATE characters SET data=?,public=?,updated=?,revision=? WHERE id=?',
            (json.dumps(after, ensure_ascii=False), 1 if after.get('public') else 0,
             time.time(), revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json(self.char_payload(fresh, fresh['owner'], conn=conn))

    @atomic_endpoint
    def api_character_specialization(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        data = ensure_progression(json.loads(row['data']))
        parent = str((body or {}).get('parent') or '')
        name = str((body or {}).get('name') or '').strip()[:80]
        delta = 1 if (_num((body or {}).get('delta')) or 0) > 0 else -1
        if parent not in SPECIALIZED_SKILLS or not name:
            raise ApiError(400, 'Укажите parent и specialization')
        key = f'{parent} ({name})'; skills = data.setdefault('skills', {})
        current = _num(skills.get(key)) or 0
        native_key = f'Language ({data.get("native_language")})' if data.get('native_language') else None
        children = 0
        for skill, raw in skills.items():
            if skill_base(skill) != parent or skill == parent: continue
            level = _num(raw) or 0
            children += max(0, level - 4) if skill == native_key else level
        pool = _num((data.get('skill_pools') or {}).get(parent)) or 0
        if delta > 0:
            if current >= 10: raise ApiError(400, 'Specialization уже достигла Level 10')
            if children >= pool: raise ApiError(400, 'Нет свободных parent points')
            skills[key] = current + 1
        else:
            minimum = 4 if key == native_key else 0
            if current <= minimum: raise ApiError(400, f'Specialization уже на минимальном Level {minimum}')
            skills[key] = current - 1
        reason = f'{key} {current} → {skills[key]}'
        self.add_ip_ledger(conn, row['id'], user['id'], 0, data['ip_available'],
                           data['ip_available'], 'allocation', key, reason)
        self.send_json(self.save_character_data(conn, row, data, user['id'], reason))

    @atomic_endpoint
    def api_character_tech_maker_action(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {'revision', 'action', 'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Tech Maker action содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        reason_detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason_detail) < 3:
            raise ApiError(400, 'Укажите причину Tech Maker action')
        modification_id = str(m.group(2)).lower()
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        state = data.get('tech_maker_state')
        mods = state.get('modifications') if isinstance(state, dict) else {}
        mod = mods.get(modification_id) if isinstance(mods, dict) else None
        if not isinstance(mod, dict):
            raise ApiError(404, 'Tech Maker modification не найдена')
        action = str((body or {}).get('action') or '').lower()
        if action == 'remove':
            if mod.get('permanent'):
                raise ApiError(409, 'Permanent Tech Maker modification нельзя снять')
            if not mod.get('active'):
                raise ApiError(409, 'Tech Maker modification уже снята')
            mod['active'] = False
            mod['removed_by'] = user['id']
            mod['removed_at'] = time.time()
            state.setdefault('history', []).append({
                'action': 'remove', 'modification_id': modification_id,
                'name': mod.get('name'), 'host_instance_id': mod.get('host_instance_id'),
                'host_type': mod.get('host_type'), 'at': time.time(),
            })
            state['history'] = state['history'][-50:]
            reason = f'Remove Tech Maker modification {mod.get("name")}: {reason_detail}'
        else:
            raise ApiError(400, 'Tech Maker action: remove')
        validate_tech_maker_references(data)
        persist_character_item_instances(
            conn, row['id'], data, 'tech_maker_action', source_ref=reason_detail, prune=True)
        revision_after = current_revision + 1
        record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='modification')
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), time.time(),
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'modification_id': modification_id,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    @atomic_endpoint
    def api_character_tech_maker_create(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {'revision', 'name', 'description', 'host_instance_id',
                   'maker_specialty', 'tech_name', 'effect', 'manual_rule',
                   'manual_confirm', 'reason', 'notes'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Tech Maker modification содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        name = str((body or {}).get('name') or '').strip()[:120]
        if len(name) < 2:
            raise ApiError(400, 'Укажите название Tech Maker modification')
        tech_name = str((body or {}).get('tech_name') or '').strip()[:120]
        reason_detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(tech_name) < 2 or len(reason_detail) < 3:
            raise ApiError(400, 'Укажите Tech и причину Tech Maker modification')
        specialty = str((body or {}).get('maker_specialty') or '').strip().lower()
        if specialty not in TECH_MAKER_SPECIALTIES:
            raise ApiError(400, 'maker_specialty: upgrade/invention')
        host_id = str((body or {}).get('host_instance_id') or '').lower()
        if not INSTANCE_ID_RE.fullmatch(host_id):
            raise ApiError(400, 'Выберите конкретный host instance')
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        owned = {item.get('instance_id'): item for item in data.get('inventory') or []
                 if isinstance(item, dict) and item.get('instance_id')}
        owned.update({item.get('instance_id'): item for item in data.get('cyberware') or []
                      if isinstance(item, dict) and item.get('instance_id')})
        host = owned.get(host_id)
        if not host:
            raise ApiError(404, 'Host instance не найден')
        if host.get('state') in ('stored', 'broken', 'consumed'):
            raise ApiError(409, 'Host должен быть исправен и находиться при персонаже')
        host_type = tech_maker_host_type(host)
        if not host_type:
            raise ApiError(400, 'Host не поддерживает Tech Maker modifications')
        ranks = character_maker_ranks(data)
        rank = ranks.get(specialty, 0)
        if rank < 1:
            raise ApiError(409, f'Требуется Maker {specialty} rank 1+ для Tech Maker modification')
        effect = clean_tech_maker_effect(host_type, (body or {}).get('effect'))
        manual_rule = str((body or {}).get('manual_rule') or '').strip()[:1000]
        if effect is None and not manual_rule:
            raise ApiError(400, 'Tech Maker modification требует effect или manual_rule')
        if effect is not None and not bool((body or {}).get('manual_confirm')):
            raise ApiError(409, 'Подтвердите успешный Tech Maker Check за столом')
        state = data.setdefault('tech_maker_state', {})
        mods = state.setdefault('modifications', {})
        stack_key = (host_id, (effect or {}).get('target') or 'manual')
        for mod in mods.values():
            if (isinstance(mod, dict) and mod.get('active') and
                    (mod.get('host_instance_id'), (mod.get('effect') or {}).get('target') or 'manual') == stack_key):
                raise ApiError(409, 'Host уже имеет Tech Maker modification этого типа')
        if len(mods) >= 100:
            raise ApiError(409, 'Достигнут лимит Tech Maker modifications')
        modification_id = secrets.token_hex(16)
        now = time.time()
        source = f'Maker: {TECH_MAKER_SPECIALTY_LABELS[specialty][0]} · CP:R 148'
        record = {
            'modification_id': modification_id, 'name': name,
            'description': str((body or {}).get('description') or '').strip()[:2000],
            'host_instance_id': host_id, 'host_type': host_type,
            'host_catalog_item_id': catalog_item_id_for_entry(host),
            'maker_specialty': specialty, 'maker_rank': rank,
            'tech_name': tech_name, 'effect': effect,
            'manual_rule': manual_rule,
            'manual_resolution_required': effect is None,
            'source': source, 'active': True, 'permanent': False,
            'installed_by': user['id'], 'installed_at': now,
            'reason': reason_detail,
            'notes': str((body or {}).get('notes') or '')[:2000],
        }
        mods[modification_id] = record
        state.setdefault('history', []).append({
            'action': 'create', 'modification_id': modification_id,
            'name': name, 'host_instance_id': host_id, 'host_type': host_type,
            'maker_specialty': specialty, 'tech_name': tech_name, 'at': now,
        })
        state['history'] = state['history'][-50:]
        validate_tech_maker_references(data)
        persist_character_item_instances(
            conn, row['id'], data, 'tech_maker_create', source_ref=reason_detail, prune=True)
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data,
            f'Tech Maker {specialty}: {name} on {host.get("name")}: {reason_detail}',
            current_revision, revision_after, category='modification')
        ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                  (ledger_id,)).fetchone()
        delta = parse_json_object(ledger_row['delta_json'])
        delta['tech_maker_modification'] = {
            'modification_id': modification_id, 'name': name,
            'host_instance_id': host_id, 'host_type': host_type,
            'maker_specialty': specialty, 'effect': copy.deepcopy(effect),
            'manual_rule': manual_rule,
        }
        conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                     (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now, revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id, 'modification_id': modification_id,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        }, status=201)

    @atomic_endpoint
    def api_character_tech_maker_fabricate(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {'revision', 'name', 'description', 'blueprint_catalog_id',
                   'category', 'price', 'qty', 'maker_specialty', 'tech_name',
                   'material_cost', 'manual_confirm', 'reason', 'notes'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Tech Maker fabrication содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        name = str((body or {}).get('name') or '').strip()[:120]
        tech_name = str((body or {}).get('tech_name') or '').strip()[:120]
        reason_detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(name) < 2 or len(tech_name) < 2 or len(reason_detail) < 3:
            raise ApiError(400, 'Укажите название, Tech и причину Tech Maker fabrication')
        specialty = str((body or {}).get('maker_specialty') or '').strip().lower()
        if specialty not in TECH_MAKER_FABRICATION_SPECIALTIES:
            raise ApiError(400, 'maker_specialty: fabrication/invention')
        if (body or {}).get('manual_confirm') is not True:
            raise ApiError(400, 'Подтвердите успешный Tech Maker Check за столом')
        try:
            material_cost = max(0, min(9_999_999, int((body or {}).get('material_cost') or 0)))
        except (TypeError, ValueError):
            raise ApiError(400, 'Некорректная стоимость материалов')
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        ranks = character_maker_ranks(data)
        rank = ranks.get(specialty, 0)
        if rank < 1:
            raise ApiError(409, f'Требуется Maker {specialty} rank 1+ для Tech Maker fabrication')
        blueprint_id = str((body or {}).get('blueprint_catalog_id') or '').strip()
        blueprint = item_by_id(blueprint_id) if blueprint_id else None
        if blueprint_id and not blueprint:
            raise ApiError(400, 'Неизвестный blueprint item')
        if blueprint and not tech_maker_fabricable_item(blueprint):
            raise ApiError(400, 'Этот предмет нельзя изготовить через Fabrication Expertise')
        if blueprint and specialty != 'fabrication':
            raise ApiError(400, 'Blueprint fabrication требует maker_specialty fabrication')
        if not blueprint and specialty == 'fabrication':
            raise ApiError(400, 'Fabrication Expertise требует blueprint item')
        try:
            qty = max(1, min(99, int((body or {}).get('qty') or 1)))
        except (TypeError, ValueError):
            raise ApiError(400, 'Некорректное количество')
        if len(data.get('inventory') or []) + len(data.get('cyberware') or []) + qty > 500:
            raise ApiError(400, 'Инвентарь не может содержать больше 500 экземпляров')
        cash = float(data.get('cash') or 0)
        if material_cost > cash + 1e-9:
            raise ApiError(400, f'Не хватает €$: нужно {material_cost:,.0f}, есть {cash:,.0f}')
        inventory = data.setdefault('inventory', [])
        created_instance_ids = []
        if blueprint:
            owned = {
                'key': blueprint['id'], 'catalog_item_id': blueprint['id'],
                'cat': blueprint['cat'], 'name': blueprint['name'],
                'price': blueprint.get('price'), 'qty': 1, 'state': 'carried',
                'damage': blueprint.get('damage'), 'sp': blueprint.get('sp'),
                'hl': blueprint.get('hl'),
                'fields': copy.deepcopy(blueprint.get('fields') or {}),
                'mechanics': copy.deepcopy(blueprint.get('mechanics') or {}),
                'source': blueprint.get('source'),
                'acquisition_source': 'crafted',
                'acquisition_note': f'Fabricated by {tech_name}: {reason_detail}'[:500],
            }
            owned.update(catalog_interaction_data(blueprint))
            owned.update({key: copy.deepcopy(blueprint[key]) for key in ITEM_MODIFICATION_FIELDS if key in blueprint})
            coverage = item_effect_coverage(blueprint.get('id'))
            if coverage:
                owned['effect_coverage'] = coverage
            if item_entry_stackable(owned):
                owned['instance_id'] = new_item_instance_id()
                owned['qty'] = qty
                if blueprint.get('cat') == 'ammo':
                    owned['ammo_rounds'] = qty * ammo_pack_size(owned)
                inventory.append(owned)
                created_instance_ids.append(owned['instance_id'])
            else:
                for _ in range(qty):
                    instance = copy.deepcopy(owned)
                    instance['instance_id'] = new_item_instance_id()
                    inventory.append(instance)
                    created_instance_ids.append(instance['instance_id'])
        else:
            category = str((body or {}).get('category') or 'custom').strip().lower()
            allowed_categories = {row2['id'] for row2 in catalog().get('cats') or []} | {'custom'}
            if category not in allowed_categories:
                raise ApiError(400, 'Некорректная категория custom item')
            price = trust_number((body or {}).get('price', 0),
                                 'Custom item value', 0, 9_999_999)
            stackable = False
            owned = {
                'is_custom': True, 'key': 'custom', 'cat': category,
                'name': name, 'custom_name': name,
                'desc': str((body or {}).get('description') or '')[:4000],
                'price': price, 'stackable': stackable, 'qty': 1,
                'state': 'carried', 'source': 'Tech Maker Invention',
                'manual_resolution_required': True,
                'acquisition_source': 'crafted',
                'acquisition_note': f'Invented by {tech_name}: {reason_detail}'[:500],
            }
            for _ in range(qty):
                instance = copy.deepcopy(owned)
                instance['instance_id'] = new_item_instance_id()
                instance['key'] = f'custom-{instance["instance_id"]}'
                inventory.append(instance)
                created_instance_ids.append(instance['instance_id'])
        data['cash'] = round(cash - material_cost, 2)
        # Fabricated firearms start unloaded, mirroring Night Market purchases.
        for instance_id in created_instance_ids:
            weapon = next((item for item in inventory
                           if isinstance(item, dict) and
                           item.get('instance_id') == instance_id), None)
            if weapon and weapon.get('cat') in ('guns', 'melee'):
                state = (data.get('weapon_state') or {}).get(instance_id)
                if state:
                    state['magazine'] = 0
        state = data.setdefault('tech_maker_state', {})
        fabrication_record = {
            'fabrication_id': secrets.token_hex(16), 'name': name,
            'blueprint_catalog_id': blueprint_id or None,
            'category': blueprint.get('cat') if blueprint else str(
                (body or {}).get('category') or 'custom'),
            'qty': qty, 'maker_specialty': specialty, 'maker_rank': rank,
            'tech_name': tech_name, 'material_cost': material_cost,
            'source': f'Maker: {TECH_MAKER_SPECIALTY_LABELS[specialty][0]} · CP:R 148',
            'at': time.time(), 'reason': reason_detail,
            'instance_ids': created_instance_ids,
        }
        fabrications = state.setdefault('fabrications', [])
        if not isinstance(fabrications, list):
            fabrications = []
            state['fabrications'] = fabrications
        fabrications.append(fabrication_record)
        state['fabrications'] = fabrications[-50:]
        validate_tech_maker_references(data)
        persist_character_item_instances(
            conn, row['id'], data, 'tech_maker_fabricate',
            source_ref=reason_detail, prune=True)
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data,
            f'Tech Maker {specialty}: fabricate {name} ×{qty}: {reason_detail}',
            current_revision, revision_after, category='item_action')
        ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                  (ledger_id,)).fetchone()
        delta = parse_json_object(ledger_row['delta_json'])
        delta['tech_maker_fabrication'] = {
            'fabrication_id': fabrication_record['fabrication_id'],
            'name': name, 'blueprint_catalog_id': blueprint_id or None,
            'qty': qty, 'maker_specialty': specialty, 'material_cost': material_cost,
            'instance_ids': created_instance_ids,
        }
        conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                     (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), time.time(),
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id, 'fabrication': fabrication_record,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        }, status=201)

    @atomic_endpoint
    def api_character_therapy_action(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {
            'revision', 'action', 'therapy_type', 'therapist',
            'addiction_label', 'manual_time_confirmed', 'reason',
        }
        if set(body or {}) - allowed:
            raise ApiError(400, 'Therapy action содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        reason_detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason_detail) < 3:
            raise ApiError(400, 'Укажите причину Therapy action')
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        therapy_state = data.get('therapy_state')
        if not isinstance(therapy_state, dict):
            therapy_state = {'active': None, 'history': []}
            data['therapy_state'] = therapy_state
        if not isinstance(therapy_state.get('history'), list):
            therapy_state['history'] = []
        active = therapy_state.get('active') \
            if isinstance(therapy_state.get('active'), dict) else None
        action = str((body or {}).get('action') or '').lower()
        now = time.time()
        result = {'action': action}
        if action == 'start':
            if active:
                raise ApiError(409, 'Therapy course уже активен')
            therapy_type = str((body or {}).get('therapy_type') or '').lower()
            profile = THERAPY_PROFILES.get(therapy_type)
            if not profile:
                raise ApiError(400, 'Неизвестный Therapy type')
            therapist = str((body or {}).get('therapist') or '').strip()[:120]
            if len(therapist) < 2:
                raise ApiError(400, 'Укажите therapist или clinic')
            cash = float(data.get('cash') or 0)
            if cash < profile['cost']:
                raise ApiError(409, 'Недостаточно средств для Therapy')
            current_humanity = derive(data).get('humanity_cur')
            maximum_humanity = derive(data).get('humanity_max')
            if (profile['humanity_dice'] and current_humanity is not None and
                    maximum_humanity is not None and
                    current_humanity >= maximum_humanity):
                raise ApiError(409, 'Humanity уже достигла Therapy maximum')
            addiction_label = str((body or {}).get('addiction_label') or '').strip()[:120]
            if therapy_type == 'addiction' and len(addiction_label) < 2:
                raise ApiError(400, 'Укажите addiction для Therapy')
            data['cash'] = round(cash - profile['cost'], 2)
            campaign_started = campaign_now(conn)
            active = {
                'therapy_id': secrets.token_hex(16), 'therapy_type': therapy_type,
                'label': profile['label'], 'catalog_id': profile['catalog_id'],
                'cost': profile['cost'], 'duration_days': profile['duration_days'],
                'humanity_dice': profile['humanity_dice'],
                'therapist': therapist, 'addiction_label': addiction_label or None,
                'started_at': now, 'status': 'active', 'source': profile['source'],
                'manual_time_required': True,
                'campaign_started_at': campaign_started,
                'campaign_due_at': campaign_started + campaign_duration_seconds('1_week'),
            }
            therapy_state['active'] = active
            result['therapy'] = copy.deepcopy(active)
            reason = f'Start {profile["label"]}: {reason_detail}'
        elif action in ('resolve', 'cancel'):
            if not active:
                raise ApiError(409, 'Нет активного Therapy course')
            profile = THERAPY_PROFILES.get(active.get('therapy_type'))
            if not profile:
                raise ApiError(409, 'Therapy profile повреждён')
            completed = action == 'resolve'
            if completed and (body or {}).get('manual_time_confirmed') is not True:
                raise ApiError(400, 'Подтвердите завершение недели Therapy')
            history = copy.deepcopy(active)
            history['resolved_at'] = now
            history['status'] = 'completed' if completed else 'canceled'
            history['reason'] = reason_detail
            if completed and profile['humanity_dice']:
                rolled = roll_dice(profile['humanity_dice'], 6)
                derived_before = derive(data)
                current = int(_num(derived_before.get('humanity_cur')) or 0)
                maximum = int(_num(derived_before.get('humanity_max')) or current)
                after = min(maximum, current + rolled['total'])
                data['humanity_cur'] = after
                history.update({
                    'rolls': rolled['rolls'], 'rolled_humanity': rolled['total'],
                    'humanity_before': current, 'humanity_after': after,
                    'humanity_restored': after - current, 'humanity_maximum': maximum,
                })
                result['humanity'] = {
                    'rolls': rolled['rolls'], 'rolled': rolled['total'],
                    'before': current, 'after': after,
                    'restored': after - current, 'maximum': maximum,
                }
            elif completed:
                history['manual_effect'] = (
                    f'Addiction therapy completed for {active.get("addiction_label")}; '
                    'addiction state remains MANUAL RESOLUTION')
                result['manual_effect'] = history['manual_effect']
            therapy_state['history'].append(history)
            therapy_state['history'] = therapy_state['history'][-50:]
            therapy_state['active'] = None
            result['therapy'] = history
            reason = f'{"Resolve" if completed else "Cancel"} {active.get("label")}: {reason_detail}'
        else:
            raise ApiError(400, 'Therapy action: start/resolve/cancel')
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='item_action')
        ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                  (ledger_id,)).fetchone()
        delta = parse_json_object(ledger_row['delta_json'])
        delta['therapy_lifecycle'] = copy.deepcopy(result)
        conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                     (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id, 'result': result,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    @atomic_endpoint
    def api_character_vehicle_repair(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {'revision', 'action', 'technician', 'check_total', 'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Vehicle repair содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        instance_id = str(m.group(2)).lower()
        vehicle = next((item for item in data.get('inventory') or []
                        if isinstance(item, dict) and item.get('instance_id') == instance_id and
                        item.get('cat') == 'vehicles'), None)
        if not vehicle:
            raise ApiError(404, 'Vehicle instance не найден')
        sync_vehicle_states_with_modifications(conn, row['id'], data)
        state = (data.get('vehicle_state') or {}).get(instance_id) or {}
        current = max(0, int(_num(state.get('sdp_current')) or 0))
        maximum = max(0, int(_num(state.get('sdp_max')) or 0))
        action = str((body or {}).get('action') or '').lower()
        reason_detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason_detail) < 3:
            raise ApiError(400, 'Укажите причину Vehicle repair')
        active = state.get('repair') if isinstance(state.get('repair'), dict) else None
        now = time.time()
        if action == 'start':
            if active:
                raise ApiError(409, 'Vehicle repair уже выполняется')
            if maximum <= 0 or current >= maximum:
                raise ApiError(409, 'Vehicle не нуждается в ремонте')
            technician = str((body or {}).get('technician') or '').strip()[:120]
            if len(technician) < 2:
                raise ApiError(400, 'Укажите техника для Vehicle repair')
            severity = vehicle_repair_severity(current, maximum)
            rule = VEHICLE_REPAIR_RULES[severity]
            campaign_started = campaign_now(conn)
            active = {
                'repair_id': secrets.token_hex(16), 'status': 'in_progress',
                'severity': severity, 'skill': vehicle_repair_skill(vehicle),
                'dv': rule['dv'], 'duration_key': rule['duration_key'],
                'duration_en': rule['duration_en'],
                'duration_ru': rule['duration_ru'],
                'technician': technician, 'sdp_before': current,
                'sdp_target': maximum, 'started_at': now,
                'source': 'CP:R 140', 'manual_resolution_required': True,
                'campaign_started_at': campaign_started,
                'campaign_due_at': campaign_started + campaign_duration_seconds(rule['duration_key']),
            }
            state['repair'] = active
            reason = (
                f'Start Vehicle repair for {vehicle.get("custom_name") or vehicle.get("name")}: '
                f'{severity} DV{rule["dv"]}, {rule["duration_en"]}; {reason_detail}')
        elif action in ('resolve', 'cancel'):
            if not active or active.get('status') != 'in_progress':
                raise ApiError(409, 'Нет активного Vehicle repair')
            history_entry = copy.deepcopy(active)
            history_entry['resolved_at'] = now
            if action == 'resolve':
                total = _num((body or {}).get('check_total'))
                if total is None or int(total) != total or not -50 <= total <= 100:
                    raise ApiError(400, 'Укажите итог Repair Check')
                total = int(total)
                success = total >= int(active.get('dv') or 0)
                history_entry.update({
                    'check_total': total,
                    'status': 'success' if success else 'failed',
                    'sdp_after': maximum if success else current,
                })
                if success:
                    state['sdp_current'] = maximum
                reason = (
                    f'Resolve Vehicle repair {active.get("repair_id")}: '
                    f'{total} vs DV{active.get("dv")} → '
                    f'{"success" if success else "failed"}; {reason_detail}')
            else:
                history_entry.update({'status': 'canceled', 'sdp_after': current})
                reason = f'Cancel Vehicle repair {active.get("repair_id")}: {reason_detail}'
            history = state.setdefault('repair_history', [])
            history.append(history_entry)
            state['repair_history'] = history[-50:]
            state.pop('repair', None)
        else:
            raise ApiError(400, 'Vehicle repair action: start/resolve/cancel')
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='vehicle')
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    @atomic_endpoint
    def api_create_character(self, conn, qs, m, body):
        u = self.require_user(conn)
        data = clean_character(body.get('data') if isinstance(body, dict) else body)
        validate_creation(data)
        # Client-provided IDs are never trusted for a new Dossier. Durable items
        # become separate owned instances; clearly stackable ammunition stays one row.
        ensure_character_item_instances(data, regenerate=True)
        if len(data.get('inventory') or []) + len(data.get('cyberware') or []) > 500:
            raise ApiError(400, 'Инвентарь не может содержать больше 500 экземпляров')
        ensure_progression(data)
        owned_rows = conn.execute('SELECT data FROM characters WHERE owner_id=?',
                                  (u['id'],)).fetchall()
        count = sum(1 for item in owned_rows if not parse_json_object(item['data']).get('archived'))
        if count >= 50:
            raise ApiError(400, 'Слишком много персонажей (максимум 50)')
        now = time.time()
        pub = 1 if data.get('public', False) else 0
        cur = conn.execute(
            'INSERT INTO characters(owner_id, public, data, created, updated) VALUES(?,?,?,?,?)',
            (u['id'], pub, json.dumps(data, ensure_ascii=False), now, now))
        attach_character_media(conn, u['id'], cur.lastrowid, data)
        persist_character_item_instances(
            conn, cur.lastrowid, data, 'character_creation', acquired_at=now, prune=True)
        record_character_changes(conn, cur.lastrowid, u['id'], {}, data, 'Character created')
        conn.commit()
        row = conn.execute('SELECT * FROM characters WHERE id=?', (cur.lastrowid,)).fetchone()
        self.send_json(self.char_payload(row, u['display_name'], conn=conn), status=201)

    def api_crew_reputation(self, conn, qs, m, body):
        rows = conn.execute(
            'SELECT cr.*,p.display_name org_name,p.handle org_handle '
            'FROM crew_reputation cr JOIN personas p ON p.id=cr.organization_persona_id '
            'ORDER BY cr.updated DESC').fetchall()
        self.send_json({'reputation': [dict(r) for r in rows]})

    @atomic_endpoint
    def api_crew_reputation_delete(self, conn, qs, m, body):
        user = self.require_gm(conn)
        conn.execute('DELETE FROM crew_reputation WHERE id=?', (int(m.group(1)),))
        conn.commit()
        self.send_json({'ok': True})

    @atomic_endpoint
    def api_crew_reputation_set(self, conn, qs, m, body):
        user = self.require_gm(conn)
        cleaned = clean_reputation_input(body or {})
        if not cleaned['organization_persona_id']:
            raise ApiError(400, 'Укажите организацию')
        now = time.time()
        conn.execute(
            'INSERT INTO crew_reputation(organization_persona_id,reputation,'
            'favor,heat,standing,note,created_by,created,updated) '
            'VALUES(?,?,?,?,?,?,?,?,?) '
            'ON CONFLICT(organization_persona_id) DO UPDATE SET '
            'reputation=excluded.reputation,favor=excluded.favor,heat=excluded.heat,'
            'standing=excluded.standing,note=excluded.note,updated=excluded.updated',
            (cleaned['organization_persona_id'], cleaned['reputation'],
             cleaned['favor'], cleaned['heat'], cleaned['standing'],
             cleaned['note'], user['id'], now, now))
        conn.commit()
        row = conn.execute(
            'SELECT * FROM crew_reputation WHERE organization_persona_id=?',
            (cleaned['organization_persona_id'],)).fetchone()
        self.send_json(dict(row))

    def api_crew_stash(self, conn, qs, m, body):
        user = self.require_user(conn)
        self.send_json({
            'stash': crew_stash_payload(conn),
            'characters': transfer_targets(conn, user),
        })

    @atomic_endpoint
    def api_crew_stash_take(self, conn, qs, m, body):
        user, target_row = self.require_character_editor(
            conn, _num((body or {}).get('char_id')), allow_gm=True)
        allowed = {'char_id', 'instance_id', 'quantity', 'notes'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Crew Stash take содержит неподдерживаемые поля')
        instance_id = str((body or {}).get('instance_id') or '').lower()
        if not INSTANCE_ID_RE.fullmatch(instance_id):
            raise ApiError(400, 'Некорректный идентификатор предмета')
        stash_row = conn.execute(
            'SELECT * FROM crew_stash WHERE instance_id=?', (instance_id,)).fetchone()
        if not stash_row:
            raise ApiError(404, 'Предмет не найден в Crew Stash')
        notes = str((body or {}).get('notes') or '').strip()[:500]
        target_before = enrich_owned_item_interactions(
            ensure_progression(json.loads(target_row['data'])))
        target_data = copy.deepcopy(target_before)
        entry = parse_json_object(stash_row['data_json'])
        full_qty = max(1, int(entry.get('qty') or 1))
        try:
            qty = max(1, int((body or {}).get('quantity') or 0)) \
                if (body or {}).get('quantity') is not None else full_qty
        except (TypeError, ValueError):
            raise ApiError(400, 'Некорректное количество')
        if qty > full_qty:
            raise ApiError(400, 'Недостаточно единиц в Crew Stash')
        if not item_entry_stackable(entry) and qty > 1:
            raise ApiError(400, 'Этот предмет берётся поштучно (не stackable)')
        partial = qty < full_qty
        taken = copy.deepcopy(entry)
        taken['qty'] = qty
        if entry.get('cat') == 'ammo':
            pack = ammo_pack_size(entry)
            rounds = ammo_rounds(entry)
            taken['ammo_rounds'] = qty * pack
            remaining_rounds = max(0, rounds - qty * pack)
        else:
            remaining_rounds = None
        moved_id = instance_id
        if partial:
            remaining = copy.deepcopy(entry)
            remaining['qty'] = full_qty - qty
            if remaining_rounds is not None:
                remaining['ammo_rounds'] = remaining_rounds
            moved_id = new_item_instance_id()
            taken['instance_id'] = moved_id
            conn.execute(
                'UPDATE crew_stash SET quantity=?,data_json=?,updated=? WHERE instance_id=?',
                (remaining['qty'], json.dumps(remaining, ensure_ascii=False),
                 time.time(), instance_id))
        else:
            conn.execute('DELETE FROM crew_stash WHERE instance_id=?', (instance_id,))
        taken['instance_id'] = moved_id
        _attach_runtime_state(target_data, taken, moved_id)
        _attach_tech_maker_modifications(target_data, taken)
        cleaned = _prepare_entry_for_holder(taken, 'char')
        cleaned['instance_id'] = moved_id
        target_data.setdefault('inventory', []).append(cleaned)
        message = f'Take {_character_item_name(taken)} ×{qty} from Crew Stash'
        _record_item_transfer(
            conn, moved_id, 'take', user['id'], notes,
            from_character_id=None, to_character_id=target_row['id'],
            from_bucket='stash', to_bucket='inventory', quantity=qty)
        _persist_transfer_side(conn, target_row['id'], target_data,
                               'crew_stash_take', message)
        revision = _row_value(target_row, 'revision', 0) or 0
        _record_transfer_ledger(conn, target_row['id'], user['id'], target_before,
                                target_data, message, revision, revision + 1)
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(target_data, ensure_ascii=False), time.time(),
                      revision + 1, target_row['id']))
        conn.commit()
        fresh = self.get_char(conn, target_row['id'])
        self.send_json({'ok': True, 'action': 'take', 'message': message,
                        'character': self.char_payload(fresh, fresh['owner'], conn=conn)})

    @atomic_endpoint
    def api_delete_character(self, conn, qs, m, body):
        u = self.require_user(conn)
        row = self.get_char(conn, m.group(1))
        if row['owner_id'] != u['id']:
            raise ApiError(403, 'Это не ваш персонаж')
        network_refs = sum(conn.execute(query, (row['id'],)).fetchone()['n'] for query in (
            'SELECT COUNT(*) n FROM contract_signups WHERE character_id=?',
            'SELECT COUNT(*) n FROM feed_posts WHERE author_character_id=?',
            'SELECT COUNT(*) n FROM feed_comments WHERE author_character_id=?',
            'SELECT COUNT(*) n FROM session_combatants WHERE character_id=?',
        ))
        if network_refs:
            data = json.loads(row['data'])
            data['archived'] = True
            data['public'] = False
            data['archive_reason'] = 'Preserved because this Dossier has NC//NET history.'
            now = time.time()
            active = conn.execute(
                "SELECT s.* FROM contract_signups s JOIN contracts c ON c.id=s.contract_id "
                "WHERE s.character_id=? AND s.status IN ('crew','waitlist') "
                "AND c.status IN ('open','crew_full','in_progress')",
                (row['id'],)).fetchall()
            for signup in active:
                conn.execute("UPDATE contract_signups SET status='withdrawn',updated=? WHERE id=?",
                             (now, signup['id']))
                if signup['status'] == 'crew':
                    promoted = conn.execute(
                        "SELECT * FROM contract_signups WHERE contract_id=? AND status='waitlist' "
                        'ORDER BY queue_position,joined_at LIMIT 1', (signup['contract_id'],)).fetchone()
                    if promoted:
                        conn.execute("UPDATE contract_signups SET status='crew',updated=? WHERE id=?",
                                     (now, promoted['id']))
                        add_notification(conn, promoted['user_id'], 'contract_promoted',
                                         'Promoted from waitlist', 'A Crew place became available.',
                                         f'#/contracts/{signup["contract_id"]}')
                    else:
                        conn.execute("UPDATE contracts SET status='open',updated=? WHERE id=? AND status='crew_full'",
                                     (now, signup['contract_id']))
            conn.execute('UPDATE characters SET public=0,data=?,updated=?,revision=revision+1 WHERE id=?',
                         (json.dumps(data, ensure_ascii=False), now, row['id']))
            record_character_changes(conn, row['id'], u['id'], json.loads(row['data']), data,
                                     'Dossier archived with NC//NET history')
            conn.commit()
            self.send_json({'ok': True, 'archived': True})
            return
        media_rows = conn.execute("SELECT * FROM media WHERE attached_type='character' AND attached_id=?", (row['id'],)).fetchall()
        conn.execute("DELETE FROM media WHERE attached_type='character' AND attached_id=?", (row['id'],))
        conn.execute('DELETE FROM ip_ledger WHERE character_id=?', (row['id'],))
        conn.execute('DELETE FROM character_ledger WHERE character_id=?', (row['id'],))
        conn.execute('DELETE FROM item_modifications WHERE character_id=?', (row['id'],))
        conn.execute('DELETE FROM item_instances WHERE character_id=?', (row['id'],))
        conn.execute('DELETE FROM active_effect_instances WHERE character_id=?', (row['id'],))
        conn.execute('DELETE FROM characters WHERE id=?', (row['id'],))
        conn.commit()
        for media in media_rows:
            try: os.remove(os.path.join(UPLOAD_DIR, media['filename']))
            except FileNotFoundError: pass
        self.send_json({'ok': True, 'archived': False})

    def api_get_character(self, conn, qs, m, body):
        row = self.get_char(conn, m.group(1))
        user = self.current_user(conn)
        owner_view = bool(user and user['id'] == row['owner_id'])
        admin_view = user_is_admin(user)
        if not row['public'] and not (owner_view or admin_view):
            raise ApiError(403, 'Персонаж приватный')
        privileged_name = bool(owner_view or user_is_gm(user))
        owner_name = row['owner'] if (privileged_name or row['owner_show_name']) else None
        self.send_json(self.char_payload(
            row, owner_name, public_view=not (owner_view or admin_view), conn=conn))

    def api_my_characters(self, conn, qs, m, body):
        u = self.require_user(conn)
        rows = conn.execute(
            'SELECT * FROM characters WHERE owner_id=? ORDER BY updated DESC',
            (u['id'],)).fetchall()
        self.send_json({'characters': [self.char_payload(r, u['display_name'], conn=conn) for r in rows]})

    def api_personal_stash(self, conn, qs, m, body):
        user = self.require_user(conn)
        cid = int(m.group(1))
        char = conn.execute('SELECT * FROM characters WHERE id=?', (cid,)).fetchone()
        if not char:
            raise ApiError(404, 'Персонаж не найден')
        if char['owner_id'] != user['id'] and not user_is_gm(user):
            raise ApiError(403, 'Это не ваш персонаж')
        rows = conn.execute(
            'SELECT * FROM personal_stash WHERE character_id=? ORDER BY stored_at', (cid,)).fetchall()
        payload = []
        for row in rows:
            item = dict(row)
            try:
                item.update(json.loads(row['data_json'] or '{}'))
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
            payload.append(item)
        self.send_json({'stash': payload, 'character_id': cid})

    @atomic_endpoint
    def api_personal_stash_action(self, conn, qs, m, body):
        user = self.require_user(conn)
        cid = int(m.group(1))
        char = conn.execute('SELECT * FROM characters WHERE id=?', (cid,)).fetchone()
        if not char:
            raise ApiError(404, 'Персонаж не найден')
        if char['owner_id'] != user['id'] and not user_is_gm(user):
            raise ApiError(403, 'Это не ваш персонаж')
        action = str((body or {}).get('action') or '').lower()
        instance_id = str((body or {}).get('instance_id') or '').lower()
        if action not in ('store', 'take'):
            raise ApiError(400, 'Действие: store или take')
        if action == 'take':
            row = conn.execute(
                'SELECT * FROM personal_stash WHERE instance_id=? AND character_id=?',
                (instance_id, cid)).fetchone()
            if not row:
                raise ApiError(404, 'Предмет не найден в личном тайнике')
            data = json.loads(char['data'])
            data = ensure_progression(data)
            ensure_character_item_instances(data)
            item_data = json.loads(row['data_json'] or '{}')
            item_data['instance_id'] = instance_id
            item_data['state'] = 'carried'
            data.setdefault('inventory', []).append(item_data)
            persist_character_item_instances(conn, cid, data, 'personal_stash_take')
            conn.execute('DELETE FROM personal_stash WHERE instance_id=? AND character_id=?',
                         (instance_id, cid))
            conn.execute('UPDATE characters SET data=?,updated=?,revision=revision+1 WHERE id=?',
                         (json.dumps(data, ensure_ascii=False), time.time(), cid))
            conn.commit()
            self.send_json({'ok': True, 'action': 'take'})
        else:  # store
            data = json.loads(char['data'])
            data = ensure_progression(data)
            inv = data.get('inventory') or []
            item = next((e for e in inv if isinstance(e, dict) and e.get('instance_id') == instance_id), None)
            if not item:
                raise ApiError(404, 'Предмет не найден в инвентаре')
            if item.get('state') in ('equipped', 'installed'):
                raise ApiError(409, 'Сначала снимите предмет')
            stash_data = copy.deepcopy(item)
            for key in ('active',):
                stash_data.pop(key, None)
            stash_data['state'] = 'stored'
            now = time.time()
            conn.execute(
                'INSERT OR REPLACE INTO personal_stash(instance_id,character_id,catalog_item_id,'
                'custom_name,state,quantity,notes,stored_at,data_json,created,updated) '
                'VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (instance_id, cid, stash_data.get('catalog_item_id') or stash_data.get('key') or '',
                 str(stash_data.get('custom_name') or stash_data.get('name') or '')[:120],
                 'stored', max(1, int(stash_data.get('qty') or 1)),
                 str(stash_data.get('notes') or '')[:5000], now,
                 json.dumps(stash_data, ensure_ascii=False), now, now))
            inv = [e for e in inv if not (isinstance(e, dict) and e.get('instance_id') == instance_id)]
            data['inventory'] = inv
            persist_character_item_instances(conn, cid, data, 'personal_stash_store')
            conn.execute('UPDATE characters SET data=?,updated=?,revision=revision+1 WHERE id=?',
                         (json.dumps(data, ensure_ascii=False), time.time(), cid))
            conn.commit()
            self.send_json({'ok': True, 'action': 'store'})

    @atomic_endpoint
    def api_save_character(self, conn, qs, m, body):
        u = self.require_user(conn)
        row = self.get_char(conn, m.group(1))
        if row['owner_id'] != u['id']:
            raise ApiError(403, 'Это не ваш персонаж')
        old_data = json.loads(row['data'])
        if old_data.get('archived'):
            raise ApiError(409, 'Архивное досье доступно только для чтения')
        expected_revision = _num((body or {}).get('revision'))
        if expected_revision is None:
            raise ApiError(428, 'Укажите revision Dossier')
        if expected_revision != (_row_value(row, 'revision', 0) or 0):
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        patch = clean_character_profile_patch(old_data, body or {})
        data = dict(old_data)
        data.update(patch)
        pub = 1 if patch.get('public', bool(row['public'])) else 0
        data['public'] = bool(pub)
        old_media = str(old_data.get('portrait_media_id') or '')
        new_media = str(data.get('portrait_media_id') or '')
        if old_media and old_media != new_media:
            conn.execute("UPDATE media SET attached_type=NULL, attached_id=NULL WHERE id=? AND owner_id=? AND attached_type='character' AND attached_id=?",
                         (old_media, u['id'], row['id']))
        attach_character_media(conn, u['id'], row['id'], data)
        record_character_changes(conn, row['id'], u['id'], old_data, data,
                                 str((body or {}).get('reason') or 'Dossier profile update'))
        conn.execute('UPDATE characters SET data=?,public=?,updated=?,revision=revision+1 WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), pub, time.time(), row['id']))
        conn.commit()
        row = self.get_char(conn, row['id'])
        self.send_json(self.char_payload(row, row['owner'], conn=conn))

    def char_payload(self, row, owner_name=None, public_view=False, conn=None):
        full_data = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        visibility = ensure_character_visibility(full_data)
        data = public_character_data(full_data) if public_view else full_data
        active_effects = character_effect_instances(conn, row['id']) if conn is not None else []
        derived = derive(full_data, active_effects)
        if conn is not None:
            modifications = character_modifications(conn, row['id'])
            derived['modifications'] = modifications
            derived['effective_weapons'] = character_effective_weapons(
                full_data, modifications)
            derived['effective_vehicles'] = character_effective_vehicles(
                full_data, modifications)
            derived['effective_cyberdecks'] = character_effective_cyberdecks(
                full_data, modifications)
            derived['tech_maker'] = tech_maker_payload(full_data)
            derived['campaign_services'] = character_campaign_services(full_data, conn)
            derived['campaign_time'] = campaign_now(conn)
            derived['loans'] = character_open_loans(conn, row['id'])
            derived['downtime'] = downtime_payload(full_data, conn=conn)
        if public_view:
            derived.pop('loans', None)
            derived.pop('downtime', None)
        if public_view and not visibility['combat']:
            derived = {}
        elif public_view:
            if not visibility['equipment']:
                for private_key in ('modifications', 'effective_weapons',
                                    'effective_vehicles', 'effective_cyberdecks',
                                    'effective_cyberware', 'effective_armor_hosts',
                                    'tech_maker', 'campaign_services', 'downtime'):
                    derived.pop(private_key, None)
            for effect in (derived.get('effects') or {}).get('instances') or []:
                for private_key in ('reason', 'actor', 'source_item_instance_id'):
                    effect.pop(private_key, None)
            for modification in derived.get('modifications') or []:
                for private_key in ('notes', 'installer', 'configuration'):
                    modification.pop(private_key, None)
            for armor_host in (derived.get('effective_armor_hosts') or {}).get('hosts', []):
                tech_upgrade = armor_host.get('tech_upgrade')
                if isinstance(tech_upgrade, dict):
                    for private_key in ('tech_name', 'installed_by', 'reason'):
                        tech_upgrade.pop(private_key, None)
                tech_maker = armor_host.get('tech_maker_modification')
                if isinstance(tech_maker, dict):
                    for private_key in ('tech_name', 'installed_by', 'reason', 'notes'):
                        tech_maker.pop(private_key, None)
            for vehicle in (derived.get('effective_vehicles') or {}).values():
                repair_state = vehicle.get('state') or {}
                if isinstance(repair_state.get('repair'), dict):
                    repair_state['repair'].pop('technician', None)
                for repair in repair_state.get('repair_history') or []:
                    if isinstance(repair, dict):
                        repair.pop('technician', None)
                tech_maker = vehicle.get('tech_maker_modification')
                if isinstance(tech_maker, dict):
                    for private_key in ('tech_name', 'installed_by', 'reason', 'notes'):
                        tech_maker.pop(private_key, None)
            for mod in (derived.get('tech_maker') or {}).get('modifications') or []:
                for private_key in ('tech_name', 'reason', 'notes'):
                    mod.pop(private_key, None)
            for deck in (derived.get('effective_cyberdecks') or {}).values():
                for program in deck.get('programs') or []:
                    entity = program.get('net_entity')
                    if isinstance(entity, dict):
                        for private_key in ('floor_label', 'target_label',
                                            'owner_character_id', 'initiative_roll',
                                            'session_id', 'session_floor_id',
                                            'session_node_id', 'session_node_label',
                                            'target_combatant_id'):
                            entity.pop(private_key, None)
        return {
            'id': row['id'], 'revision': _row_value(row, 'revision', 0),
            'owner_id': row['owner_id'] if (not public_view or owner_name) else None,
            'public': bool(row['public']),
            'owner_name': owner_name, 'created': row['created'], 'updated': row['updated'],
            'data': data, 'derived': derived,
            'reputation': self._reputation_for(row['id'], conn, public_view),
        }

    def get_char(self, conn, cid):
        try:
            cid = int(cid)
        except (TypeError, ValueError):
            raise ApiError(404, 'Персонаж не найден')
        row = conn.execute(
            'SELECT c.*,u.display_name owner,u.show_display_name owner_show_name '
            'FROM characters c JOIN users u ON u.id=c.owner_id WHERE c.id=?',
            (cid,)).fetchone()
        if not row:
            raise ApiError(404, 'Персонаж не найден')
        return row

    def modification_management_payload(self, conn, row):
        data = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        owned = {entry.get('instance_id'): entry for bucket in ('inventory', 'cyberware')
                 for entry in data.get(bucket) or [] if isinstance(entry, dict) and entry.get('instance_id')}
        modifications = character_modifications(conn, row['id'])
        hosts = []
        for host in (entry for entry in data.get('inventory') or []
                     if isinstance(entry, dict) and entry.get('cat') == 'guns'):
            active = [mod for mod in modifications if mod['host_instance_id'] == host.get('instance_id')]
            pools = weapon_slot_capacity(host, active, owned)
            host_summary = {
                'instance_id': host.get('instance_id'), 'name': host.get('custom_name') or host.get('name'),
                'catalog_item_id': catalog_item_id_for_entry(host), 'state': host.get('state'),
                'weapon_type': (host.get('mechanics') or {}).get('type'),
                'skill': (host.get('mechanics') or {}).get('skill'),
                'exotic': weapon_is_exotic(host),
                'slots_total': sum(pool['total'] for pool in pools.values()),
                'slots_used': sum(pool['used'] for pool in pools.values()),
                'slot_pools': pools,
                'modification_ids': [mod['modification_id'] for mod in active],
            }
            hosts.append(host_summary)
        upgrades = []
        for upgrade in (entry for entry in data.get('inventory') or []
                        if isinstance(entry, dict) and entry.get('cat') == 'gun_upgrades'):
            matrix = {}
            configuration_by_host = {}
            for host in (entry for entry in data.get('inventory') or []
                         if isinstance(entry, dict) and entry.get('cat') == 'guns'):
                active = [mod for mod in modifications if mod['host_instance_id'] == host.get('instance_id')]
                matrix[host['instance_id']] = weapon_upgrade_compatibility(
                    host, upgrade, active, owned)
                configuration_by_host[host['instance_id']] = weapon_modification_configuration_schema(
                    catalog_item_id_for_entry(upgrade), host)
            upgrades.append({
                'instance_id': upgrade.get('instance_id'),
                'catalog_item_id': catalog_item_id_for_entry(upgrade),
                'name': upgrade.get('custom_name') or upgrade.get('name'),
                'state': upgrade.get('state'), 'slots_used': upgrade.get('slots_used') or 0,
                'permanent_installation': bool(upgrade.get('permanent_installation')),
                'compatibility_manual': bool(upgrade.get('compatibility_manual')),
                'compatibility_text': upgrade.get('compatibility_text') or '',
                'configuration_schemas': weapon_modification_configuration_schema(
                    catalog_item_id_for_entry(upgrade)),
                'configuration_by_host': configuration_by_host,
                'compatibility': matrix,
            })
        effective_vehicle_map = character_effective_vehicles(data, modifications)
        vehicle_hosts = []
        for host in (entry for entry in data.get('inventory') or []
                     if isinstance(entry, dict) and entry.get('cat') == 'vehicles'):
            active = [mod for mod in modifications if mod['host_instance_id'] == host.get('instance_id')]
            mechanics = host.get('mechanics') or {}
            vehicle_effective = effective_vehicle_map.get(host.get('instance_id')) or {}
            vehicle_hosts.append({
                'instance_id': host.get('instance_id'),
                'catalog_item_id': catalog_item_id_for_entry(host),
                'name': host.get('custom_name') or host.get('name'),
                'state': host.get('state'), 'classes': sorted(vehicle_classification(host)),
                'sdp': mechanics.get('sdp'), 'sp': mechanics.get('sp'),
                'seats': mechanics.get('seats'),
                'combat_speed': mechanics.get('combat_speed'),
                'narrative_speed': mechanics.get('narrative_speed'),
                'nomad_access': mechanics.get('nomad_access'),
                'base': vehicle_effective.get('base') or mechanics,
                'effective': vehicle_effective.get('effective') or mechanics,
                'vehicle_state': vehicle_effective.get('state') or {},
                'effect_sources': vehicle_effective.get('sources') or [],
                'nos_tanks': vehicle_effective.get('nos_tanks') or [],
                'mounted_weapons': vehicle_effective.get('mounted_weapons') or [],
                'weapon_mounts': vehicle_effective.get('weapon_mounts') or [],
                'interior': vehicle_effective.get('interior') or {},
                'cargo_modules': vehicle_effective.get('cargo_modules') or [],
                'modification_ids': [mod['modification_id'] for mod in active],
            })
        vehicle_upgrades = []
        for upgrade in (entry for entry in data.get('inventory') or []
                        if isinstance(entry, dict) and entry.get('cat') == 'vehicles_upgrades'):
            matrix = {}
            for host in (entry for entry in data.get('inventory') or []
                         if isinstance(entry, dict) and entry.get('cat') == 'vehicles'):
                active = [mod for mod in modifications if mod['host_instance_id'] == host.get('instance_id')]
                matrix[host['instance_id']] = vehicle_upgrade_compatibility(
                    host, upgrade, active, owned, data)
            vehicle_upgrades.append({
                'instance_id': upgrade.get('instance_id'),
                'catalog_item_id': catalog_item_id_for_entry(upgrade),
                'name': upgrade.get('custom_name') or upgrade.get('name'),
                'state': upgrade.get('state'),
                'availability_text': upgrade.get('availability_text') or '',
                'nomad_access_required': upgrade.get('nomad_access_required'),
                'repeatable_max': upgrade.get('repeatable_max') or 1,
                'permanent_installation': bool(upgrade.get('permanent_installation')),
                'compatibility_manual': bool(upgrade.get('compatibility_manual')),
                'configuration_schemas': vehicle_modification_configuration_schema(
                    catalog_item_id_for_entry(upgrade)),
                'compatibility': matrix,
            })
        effective_deck_map = character_effective_cyberdecks(data, modifications)
        cyberdeck_hosts = []
        deck_entries = [
            entry for entry in data.get('inventory') or []
            if isinstance(entry, dict) and entry.get('cat') == 'net_stuff' and
            (entry.get('mechanics') or {}).get('type') == 'Cyberdeck']
        for host in deck_entries:
            effective = effective_deck_map.get(host.get('instance_id')) or {}
            cyberdeck_hosts.append({
                'instance_id': host.get('instance_id'),
                'catalog_item_id': catalog_item_id_for_entry(host),
                'name': host.get('custom_name') or host.get('name'),
                'state': host.get('state'),
                'slot_pools': effective.get('pools') or {},
                'slots_total': effective.get('slots_total') or 0,
                'slots_used': effective.get('slots_used') or 0,
                'hardware': effective.get('hardware') or [],
                'programs': effective.get('programs') or [],
                'modification_ids': [
                    mod['modification_id'] for mod in modifications
                    if mod.get('host_instance_id') == host.get('instance_id')],
            })
        cyberdeck_items = []
        for upgrade in (entry for entry in data.get('inventory') or []
                        if isinstance(entry, dict) and
                        entry.get('host_type') == 'cyberdeck'):
            matrix = {}
            for host in deck_entries:
                active = [mod for mod in modifications
                          if mod.get('host_instance_id') == host.get('instance_id')]
                matrix[host['instance_id']] = cyberdeck_item_compatibility(
                    host, upgrade, active, owned)
            cyberdeck_items.append({
                'instance_id': upgrade.get('instance_id'),
                'catalog_item_id': catalog_item_id_for_entry(upgrade),
                'name': upgrade.get('custom_name') or upgrade.get('name'),
                'state': upgrade.get('state'),
                'item_kind': upgrade.get('modification_kind'),
                'program_class': (upgrade.get('mechanics') or {}).get('program_class'),
                'slots_used': upgrade.get('slots_used') or 1,
                'compatibility': matrix,
            })
        for modification in modifications:
            config = modification.get('configuration') or {}
            modification['host_name'] = (owned.get(modification['host_instance_id']) or {}).get('custom_name') or (owned.get(modification['host_instance_id']) or {}).get('name') or config.get('host_name')
            modification['upgrade_name'] = (owned.get(modification['upgrade_instance_id']) or {}).get('custom_name') or (owned.get(modification['upgrade_instance_id']) or {}).get('name') or config.get('upgrade_name')
        return {
            'character_id': row['id'], 'revision': _row_value(row, 'revision', 0) or 0,
            'hosts': hosts, 'upgrades': upgrades,
            'vehicle_hosts': vehicle_hosts, 'vehicle_upgrades': vehicle_upgrades,
            'cyberdeck_hosts': cyberdeck_hosts, 'cyberdeck_items': cyberdeck_items,
            'modifications': modifications,
        }

    def save_character_data(self, conn, row, data, actor_id=None, reason='Character progression'):
        if actor_id is not None:
            record_character_changes(conn, row['id'], actor_id, json.loads(row['data']), data, reason)
        conn.execute('UPDATE characters SET data=?,public=?,updated=?,revision=revision+1 WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), 1 if data.get('public') else 0,
                      time.time(), row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        return self.char_payload(fresh, fresh['owner'], conn=conn)

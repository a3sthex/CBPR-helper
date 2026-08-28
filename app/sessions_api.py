"""Сессии NC//NET: комнаты, доступ, бой с инициативой, NET-действия раннера, шаблоны NPC (миксин Handler; P1, логика не менялась)."""


import copy
import json
import secrets
import time

from catalog import enrich_owned_item_interactions, item_by_id
from charbuild import ensure_progression
from core import (ApiError, _row_value, can_edit_contract, parse_json_object,
                  user_is_admin, user_is_gm)
from db import (ATTACKER_PROGRAM_BLACK_ICE_DAMAGE, SAFETY_SIGNAL_KINDS,
                SESSION_ACCESS_ROLES, SESSION_NET_NODE_TYPES,
                SESSION_NET_PATH_DIRECTIONS, SESSION_ROLE_CAPABILITIES,
                SESSION_VIEW_DEFAULTS, black_ice_effect_profile,
                character_effective_cyberdecks, character_interface_rank,
                clean_npc_statblock, clean_npc_template_input,
                cyberdeck_program_category, initial_program_runtime_state,
                instantiate_black_ice_stat_effects, net_actions_for_interface,
                npc_statblock_derived, parse_json_list,
                queue_defense_sequencer_trigger, roll_dice,
                session_net_path_between, session_net_state,
                session_safety_config, session_view_config,
                validate_active_modification_references)
from httpkit import atomic_endpoint, q1
from inventory import (catalog_item_id_for_entry, character_modifications,
                       persist_character_item_instances)
from recap import (add_notification, readable_change_value,
                   record_character_change_set, record_character_changes)
from rules import _num, derive


class SessionsMixin:

    def api_session_access(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or not self.can_manage_session_access(conn, user, session):
            raise ApiError(403, 'Нет права управлять доступом сессии')
        assignments = conn.execute(
            'SELECT a.*,u.username,u.display_name,u.account_role FROM session_access a '
            'JOIN users u ON u.id=a.user_id WHERE a.session_id=? ORDER BY a.role,u.display_name',
            (session['id'],)).fetchall()
        candidates = conn.execute(
            "SELECT id,username,display_name,account_role FROM users "
            "WHERE id>1 AND disabled_at IS NULL AND account_role!='admin' "
            'ORDER BY display_name,username').fetchall()
        self.send_json({
            'owner_user_id': session['owner_user_id'],
            'roles': sorted(SESSION_ACCESS_ROLES),
            'assignments': [dict(row) for row in assignments],
            'candidates': [dict(row) for row in candidates],
        })

    @atomic_endpoint
    def api_session_access_grant(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or not self.can_manage_session_access(conn, user, session):
            raise ApiError(403, 'Нет права управлять доступом сессии')
        target_id = _num((body or {}).get('user_id'))
        role = str((body or {}).get('role') or '').lower()
        target = conn.execute('SELECT * FROM users WHERE id=? AND disabled_at IS NULL',
                              (target_id,)).fetchone()
        if not target or target['id'] == session['owner_user_id'] or role not in SESSION_ACCESS_ROLES:
            raise ApiError(400, 'Некорректная роль участника сессии')
        before = conn.execute('SELECT role FROM session_access WHERE session_id=? AND user_id=?',
                              (session['id'], target['id'])).fetchone()
        now = time.time()
        conn.execute(
            'INSERT INTO session_access(session_id,user_id,role,created_by,created,updated) '
            'VALUES(?,?,?,?,?,?) ON CONFLICT(session_id,user_id) DO UPDATE SET '
            'role=excluded.role,created_by=excluded.created_by,updated=excluded.updated',
            (session['id'], target['id'], role, user['id'], now, now))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,after_json,note,created) '
            'VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'access_grant',
             json.dumps({'user_id': target['id'], 'role': before['role'] if before else None}),
             json.dumps({'user_id': target['id'], 'role': role}), '', now))
        add_notification(conn, target['id'], 'session_access', 'NC//NET Session access',
                         f'{session["title"]}: {role}', f'#/session/{session["id"]}')
        conn.commit()
        self.send_json({'ok': True, 'user_id': target['id'], 'role': role})

    @atomic_endpoint
    def api_session_access_revoke(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or not self.can_manage_session_access(conn, user, session):
            raise ApiError(403, 'Нет права управлять доступом сессии')
        target_id = int(m.group(2))
        before = conn.execute('SELECT * FROM session_access WHERE session_id=? AND user_id=?',
                              (session['id'], target_id)).fetchone()
        if not before:
            raise ApiError(404, 'Назначение доступа не найдено')
        conn.execute('DELETE FROM session_access WHERE session_id=? AND user_id=?',
                     (session['id'], target_id))
        now = time.time()
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,after_json,note,created) '
            'VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'access_revoke', json.dumps(dict(before)),
             json.dumps({'user_id': target_id, 'role': None}), '', now))
        add_notification(conn, target_id, 'session_access_revoked', 'NC//NET Session access revoked',
                         session['title'], None)
        conn.commit()
        self.send_json({'ok': True})

    @atomic_endpoint
    def api_session_black_ice_attack(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or 'edit_combatants' not in self.session_capabilities(conn, user, session)[1]:
            raise ApiError(403, 'Нет права выполнять Black ICE attack')
        allowed = {'selection_mode', 'target_program_instance_id',
                   'target_character_revision', 'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Black ICE attack содержит неподдерживаемые поля')
        entity_id = str(m.group(2)).lower()
        state = session_net_state(_row_value(session, 'net_state_json', '{}'))
        state_before = copy.deepcopy(state)
        link = next((item for item in state['links']
                     if item['net_entity_id'] == entity_id and item['active']), None)
        if not link or not link.get('target_combatant_id'):
            raise ApiError(409, 'Black ICE attack требует active target link')
        source_character = conn.execute('SELECT * FROM characters WHERE id=?',
                                        (link['character_id'],)).fetchone()
        if not source_character:
            raise ApiError(409, 'Source Black ICE Character отсутствует')
        source_data = enrich_owned_item_interactions(
            ensure_progression(json.loads(source_character['data'])))
        entity = (source_data.get('net_entities') or {}).get(entity_id)
        if not isinstance(entity, dict) or entity.get('status') != 'hunting':
            raise ApiError(409, 'Black ICE attack требует hunting entity')
        source_program = next((item for item in source_data.get('inventory') or []
                               if isinstance(item, dict) and
                               item.get('instance_id') == entity.get('source_program_instance_id')), None)
        if not source_program:
            raise ApiError(409, 'Source Black ICE Program отсутствует')
        target_combatant = conn.execute(
            'SELECT * FROM session_combatants WHERE session_id=? AND id=?',
            (session['id'], link['target_combatant_id'])).fetchone()
        if not target_combatant or not target_combatant['character_id']:
            raise ApiError(409, 'Black ICE target требует Netrunner Character')
        target_runner = next((item for item in state['runners']
                              if item['combatant_id'] == target_combatant['id']), None)
        if (not target_runner or not target_runner['jacked_in'] or
                target_runner.get('node_id') != link.get('node_id')):
            raise ApiError(409, 'Black ICE target должен быть Jacked In на том же node')
        target_character = conn.execute('SELECT * FROM characters WHERE id=?',
                                        (target_combatant['character_id'],)).fetchone()
        target_data = enrich_owned_item_interactions(
            ensure_progression(json.loads(target_character['data'])))
        target_interface = character_interface_rank(target_data)
        if target_interface <= 0:
            raise ApiError(409, 'Black ICE target не имеет Interface Rank')
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину Black ICE attack')
        effect = black_ice_effect_profile(source_program)
        attack_die = secrets.randbelow(10) + 1
        attack_total = int(entity.get('atk') or 0) + attack_die
        target_before = None
        target_ledger_id = None
        removed_modification_ids = []
        created_effects = []
        now = time.time()
        result = {
            'action': 'black_ice_attack', 'actor_entity_id': entity_id,
            'name': entity.get('name'), 'attack_roll': attack_die,
            'attack_total': attack_total, 'effect_profile': effect,
        }
        target_program_id = None
        if entity.get('target_type') == 'enemy_program_source':
            target_modifications = character_modifications(conn, target_character['id'])
            target_decks = character_effective_cyberdecks(target_data, target_modifications)
            valid_programs = [
                program for deck in target_decks.values()
                for program in deck.get('programs') or []
                if (program.get('runtime') or {}).get('status') == 'rezzed']
            if not valid_programs:
                raise ApiError(409, 'Нет Rezzed Programs для Anti-Program Black ICE')
            selection_mode = str((body or {}).get('selection_mode') or 'random').lower()
            if selection_mode == 'random':
                target_program = valid_programs[secrets.randbelow(len(valid_programs))]
            elif selection_mode == 'override':
                requested_id = str((body or {}).get('target_program_instance_id') or '').lower()
                target_program = next((program for program in valid_programs
                                       if program['instance_id'] == requested_id), None)
                if not target_program:
                    raise ApiError(400, 'Выбранная target Program не является Rezzed')
            else:
                raise ApiError(400, 'selection_mode: random/override')
            expected_revision = _num((body or {}).get('target_character_revision'))
            if expected_revision != (_row_value(target_character, 'revision', 0) or 0):
                raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
            target_program_id = target_program['instance_id']
            defense_die = secrets.randbelow(10) + 1
            defense_total = int(_num((target_program.get('mechanics') or {}).get('def')) or 0) + defense_die
            success = attack_total > defense_total
            result.update({
                'selection_mode': selection_mode,
                'target_program_instance_id': target_program_id,
                'target_program_name': target_program['name'],
                'defense_roll': defense_die, 'defense_total': defense_total,
                'success': success,
            })
            if success:
                damage = roll_dice(effect.get('damage_dice') or 0, 6)
                if not damage['rolls']:
                    raise ApiError(409, 'Anti-Program Black ICE effect требует manual resolution')
                target_before = copy.deepcopy(target_data)
                program_item = next(item for item in target_data.get('inventory') or []
                                    if isinstance(item, dict) and
                                    item.get('instance_id') == target_program_id)
                runtime = initial_program_runtime_state(
                    program_item, (target_program.get('runtime') or {}).get('deck_instance_id'),
                    (target_program.get('runtime') or {}).get('modification_id'),
                    (target_data.get('program_state') or {}).get(target_program_id))
                previous_rez = runtime['rez_current']
                destroyed = damage['total'] >= previous_rez and effect['destroy_on_derez']
                if destroyed:
                    program_modification = next(
                        item for item in target_modifications
                        if item.get('upgrade_instance_id') == target_program_id)
                    backup_modification = next((
                        item for item in target_modifications
                        if item.get('host_instance_id') == program_modification.get('host_instance_id') and
                        (next((owned for owned in target_data.get('inventory') or []
                               if isinstance(owned, dict) and
                               owned.get('instance_id') == item.get('upgrade_instance_id')), {}) or {}).get('name') == 'Backup Drive'), None)
                    if runtime['category'] != 'black_ice' and backup_modification:
                        backup_state = target_data.setdefault('modification_state', {}).setdefault(
                            backup_modification['modification_id'],
                            {'resource_type': 'backup_drive', 'saved_programs': []})
                        backup_state.setdefault('saved_programs', []).append({
                            'program_instance_id': target_program_id,
                            'modification_id': program_modification['modification_id'],
                            'catalog_item_id': catalog_item_id_for_entry(program_item),
                            'name': program_item.get('name'),
                            'runtime_before': copy.deepcopy(runtime), 'saved_at': now,
                        })
                    runtime['status'] = 'destroyed'
                    runtime['rez_current'] = 0
                    if runtime['category'] == 'black_ice':
                        target_ice = next((ice for ice in
                                           (target_data.get('net_entities') or {}).values()
                                           if isinstance(ice, dict) and
                                           ice.get('source_program_instance_id') == target_program_id and
                                           ice.get('status') in ('lying_in_wait', 'hunting', 'derezzed')), None)
                        if target_ice:
                            target_ice['status'] = 'destroyed'
                            target_ice['rez_current'] = 0
                            target_ice['archived_at'] = now
                            target_ice['updated_at'] = now
                            linked_target_ice = next((item for item in state['links']
                                                      if item['net_entity_id'] ==
                                                      target_ice.get('net_entity_id')), None)
                            if linked_target_ice:
                                linked_target_ice['active'] = False
                    program_item['state'] = 'broken'
                    program_item.pop('host_instance_id', None)
                    conn.execute(
                        'UPDATE item_modifications SET active=0,removed_by=?,removed_at=?,updated=? '
                        'WHERE modification_id=?',
                        (user['id'], now, now, program_modification['modification_id']))
                    removed_modification_ids.append(program_modification['modification_id'])
                else:
                    runtime['rez_current'] = max(0, previous_rez - damage['total'])
                    if runtime['rez_current'] == 0:
                        runtime['status'] = 'derezzed'
                target_data.setdefault('program_state', {})[target_program_id] = runtime
                if runtime['status'] in ('derezzed', 'destroyed'):
                    pending = queue_defense_sequencer_trigger(
                        target_data, target_modifications,
                        runtime.get('deck_instance_id'), target_program_id)
                    if pending:
                        result['defense_sequencer_pending'] = pending
                result.update({
                    'damage_rolls': damage['rolls'], 'damage_total': damage['total'],
                    'rez_before': previous_rez, 'rez_after': runtime['rez_current'],
                    'destroyed': destroyed,
                })
        else:
            defense_die = secrets.randbelow(10) + 1
            defense_total = target_interface + defense_die
            result.update({
                'target_combatant_id': target_combatant['id'],
                'target_interface_rank': target_interface,
                'defense_roll': defense_die, 'defense_total': defense_total,
                'success': attack_total > defense_total,
                'manual_effect': effect['manual_effect'],
            })
            if result['success'] and source_program.get('name') == 'Wisp':
                target_runner['next_action_penalty'] = max(
                    1, target_runner.get('next_action_penalty', 0))
                result['next_action_penalty'] = 1
                result['action_penalty_minimum'] = 2
            if result['success'] and effect['resolution'] == 'automated_stat_penalty':
                expected_revision = _num((body or {}).get('target_character_revision'))
                if expected_revision != (_row_value(target_character, 'revision', 0) or 0):
                    raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
                target_before = copy.deepcopy(target_data)
                stat_effect = instantiate_black_ice_stat_effects(
                    conn, target_character['id'], user['id'], source_program,
                    session['id'], now=now)
                created_effects = stat_effect['created']
                result.update({
                    'effect_application': 'automated',
                    'stat_penalty_roll': stat_effect['penalty_roll'],
                    'stat_penalty_targets': stat_effect['targets'],
                    'created_effects': [{
                        'effect_id': item['effect_id'], 'label': item['label'],
                        'target': (item.get('definition') or {}).get('target'),
                        'value': (item.get('definition') or {}).get('value'),
                        'minimum_value': (item.get('definition') or {}).get(
                            'minimum_value'),
                        'duration_type': item.get('duration_type'),
                    } for item in created_effects],
                    'manual_expiry': True, 'campaign_minutes': 60,
                })
            if result['success'] and effect['resolution'] in (
                    'automated_random_destroy', 'automated_random_derez_plus_manual'):
                target_modifications = character_modifications(conn, target_character['id'])
                target_decks = character_effective_cyberdecks(target_data, target_modifications)
                eligible = [
                    program for deck in target_decks.values()
                    for program in deck.get('programs') or []
                    if (effect['resolution'] == 'automated_random_destroy' or
                        ((program.get('runtime') or {}).get('status') == 'rezzed' and
                         (program.get('runtime') or {}).get('category') == 'defender'))]
                if not eligible:
                    raise ApiError(409, 'Нет допустимых Programs для curated Black ICE effect')
                selection_mode = str((body or {}).get('selection_mode') or 'random').lower()
                if selection_mode == 'random':
                    target_program = eligible[secrets.randbelow(len(eligible))]
                elif selection_mode == 'override':
                    requested_id = str((body or {}).get('target_program_instance_id') or '').lower()
                    target_program = next((program for program in eligible
                                           if program['instance_id'] == requested_id), None)
                    if not target_program:
                        raise ApiError(400, 'Выбранная target Program недопустима')
                else:
                    raise ApiError(400, 'selection_mode: random/override')
                expected_revision = _num((body or {}).get('target_character_revision'))
                if expected_revision != (_row_value(target_character, 'revision', 0) or 0):
                    raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
                target_program_id = target_program['instance_id']
                target_before = copy.deepcopy(target_data)
                program_item = next(item for item in target_data.get('inventory') or []
                                    if isinstance(item, dict) and
                                    item.get('instance_id') == target_program_id)
                runtime = initial_program_runtime_state(
                    program_item, (target_program.get('runtime') or {}).get('deck_instance_id'),
                    (target_program.get('runtime') or {}).get('modification_id'),
                    (target_data.get('program_state') or {}).get(target_program_id))
                if effect['resolution'] == 'automated_random_destroy':
                    program_modification = next(
                        item for item in target_modifications
                        if item.get('upgrade_instance_id') == target_program_id)
                    backup_modification = next((
                        item for item in target_modifications
                        if item.get('host_instance_id') == program_modification.get('host_instance_id') and
                        (next((owned for owned in target_data.get('inventory') or []
                               if isinstance(owned, dict) and
                               owned.get('instance_id') == item.get('upgrade_instance_id')), {}) or {}).get('name') == 'Backup Drive'), None)
                    if runtime['category'] != 'black_ice' and backup_modification:
                        backup_state = target_data.setdefault('modification_state', {}).setdefault(
                            backup_modification['modification_id'],
                            {'resource_type': 'backup_drive', 'saved_programs': []})
                        backup_state.setdefault('saved_programs', []).append({
                            'program_instance_id': target_program_id,
                            'modification_id': program_modification['modification_id'],
                            'catalog_item_id': catalog_item_id_for_entry(program_item),
                            'name': program_item.get('name'),
                            'runtime_before': copy.deepcopy(runtime), 'saved_at': now,
                        })
                    runtime['status'] = 'destroyed'
                    runtime['rez_current'] = 0
                    if runtime['category'] == 'black_ice':
                        target_ice = next((ice for ice in
                                           (target_data.get('net_entities') or {}).values()
                                           if isinstance(ice, dict) and
                                           ice.get('source_program_instance_id') == target_program_id and
                                           ice.get('status') in ('lying_in_wait', 'hunting', 'derezzed')), None)
                        if target_ice:
                            target_ice['status'] = 'destroyed'
                            target_ice['rez_current'] = 0
                            target_ice['archived_at'] = now
                            target_ice['updated_at'] = now
                            linked_target_ice = next((item for item in state['links']
                                                      if item['net_entity_id'] ==
                                                      target_ice.get('net_entity_id')), None)
                            if linked_target_ice:
                                linked_target_ice['active'] = False
                    program_item['state'] = 'broken'
                    program_item.pop('host_instance_id', None)
                    conn.execute(
                        'UPDATE item_modifications SET active=0,removed_by=?,removed_at=?,updated=? '
                        'WHERE modification_id=?',
                        (user['id'], now, now, program_modification['modification_id']))
                    removed_modification_ids.append(program_modification['modification_id'])
                    result['destroyed'] = True
                else:
                    runtime['status'] = 'derezzed'
                    runtime['rez_current'] = 0
                    result['derezzed'] = True
                target_data.setdefault('program_state', {})[target_program_id] = runtime
                if runtime['status'] in ('derezzed', 'destroyed'):
                    pending = queue_defense_sequencer_trigger(
                        target_data, target_modifications,
                        runtime.get('deck_instance_id'), target_program_id)
                    if pending:
                        result['defense_sequencer_pending'] = pending
                result.update({
                    'selection_mode': selection_mode,
                    'target_program_instance_id': target_program_id,
                    'target_program_name': target_program['name'],
                    'rez_after': runtime['rez_current'],
                })
        summary = (f'{entity.get("name")} attack {attack_total} vs '
                   f'{result.get("defense_total")} → '
                   f'{"hit" if result.get("success") else "miss"}')
        action_entry = {
            'action_id': secrets.token_hex(16), 'combatant_id': target_combatant['id'],
            'actor_entity_id': entity_id, 'action': 'black_ice_attack',
            'target_node_id': link.get('node_id'),
            'target_program_instance_id': target_program_id,
            'success': result.get('success'), 'actor_total': attack_total,
            'defense_total': result.get('defense_total'), 'created': now,
            'summary': summary,
        }
        state.setdefault('action_log', []).append(action_entry)
        state['action_log'] = state['action_log'][-100:]
        queue_count = sum(1 for item in state['links']
                          if item['active'] and (_num(item.get('initiative')) or 0) > 0)
        state['active_turn'] = min(state['active_turn'], max(0, queue_count - 1))
        if target_before is not None:
            validate_active_modification_references(
                conn, target_character['id'], target_data)
            persist_character_item_instances(
                conn, target_character['id'], target_data,
                'black_ice_attack', source_ref=summary, prune=True)
            revision_before = _row_value(target_character, 'revision', 0) or 0
            target_ledger_id = record_character_change_set(
                conn, target_character['id'], user['id'], target_before, target_data,
                f'Live NET {summary}: {reason}', revision_before,
                revision_before + 1,
                category='modification' if removed_modification_ids else 'item_action')
            ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                      (target_ledger_id,)).fetchone()
            delta = parse_json_object(ledger_row['delta_json'])
            if removed_modification_ids:
                delta['removed_modification_ids'] = removed_modification_ids
            if created_effects:
                delta['created_effect_ids'] = [
                    item['effect_id'] for item in created_effects]
                delta['automated_black_ice_effect'] = entity.get('name')
                delta['manual_campaign_expiry'] = True
                for created_effect in created_effects:
                    definition = created_effect.get('definition') or {}
                    delta.setdefault('changes', []).append({
                        'path': f'effects.instances.{created_effect["effect_id"]}',
                        'label': f'Effect: {created_effect["label"]}',
                        'kind': 'added', 'before': '—',
                        'after': readable_change_value({
                            'status': created_effect.get('status'),
                            'target': definition.get('target'),
                            'operation': definition.get('operation'),
                            'value': definition.get('value'),
                            'minimum_value': definition.get('minimum_value'),
                            'duration': created_effect.get('duration_type'),
                        }),
                    })
                delta['change_count'] = len(delta.get('changes') or [])
            delta['session_net_change'] = {
                'session_id': session['id'], 'before': state_before,
                'after': copy.deepcopy(state),
            }
            conn.execute('UPDATE character_ledger SET session_id=?,delta_json=? WHERE id=?',
                         (session['id'], json.dumps(delta, ensure_ascii=False),
                          target_ledger_id))
            conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                         (json.dumps(target_data, ensure_ascii=False), now,
                          revision_before + 1, target_character['id']))
            result['target_character_revision'] = revision_before + 1
        conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                     (json.dumps(state, ensure_ascii=False), now, session['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,'
            'after_json,note,created) VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'net_action',
             json.dumps(state_before, ensure_ascii=False),
             json.dumps(action_entry, ensure_ascii=False), reason, now))
        conn.commit()
        updated = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (session['id'],)).fetchone()
        self.send_json({'result': result,
                        'session': self.session_payload(conn, updated, user)})

    @atomic_endpoint
    def api_session_combatant_create(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?', (int(m.group(1)),)).fetchone()
        if not session or 'edit_combatants' not in self.session_capabilities(conn, user, session)[1]:
            raise ApiError(403, 'Нет права редактировать сессию')
        before_rows = self.ordered_session_combatants(conn, session['id'])
        old_index = min(max(0, session['active_turn']), max(0, len(before_rows) - 1))
        active_id = before_rows[old_index]['id'] if before_rows else None
        template = None
        template_id = _num((body or {}).get('template_id'))
        if template_id:
            template = conn.execute(
                "SELECT * FROM npc_templates WHERE id=? AND archived=0 "
                "AND (? OR access='shared' OR owner_user_id=?)",
                (template_id, 1 if user_is_admin(user) else 0, user['id'])).fetchone()
            if not template:
                raise ApiError(403, 'Недоступный NPC template')
        source = parse_json_object(template['data_json']) if template else (body or {})
        name = str((body or {}).get('name') or (template['name'] if template else '')).strip()[:120]
        if not name:
            raise ApiError(400, 'Участнику сессии нужно имя')
        # Snapshot the full statblock (STATs/Skills/Weapons) when adding from a
        # template, or accept an explicit statblock for a custom NPC.
        statblock_source = (body or {}).get('statblock') if not template else source.get('statblock')
        statblock = clean_npc_statblock(statblock_source)
        conditions = source.get('conditions') or []
        injuries = source.get('injuries') or []
        secret = source.get('secret') or {}
        if not isinstance(conditions, list) or not isinstance(injuries, list) or not isinstance(secret, dict):
            raise ApiError(400, 'Некорректные данные участника сессии')
        conditions = [str(value)[:120] for value in conditions[:20]]
        injuries = [str(value)[:120] for value in injuries[:20]]
        if len(json.dumps(secret, ensure_ascii=False)) > 20000:
            raise ApiError(400, 'Некорректные данные участника сессии')
        maximum = max(0, _num(source.get('hp_max')) or 0)
        current = _num(source.get('hp_current'))
        current = maximum if current is None else max(0, min(maximum or current, current))
        sp_head = max(0, _num(source.get('sp_head')) or 0)
        sp_head_max = max(sp_head, _num(source.get('sp_head_max')) or 0)
        sp_body = max(0, _num(source.get('sp_body')) or 0)
        sp_body_max = max(sp_body, _num(source.get('sp_body_max')) or 0)
        shield_current = max(0, _num(source.get('shield_current')) or 0)
        shield_max = max(shield_current, _num(source.get('shield_max')) or 0)
        ammo_current = max(0, _num(source.get('ammo_current')) or 0)
        ammo_max = max(ammo_current, _num(source.get('ammo_max')) or 0)
        luck_current = max(0, _num(source.get('luck_current')) or 0)
        luck_max = max(luck_current, _num(source.get('luck_max')) or 0)
        order = conn.execute('SELECT COALESCE(MAX(sort_order),-1)+1 n FROM session_combatants WHERE session_id=?',
                             (session['id'],)).fetchone()['n']
        cur = conn.execute(
            'INSERT INTO session_combatants(session_id,kind,template_id,name,initiative,hp_current,hp_max,'
            'sp_head,sp_head_max,sp_body,sp_body_max,shield_current,shield_max,ammo_current,ammo_max,'
            'luck_current,luck_max,move,conditions_json,injuries_json,death_penalty,visible,secret_json,'
            'statblock_json,sort_order) '
            'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (session['id'], 'npc', template['id'] if template else None, name,
             max(-1000, min(1000, _num(source.get('initiative')) or 0)), current, maximum,
             sp_head, sp_head_max, sp_body, sp_body_max, shield_current, shield_max,
             ammo_current, ammo_max, luck_current, luck_max,
             max(0, _num(source.get('move')) or 0), json.dumps(conditions), json.dumps(injuries),
             max(0, _num(source.get('death_penalty')) or 0),
             0 if source.get('visible') is False else 1,
             json.dumps(secret, ensure_ascii=False),
             json.dumps(statblock, ensure_ascii=False), order))
        after_rows = self.ordered_session_combatants(conn, session['id'])
        active_turn = next((index for index, item in enumerate(after_rows) if item['id'] == active_id), 0)
        now = time.time()
        conn.execute('UPDATE nc_sessions SET active_turn=?,updated=? WHERE id=?',
                     (active_turn, now, session['id']))
        created = dict(conn.execute('SELECT * FROM session_combatants WHERE id=?', (cur.lastrowid,)).fetchone())
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,combatant_id,event_type,after_json,note,created) '
            'VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], cur.lastrowid, 'combatant_create',
             json.dumps(created, ensure_ascii=False), '', now))
        conn.commit(); self.send_json({'id': cur.lastrowid}, status=201)

    @atomic_endpoint
    def api_session_combatant_delete(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?', (int(m.group(1)),)).fetchone()
        if not session or 'edit_combatants' not in self.session_capabilities(conn, user, session)[1]:
            raise ApiError(403, 'Нет права редактировать сессию')
        ordered_before = self.ordered_session_combatants(conn, session['id'])
        combatant_id = int(m.group(2))
        combatant = next((item for item in ordered_before if item['id'] == combatant_id), None)
        if not combatant:
            raise ApiError(404, 'Участник сессии не найден')
        old_index = min(max(0, session['active_turn']), max(0, len(ordered_before) - 1))
        active_id = ordered_before[old_index]['id'] if ordered_before else None
        conn.execute('DELETE FROM session_combatants WHERE id=? AND session_id=?',
                     (combatant_id, session['id']))
        ordered_after = self.ordered_session_combatants(conn, session['id'])
        if active_id != combatant_id:
            active_turn = next((index for index, item in enumerate(ordered_after)
                                if item['id'] == active_id), 0)
        else:
            active_turn = old_index % len(ordered_after) if ordered_after else 0
        now = time.time()
        conn.execute('UPDATE nc_sessions SET active_turn=?,updated=? WHERE id=?',
                     (active_turn, now, session['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,combatant_id,event_type,before_json,note,created) '
            'VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], combatant_id, 'combatant_delete',
             json.dumps(dict(combatant), ensure_ascii=False),
             str((body or {}).get('note') or '')[:500], now))
        conn.commit(); self.send_json({'ok': True})

    @atomic_endpoint
    def api_session_combatant_update(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?', (int(m.group(1)),)).fetchone()
        combatant = conn.execute('SELECT * FROM session_combatants WHERE id=? AND session_id=?',
                                 (int(m.group(2)), int(m.group(1)))).fetchone()
        if (not session or not combatant or
                'edit_combatants' not in self.session_capabilities(conn, user, session)[1]):
            raise ApiError(403, 'Нет права редактировать участника')
        ordered_before = self.ordered_session_combatants(conn, session['id'])
        old_index = min(max(0, session['active_turn']), max(0, len(ordered_before) - 1))
        active_id = ordered_before[old_index]['id'] if ordered_before else None
        before = dict(combatant)
        numeric = ['initiative', 'hp_current', 'hp_max', 'sp_head', 'sp_head_max',
                   'sp_body', 'sp_body_max', 'shield_current', 'shield_max', 'ammo_current', 'ammo_max',
                   'luck_current', 'luck_max', 'move', 'death_penalty', 'sort_order']
        values = {key: _num((body or {}).get(key, combatant[key])) or 0 for key in numeric}
        values['initiative'] = max(-1000, min(1000, values['initiative']))
        for key in numeric:
            if key != 'initiative':
                values[key] = max(0, values[key])
        hp_limit = values['hp_max'] if values['hp_max'] > 0 else values['hp_current']
        values['hp_current'] = min(hp_limit, values['hp_current'])
        for current_key, maximum_key in (('sp_head', 'sp_head_max'),
                                         ('sp_body', 'sp_body_max'),
                                         ('shield_current', 'shield_max'),
                                         ('ammo_current', 'ammo_max'),
                                         ('luck_current', 'luck_max')):
            if values[maximum_key] > 0:
                values[current_key] = min(values[maximum_key], values[current_key])
        conditions = (body or {}).get('conditions', parse_json_list(combatant['conditions_json']))
        injuries = (body or {}).get('injuries', parse_json_list(combatant['injuries_json']))
        secret = (body or {}).get('secret', parse_json_object(combatant['secret_json']))
        if not isinstance(conditions, list) or not isinstance(injuries, list) or not isinstance(secret, dict):
            raise ApiError(400, 'Некорректные данные участника сессии')
        conditions = [str(value)[:120] for value in conditions[:20]]
        injuries = [str(value)[:120] for value in injuries[:20]]
        if len(json.dumps(secret, ensure_ascii=False)) > 20000:
            raise ApiError(400, 'Некорректные данные участника сессии')
        visible = (body or {}).get('visible', bool(combatant['visible']))
        visible = visible if isinstance(visible, bool) else bool(combatant['visible'])
        name = str((body or {}).get('name', combatant['name'])).strip()[:120] or combatant['name']
        if 'statblock' in (body or {}):
            statblock = clean_npc_statblock((body or {}).get('statblock'))
        else:
            statblock = parse_json_object(combatant['statblock_json'])
        conn.execute(
            'UPDATE session_combatants SET name=?,initiative=?,hp_current=?,hp_max=?,sp_head=?,sp_head_max=?,'
            'sp_body=?,sp_body_max=?,shield_current=?,shield_max=?,ammo_current=?,ammo_max=?,luck_current=?,'
            'luck_max=?,move=?,conditions_json=?,injuries_json=?,death_penalty=?,visible=?,secret_json=?,'
            'statblock_json=?,sort_order=? WHERE id=?',
            (name, values['initiative'], values['hp_current'], values['hp_max'],
             values['sp_head'], values['sp_head_max'], values['sp_body'], values['sp_body_max'],
             values['shield_current'], values['shield_max'],
             values['ammo_current'], values['ammo_max'], values['luck_current'], values['luck_max'],
             values['move'], json.dumps(conditions), json.dumps(injuries), values['death_penalty'],
             1 if visible else 0, json.dumps(secret, ensure_ascii=False),
             json.dumps(statblock, ensure_ascii=False),
             values['sort_order'], combatant['id']))
        ordered_after = self.ordered_session_combatants(conn, session['id'])
        active_turn = next((index for index, item in enumerate(ordered_after) if item['id'] == active_id), 0)
        now = time.time()
        conn.execute('UPDATE nc_sessions SET active_turn=?,updated=? WHERE id=?',
                     (active_turn, now, session['id']))
        after = dict(conn.execute('SELECT * FROM session_combatants WHERE id=?', (combatant['id'],)).fetchone())
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,combatant_id,event_type,before_json,after_json,note,created) '
            'VALUES(?,?,?,?,?,?,?,?)',
            (session['id'], user['id'], combatant['id'], 'combatant_update',
             json.dumps(before, ensure_ascii=False), json.dumps(after, ensure_ascii=False),
             str((body or {}).get('note') or '')[:500], now))
        conn.commit(); self.send_json({'ok': True})

    @atomic_endpoint
    def api_session_create(self, conn, qs, m, body):
        user = self.require_gm(conn)
        contract_id = _num((body or {}).get('contract_id'))
        contract = None
        if contract_id:
            contract = conn.execute('SELECT * FROM contracts WHERE id=?', (contract_id,)).fetchone()
            if not contract or not can_edit_contract(conn, user, contract):
                raise ApiError(403, 'Нет доступа к контракту сессии')
        title = str((body or {}).get('title') or (contract['title'] if contract else 'NC//NET Session')).strip()[:180]
        if not title:
            title = contract['title'] if contract else 'NC//NET Session'
        config = session_view_config((body or {}).get('player_view_config'))
        safety = session_safety_config((body or {}).get('safety_config'))
        now = time.time()
        cur = conn.execute(
            'INSERT INTO nc_sessions(contract_id,owner_user_id,title,status,player_view_config,'
            'safety_config,notes,created,updated) VALUES(?,?,?,\'preparing\',?,?,?,?,?)',
            (contract_id, user['id'], title, json.dumps(config), json.dumps(safety),
             str((body or {}).get('notes') or '')[:20000], now, now))
        session_id = cur.lastrowid
        if contract:
            signups = conn.execute(
                "SELECT s.*,c.data FROM contract_signups s JOIN characters c ON c.id=s.character_id "
                "WHERE s.contract_id=? AND s.status='crew' ORDER BY s.queue_position",
                (contract_id,)).fetchall()
            for index, signup in enumerate(signups):
                char = ensure_progression(json.loads(signup['data'])); derived = derive(char)
                shield = (char.get('armor') or {}).get('shield') or {}
                shield_max = (_num(shield.get('maximum')) or _num(shield.get('sdp')) or
                              _num(shield.get('sp')) or 0) if isinstance(shield, dict) else 0
                shield_current = (_num(shield.get('current')) if isinstance(shield, dict) else None)
                shield_current = shield_max if shield_current is None else max(0, min(shield_max, shield_current))
                weapon_states = [value for value in (char.get('weapon_state') or {}).values()
                                 if isinstance(value, dict)]
                ammo_current = sum(max(0, _num(value.get('magazine')) or 0) for value in weapon_states)
                ammo_max = sum(max(0, _num(value.get('magazine_max')) or 0) for value in weapon_states)
                luck_max = max(0, _num((char.get('stats') or {}).get('LUCK')) or 0)
                injuries = char.get('critical_injuries') or []
                injuries = injuries if isinstance(injuries, list) else []
                conn.execute(
                    "INSERT INTO session_combatants(session_id,kind,character_id,name,initiative,hp_current,"
                    "hp_max,sp_head,sp_head_max,sp_body,sp_body_max,shield_current,shield_max,ammo_current,"
                    "ammo_max,luck_current,luck_max,move,injuries_json,death_penalty,visible,sort_order) "
                    "VALUES(?,'character',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)",
                    (session_id, signup['character_id'], char.get('handle') or 'Edgerunner', 0,
                     char.get('hp_cur') if char.get('hp_cur') is not None else (derived.get('hp_max') or 0),
                     derived.get('hp_max') or 0, derived.get('sp_head') or 0,
                     derived.get('sp_head') or 0, derived.get('sp_body') or 0,
                     derived.get('sp_body') or 0, shield_current, shield_max,
                     ammo_current, ammo_max, max(0, min(luck_max, _num(char.get('luck_cur')) or 0)),
                     luck_max, _num((char.get('stats') or {}).get('MOVE')) or 0,
                     json.dumps([str(value)[:120] for value in injuries[:20]], ensure_ascii=False),
                     max(0, _num(char.get('death_penalty')) or 0), index))
        conn.commit(); row = conn.execute('SELECT * FROM nc_sessions WHERE id=?', (session_id,)).fetchone()
        self.send_json(self.session_payload(conn, row, user), status=201)

    def api_session_detail(self, conn, qs, m, body):
        user = self.require_user(conn)
        row = conn.execute('SELECT * FROM nc_sessions WHERE id=?', (int(m.group(1)),)).fetchone()
        role, capabilities = self.session_capabilities(conn, user, row)
        if not row or 'view_gm' not in capabilities:
            raise ApiError(404, 'Сессия не найдена')
        self.send_json(self.session_payload(conn, row, user))

    @atomic_endpoint
    def api_session_net_action(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or session['status'] not in ('preparing', 'active', 'paused'):
            raise ApiError(404, 'Live NET Session не найдена')
        allowed = {'action', 'actor_combatant_id', 'target_node_id',
                   'program_instance_id', 'target_entity_id',
                   'character_revision', 'target_character_revision', 'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'NET action содержит неподдерживаемые поля')
        actor_id = _num((body or {}).get('actor_combatant_id'))
        actor = conn.execute(
            'SELECT * FROM session_combatants WHERE session_id=? AND id=?',
            (session['id'], int(actor_id))).fetchone() \
            if actor_id is not None and int(actor_id) == actor_id else None
        if not actor or not actor['character_id']:
            raise ApiError(400, 'NET action требует Character combatant')
        character = conn.execute('SELECT * FROM characters WHERE id=?',
                                 (actor['character_id'],)).fetchone()
        if not character:
            raise ApiError(404, 'Character для NET action не найден')
        capabilities = self.session_capabilities(conn, user, session)[1]
        if character['owner_id'] != user['id'] and 'edit_combatants' not in capabilities:
            raise ApiError(403, 'Нет права выполнять NET action этим Character')
        character_data = enrich_owned_item_interactions(
            ensure_progression(json.loads(character['data'])))
        interface_rank = character_interface_rank(character_data)
        if interface_rank <= 0:
            raise ApiError(409, 'NET action требует Netrunner Role')
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину NET action')
        state = session_net_state(_row_value(session, 'net_state_json', '{}'))
        before_state = copy.deepcopy(state)
        node_by_id = {item['node_id']: item for item in state['nodes']}
        runner = next((item for item in state['runners']
                       if item['combatant_id'] == actor['id']), None)
        if not runner:
            runner = {
                'combatant_id': actor['id'], 'character_id': character['id'],
                'node_id': None, 'previous_node_id': None, 'jacked_in': False,
                'interface_rank': interface_rank, 'actions_recorded': 0,
                'action_round': state['round'], 'actions_used': 0,
                'action_penalty': 0, 'next_action_penalty': 0,
                'last_action_at': None,
            }
            state['runners'].append(runner)
        runner['interface_rank'] = interface_rank
        action = str((body or {}).get('action') or '').lower()
        if runner.get('action_round') != state['round']:
            runner['action_round'] = state['round']
            runner['actions_used'] = 0
            runner['action_penalty'] = runner.get('next_action_penalty', 0)
            runner['next_action_penalty'] = 0
        consumes_net_action = action not in ('jack_in', 'jack_out')
        actions_max = max(
            2, net_actions_for_interface(interface_rank) - runner.get('action_penalty', 0))
        if consumes_net_action and runner.get('actions_used', 0) >= actions_max:
            raise ApiError(409, 'NET Action budget исчерпан для текущего NET Round')
        target_node_id = str((body or {}).get('target_node_id') or '').lower()
        target_node = node_by_id.get(target_node_id)
        now = time.time()
        result = {'action': action, 'actor_combatant_id': actor['id'],
                  'interface_rank': interface_rank}
        character_before = None
        character_ledger_id = None
        target_character = None
        target_character_data = None
        target_character_before = None
        target_character_ledger_id = None
        if action == 'jack_in':
            if not target_node or target_node['type'] != 'access_point':
                raise ApiError(400, 'Jack In требует Access Point node')
            if not target_node['visible'] and 'edit_combatants' not in capabilities:
                raise ApiError(403, 'Access Point node ещё не revealed')
            runner.update({'jacked_in': True, 'node_id': target_node_id,
                           'previous_node_id': None})
            target_node['visible'] = True
            result.update({'success': True, 'summary': f'Jack In at {target_node["label"]}'})
        elif action == 'jack_out':
            if not runner['jacked_in']:
                raise ApiError(409, 'Netrunner не Jacked In')
            runner.update({'jacked_in': False, 'node_id': None,
                           'previous_node_id': None})
            result.update({'success': True, 'summary': 'Safe Jack Out recorded'})
        else:
            if not runner['jacked_in'] or runner.get('node_id') not in node_by_id:
                raise ApiError(409, 'NET action требует Jacked In Netrunner')
            current_node = node_by_id[runner['node_id']]
            if action == 'move':
                if not target_node or not target_node['visible']:
                    raise ApiError(409, 'Move требует revealed target node')
                path = session_net_path_between(
                    state, current_node['node_id'], target_node_id,
                    require_visible=True)
                if not path:
                    raise ApiError(409, 'NET nodes не соединены revealed path')
                if (current_node['type'] == 'password' and
                        not current_node['resolved'] and
                        target_node_id != runner.get('previous_node_id')):
                    raise ApiError(409, 'Unresolved Password блокирует движение вперёд')
                runner['previous_node_id'] = current_node['node_id']
                runner['node_id'] = target_node_id
                result.update({'success': True,
                               'summary': f'Move to {target_node["label"]}'})
            elif action == 'pathfinder':
                if not target_node:
                    target_node = next((node for node in state['nodes']
                                        if not node['visible'] and
                                        session_net_path_between(
                                            state, current_node['node_id'],
                                            node['node_id'], require_visible=False)), None)
                    target_node_id = target_node['node_id'] if target_node else ''
                if not target_node:
                    raise ApiError(404, 'Pathfinder target node не найден')
                path = session_net_path_between(
                    state, current_node['node_id'], target_node_id,
                    require_visible=False)
                if not path:
                    raise ApiError(409, 'Pathfinder target должен быть adjacent node')
                dv = max(1, target_node['dv'] or 9)
                die = secrets.randbelow(10) + 1
                total = interface_rank + die
                success = total >= dv
                if success:
                    target_node['visible'] = True
                    path['visible'] = True
                result.update({'success': success, 'actor_roll': die,
                               'actor_total': total, 'defense_total': dv,
                               'summary': f'Pathfinder {total} vs DV{dv}'})
            elif action == 'backdoor':
                node = target_node or current_node
                if node['node_id'] != current_node['node_id'] or node['type'] != 'password':
                    raise ApiError(409, 'Backdoor требует текущий Password node')
                dv = max(1, node['dv'] or 9)
                die = secrets.randbelow(10) + 1
                total = interface_rank + die
                success = total >= dv
                if success:
                    node['resolved'] = True
                    node['visible'] = True
                result.update({'success': success, 'actor_roll': die,
                               'actor_total': total, 'defense_total': dv,
                               'summary': f'Backdoor {total} vs DV{dv}'})
            elif action == 'eye_dee':
                node = target_node or current_node
                if node['node_id'] != current_node['node_id']:
                    raise ApiError(409, 'Eye-Dee доступен только для текущего node')
                node['visible'] = True
                result.update({'success': True,
                               'summary': f'Eye-Dee identifies {node["label"]}'})
            elif action == 'control':
                node = target_node or current_node
                if node['node_id'] != current_node['node_id'] or node['type'] != 'control':
                    raise ApiError(409, 'Control action требует текущий Control node')
                dv = max(1, node['dv'] or node['defense'] or 9)
                die = secrets.randbelow(10) + 1
                total = interface_rank + die
                success = total >= dv
                if success:
                    node['resolved'] = True
                    node['visible'] = True
                    node['controlled_by_combatant_id'] = actor['id']
                result.update({'success': success, 'actor_roll': die,
                               'actor_total': total, 'defense_total': dv,
                               'summary': f'Control {total} vs DV{dv}'})
            elif action == 'program_attack':
                program_id = str((body or {}).get('program_instance_id') or '').lower()
                entity_id = str((body or {}).get('target_entity_id') or '').lower()
                link = next((item for item in state['links']
                             if item['net_entity_id'] == entity_id and item['active']), None)
                if not link or link.get('node_id') != current_node['node_id']:
                    raise ApiError(409, 'Program Attack требует Black ICE на текущем node')
                target_character = conn.execute('SELECT * FROM characters WHERE id=?',
                                                (link['character_id'],)).fetchone()
                target_character_data = enrich_owned_item_interactions(
                    ensure_progression(json.loads(target_character['data']))) \
                    if target_character else None
                if target_character and target_character['id'] == character['id']:
                    target_character_data = character_data
                target_entity = (target_character_data.get('net_entities') or {}).get(
                    entity_id) if target_character_data else None
                if not isinstance(target_entity, dict) or target_entity.get('status') not in (
                        'lying_in_wait', 'hunting'):
                    raise ApiError(409, 'Program Attack target entity недоступна')
                owned = {item.get('instance_id'): item for item in character_data.get('inventory') or []
                         if isinstance(item, dict) and item.get('instance_id')}
                program = owned.get(program_id)
                modifications = character_modifications(conn, character['id'])
                program_modification = next((item for item in modifications
                                             if item.get('upgrade_instance_id') == program_id and
                                             item.get('host_type') == 'cyberdeck'), None)
                if (not program or not program_modification or
                        cyberdeck_program_category(program) != 'attacker'):
                    raise ApiError(409, 'Program Attack требует installed Attacker Program')
                expected_revision = _num((body or {}).get('character_revision'))
                if expected_revision != (_row_value(character, 'revision', 0) or 0):
                    raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
                attack_die = secrets.randbelow(10) + 1
                defense_die = secrets.randbelow(10) + 1
                attack = interface_rank + int(_num((program.get('mechanics') or {}).get('atk')) or 0) + attack_die
                defense = int(_num(target_entity.get('def')) or 0) + defense_die
                success = attack > defense
                character_before = copy.deepcopy(character_data)
                runtime = initial_program_runtime_state(
                    program, program_modification['host_instance_id'],
                    program_modification['modification_id'],
                    (character_data.get('program_state') or {}).get(program_id))
                runtime['run_count'] += 1
                runtime['last_run_at'] = now
                character_data.setdefault('program_state', {})[program_id] = runtime
                catalog_program = item_by_id(catalog_item_id_for_entry(program)) or {}
                result.update({
                    'success': success, 'actor_roll': attack_die,
                    'defense_roll': defense_die, 'actor_total': attack,
                    'defense_total': defense,
                    'manual_effect': str(catalog_program.get('desc') or '')[:2000],
                    'summary': f'{program.get("name")} attack {attack} vs DEF {defense}',
                })
                damage_dice = ATTACKER_PROGRAM_BLACK_ICE_DAMAGE.get(
                    str(program.get('name') or ''))
                if success and damage_dice:
                    expected_target_revision = _num(
                        (body or {}).get('target_character_revision'))
                    if expected_target_revision != (
                            _row_value(target_character, 'revision', 0) or 0):
                        raise ApiError(409, 'Target Dossier изменён в другой вкладке')
                    damage = roll_dice(damage_dice, 6)
                    if target_character['id'] != character['id']:
                        target_character_before = copy.deepcopy(target_character_data)
                    previous_target_rez = int(target_entity.get('rez_current') or 0)
                    target_entity['rez_current'] = max(
                        0, previous_target_rez - damage['total'])
                    target_entity['updated_at'] = now
                    source_program_id = str(
                        target_entity.get('source_program_instance_id') or '')
                    target_program_item = next(
                        (item for item in target_character_data.get('inventory') or []
                         if isinstance(item, dict) and
                         item.get('instance_id') == source_program_id), None)
                    target_modifications = character_modifications(
                        conn, target_character['id'])
                    target_program_modification = next(
                        (item for item in target_modifications
                         if item.get('upgrade_instance_id') == source_program_id), None)
                    if target_program_item and target_program_modification:
                        target_runtime = initial_program_runtime_state(
                            target_program_item,
                            target_program_modification['host_instance_id'],
                            target_program_modification['modification_id'],
                            (target_character_data.get('program_state') or {}).get(
                                source_program_id))
                        target_runtime['rez_current'] = target_entity['rez_current']
                        if target_entity['rez_current'] == 0:
                            target_entity['status'] = 'derezzed'
                            target_runtime['status'] = 'derezzed'
                            link['initiative'] = 0
                        target_character_data.setdefault('program_state', {})[
                            source_program_id] = target_runtime
                    result.update({
                        'damage_rolls': damage['rolls'],
                        'damage_total': damage['total'],
                        'damage_target': 'black_ice_rez',
                        'damage_application': 'automated',
                        'rez_before': previous_target_rez,
                        'rez_after': target_entity['rez_current'],
                        'target_derezzed': target_entity['rez_current'] == 0,
                    })
            else:
                raise ApiError(400, 'NET action: jack_in/jack_out/move/pathfinder/backdoor/eye_dee/control/program_attack')
            runner['actions_recorded'] += 1
            runner['actions_used'] = runner.get('actions_used', 0) + 1
        runner['last_action_at'] = now
        action_entry = {
            'action_id': secrets.token_hex(16), 'combatant_id': actor['id'],
            'action': action, 'target_node_id': target_node_id or None,
            'target_entity_id': str((body or {}).get('target_entity_id') or '') or None,
            'success': result.get('success'),
            'actor_total': result.get('actor_total'),
            'defense_total': result.get('defense_total'),
            'created': now, 'summary': result.get('summary') or action,
        }
        state.setdefault('action_log', []).append(action_entry)
        state['action_log'] = state['action_log'][-100:]
        if target_character_before is not None:
            target_revision_before = _row_value(target_character, 'revision', 0) or 0
            target_character_ledger_id = record_character_change_set(
                conn, target_character['id'], user['id'],
                target_character_before, target_character_data,
                f'Live NET target damage from {result["summary"]}: {reason}',
                target_revision_before, target_revision_before + 1,
                category='item_action')
            target_ledger_row = conn.execute(
                'SELECT delta_json FROM character_ledger WHERE id=?',
                (target_character_ledger_id,)).fetchone()
            target_delta = parse_json_object(target_ledger_row['delta_json'])
            target_delta.update({
                'revertible': False, 'multi_character_operation': True,
                'session_id': session['id'],
            })
            conn.execute('UPDATE character_ledger SET session_id=?,delta_json=? WHERE id=?',
                         (session['id'], json.dumps(target_delta, ensure_ascii=False),
                          target_character_ledger_id))
            conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                         (json.dumps(target_character_data, ensure_ascii=False), now,
                          target_revision_before + 1, target_character['id']))
            result['target_character_revision'] = target_revision_before + 1
        if character_before is not None:
            revision_before = _row_value(character, 'revision', 0) or 0
            character_ledger_id = record_character_change_set(
                conn, character['id'], user['id'], character_before, character_data,
                f'Live NET {result["summary"]}: {reason}',
                revision_before, revision_before + 1, category='item_action')
            ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                      (character_ledger_id,)).fetchone()
            ledger_delta = parse_json_object(ledger_row['delta_json'])
            ledger_delta['session_net_change'] = {
                'session_id': session['id'], 'before': before_state,
                'after': copy.deepcopy(state),
            }
            if target_character_ledger_id is not None:
                ledger_delta.update({
                    'revertible': False, 'multi_character_operation': True,
                    'linked_target_ledger_id': target_character_ledger_id,
                    'linked_target_character_id': target_character['id'],
                })
            conn.execute('UPDATE character_ledger SET session_id=?,delta_json=? WHERE id=?',
                         (session['id'], json.dumps(ledger_delta, ensure_ascii=False),
                          character_ledger_id))
            conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                         (json.dumps(character_data, ensure_ascii=False), now,
                          revision_before + 1, character['id']))
            result['character_revision'] = revision_before + 1
        conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                     (json.dumps(state, ensure_ascii=False), now, session['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,'
            'after_json,note,created) VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'net_action',
             json.dumps(before_state, ensure_ascii=False),
             json.dumps(action_entry, ensure_ascii=False), reason, now))
        conn.commit()
        updated = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (session['id'],)).fetchone()
        self.send_json({
            'result': result,
            'session': self.session_payload(
                conn, updated, user,
                player_view='view_gm' not in capabilities),
        })

    @atomic_endpoint
    def api_session_net_floor_create(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or 'edit_session' not in self.session_capabilities(conn, user, session)[1]:
            raise ApiError(403, 'Нет права редактировать Session NET Floors')
        label = str((body or {}).get('label') or '').strip()[:120]
        note = str((body or {}).get('reason') or '').strip()[:500]
        if not label:
            raise ApiError(400, 'NET Floor требует label')
        if len(note) < 3:
            raise ApiError(400, 'Укажите причину изменения NET Floors')
        state = session_net_state(_row_value(session, 'net_state_json', '{}'))
        if len(state['floors']) >= 100 or any(
                item['label'].lower() == label.lower() for item in state['floors']):
            raise ApiError(409, 'NET Floor уже существует или достигнут лимит')
        before = copy.deepcopy(state)
        floor = {'floor_id': secrets.token_hex(16), 'label': label,
                 'sort_order': len(state['floors'])}
        state['floors'].append(floor)
        now = time.time()
        conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                     (json.dumps(state, ensure_ascii=False), now, session['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,'
            'after_json,note,created) VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'net_floor_create',
             json.dumps(before, ensure_ascii=False),
             json.dumps(state, ensure_ascii=False), note, now))
        conn.commit()
        self.send_json(floor, status=201)

    @atomic_endpoint
    def api_session_net_floor_delete(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or 'edit_session' not in self.session_capabilities(conn, user, session)[1]:
            raise ApiError(403, 'Нет права редактировать Session NET Floors')
        floor_id = str(m.group(2)).lower()
        note = str((body or {}).get('reason') or '').strip()[:500]
        if len(note) < 3:
            raise ApiError(400, 'Укажите причину изменения NET Floors')
        state = session_net_state(_row_value(session, 'net_state_json', '{}'))
        floor = next((item for item in state['floors']
                      if item['floor_id'] == floor_id), None)
        if not floor:
            raise ApiError(404, 'Session NET Floor не найден')
        if any(item['floor_id'] == floor_id for item in state['nodes']):
            raise ApiError(409, 'Сначала удалите NET nodes с этого Floor')
        if any(item['active'] and item['floor_id'] == floor_id
               for item in state['links']):
            raise ApiError(409, 'NET Floor используется active entity')
        before = copy.deepcopy(state)
        state['floors'] = [item for item in state['floors']
                           if item['floor_id'] != floor_id]
        for index, item in enumerate(state['floors']):
            item['sort_order'] = index
        state['links'] = [item for item in state['links']
                          if item['floor_id'] != floor_id]
        now = time.time()
        conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                     (json.dumps(state, ensure_ascii=False), now, session['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,'
            'after_json,note,created) VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'net_floor_delete',
             json.dumps(before, ensure_ascii=False), json.dumps(state, ensure_ascii=False),
             note, now))
        conn.commit()
        self.send_json({'ok': True})

    @atomic_endpoint
    def api_session_net_node_create(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or 'edit_session' not in self.session_capabilities(conn, user, session)[1]:
            raise ApiError(403, 'Нет права редактировать NET Architecture')
        allowed = {'floor_id', 'type', 'label', 'dv', 'defense',
                   'visible', 'resolved', 'gm_note', 'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'NET node содержит неподдерживаемые поля')
        state = session_net_state(_row_value(session, 'net_state_json', '{}'))
        floor_id = str((body or {}).get('floor_id') or '').lower()
        node_type = str((body or {}).get('type') or '').lower()
        label = str((body or {}).get('label') or '').strip()[:120]
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if not any(item['floor_id'] == floor_id for item in state['floors']):
            raise ApiError(400, 'NET node требует validated Floor')
        if node_type not in SESSION_NET_NODE_TYPES or not label:
            raise ApiError(400, 'Некорректный NET node type или label')
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину изменения NET Architecture')
        if len(state['nodes']) >= 500:
            raise ApiError(409, 'Достигнут лимит NET nodes')
        before = copy.deepcopy(state)
        node = {
            'node_id': secrets.token_hex(16), 'floor_id': floor_id,
            'type': node_type, 'label': label,
            'dv': max(0, min(29, int(_num((body or {}).get('dv')) or 0))),
            'defense': max(0, min(29, int(_num((body or {}).get('defense')) or 0))),
            'visible': (body or {}).get('visible') is True,
            'resolved': (body or {}).get('resolved') is True,
            'gm_note': str((body or {}).get('gm_note') or '')[:2000],
            'sort_order': len(state['nodes']),
        }
        state['nodes'].append(node)
        now = time.time()
        conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                     (json.dumps(state, ensure_ascii=False), now, session['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,'
            'after_json,note,created) VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'net_node_create',
             json.dumps(before, ensure_ascii=False), json.dumps(state, ensure_ascii=False),
             reason, now))
        conn.commit()
        self.send_json(node, status=201)

    @atomic_endpoint
    def api_session_net_node_delete(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or 'edit_session' not in self.session_capabilities(conn, user, session)[1]:
            raise ApiError(403, 'Нет права редактировать NET Architecture')
        state = session_net_state(_row_value(session, 'net_state_json', '{}'))
        node_id = str(m.group(2)).lower()
        node = next((item for item in state['nodes']
                     if item['node_id'] == node_id), None)
        if not node:
            raise ApiError(404, 'NET node не найден')
        if any(item['from_node_id'] == node_id or item['to_node_id'] == node_id
               for item in state['paths']):
            raise ApiError(409, 'Сначала удалите NET paths этого node')
        if any(item['active'] and item.get('node_id') == node_id
               for item in state['links']):
            raise ApiError(409, 'NET node используется active entity')
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину изменения NET Architecture')
        before = copy.deepcopy(state)
        state['nodes'] = [item for item in state['nodes'] if item['node_id'] != node_id]
        for index, item in enumerate(state['nodes']):
            item['sort_order'] = index
        for link in state['links']:
            if link.get('node_id') == node_id:
                link['node_id'] = None
        now = time.time()
        conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                     (json.dumps(state, ensure_ascii=False), now, session['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,'
            'after_json,note,created) VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'net_node_delete',
             json.dumps(before, ensure_ascii=False), json.dumps(state, ensure_ascii=False),
             reason, now))
        conn.commit()
        self.send_json({'ok': True})

    @atomic_endpoint
    def api_session_net_node_update(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or 'edit_session' not in self.session_capabilities(conn, user, session)[1]:
            raise ApiError(403, 'Нет права редактировать NET Architecture')
        allowed = {'type', 'label', 'dv', 'defense', 'visible',
                   'resolved', 'gm_note', 'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'NET node содержит неподдерживаемые поля')
        state = session_net_state(_row_value(session, 'net_state_json', '{}'))
        node_id = str(m.group(2)).lower()
        node = next((item for item in state['nodes']
                     if item['node_id'] == node_id), None)
        if not node:
            raise ApiError(404, 'NET node не найден')
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину изменения NET Architecture')
        before = copy.deepcopy(state)
        node_type = str((body or {}).get('type', node['type'])).lower()
        label = str((body or {}).get('label', node['label'])).strip()[:120]
        if node_type not in SESSION_NET_NODE_TYPES or not label:
            raise ApiError(400, 'Некорректный NET node type или label')
        node.update({
            'type': node_type, 'label': label,
            'dv': max(0, min(29, int(_num((body or {}).get('dv', node['dv'])) or 0))),
            'defense': max(0, min(29, int(_num(
                (body or {}).get('defense', node['defense'])) or 0))),
            'visible': (body or {}).get('visible', node['visible']) is True,
            'resolved': (body or {}).get('resolved', node['resolved']) is True,
            'gm_note': str((body or {}).get('gm_note', node['gm_note']) or '')[:2000],
        })
        now = time.time()
        conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                     (json.dumps(state, ensure_ascii=False), now, session['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,'
            'after_json,note,created) VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'net_node_update',
             json.dumps(before, ensure_ascii=False), json.dumps(state, ensure_ascii=False),
             reason, now))
        conn.commit()
        self.send_json(node)

    @atomic_endpoint
    def api_session_net_path_create(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or 'edit_session' not in self.session_capabilities(conn, user, session)[1]:
            raise ApiError(403, 'Нет права редактировать NET Architecture')
        allowed = {'from_node_id', 'to_node_id', 'direction',
                   'label', 'visible', 'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'NET path содержит неподдерживаемые поля')
        state = session_net_state(_row_value(session, 'net_state_json', '{}'))
        from_id = str((body or {}).get('from_node_id') or '').lower()
        to_id = str((body or {}).get('to_node_id') or '').lower()
        direction = str((body or {}).get('direction') or 'bidirectional').lower()
        node_ids = {item['node_id'] for item in state['nodes']}
        if (from_id not in node_ids or to_id not in node_ids or from_id == to_id or
                direction not in SESSION_NET_PATH_DIRECTIONS):
            raise ApiError(400, 'Некорректные NET path endpoints или direction')
        if any(item['from_node_id'] == from_id and item['to_node_id'] == to_id and
               item['direction'] == direction for item in state['paths']):
            raise ApiError(409, 'NET path уже существует')
        if direction == 'bidirectional' and any(
                item['from_node_id'] == to_id and item['to_node_id'] == from_id and
                item['direction'] == direction for item in state['paths']):
            raise ApiError(409, 'NET path уже существует')
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину изменения NET Architecture')
        if len(state['paths']) >= 1000:
            raise ApiError(409, 'Достигнут лимит NET paths')
        before = copy.deepcopy(state)
        path = {
            'path_id': secrets.token_hex(16), 'from_node_id': from_id,
            'to_node_id': to_id, 'direction': direction,
            'label': str((body or {}).get('label') or '')[:120],
            'visible': (body or {}).get('visible') is True,
        }
        state['paths'].append(path)
        now = time.time()
        conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                     (json.dumps(state, ensure_ascii=False), now, session['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,'
            'after_json,note,created) VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'net_path_create',
             json.dumps(before, ensure_ascii=False), json.dumps(state, ensure_ascii=False),
             reason, now))
        conn.commit()
        self.send_json(path, status=201)

    @atomic_endpoint
    def api_session_net_path_delete(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or 'edit_session' not in self.session_capabilities(conn, user, session)[1]:
            raise ApiError(403, 'Нет права редактировать NET Architecture')
        state = session_net_state(_row_value(session, 'net_state_json', '{}'))
        path_id = str(m.group(2)).lower()
        if not any(item['path_id'] == path_id for item in state['paths']):
            raise ApiError(404, 'NET path не найден')
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину изменения NET Architecture')
        before = copy.deepcopy(state)
        state['paths'] = [item for item in state['paths'] if item['path_id'] != path_id]
        now = time.time()
        conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                     (json.dumps(state, ensure_ascii=False), now, session['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,'
            'after_json,note,created) VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'net_path_delete',
             json.dumps(before, ensure_ascii=False), json.dumps(state, ensure_ascii=False),
             reason, now))
        conn.commit()
        self.send_json({'ok': True})

    @atomic_endpoint
    def api_session_net_path_update(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or 'edit_session' not in self.session_capabilities(conn, user, session)[1]:
            raise ApiError(403, 'Нет права редактировать NET Architecture')
        if set(body or {}) - {'label', 'visible', 'reason'}:
            raise ApiError(400, 'NET path содержит неподдерживаемые поля')
        state = session_net_state(_row_value(session, 'net_state_json', '{}'))
        path_id = str(m.group(2)).lower()
        path = next((item for item in state['paths']
                     if item['path_id'] == path_id), None)
        if not path:
            raise ApiError(404, 'NET path не найден')
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину изменения NET Architecture')
        before = copy.deepcopy(state)
        path['label'] = str((body or {}).get('label', path['label']) or '')[:120]
        path['visible'] = (body or {}).get('visible', path['visible']) is True
        now = time.time()
        conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                     (json.dumps(state, ensure_ascii=False), now, session['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,'
            'after_json,note,created) VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'net_path_update',
             json.dumps(before, ensure_ascii=False), json.dumps(state, ensure_ascii=False),
             reason, now))
        conn.commit()
        self.send_json(path)

    @atomic_endpoint
    def api_session_net_state_update(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or 'edit_combatants' not in self.session_capabilities(conn, user, session)[1]:
            raise ApiError(403, 'Нет права управлять Session NET Queue')
        state = session_net_state(_row_value(session, 'net_state_json', '{}'))
        before = copy.deepcopy(state)
        net_payload = self.session_net_payload(conn, session, player_view=False)
        queue_count = sum(1 for item in net_payload['entities'] if item['in_queue'])
        round_number = _num((body or {}).get('round', state['round']))
        active_turn = _num((body or {}).get('active_turn', state['active_turn']))
        if (round_number is None or int(round_number) != round_number or round_number < 0 or
                active_turn is None or int(active_turn) != active_turn or active_turn < 0):
            raise ApiError(400, 'Некорректный Session NET turn state')
        state['round'] = int(round_number)
        state['active_turn'] = min(int(active_turn), max(0, queue_count - 1))
        note = str((body or {}).get('reason') or '').strip()[:500]
        if len(note) < 3:
            raise ApiError(400, 'Укажите причину изменения NET Queue')
        now = time.time()
        conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                     (json.dumps(state, ensure_ascii=False), now, session['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,'
            'after_json,note,created) VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'net_turn_update',
             json.dumps(before, ensure_ascii=False), json.dumps(state, ensure_ascii=False),
             note, now))
        conn.commit()
        updated = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (session['id'],)).fetchone()
        self.send_json(self.session_payload(conn, updated, user))

    def api_session_player_view(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?', (int(m.group(1)),)).fetchone()
        if not session:
            raise ApiError(404, 'Сессия не найдена')
        role, capabilities = self.session_capabilities(conn, user, session)
        if 'view_player' not in capabilities and 'view_gm' not in capabilities:
            raise ApiError(403, 'Нет доступа к экрану сессии')
        self.send_json(self.session_payload(conn, session, user, player_view=True))

    def api_session_safety(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        role, capabilities = self.session_capabilities(conn, user, session)
        if not session or not role:
            raise ApiError(403, 'Нет доступа к экрану сессии')
        if 'manage_safety' in capabilities:
            rows = conn.execute(
                'SELECT * FROM session_safety_signals WHERE session_id=? '
                'ORDER BY CASE status WHEN \'open\' THEN 0 WHEN \'acknowledged\' THEN 1 ELSE 2 END,created DESC',
                (session['id'],)).fetchall()
        else:
            rows = conn.execute(
                'SELECT * FROM session_safety_signals WHERE session_id=? AND user_id=? ORDER BY created DESC',
                (session['id'], user['id'])).fetchall()
        self.send_json({'safety_config': session_safety_config(session['safety_config']),
                        'can_manage': 'manage_safety' in capabilities,
                        'signals': [self.safety_signal_payload(row) for row in rows]})

    @atomic_endpoint
    def api_session_safety_create(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        role, capabilities = self.session_capabilities(conn, user, session)
        if not session or not role:
            raise ApiError(403, 'Нет доступа к экрану сессии')
        config = session_safety_config(session['safety_config'])
        if not config['pause_enabled']:
            raise ApiError(409, 'Safety signal отключён для этой сессии')
        self.rate_limit('session-safety', 10, 3600, user['id'])
        kind = str((body or {}).get('kind') or 'pause').lower()
        if kind not in SAFETY_SIGNAL_KINDS:
            raise ApiError(400, 'Некорректный тип Safety signal')
        message = str((body or {}).get('message') or '').strip()[:500]
        now = time.time()
        cur = conn.execute(
            'INSERT INTO session_safety_signals(session_id,user_id,kind,message,status,created) '
            "VALUES(?,?,?,?,'open',?)", (session['id'], user['id'], kind, message, now))
        recipients = {session['owner_user_id']}
        recipients.update(row['user_id'] for row in conn.execute(
            "SELECT user_id FROM session_access WHERE session_id=? AND role='co_gm'",
            (session['id'],)).fetchall())
        for recipient in recipients:
            if recipient != user['id']:
                add_notification(conn, recipient, 'session_safety', 'Anonymous Session safety signal',
                                 session['title'], f'#/session/{session["id"]}')
        conn.commit()
        row = conn.execute('SELECT * FROM session_safety_signals WHERE id=?',
                           (cur.lastrowid,)).fetchone()
        self.send_json(self.safety_signal_payload(row), status=201)

    @atomic_endpoint
    def api_session_safety_update(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        role, capabilities = self.session_capabilities(conn, user, session)
        if not session or 'manage_safety' not in capabilities:
            raise ApiError(403, 'Нет права управлять Safety signal')
        signal = conn.execute(
            'SELECT * FROM session_safety_signals WHERE id=? AND session_id=?',
            (int(m.group(2)), session['id'])).fetchone()
        if not signal:
            raise ApiError(404, 'Safety signal не найден')
        status = str((body or {}).get('status') or '').lower()
        if status not in ('acknowledged', 'resolved'):
            raise ApiError(400, 'Некорректный статус Safety signal')
        if signal['status'] == 'resolved' and status != 'resolved':
            raise ApiError(409, 'Resolved Safety signal нельзя открыть повторно')
        now = time.time()
        if status == 'acknowledged':
            conn.execute(
                "UPDATE session_safety_signals SET status='acknowledged',acknowledged_by=?,"
                'acknowledged_at=? WHERE id=?', (user['id'], now, signal['id']))
        else:
            conn.execute(
                "UPDATE session_safety_signals SET status='resolved',resolved_by=?,resolved_at=?,"
                'acknowledged_by=COALESCE(acknowledged_by,?),'
                'acknowledged_at=COALESCE(acknowledged_at,?) WHERE id=?',
                (user['id'], now, user['id'], now, signal['id']))
        conn.commit()
        updated = conn.execute('SELECT * FROM session_safety_signals WHERE id=?',
                               (signal['id'],)).fetchone()
        self.send_json(self.safety_signal_payload(updated))

    @atomic_endpoint
    def api_session_sync(self, conn, qs, m, body):
        """Write Session combatant resources back to their Dossiers (P-Sync)."""
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or 'edit_combatants' not in self.session_capabilities(conn, user, session)[1]:
            raise ApiError(403, 'Нет права синхронизировать сессию')
        combatants = conn.execute(
            'SELECT * FROM session_combatants WHERE session_id=? AND character_id IS NOT NULL',
            (session['id'],)).fetchall()
        synced = []
        for combatant in combatants:
            char = conn.execute('SELECT * FROM characters WHERE id=?',
                                (combatant['character_id'],)).fetchone()
            if not char:
                continue
            before = json.loads(char['data'])
            after = copy.deepcopy(before)
            changed = False
            if combatant['hp_current'] is not None:
                after['hp_cur'] = max(0, combatant['hp_current'])
                changed = True
            if combatant['luck_current'] is not None:
                after['luck_cur'] = max(0, combatant['luck_current'])
                changed = True
            if changed:
                record_character_changes(conn, char['id'], user['id'], before, after,
                                         f'Session sync: {session["title"]}',
                                         session_id=session['id'])
                conn.execute('UPDATE characters SET data=?,updated=?,revision=revision+1 WHERE id=?',
                             (json.dumps(after, ensure_ascii=False), time.time(), char['id']))
                synced.append(char['id'])
        conn.commit()
        self.send_json({'ok': True, 'synced': synced, 'count': len(synced)})

    @atomic_endpoint
    def api_session_update(self, conn, qs, m, body):
        user = self.require_user(conn)
        row = conn.execute('SELECT * FROM nc_sessions WHERE id=?', (int(m.group(1)),)).fetchone()
        role, capabilities = self.session_capabilities(conn, user, row)
        if not row or not capabilities.intersection({'edit_session', 'edit_combatants'}):
            raise ApiError(403, 'Нет права редактировать сессию')
        if 'edit_session' not in capabilities:
            forbidden = set(body or {}) - {'round', 'active_turn', 'status', 'activity_note'}
            if forbidden:
                raise ApiError(403, 'Assistant может менять только ход и раунд')
        status = str((body or {}).get('status', row['status']))
        if status not in ('preparing', 'active', 'paused', 'completed', 'archived'):
            raise ApiError(400, 'Некорректный статус сессии')
        before = {
            'title': row['title'], 'status': row['status'], 'round': row['round'],
            'active_turn': row['active_turn'],
            'player_view_config': session_view_config(row['player_view_config']),
            'safety_config': session_safety_config(row['safety_config']),
            'notes': row['notes'],
        }
        title = str((body or {}).get('title', row['title'])).strip()[:180] or row['title']
        round_number = max(0, _num((body or {}).get('round', row['round'])) or 0)
        combatant_count = conn.execute(
            'SELECT COUNT(*) n FROM session_combatants WHERE session_id=?',
            (row['id'],)).fetchone()['n']
        active_turn = max(0, _num((body or {}).get('active_turn', row['active_turn'])) or 0)
        active_turn = min(active_turn, max(0, combatant_count - 1))
        config = session_view_config(
            (body or {}).get('player_view_config', row['player_view_config']))
        safety = session_safety_config(
            (body or {}).get('safety_config', row['safety_config']))
        notes = str((body or {}).get('notes', row['notes']))[:20000]
        now = time.time()
        after = {
            'title': title, 'status': status, 'round': round_number,
            'active_turn': active_turn, 'player_view_config': config,
            'safety_config': safety, 'notes': notes,
        }
        conn.execute(
            'UPDATE nc_sessions SET title=?,status=?,round=?,active_turn=?,player_view_config=?,'
            'safety_config=?,notes=?,updated=? WHERE id=?',
            (title, status, round_number, active_turn, json.dumps(config), json.dumps(safety),
             notes, now, row['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,after_json,note,created) '
            'VALUES(?,?,?,?,?,?,?)',
            (row['id'], user['id'], 'session_update', json.dumps(before, ensure_ascii=False),
             json.dumps(after, ensure_ascii=False),
             str((body or {}).get('activity_note') or '')[:500], now))
        conn.commit(); updated = conn.execute('SELECT * FROM nc_sessions WHERE id=?', (row['id'],)).fetchone()
        self.send_json(self.session_payload(conn, updated, user))

    def session_access_role(self, conn, user, session):
        if not user or not session:
            return None
        if user_is_admin(user) or session['owner_user_id'] == user['id']:
            return 'owner'
        explicit = conn.execute(
            'SELECT role FROM session_access WHERE session_id=? AND user_id=?',
            (session['id'], user['id'])).fetchone()
        if explicit and explicit['role'] in SESSION_ACCESS_ROLES:
            return explicit['role']
        if conn.execute(
                'SELECT 1 FROM session_combatants sc JOIN characters c '
                'ON c.id=sc.character_id WHERE sc.session_id=? AND c.owner_id=?',
                (session['id'], user['id'])).fetchone():
            return 'crew'
        if session['contract_id']:
            contract = conn.execute('SELECT * FROM contracts WHERE id=?',
                                    (session['contract_id'],)).fetchone()
            if user_is_gm(user) and can_edit_contract(conn, user, contract):
                return 'co_gm'
            if conn.execute(
                    "SELECT 1 FROM contract_signups WHERE contract_id=? AND user_id=? AND status='crew'",
                    (session['contract_id'], user['id'])).fetchone():
                return 'crew'
        return None

    def session_activity_payload(self, row):
        before = parse_json_object(row['before_json'])
        after = parse_json_object(row['after_json'])
        event_type = row['event_type']
        changes = []

        def display_value(key, value):
            if key in ('conditions_json', 'injuries_json'):
                value = parse_json_list(value)
            if key == 'visible':
                return bool(value)
            if key == 'player_view_config':
                return session_view_config(value)
            if key == 'safety_config':
                return session_safety_config(value)
            if isinstance(value, (dict, list)):
                return value
            return value

        if event_type == 'session_update':
            for key in ('title', 'status', 'round', 'active_turn',
                        'player_view_config', 'safety_config', 'notes'):
                if key not in after:
                    continue
                old_value = before.get(key)
                new_value = after.get(key)
                if key == 'notes':
                    if str(old_value or '') != str(new_value or ''):
                        changes.append({'field': 'notes', 'before': None, 'after': 'updated'})
                    continue
                if key == 'player_view_config':
                    old_config = session_view_config(old_value)
                    new_config = session_view_config(new_value)
                    for setting in SESSION_VIEW_DEFAULTS:
                        if old_config[setting] != new_config[setting]:
                            changes.append({'field': f'player_view.{setting}',
                                            'before': old_config[setting],
                                            'after': new_config[setting]})
                    continue
                old_value = display_value(key, old_value)
                new_value = display_value(key, new_value)
                if old_value != new_value:
                    changes.append({'field': key, 'before': old_value, 'after': new_value})
        elif event_type in ('combatant_create', 'combatant_delete'):
            snapshot = after if event_type == 'combatant_create' else before
            changes.append({
                'field': 'combatant', 'before': None if event_type == 'combatant_create'
                else snapshot.get('name'),
                'after': snapshot.get('name') if event_type == 'combatant_create' else None,
            })
        elif event_type == 'net_action':
            changes.append({
                'field': after.get('action') or 'net_action',
                'before': None,
                'after': after.get('summary') or 'resolved',
            })
        elif event_type.startswith('net_'):
            def net_summary(value):
                if not value:
                    return None
                if value.get('type') == 'black_ice':
                    return {
                        'name': value.get('name'), 'status': value.get('status'),
                        'floor': value.get('floor_label'),
                        'target': value.get('target_label'),
                        'initiative': value.get('initiative'),
                        'rez': f"{value.get('rez_current')}/{value.get('rez_max')}",
                    }
                return {
                    'round': value.get('round'),
                    'active_turn': value.get('active_turn'),
                    'floors': len(value.get('floors') or []),
                    'nodes': len(value.get('nodes') or []),
                    'paths': len(value.get('paths') or []),
                    'links': len(value.get('links') or []),
                }
            changes.append({'field': 'net_context',
                            'before': net_summary(before),
                            'after': net_summary(after)})
        else:
            fields = (
                'name', 'initiative', 'hp_current', 'hp_max',
                'sp_head', 'sp_head_max', 'sp_body', 'sp_body_max',
                'shield_current', 'shield_max', 'ammo_current', 'ammo_max',
                'luck_current', 'luck_max', 'move', 'death_penalty',
                'conditions_json', 'injuries_json', 'visible', 'sort_order',
            )
            for key in fields:
                old_value = display_value(key, before.get(key))
                new_value = display_value(key, after.get(key))
                if old_value != new_value:
                    changes.append({'field': key[:-5] if key.endswith('_json') else key,
                                    'before': old_value, 'after': new_value})
                if len(changes) >= 20:
                    break
        return {
            'id': row['id'], 'combatant_id': row['combatant_id'],
            'event_type': event_type, 'actor': row['actor'],
            'note': row['note'], 'created': row['created'], 'changes': changes,
        }

    def session_capabilities(self, conn, user, session):
        role = self.session_access_role(conn, user, session)
        return role, set(SESSION_ROLE_CAPABILITIES.get(role, set()))

    def session_net_payload(self, conn, row, user=None, player_view=False):
        state = session_net_state(_row_value(row, 'net_state_json', '{}'))
        floor_by_id = {item['floor_id']: item for item in state['floors']}
        node_by_id = {item['node_id']: item for item in state['nodes']}
        combatants = {item['id']: item for item in self.ordered_session_combatants(
            conn, row['id'])}
        entities = []
        skunk_sources_by_target = {}
        for link in state['links']:
            if not link['active'] or (player_view and not link['visible']):
                continue
            character = conn.execute(
                'SELECT id,revision,data FROM characters WHERE id=?',
                (link['character_id'],)).fetchone()
            if not character:
                continue
            character_data = ensure_progression(json.loads(character['data']))
            entity = (character_data.get('net_entities') or {}).get(
                link['net_entity_id'])
            if (not isinstance(entity, dict) or
                    entity.get('status') not in ('lying_in_wait', 'hunting', 'derezzed')):
                continue
            floor = floor_by_id.get(link['floor_id'])
            node = node_by_id.get(link.get('node_id'))
            target = combatants.get(link.get('target_combatant_id'))
            payload = {
                'net_entity_id': link['net_entity_id'],
                'character_id': link['character_id'],
                'name': entity.get('name') or 'Black ICE',
                'status': entity.get('status'),
                'initiative': link['initiative'] if entity.get('status') == 'hunting' else None,
                'in_queue': entity.get('status') == 'hunting',
                'floor_id': link['floor_id'],
                'floor_label': floor['label'] if floor else entity.get('floor_label'),
                'node_id': link.get('node_id'),
                'node_label': node['label'] if node else None,
                'target_combatant_id': link.get('target_combatant_id'),
                'target_label': target['name'] if target and
                    (not player_view or target['visible']) else None,
                'target_type': entity.get('target_type'),
                'per': entity.get('per'), 'spd': entity.get('spd'),
                'atk': entity.get('atk'), 'def': entity.get('def'),
                'rez_current': entity.get('rez_current'),
                'rez_max': entity.get('rez_max'),
                'entity_character_revision': character['revision'],
                'visible': link['visible'],
            }
            source_program = next((item for item in character_data.get('inventory') or []
                                   if isinstance(item, dict) and
                                   item.get('instance_id') == entity.get('source_program_instance_id')), {})
            effect_profile = black_ice_effect_profile(source_program)
            payload['effect_resolution'] = effect_profile['resolution']
            if (payload.get('name') == 'Skunk' and
                    payload.get('status') == 'hunting' and
                    link.get('target_combatant_id')):
                skunk_sources_by_target.setdefault(
                    link['target_combatant_id'], []).append(link['net_entity_id'])
            if not player_view:
                payload['character_revision'] = character['revision']
                payload['initiative_roll'] = entity.get('initiative_roll')
                payload['effect_profile'] = effect_profile
                if target and target['character_id']:
                    target_character = conn.execute(
                        'SELECT id,revision,data FROM characters WHERE id=?',
                        (target['character_id'],)).fetchone()
                    if target_character:
                        target_data = enrich_owned_item_interactions(
                            ensure_progression(json.loads(target_character['data'])))
                        target_modifications = character_modifications(
                            conn, target_character['id'])
                        target_decks = character_effective_cyberdecks(
                            target_data, target_modifications)
                        payload['target_interface_rank'] = character_interface_rank(target_data)
                        payload['target_character_revision'] = target_character['revision']
                        all_target_programs = [
                            {
                                'instance_id': program['instance_id'],
                                'name': program['name'],
                                'def': int(_num((program.get('mechanics') or {}).get('def')) or 0),
                                'rez_current': int(_num((program.get('runtime') or {}).get('rez_current')) or 0),
                                'rez_max': int(_num((program.get('runtime') or {}).get('rez_max')) or 0),
                                'category': (program.get('runtime') or {}).get('category'),
                                'status': (program.get('runtime') or {}).get('status'),
                            }
                            for deck in target_decks.values()
                            for program in deck.get('programs') or []]
                        payload['valid_target_programs'] = [
                            program for program in all_target_programs
                            if program['status'] == 'rezzed']
                        if effect_profile['resolution'] == 'automated_random_destroy':
                            payload['curated_target_programs'] = all_target_programs
                        elif effect_profile['resolution'] == 'automated_random_derez_plus_manual':
                            payload['curated_target_programs'] = [
                                program for program in all_target_programs
                                if program['status'] == 'rezzed' and
                                program['category'] == 'defender']
            else:
                for private_key in ('character_id', 'target_combatant_id', 'visible',
                                    'node_id'):
                    payload.pop(private_key, None)
            entities.append(payload)
        queue = sorted(
            (item for item in entities if item['in_queue']),
            key=lambda item: (-(_num(item.get('initiative')) or 0), item['net_entity_id']))
        active_turn = min(state['active_turn'], max(0, len(queue) - 1))
        active_id = queue[active_turn]['net_entity_id'] if queue else None
        for item in entities:
            item['active'] = item['net_entity_id'] == active_id
        entities.sort(key=lambda item: (
            0 if item['in_queue'] else 1,
            -(_num(item.get('initiative')) or 0), item['net_entity_id']))
        runners = []
        runner_by_combatant = {item['combatant_id']: item
                              for item in state.get('runners') or []}
        for combatant in combatants.values():
            if not combatant['character_id'] or (player_view and not combatant['visible']):
                continue
            character = conn.execute(
                'SELECT id,owner_id,revision,data FROM characters WHERE id=?',
                (combatant['character_id'],)).fetchone()
            if not character:
                continue
            character_data = enrich_owned_item_interactions(
                ensure_progression(json.loads(character['data'])))
            interface_rank = character_interface_rank(character_data)
            if interface_rank <= 0:
                continue
            runner = runner_by_combatant.get(combatant['id']) or {
                'combatant_id': combatant['id'], 'character_id': character['id'],
                'node_id': None, 'jacked_in': False, 'actions_recorded': 0,
                'action_round': state['round'], 'actions_used': 0,
                'action_penalty': 0, 'next_action_penalty': 0,
            }
            node = node_by_id.get(runner.get('node_id'))
            same_action_round = runner.get('action_round') == state['round']
            current_actions_used = runner.get('actions_used', 0) if same_action_round else 0
            action_penalty = (runner.get('action_penalty', 0) if same_action_round else
                              runner.get('next_action_penalty', 0))
            actions_max = max(2, net_actions_for_interface(interface_rank) - action_penalty)
            skunk_sources = skunk_sources_by_target.get(combatant['id'], [])
            runner_payload = {
                'combatant_id': combatant['id'],
                'character_id': character['id'],
                'name': combatant['name'], 'jacked_in': runner.get('jacked_in', False),
                'node_id': runner.get('node_id'),
                'node_label': node['label'] if node else None,
                'interface_rank': interface_rank,
                'actions_recorded': runner.get('actions_recorded', 0),
                'actions_used': current_actions_used,
                'actions_max': actions_max,
                'actions_remaining': max(0, actions_max - current_actions_used),
                'action_penalty': action_penalty,
                'skunk_slide_penalty': -2 * len(skunk_sources),
                'skunk_source_count': len(skunk_sources),
            }
            can_act = bool(user and character['owner_id'] == user['id'])
            if not player_view or can_act:
                modifications = character_modifications(conn, character['id'])
                decks = character_effective_cyberdecks(character_data, modifications)
                runner_payload['character_revision'] = character['revision']
                runner_payload['attacker_programs'] = [
                    {'instance_id': program['instance_id'], 'name': program['name'],
                     'atk': (program.get('mechanics') or {}).get('atk') or 0}
                    for deck in decks.values() for program in deck.get('programs') or []
                    if (program.get('runtime') or {}).get('category') == 'attacker']
            if player_view:
                runner_payload['can_act'] = can_act
                runner_payload.pop('character_id', None)
                runner_payload.pop('node_id', None)
            runners.append(runner_payload)
        if player_view:
            visible_nodes = [item for item in state['nodes'] if item['visible']]
            visible_node_ids = {item['node_id'] for item in visible_nodes}
            nodes = [{
                key: value for key, value in item.items()
                if key not in ('gm_note', 'visible', 'sort_order', 'floor_id',
                               'controlled_by_combatant_id')
            } | {
                'floor_label': (floor_by_id.get(item['floor_id']) or {}).get('label'),
                'controlled': item.get('controlled_by_combatant_id') is not None,
            } for item in visible_nodes]
            paths = [copy.deepcopy(item) for item in state['paths']
                     if item['visible'] and item['from_node_id'] in visible_node_ids and
                     item['to_node_id'] in visible_node_ids]
            visible_floor_ids = {item['floor_id'] for item in visible_nodes} | {
                item['floor_id'] for item in entities}
            floors = [{'label': item['label']} for item in state['floors']
                      if item['floor_id'] in visible_floor_ids]
            for item in entities:
                item.pop('floor_id', None)
        else:
            floors = state['floors']
            nodes = state['nodes']
            paths = state['paths']
        actions = state.get('action_log', [])[-20:]
        if player_view:
            actions = [{key: item.get(key) for key in (
                'action', 'success', 'actor_total', 'defense_total',
                'created', 'summary')} for item in actions]
        return {
            'round': state['round'], 'active_turn': active_turn,
            'floors': floors, 'nodes': nodes, 'paths': paths,
            'entities': entities, 'runners': runners,
            'action_log': actions,
        }

    def session_payload(self, conn, row, user, player_view=False):
        access_role, capabilities = self.session_capabilities(conn, user, row)
        can_edit = 'edit_session' in capabilities
        config = session_view_config(row['player_view_config'])
        safety = session_safety_config(_row_value(row, 'safety_config', '{}'))
        combatants = self.ordered_session_combatants(conn, row['id'])
        active_turn = min(max(0, _num(row['active_turn']) or 0), max(0, len(combatants) - 1))
        out_combatants = []
        for index, item in enumerate(combatants):
            if player_view and not item['visible']:
                continue
            data = {
                'id': item['id'], 'kind': item['kind'], 'character_id': item['character_id'],
                'name': item['name'], 'visible': bool(item['visible']),
                'sort_order': item['sort_order'],
                'active': bool(combatants) and index == active_turn,
            }
            if not player_view or config['show_initiative']:
                data['initiative'] = item['initiative']
            if not player_view:
                data.update({
                    'hp_current': item['hp_current'], 'hp_max': item['hp_max'],
                    'sp_head': item['sp_head'], 'sp_head_max': item['sp_head_max'],
                    'sp_body': item['sp_body'], 'sp_body_max': item['sp_body_max'],
                    'shield_current': item['shield_current'], 'shield_max': item['shield_max'],
                    'ammo_current': item['ammo_current'], 'ammo_max': item['ammo_max'],
                    'luck_current': item['luck_current'], 'luck_max': item['luck_max'],
                    'move': item['move'], 'conditions': parse_json_list(item['conditions_json']),
                    'injuries': parse_json_list(item['injuries_json']),
                    'death_penalty': item['death_penalty'],
                })
                if 'view_secrets' in capabilities:
                    data['secret'] = parse_json_object(item['secret_json'])
            else:
                if item['kind'] == 'character' and config['show_ally_hp']:
                    data.update({'hp_current': item['hp_current'], 'hp_max': item['hp_max']})
                if config['show_armor']:
                    data.update({'sp_head': item['sp_head'], 'sp_head_max': item['sp_head_max'],
                                 'sp_body': item['sp_body'], 'sp_body_max': item['sp_body_max']})
                if config['show_shield']:
                    data.update({'shield_current': item['shield_current'],
                                 'shield_max': item['shield_max']})
                if config['show_ammo']:
                    data.update({'ammo_current': item['ammo_current'], 'ammo_max': item['ammo_max']})
                if config['show_move']:
                    data['move'] = item['move']
                if config['show_luck'] and item['luck_max']:
                    data.update({'luck_current': item['luck_current'], 'luck_max': item['luck_max']})
                if config['show_conditions']:
                    data['conditions'] = parse_json_list(item['conditions_json'])
                if config['show_injuries']:
                    data['injuries'] = parse_json_list(item['injuries_json'])
                    data['death_penalty'] = item['death_penalty']
            if item['kind'] == 'npc':
                statblock = parse_json_object(item['statblock_json'])
                if statblock and (not player_view or config['show_npc_stats']):
                    data['statblock'] = statblock
                    data['derived'] = npc_statblock_derived(statblock)
            out_combatants.append(data)
        visible_active_turn = next(
            (index for index, item in enumerate(out_combatants) if item['active']), None)
        payload = {
            'id': row['id'], 'contract_id': row['contract_id'], 'title': row['title'],
            'status': row['status'], 'round': row['round'],
            'active_turn': visible_active_turn if player_view else active_turn,
            'player_view_config': config, 'safety_config': safety,
            'combatants': out_combatants,
            'net': self.session_net_payload(conn, row, user=user, player_view=player_view),
            'created': row['created'], 'updated': row['updated'], 'can_edit': can_edit,
            'access_role': access_role,
            'capabilities': {key: key in capabilities for key in (
                'view_gm', 'view_secrets', 'edit_session', 'edit_combatants',
                'manage_access', 'manage_safety')},
        }
        if not player_view and 'edit_session' in capabilities:
            payload['notes'] = row['notes']
        if not player_view and capabilities.intersection({'edit_session', 'edit_combatants'}):
            activity = conn.execute(
                'SELECT a.*,u.display_name actor FROM session_activity a '
                'JOIN users u ON u.id=a.actor_user_id WHERE session_id=? '
                'ORDER BY a.id DESC LIMIT 200', (row['id'],)).fetchall()
            payload['activity'] = [self.session_activity_payload(item) for item in activity]
        return payload

    def api_sessions(self, conn, qs, m, body):
        user = self.require_user(conn)
        rows = conn.execute('SELECT * FROM nc_sessions ORDER BY updated DESC').fetchall()
        visible = []
        for row in rows:
            role, capabilities = self.session_capabilities(conn, user, row)
            if not role:
                continue
            visible.append(self.session_payload(
                conn, row, user, player_view='view_gm' not in capabilities))
        self.send_json({'sessions': visible})

    def can_edit_nc_session(self, conn, user, session):
        return 'edit_session' in self.session_capabilities(conn, user, session)[1]

    def can_edit_npc_template(self, user, template):
        return bool(user and template and user_is_gm(user) and
                    (user_is_admin(user) or template['owner_user_id'] == user['id']))

    def can_manage_session_access(self, conn, user, session):
        return 'manage_access' in self.session_capabilities(conn, user, session)[1]

    def ordered_session_combatants(self, conn, session_id):
        return conn.execute(
            'SELECT * FROM session_combatants WHERE session_id=? '
            'ORDER BY initiative DESC,sort_order,id', (session_id,)).fetchall()

    def safety_signal_payload(self, row):
        return {
            'id': row['id'], 'kind': row['kind'], 'message': row['message'],
            'status': row['status'], 'created': row['created'],
            'acknowledged_at': row['acknowledged_at'], 'resolved_at': row['resolved_at'],
        }

    def api_npc_template_clone(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute(
            "SELECT * FROM npc_templates WHERE id=? AND archived=0 AND "
            "(? OR access='shared' OR owner_user_id=?)",
            (int(m.group(1)), 1 if user_is_admin(user) else 0, user['id'])).fetchone()
        if not row:
            raise ApiError(404, 'NPC template не найден')
        cleaned = clean_npc_template_input({
            'name': str((body or {}).get('name') or f'{row["name"]} Copy'),
            'role': row['role'],
            'access': (body or {}).get('access') or 'private',
            'data': parse_json_object(row['data_json']),
        })
        now = time.time()
        cur = conn.execute(
            'INSERT INTO npc_templates(owner_user_id,access,name,role,data_json,created,updated) '
            'VALUES(?,?,?,?,?,?,?)',
            (user['id'], cleaned['access'], cleaned['name'], cleaned['role'],
             json.dumps(cleaned['data'], ensure_ascii=False), now, now))
        conn.commit()
        cloned = conn.execute('SELECT * FROM npc_templates WHERE id=?', (cur.lastrowid,)).fetchone()
        self.send_json(self.npc_template_payload(cloned, user), status=201)

    def api_npc_template_create(self, conn, qs, m, body):
        user = self.require_gm(conn)
        cleaned = clean_npc_template_input(body or {})
        now = time.time()
        cur = conn.execute(
            'INSERT INTO npc_templates(owner_user_id,access,name,role,data_json,created,updated) '
            'VALUES(?,?,?,?,?,?,?)',
            (user['id'], cleaned['access'], cleaned['name'], cleaned['role'],
             json.dumps(cleaned['data'], ensure_ascii=False), now, now))
        conn.commit()
        row = conn.execute('SELECT * FROM npc_templates WHERE id=?', (cur.lastrowid,)).fetchone()
        self.send_json(self.npc_template_payload(row, user), status=201)

    def api_npc_template_delete(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute('SELECT * FROM npc_templates WHERE id=? AND archived=0',
                           (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'NPC template не найден')
        if not self.can_edit_npc_template(user, row):
            raise ApiError(403, 'Нет права редактировать NPC template')
        conn.execute('UPDATE npc_templates SET archived=1,updated=? WHERE id=?',
                     (time.time(), row['id']))
        conn.commit(); self.send_json({'ok': True, 'archived': True})

    def api_npc_template_update(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute('SELECT * FROM npc_templates WHERE id=? AND archived=0',
                           (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'NPC template не найден')
        if not self.can_edit_npc_template(user, row):
            raise ApiError(403, 'Нет права редактировать NPC template')
        cleaned = clean_npc_template_input(body or {}, row)
        conn.execute(
            'UPDATE npc_templates SET access=?,name=?,role=?,data_json=?,updated=? WHERE id=?',
            (cleaned['access'], cleaned['name'], cleaned['role'],
             json.dumps(cleaned['data'], ensure_ascii=False), time.time(), row['id']))
        conn.commit()
        updated = conn.execute('SELECT * FROM npc_templates WHERE id=?', (row['id'],)).fetchone()
        self.send_json(self.npc_template_payload(updated, user))

    def api_npc_templates(self, conn, qs, m, body):
        user = self.require_user(conn)
        if not user_is_gm(user):
            session_id = _num(q1(qs.get('session_id')))
            session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                                   (session_id,)).fetchone() if session_id else None
            if not session or 'edit_combatants' not in self.session_capabilities(conn, user, session)[1]:
                raise ApiError(403, 'Только для пользователей с ролью ГМ')
        rows = conn.execute(
            "SELECT * FROM npc_templates WHERE archived=0 AND "
            "(? OR access='shared' OR owner_user_id=?) ORDER BY updated DESC",
            (1 if user_is_admin(user) else 0, user['id'])).fetchall()
        self.send_json({'templates': [self.npc_template_payload(row, user) for row in rows]})

    def npc_template_payload(self, row, user):
        data = parse_json_object(row['data_json'])
        return {
            'id': row['id'], 'owner_user_id': row['owner_user_id'],
            'access': row['access'], 'name': row['name'], 'role': row['role'],
            'data': data,
            'derived': npc_statblock_derived(data.get('statblock') or {}),
            'updated': row['updated'],
            'can_edit': self.can_edit_npc_template(user, row),
        }

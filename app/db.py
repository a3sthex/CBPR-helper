"""Слой данных NC//NET: SQLite, схема, миграции, bootstrap (итерация P1-8).

Выделено из app/server.py: SCHEMA, все миграции, ensure_* bootstrap-
инициализаторы, rate-limit хранилища, бэкап-обвязка. Логика не менялась;
ensure_progression остаётся в server.py до выделения домена progression —
подключается через bind() (docs/repo-audit-2026-08.md).
"""
import copy
import json
import os
import time
import math
import secrets
import threading
import sqlite3
import sys
from datetime import datetime, timezone

from core import (ApiError, BACKUP_DIR, BASE, DB_PATH, INSTANCE_ID_RE, STATS,
                  parse_json_object, user_account_role)
from rules import SKILL_BY_NAME, _num, effect_instance_payload
from catalog import (CYBERDECK_PROFILES, item_by_id, validate_effect_definition,
                     vehicle_modification_rules_for_catalog)
from mod_engine import (character_effective_vehicles, character_effective_weapons,
                        clear_loaded_ammo_if_empty, ensure_shared_ammo_state,
                        initial_vehicle_modification_state,
                        normalize_vehicle_modification_state, vehicle_base_interior)
from inventory import (catalog_item_id_for_entry, character_modifications,
                       ensure_character_item_instances,
                       persist_character_item_instances)
from charbuild import ensure_progression, skill_base





SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL,
  pass_hash TEXT NOT NULL,
  is_gm INTEGER NOT NULL DEFAULT 0,
  account_role TEXT NOT NULL DEFAULT 'player',
  show_display_name INTEGER NOT NULL DEFAULT 0,
  vk_user_id TEXT,
  vk_linked_at REAL,
  notification_prefs TEXT NOT NULL DEFAULT '{}',
  theme_json TEXT NOT NULL DEFAULT '{}',
  avatar_media_id TEXT,
  disabled_at REAL,
  disabled_reason TEXT,
  disabled_by INTEGER,
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions(
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  created REAL NOT NULL,
  expires REAL NOT NULL,
  last_seen REAL,
  ip_address TEXT,
  user_agent TEXT
);
CREATE TABLE IF NOT EXISTS characters(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_id INTEGER NOT NULL,
  public INTEGER NOT NULL DEFAULT 1,
  data TEXT NOT NULL,
  revision INTEGER NOT NULL DEFAULT 0,
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS news(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  author_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  tag TEXT,
  body TEXT NOT NULL,
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  author_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  when_text TEXT,
  system TEXT DEFAULT 'Cyberpunk RED',
  description TEXT NOT NULL,
  slots INTEGER DEFAULT 0,
  status TEXT DEFAULT 'open',
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS job_signups(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  char_name TEXT,
  note TEXT,
  created REAL NOT NULL,
  UNIQUE(job_id, user_id)
);
CREATE TABLE IF NOT EXISTS media(
  id TEXT PRIMARY KEY,
  owner_id INTEGER NOT NULL,
  kind TEXT NOT NULL,
  mime TEXT NOT NULL,
  filename TEXT NOT NULL,
  size INTEGER NOT NULL,
  width INTEGER NOT NULL,
  height INTEGER NOT NULL,
  attached_type TEXT,
  attached_id INTEGER,
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS ip_ledger(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  character_id INTEGER NOT NULL,
  actor_id INTEGER NOT NULL,
  amount INTEGER NOT NULL,
  balance_before INTEGER NOT NULL,
  balance_after INTEGER NOT NULL,
  kind TEXT NOT NULL,
  subject TEXT,
  reason TEXT NOT NULL,
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS schema_migrations(
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  applied REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS account_role_audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  target_user_id INTEGER NOT NULL,
  actor_user_id INTEGER,
  role_before TEXT NOT NULL,
  role_after TEXT NOT NULL,
  reason TEXT NOT NULL,
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS account_security_audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  actor_user_id INTEGER,
  event_type TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT '',
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS registration_invites(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code_hash TEXT UNIQUE NOT NULL,
  label TEXT NOT NULL DEFAULT '',
  created_by INTEGER NOT NULL,
  max_uses INTEGER NOT NULL DEFAULT 1,
  uses INTEGER NOT NULL DEFAULT 0,
  expires_at REAL,
  disabled_at REAL,
  created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_char_owner ON characters(owner_id);
CREATE INDEX IF NOT EXISTS idx_news_created ON news(created);
CREATE INDEX IF NOT EXISTS idx_media_owner ON media(owner_id);
CREATE INDEX IF NOT EXISTS idx_media_attached ON media(attached_type, attached_id);
CREATE INDEX IF NOT EXISTS idx_ip_character ON ip_ledger(character_id, created);
CREATE INDEX IF NOT EXISTS idx_role_audit_target ON account_role_audit(target_user_id, created);
CREATE INDEX IF NOT EXISTS idx_registration_invites_active
  ON registration_invites(disabled_at,expires_at,uses,max_uses);
CREATE INDEX IF NOT EXISTS idx_account_security_audit
  ON account_security_audit(user_id,created);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id,expires);
"""

NETWORK_SCHEMA = """
CREATE TABLE IF NOT EXISTS personas(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_user_id INTEGER NOT NULL,
  access TEXT NOT NULL DEFAULT 'private',
  kind TEXT NOT NULL DEFAULT 'person',
  handle TEXT UNIQUE COLLATE NOCASE NOT NULL,
  display_name TEXT NOT NULL,
  avatar_media_id TEXT,
  cover_media_id TEXT,
  accent_color TEXT NOT NULL DEFAULT '#00e5ff',
  short_bio TEXT NOT NULL DEFAULT '',
  public_bio TEXT NOT NULL DEFAULT '',
  affiliation TEXT NOT NULL DEFAULT '',
  public_connections TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'active',
  secret_bio TEXT NOT NULL DEFAULT '',
  goals TEXT NOT NULL DEFAULT '',
  voice_notes TEXT NOT NULL DEFAULT '',
  secret_connections TEXT NOT NULL DEFAULT '{}',
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS persona_audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  persona_id INTEGER NOT NULL,
  actor_user_id INTEGER NOT NULL,
  action TEXT NOT NULL,
  before_json TEXT,
  after_json TEXT,
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS storylines(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_user_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  code_name TEXT NOT NULL DEFAULT '',
  public_summary TEXT NOT NULL DEFAULT '',
  private_summary TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'active',
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS storyline_collaborators(
  storyline_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  can_edit INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY(storyline_id,user_id)
);
CREATE TABLE IF NOT EXISTS storyline_timeline(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  storyline_id INTEGER NOT NULL,
  event_at REAL,
  public_text TEXT,
  private_text TEXT NOT NULL DEFAULT '',
  contract_id INTEGER,
  feed_post_id INTEGER,
  created_by INTEGER NOT NULL,
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS contracts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  legacy_job_id INTEGER UNIQUE,
  owner_user_id INTEGER NOT NULL,
  storyline_id INTEGER,
  status TEXT NOT NULL DEFAULT 'draft',
  title TEXT NOT NULL,
  teaser TEXT NOT NULL DEFAULT '',
  public_brief TEXT NOT NULL DEFAULT '',
  classified_brief TEXT NOT NULL DEFAULT '',
  district_id TEXT NOT NULL DEFAULT '',
  risk_level TEXT NOT NULL DEFAULT 'moderate',
  reward_mode TEXT NOT NULL DEFAULT 'hidden',
  reward_exact REAL,
  reward_min REAL,
  reward_max REAL,
  reward_text TEXT,
  scheduled_at REAL,
  timezone TEXT NOT NULL DEFAULT 'Europe/Moscow',
  duration_text TEXT,
  crew_capacity INTEGER NOT NULL DEFAULT 0,
  requirements TEXT NOT NULL DEFAULT '',
  content_notes TEXT NOT NULL DEFAULT '',
  service_format TEXT NOT NULL DEFAULT '',
  service_contact TEXT NOT NULL DEFAULT '',
  service_vtt_url TEXT NOT NULL DEFAULT '',
  service_notes TEXT NOT NULL DEFAULT '',
  cover_media_id TEXT,
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS contract_participants(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  contract_id INTEGER NOT NULL,
  persona_id INTEGER NOT NULL,
  role_key TEXT NOT NULL DEFAULT 'custom',
  role_label TEXT NOT NULL DEFAULT '',
  visibility TEXT NOT NULL DEFAULT 'public',
  note TEXT NOT NULL DEFAULT '',
  sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS contract_signups(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  contract_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  character_id INTEGER,
  legacy_char_name TEXT,
  status TEXT NOT NULL DEFAULT 'crew',
  queue_position INTEGER NOT NULL DEFAULT 0,
  joined_at REAL NOT NULL,
  updated REAL NOT NULL,
  UNIQUE(contract_id,character_id)
);
CREATE INDEX IF NOT EXISTS idx_personas_access ON personas(access,status);
CREATE INDEX IF NOT EXISTS idx_persona_audit ON persona_audit(persona_id,created);
CREATE INDEX IF NOT EXISTS idx_storylines_status ON storylines(status,updated);
CREATE INDEX IF NOT EXISTS idx_contracts_status ON contracts(status,scheduled_at);
CREATE INDEX IF NOT EXISTS idx_contract_signups ON contract_signups(contract_id,status,queue_position);
"""

FEED_SCHEMA = """
CREATE TABLE IF NOT EXISTS feed_posts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  legacy_news_id INTEGER UNIQUE,
  format TEXT NOT NULL DEFAULT 'short',
  status TEXT NOT NULL DEFAULT 'published',
  creator_user_id INTEGER NOT NULL,
  hidden_by_user_id INTEGER,
  hidden_reason TEXT,
  author_persona_id INTEGER,
  author_character_id INTEGER,
  storyline_id INTEGER,
  contract_id INTEGER,
  reply_to_post_id INTEGER,
  district_id TEXT,
  headline TEXT,
  lead TEXT,
  body TEXT NOT NULL,
  image_media_id TEXT,
  truth_status TEXT NOT NULL DEFAULT 'unknown',
  event_at REAL,
  published_at REAL,
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS feed_post_revisions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id INTEGER NOT NULL,
  actor_user_id INTEGER NOT NULL,
  action TEXT NOT NULL,
  before_json TEXT,
  after_json TEXT,
  reason TEXT,
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS feed_post_links(
  post_id INTEGER NOT NULL,
  linked_post_id INTEGER NOT NULL,
  relation TEXT NOT NULL DEFAULT 'related',
  PRIMARY KEY(post_id,linked_post_id,relation)
);
CREATE TABLE IF NOT EXISTS feed_comments(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id INTEGER NOT NULL,
  parent_comment_id INTEGER,
  creator_user_id INTEGER NOT NULL,
  author_persona_id INTEGER,
  author_character_id INTEGER,
  body TEXT NOT NULL,
  created REAL NOT NULL,
  updated REAL NOT NULL,
  hidden_at REAL,
  hidden_by INTEGER,
  hidden_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_feed_posts_public ON feed_posts(status,published_at);
CREATE INDEX IF NOT EXISTS idx_feed_comments_post ON feed_comments(post_id,created);
CREATE INDEX IF NOT EXISTS idx_feed_revisions ON feed_post_revisions(post_id,created);
"""

OPERATIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS character_ledger(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  character_id INTEGER NOT NULL,
  actor_user_id INTEGER NOT NULL,
  session_id INTEGER,
  contract_id INTEGER,
  category TEXT NOT NULL,
  delta_json TEXT NOT NULL DEFAULT '{}',
  before_json TEXT,
  after_json TEXT,
  reason TEXT NOT NULL DEFAULT '',
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS npc_templates(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_user_id INTEGER NOT NULL,
  access TEXT NOT NULL DEFAULT 'private',
  name TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT '',
  data_json TEXT NOT NULL DEFAULT '{}',
  archived INTEGER NOT NULL DEFAULT 0,
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS nc_sessions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  contract_id INTEGER,
  owner_user_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'preparing',
  round INTEGER NOT NULL DEFAULT 0,
  active_turn INTEGER NOT NULL DEFAULT 0,
  player_view_config TEXT NOT NULL DEFAULT '{}',
  safety_config TEXT NOT NULL DEFAULT '{}',
  net_state_json TEXT NOT NULL DEFAULT '{}',
  notes TEXT NOT NULL DEFAULT '',
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS session_access(
  session_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  role TEXT NOT NULL,
  created_by INTEGER NOT NULL,
  created REAL NOT NULL,
  updated REAL NOT NULL,
  PRIMARY KEY(session_id,user_id)
);
CREATE TABLE IF NOT EXISTS session_safety_signals(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  kind TEXT NOT NULL DEFAULT 'pause',
  message TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'open',
  acknowledged_by INTEGER,
  acknowledged_at REAL,
  resolved_by INTEGER,
  resolved_at REAL,
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS session_combatants(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL,
  kind TEXT NOT NULL DEFAULT 'npc',
  character_id INTEGER,
  template_id INTEGER,
  name TEXT NOT NULL,
  initiative INTEGER NOT NULL DEFAULT 0,
  hp_current INTEGER NOT NULL DEFAULT 0,
  hp_max INTEGER NOT NULL DEFAULT 0,
  sp_head INTEGER NOT NULL DEFAULT 0,
  sp_head_max INTEGER NOT NULL DEFAULT 0,
  sp_body INTEGER NOT NULL DEFAULT 0,
  sp_body_max INTEGER NOT NULL DEFAULT 0,
  shield_current INTEGER NOT NULL DEFAULT 0,
  shield_max INTEGER NOT NULL DEFAULT 0,
  ammo_current INTEGER NOT NULL DEFAULT 0,
  ammo_max INTEGER NOT NULL DEFAULT 0,
  luck_current INTEGER NOT NULL DEFAULT 0,
  luck_max INTEGER NOT NULL DEFAULT 0,
  move INTEGER NOT NULL DEFAULT 0,
  conditions_json TEXT NOT NULL DEFAULT '[]',
  injuries_json TEXT NOT NULL DEFAULT '[]',
  death_penalty INTEGER NOT NULL DEFAULT 0,
  visible INTEGER NOT NULL DEFAULT 1,
  secret_json TEXT NOT NULL DEFAULT '{}',
  sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS session_activity(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL,
  actor_user_id INTEGER NOT NULL,
  combatant_id INTEGER,
  event_type TEXT NOT NULL,
  before_json TEXT,
  after_json TEXT,
  note TEXT NOT NULL DEFAULT '',
  created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_character_ledger ON character_ledger(character_id,created);
CREATE INDEX IF NOT EXISTS idx_sessions_owner ON nc_sessions(owner_user_id,status,updated);
CREATE INDEX IF NOT EXISTS idx_session_access_user ON session_access(user_id,session_id);
CREATE INDEX IF NOT EXISTS idx_session_safety_open ON session_safety_signals(session_id,status,created);
CREATE INDEX IF NOT EXISTS idx_session_combatants ON session_combatants(session_id,sort_order);
CREATE INDEX IF NOT EXISTS idx_session_activity ON session_activity(session_id,created);
"""

ITEM_INSTANCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS item_instances(
  instance_id TEXT PRIMARY KEY,
  character_id INTEGER NOT NULL,
  catalog_item_id TEXT,
  bucket TEXT NOT NULL DEFAULT 'inventory',
  custom_name TEXT,
  state TEXT NOT NULL DEFAULT 'carried',
  quantity INTEGER NOT NULL DEFAULT 1,
  condition_current INTEGER,
  condition_max INTEGER,
  notes TEXT NOT NULL DEFAULT '',
  acquired_at REAL NOT NULL,
  source_type TEXT NOT NULL DEFAULT 'legacy_migration',
  source_ref TEXT,
  data_json TEXT NOT NULL DEFAULT '{}',
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_item_instances_character
  ON item_instances(character_id,bucket,state,acquired_at);
CREATE INDEX IF NOT EXISTS idx_item_instances_catalog
  ON item_instances(catalog_item_id,character_id);
"""

ACTIVE_EFFECT_SCHEMA = """
CREATE TABLE IF NOT EXISTS active_effect_instances(
  effect_id TEXT PRIMARY KEY,
  character_id INTEGER NOT NULL,
  source_type TEXT NOT NULL DEFAULT 'custom',
  source_item_instance_id TEXT,
  preset_id TEXT,
  label TEXT NOT NULL,
  definition_json TEXT NOT NULL,
  context_json TEXT NOT NULL DEFAULT '{}',
  duration_type TEXT NOT NULL DEFAULT 'manual',
  started_at REAL NOT NULL,
  expires_at REAL,
  remaining_rounds INTEGER,
  session_id INTEGER,
  active INTEGER NOT NULL DEFAULT 1,
  archived_at REAL,
  created_by INTEGER NOT NULL,
  reason TEXT NOT NULL DEFAULT '',
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_active_effects_character
  ON active_effect_instances(character_id,active,archived_at,expires_at);
CREATE INDEX IF NOT EXISTS idx_active_effects_session
  ON active_effect_instances(session_id,active,remaining_rounds);
"""

ITEM_MODIFICATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS item_modifications(
  modification_id TEXT PRIMARY KEY,
  character_id INTEGER NOT NULL,
  host_instance_id TEXT NOT NULL,
  upgrade_instance_id TEXT NOT NULL,
  host_type TEXT NOT NULL,
  slot_type TEXT NOT NULL DEFAULT 'attachment',
  slots_used INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1,
  permanent INTEGER NOT NULL DEFAULT 0,
  configuration_json TEXT NOT NULL DEFAULT '{}',
  notes TEXT NOT NULL DEFAULT '',
  source_type TEXT NOT NULL DEFAULT 'inventory',
  installed_by INTEGER NOT NULL,
  installed_at REAL NOT NULL,
  removed_by INTEGER,
  removed_at REAL,
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_item_modifications_host
  ON item_modifications(character_id,host_instance_id,active,installed_at);
CREATE INDEX IF NOT EXISTS idx_item_modifications_upgrade
  ON item_modifications(upgrade_instance_id,active);
CREATE UNIQUE INDEX IF NOT EXISTS idx_item_modifications_active_upgrade
  ON item_modifications(upgrade_instance_id) WHERE active=1;
"""

CAMPAIGN_CLOCK_SCHEMA = """
CREATE TABLE IF NOT EXISTS campaign_state(
  id INTEGER PRIMARY KEY CHECK (id = 1),
  campaign_time REAL NOT NULL,
  timezone TEXT NOT NULL DEFAULT 'Europe/Moscow',
  updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS campaign_clock_audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor_user_id INTEGER NOT NULL,
  delta_seconds REAL NOT NULL,
  before_time REAL NOT NULL,
  after_time REAL NOT NULL,
  reason TEXT NOT NULL,
  created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_campaign_clock_audit
  ON campaign_clock_audit(created);
"""

CREW_STASH_SCHEMA = """
CREATE TABLE IF NOT EXISTS crew_stash(
  instance_id TEXT PRIMARY KEY,
  catalog_item_id TEXT,
  custom_name TEXT,
  state TEXT NOT NULL DEFAULT 'stored',
  quantity INTEGER NOT NULL DEFAULT 1,
  notes TEXT NOT NULL DEFAULT '',
  stored_at REAL NOT NULL,
  data_json TEXT NOT NULL DEFAULT '{}',
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS personal_stash(
  instance_id TEXT PRIMARY KEY,
  character_id INTEGER NOT NULL,
  catalog_item_id TEXT,
  custom_name TEXT,
  state TEXT NOT NULL DEFAULT 'stored',
  quantity INTEGER NOT NULL DEFAULT 1,
  notes TEXT NOT NULL DEFAULT '',
  stored_at REAL NOT NULL,
  data_json TEXT NOT NULL DEFAULT '{}',
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_personal_stash_char ON personal_stash(character_id);
CREATE INDEX IF NOT EXISTS idx_crew_stash_stored ON crew_stash(stored_at);

CREATE TABLE IF NOT EXISTS item_transfers(
  transfer_id TEXT PRIMARY KEY,
  instance_id TEXT NOT NULL,
  from_character_id INTEGER,
  to_character_id INTEGER,
  from_bucket TEXT,
  to_bucket TEXT,
  quantity INTEGER NOT NULL DEFAULT 1,
  kind TEXT NOT NULL,
  actor_user_id INTEGER NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_item_transfers_instance ON item_transfers(instance_id, created);

CREATE TABLE IF NOT EXISTS item_loans(
  loan_id TEXT PRIMARY KEY,
  instance_id TEXT NOT NULL,
  owner_character_id INTEGER NOT NULL,
  borrower_character_id INTEGER NOT NULL,
  quantity INTEGER NOT NULL DEFAULT 1,
  loaned_by INTEGER NOT NULL,
  loaned_at REAL NOT NULL,
  returned_at REAL,
  returned_by INTEGER,
  notes TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_item_loans_owner ON item_loans(owner_character_id, returned_at);
CREATE INDEX IF NOT EXISTS idx_item_loans_borrower ON item_loans(borrower_character_id, returned_at);
"""

MARKET_STOCK_SCHEMA = """
CREATE TABLE IF NOT EXISTS market_stock(
  market_day TEXT NOT NULL,
  vendor_id TEXT NOT NULL,
  item_id TEXT NOT NULL,
  stock_initial INTEGER NOT NULL DEFAULT 0,
  stock_remaining INTEGER NOT NULL DEFAULT 0,
  reserved_character_id INTEGER,
  reserved_note TEXT NOT NULL DEFAULT '',
  created REAL NOT NULL,
  updated REAL NOT NULL,
  PRIMARY KEY(market_day, vendor_id, item_id)
);
CREATE INDEX IF NOT EXISTS idx_market_stock_day ON market_stock(market_day);

CREATE TABLE IF NOT EXISTS fixer_requests(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  character_id INTEGER NOT NULL,
  requested_by INTEGER NOT NULL,
  item_id TEXT,
  item_name TEXT NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending',
  created REAL NOT NULL,
  updated REAL NOT NULL,
  resolved_by INTEGER,
  resolved_at REAL,
  resolution_note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_fixer_requests_status ON fixer_requests(status, created);
"""

MARKET_PERMANENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS market_permanent(
  vendor_id TEXT NOT NULL,
  item_id TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created REAL NOT NULL,
  PRIMARY KEY (vendor_id, item_id)
);
"""

ORGANIZATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS persona_memberships(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  member_persona_id INTEGER NOT NULL,
  organization_persona_id INTEGER NOT NULL,
  role_title TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'active',
  visibility TEXT NOT NULL DEFAULT 'public',
  since_at REAL,
  until_at REAL,
  note TEXT NOT NULL DEFAULT '',
  sort_order INTEGER NOT NULL DEFAULT 0,
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memberships_member ON persona_memberships(member_persona_id);
CREATE INDEX IF NOT EXISTS idx_memberships_org ON persona_memberships(organization_persona_id);
CREATE TABLE IF NOT EXISTS crew_reputation(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  organization_persona_id INTEGER NOT NULL,
  reputation INTEGER NOT NULL DEFAULT 0,
  favor INTEGER NOT NULL DEFAULT 0,
  heat INTEGER NOT NULL DEFAULT 0,
  standing TEXT NOT NULL DEFAULT 'neutral',
  note TEXT NOT NULL DEFAULT '',
  created_by INTEGER,
  created REAL NOT NULL,
  updated REAL NOT NULL,
  UNIQUE(organization_persona_id)
);
CREATE TABLE IF NOT EXISTS character_reputation(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  character_id INTEGER NOT NULL,
  organization_persona_id INTEGER NOT NULL,
  reputation INTEGER NOT NULL DEFAULT 0,
  favor INTEGER NOT NULL DEFAULT 0,
  heat INTEGER NOT NULL DEFAULT 0,
  standing TEXT NOT NULL DEFAULT 'neutral',
  note TEXT NOT NULL DEFAULT '',
  created_by INTEGER,
  created REAL NOT NULL,
  updated REAL NOT NULL,
  UNIQUE(character_id, organization_persona_id)
);
"""

# Curated always-available base stock (20.10). Book price, no daily rotation,
# no finite stock. Sourced from docs/permanent-assortment.md.

SESSION_RECAP_SCHEMA = """
CREATE TABLE IF NOT EXISTS session_recaps(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_user_id INTEGER NOT NULL,
  session_id INTEGER,
  contract_id INTEGER,
  storyline_id INTEGER,
  session_date REAL NOT NULL,
  title TEXT NOT NULL,
  public_summary TEXT NOT NULL DEFAULT '',
  gm_notes TEXT NOT NULL DEFAULT '',
  participants_json TEXT NOT NULL DEFAULT '[]',
  choices_json TEXT NOT NULL DEFAULT '[]',
  npc_changes_json TEXT NOT NULL DEFAULT '[]',
  locations_json TEXT NOT NULL DEFAULT '[]',
  loot_json TEXT NOT NULL DEFAULT '[]',
  injuries_json TEXT NOT NULL DEFAULT '[]',
  quotes_json TEXT NOT NULL DEFAULT '[]',
  feed_post_id INTEGER,
  timeline_id INTEGER,
  published INTEGER NOT NULL DEFAULT 0,
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_session_recaps_date ON session_recaps(session_date);
CREATE INDEX IF NOT EXISTS idx_session_recaps_storyline ON session_recaps(storyline_id, session_date);
"""

LOCATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS locations(
  id TEXT PRIMARY KEY,
  name_en TEXT NOT NULL,
  name_ru TEXT NOT NULL DEFAULT '',
  kind TEXT NOT NULL DEFAULT 'other',
  district_id TEXT NOT NULL DEFAULT '',
  x REAL NOT NULL DEFAULT 500,
  y REAL NOT NULL DEFAULT 500,
  description_en TEXT NOT NULL DEFAULT '',
  description_ru TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT '',
  custom INTEGER NOT NULL DEFAULT 0,
  owner_user_id INTEGER,
  archived INTEGER NOT NULL DEFAULT 0,
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_locations_district ON locations(district_id, archived);
CREATE INDEX IF NOT EXISTS idx_locations_kind ON locations(kind, archived);
"""

MEMORIAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS memorials(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  character_id INTEGER,
  handle TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT '',
  role_rank INTEGER NOT NULL DEFAULT 0,
  portrait_media_id TEXT,
  status TEXT NOT NULL DEFAULT 'deceased',
  death_date REAL,
  location TEXT NOT NULL DEFAULT '',
  cause TEXT NOT NULL DEFAULT '',
  epitaph TEXT NOT NULL DEFAULT '',
  last_words TEXT NOT NULL DEFAULT '',
  obituary TEXT NOT NULL DEFAULT '',
  gm_notes TEXT NOT NULL DEFAULT '',
  visibility TEXT NOT NULL DEFAULT 'public',
  legacy_drink_name TEXT NOT NULL DEFAULT '',
  legacy_ingredients TEXT NOT NULL DEFAULT '',
  legacy_preparation TEXT NOT NULL DEFAULT '',
  legacy_glass TEXT NOT NULL DEFAULT '',
  legacy_garnish TEXT NOT NULL DEFAULT '',
  legacy_quote TEXT NOT NULL DEFAULT '',
  legacy_legend TEXT NOT NULL DEFAULT '',
  legacy_awarded_by INTEGER,
  legacy_awarded_at REAL,
  feed_post_id INTEGER,
  created_by INTEGER NOT NULL,
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memorials_status ON memorials(status, death_date);
"""

NOTIFICATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS notifications(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  link TEXT,
  read_at REAL,
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS vk_oauth_states(
  state TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  expires REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS vk_outbox(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_key TEXT UNIQUE NOT NULL,
  event_type TEXT NOT NULL,
  contract_id INTEGER,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  next_attempt_at REAL,
  last_error TEXT,
  created REAL NOT NULL,
  sent_at REAL
);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id,read_at,created);
CREATE INDEX IF NOT EXISTS idx_vk_outbox_pending ON vk_outbox(status,next_attempt_at);
"""

MIGRATION_ACCOUNT_ROLES = 1
MIGRATION_NETWORK_CORE = 2
MIGRATION_CITY_FEED = 3
MIGRATION_OPERATIONS = 4
MIGRATION_NOTIFICATIONS = 5
MIGRATION_TACTICAL_PROFILES = 6
MIGRATION_ITEM_INSTANCES = 7
MIGRATION_ACTIVE_EFFECTS = 8
MIGRATION_EFFECT_PRESETS = 9
MIGRATION_ITEM_MODIFICATIONS = 10
MIGRATION_SESSION_NET = 11
MIGRATION_CAMPAIGN_CLOCK = 12
MIGRATION_CREW_STASH = 13
MIGRATION_MARKET_STOCK = 14
MIGRATION_NPC_STATBLOCKS = 15
MIGRATION_SESSION_RECAPS = 16
MIGRATION_LOCATIONS = 17
MIGRATION_MEMORIAL = 18
MIGRATION_MEMORIAL_DRAFT = 19
MIGRATION_MARKET_PERMANENT = 20
MIGRATION_ORGANIZATIONS = 21
MIGRATION_FEED_SINGLE_FORMAT = 22
DB_BACKUP_LIMIT = 5
_RATE_LIMIT_BUCKETS = {}
_RATE_LIMIT_LOCK = threading.Lock()


def enforce_rate_limit(identifier, limit, window):
    now = time.time()
    with _RATE_LIMIT_LOCK:
        bucket = [stamp for stamp in _RATE_LIMIT_BUCKETS.get(identifier, []) if stamp > now - window]
        if len(bucket) >= limit:
            raise ApiError(429, 'Слишком много запросов; попробуйте позже')
        bucket.append(now)
        _RATE_LIMIT_BUCKETS[identifier] = bucket


# Per-account login throttle: mitigates distributed brute-force that bypasses
# the IP-level limit. Only failed attempts are counted; a successful login
# clears the counter. In-memory (resets on restart), like the IP limiter.
FAILED_LOGIN_LIMIT = 8
FAILED_LOGIN_WINDOW = 900  # 15 minutes


def _failed_login_bucket(username):
    now = time.time()
    key = f'login-user:{username}'
    with _RATE_LIMIT_LOCK:
        bucket = [stamp for stamp in _RATE_LIMIT_BUCKETS.get(key, [])
                  if stamp > now - FAILED_LOGIN_WINDOW]
        _RATE_LIMIT_BUCKETS[key] = bucket
        return bucket


def account_login_locked(username):
    return len(_failed_login_bucket(username)) >= FAILED_LOGIN_LIMIT


def record_failed_login(username):
    bucket = _failed_login_bucket(username)
    bucket.append(time.time())


def clear_failed_logins(username):
    with _RATE_LIMIT_LOCK:
        _RATE_LIMIT_BUCKETS.pop(f'login-user:{username}', None)
        if len(_RATE_LIMIT_BUCKETS) > 5000:
            for key in list(_RATE_LIMIT_BUCKETS)[:1000]:
                if not _RATE_LIMIT_BUCKETS[key] or _RATE_LIMIT_BUCKETS[key][-1] <= now - 3600:
                    _RATE_LIMIT_BUCKETS.pop(key, None)


def configured_admin_usernames():
    raw = os.environ.get('CBPR_ADMIN_USERS', '')
    return {part.strip().lower() for part in raw.split(',') if part.strip()}


def backup_tools_module():
    if BASE not in sys.path:
        sys.path.insert(0, BASE)
    import backup as tools
    return tools


def backup_retention():
    try:
        return max(1, min(365, int(os.environ.get('CBPR_BACKUP_RETENTION', '14'))))
    except (TypeError, ValueError):
        return 14


def backup_database(conn, label):
    """Create a bounded SQLite backup before a destructive-capable schema migration."""
    if not os.path.isfile(DB_PATH) or os.path.getsize(DB_PATH) == 0:
        return None
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    path = f'{DB_PATH}.backup-{label}-{stamp}'
    target = sqlite3.connect(path)
    try:
        conn.backup(target)
    finally:
        target.close()
    prefix = os.path.basename(DB_PATH) + '.backup-'
    backups = sorted(
        (os.path.join(os.path.dirname(DB_PATH), name)
         for name in os.listdir(os.path.dirname(DB_PATH) or '.')
         if name.startswith(prefix)),
        key=os.path.getmtime,
        reverse=True,
    )
    for stale in backups[DB_BACKUP_LIMIT:]:
        try:
            os.remove(stale)
        except FileNotFoundError:
            pass
    return path


def ensure_column(conn, table, name, definition):
    columns = {row['name'] for row in conn.execute(f'PRAGMA table_info({table})')}
    if name not in columns:
        conn.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')


# ITEM_INSTANCE_STATES переехала в core.py (итерация P1-2)


def cyberdeck_profile_for_host(host):
    catalog_id = catalog_item_id_for_entry(host)
    return copy.deepcopy(CYBERDECK_PROFILES.get(catalog_id) or {})


def cyberdeck_program_category(item):
    program_class = str((item.get('mechanics') or {}).get('program_class') or '')
    if 'Black ICE' in program_class:
        return 'black_ice'
    if 'Attacker' in program_class:
        return 'attacker'
    if 'Defender' in program_class:
        return 'defender'
    if 'Booster' in program_class:
        return 'booster'
    return 'program'


def cyberdeck_slot_usage(host, active_modifications=None, owned_by_id=None):
    active_modifications = active_modifications or []
    owned_by_id = owned_by_id or {}
    capacities = cyberdeck_profile_for_host(host)
    installed = [owned_by_id.get(mod.get('upgrade_instance_id')) or {}
                 for mod in active_modifications if mod.get('active', True)]
    hardware = [item for item in installed
                if item.get('modification_kind') == 'cyberdeck_hardware']
    programs = [item for item in installed
                if item.get('modification_kind') == 'cyberdeck_program']
    perfume_shoppe = any(item.get('name') == 'Perfume Shoppe' for item in hardware)
    hardware_units = sum(max(1, int(item.get('slots_used') or 1)) for item in hardware)
    program_units = 0
    flak_units = 0
    program_weights = []
    for item in programs:
        weight = max(1, int(item.get('slots_used') or 1))
        if perfume_shoppe and item.get('name') == 'Skunk':
            weight = 1
        program_weights.append({'instance_id': item.get('instance_id'),
                                'name': item.get('name'), 'slots': weight})
        program_units += weight
        if item.get('name') == 'Flak':
            flak_units += weight
    flak_used = min(capacities.get('flak', 0), flak_units)
    remaining_program = max(0, program_units - flak_used)
    program_used = min(capacities.get('program', 0), remaining_program)
    remaining_program -= program_used
    hardware_used = min(capacities.get('hardware', 0), hardware_units)
    remaining_hardware = max(0, hardware_units - hardware_used)
    mixed_used = remaining_program + remaining_hardware
    pools = {
        'program': {'total': capacities.get('program', 0), 'used': program_used},
        'hardware': {'total': capacities.get('hardware', 0), 'used': hardware_used},
        'mixed': {'total': capacities.get('mixed', 0), 'used': mixed_used},
        'flak': {'total': capacities.get('flak', 0), 'used': flak_used},
    }
    pools = {key: value for key, value in pools.items()
             if value['total'] or value['used']}
    overloaded = any(pool['used'] > pool['total'] for pool in pools.values())
    return {
        'pools': pools, 'overloaded': overloaded,
        'slots_total': sum(capacities.values()),
        'slots_used': hardware_units + program_units,
        'hardware_units': hardware_units, 'program_units': program_units,
        'program_weights': program_weights,
    }


def cyberdeck_item_compatibility(host, upgrade, active_modifications=None,
                                 owned_by_id=None):
    active_modifications = active_modifications or []
    owned_by_id = owned_by_id or {}
    reasons = []
    host_catalog = item_by_id(catalog_item_id_for_entry(host)) or {}
    if (host.get('cat') != 'net_stuff' or
            (host_catalog.get('mechanics') or {}).get('type') != 'Cyberdeck'):
        reasons.append('Host is not a Cyberdeck')
    if upgrade.get('host_type') != 'cyberdeck':
        reasons.append('Item is not Cyberdeck Hardware or a Program')
    installed = [owned_by_id.get(mod.get('upgrade_instance_id')) or {}
                 for mod in active_modifications]
    if upgrade.get('unique_per_host') and any(
            catalog_item_id_for_entry(item) == catalog_item_id_for_entry(upgrade)
            for item in installed):
        reasons.append('Only one effective copy may be installed on this Cyberdeck')
    deck_id = catalog_item_id_for_entry(host)
    name = str(upgrade.get('name') or '')
    kind = upgrade.get('modification_kind')
    category = cyberdeck_program_category(upgrade)
    if kind == 'cyberdeck_program':
        if deck_id == 'net_stuff-4':
            if sum(cyberdeck_program_category(item) == category for item in installed) >= 1:
                reasons.append('Kirama Entry Deck allows only one Program of each Class')
        elif deck_id == 'net_stuff-6' and category != 'black_ice':
            reasons.append('Microtech Assault Program slots accept only Black ICE')
        elif deck_id == 'net_stuff-12' and name != 'Hellhound':
            reasons.append('Kerberos Program slots accept only Hellhound')
        elif deck_id == 'net_stuff-13' and name not in ('Sword', 'Shield'):
            reasons.append('Verdant Knight accepts only Sword and Shield Programs')
        elif deck_id == 'net_stuff-14' and category in ('attacker', 'black_ice'):
            reasons.append("Warlock's Book cannot install Attacker or Black ICE Programs")
        elif deck_id == 'net_stuff-15':
            if category == 'defender' and name != 'Flak':
                reasons.append('Zetatech Kaliya accepts no Defender other than Flak')
            if category == 'black_ice' and name != 'Asp':
                reasons.append('Zetatech Kaliya accepts no Black ICE other than Asp')
        elif deck_id == 'net_stuff-16' and category == 'defender':
            reasons.append('Zetatech MicroMate cannot install Defender Programs')
        if (category == 'black_ice' and name != 'Wisp' and
                any(item.get('name') == 'Swamp Mist' for item in installed)):
            reasons.append('Swamp Mist permits only Wisp Black ICE')
    elif kind == 'cyberdeck_hardware':
        if name == 'Swamp Mist' and any(
                cyberdeck_program_category(item) == 'black_ice' and
                item.get('name') != 'Wisp' for item in installed):
            reasons.append('Remove non-Wisp Black ICE before installing Swamp Mist')
    candidate_id = str(upgrade.get('instance_id') or 'candidate')
    candidate_mod = {
        'modification_id': f'candidate:{candidate_id}', 'active': True,
        'host_instance_id': host.get('instance_id'),
        'upgrade_instance_id': upgrade.get('instance_id'),
    }
    candidate_owned = dict(owned_by_id)
    if upgrade.get('instance_id'):
        candidate_owned[upgrade['instance_id']] = upgrade
    usage = cyberdeck_slot_usage(
        host, [*active_modifications, candidate_mod], candidate_owned)
    if usage['overloaded']:
        reasons.append('Not enough compatible Cyberdeck slots')
    return {
        'allowed': not reasons, 'reasons': reasons,
        'manual_resolution_required': False,
        'slot_pools': usage['pools'], 'slots_total': usage['slots_total'],
        'slots_used_after': usage['slots_used'],
        'slots_required': max(1, int(upgrade.get('slots_used') or 1)),
        'item_kind': kind,
    }


PROGRAM_RUNTIME_STATUSES = {'inactive', 'rezzed', 'derezzed', 'destroyed'}


def queue_defense_sequencer_trigger(data, modifications, deck_instance_id,
                                     source_program_instance_id):
    owned = {item.get('instance_id'): item for item in data.get('inventory') or []
             if isinstance(item, dict) and item.get('instance_id')}
    source_program = owned.get(source_program_instance_id) or {}
    if source_program.get('name') != 'Armor':
        return 0
    sequencers = [mod for mod in modifications
                  if mod.get('host_instance_id') == deck_instance_id and
                  (owned.get(mod.get('upgrade_instance_id')) or {}).get('name') ==
                  'Defense Sequencer']
    eligible = [
        item.get('instance_id') for mod in modifications
        for item in [owned.get(mod.get('upgrade_instance_id')) or {}]
        if mod.get('host_instance_id') == deck_instance_id and
        item.get('name') == 'Armor' and item.get('instance_id') != source_program_instance_id and
        ((data.get('program_state') or {}).get(item.get('instance_id')) or {}).get(
            'status', 'inactive') == 'inactive']
    if not sequencers or not eligible:
        return 0
    for sequencer in sequencers:
        data.setdefault('modification_state', {})[sequencer['modification_id']] = {
            'resource_type': 'defense_sequencer',
            'pending_armor_rez': True,
            'trigger_program_instance_id': source_program_instance_id,
            'eligible_armor_instance_ids': eligible,
            'manual_eligibility_required': True,
            'source': 'DL:Up 5 / IR3 41',
        }
    return len(eligible)


def resolve_defense_sequencer_trigger(data, modifications, deck_instance_id,
                                      hardware_instance_id, armor_instance_id,
                                      now=None):
    """Resolve a pending Defense Sequencer after explicit table eligibility proof."""
    now = time.time() if now is None else now
    owned = {item.get('instance_id'): item for item in data.get('inventory') or []
             if isinstance(item, dict) and item.get('instance_id')}
    sequencer_modification = next((
        mod for mod in modifications
        if mod.get('host_instance_id') == deck_instance_id and
        mod.get('upgrade_instance_id') == hardware_instance_id and
        (owned.get(hardware_instance_id) or {}).get('name') == 'Defense Sequencer'), None)
    if not sequencer_modification:
        raise ApiError(404, 'Installed Defense Sequencer не найден')
    sequencer_state = (data.get('modification_state') or {}).get(
        sequencer_modification['modification_id']) or {}
    if (sequencer_state.get('resource_type') != 'defense_sequencer' or
            not sequencer_state.get('pending_armor_rez')):
        raise ApiError(409, 'Defense Sequencer не имеет pending Armor trigger')
    eligible_ids = [str(item) for item in
                    sequencer_state.get('eligible_armor_instance_ids') or []]
    if armor_instance_id not in eligible_ids:
        raise ApiError(409, 'Выбранная Armor не входит в pending eligibility snapshot')
    armor = owned.get(armor_instance_id)
    armor_modification = next((
        mod for mod in modifications
        if mod.get('host_instance_id') == deck_instance_id and
        mod.get('upgrade_instance_id') == armor_instance_id and
        (armor or {}).get('name') == 'Armor'), None)
    if not armor or not armor_modification:
        raise ApiError(409, 'Eligible Armor больше не установлена в этом Cyberdeck')
    runtime = initial_program_runtime_state(
        armor, deck_instance_id, armor_modification['modification_id'],
        (data.get('program_state') or {}).get(armor_instance_id))
    if runtime['status'] != 'inactive':
        raise ApiError(409, 'Defense Sequencer может Rez только inactive Armor')
    for program_id, existing in (data.get('program_state') or {}).items():
        if program_id == armor_instance_id or not isinstance(existing, dict):
            continue
        other = owned.get(program_id) or {}
        if other.get('name') == 'Armor' and existing.get('status') == 'rezzed':
            raise ApiError(409, 'Другая копия Armor уже Rezzed')
    runtime['status'] = 'rezzed'
    runtime['rez_current'] = runtime['rez_max']
    data.setdefault('program_state', {})[armor_instance_id] = runtime
    data.setdefault('modification_state', {})[
        sequencer_modification['modification_id']] = {
            'resource_type': 'defense_sequencer',
            'pending_armor_rez': False,
            'resolved_armor_instance_id': armor_instance_id,
            'trigger_program_instance_id': sequencer_state.get(
                'trigger_program_instance_id'),
            'manual_eligibility_confirmed': True,
            'resolved_at': now,
            'source': sequencer_state.get('source') or 'DL:Up 5 / IR3 41',
        }
    return {
        'armor_instance_id': armor_instance_id,
        'armor_name': armor.get('custom_name') or armor.get('name') or 'Armor',
        'rez_current': runtime['rez_current'], 'rez_max': runtime['rez_max'],
        'manual_eligibility_confirmed': True,
    }


def initial_program_runtime_state(item, deck_instance_id, modification_id, existing=None):
    existing = existing if isinstance(existing, dict) else {}
    category = cyberdeck_program_category(item)
    maximum = max(0, int(_num((item.get('mechanics') or {}).get('rez')) or 0))
    status = str(existing.get('status') or 'inactive')
    if status not in PROGRAM_RUNTIME_STATUSES or status == 'destroyed':
        status = 'inactive'
    current = _num(existing.get('rez_current'))
    if category in ('booster', 'defender', 'black_ice'):
        current = max(0, min(maximum,
                             int(current if current is not None else maximum)))
    else:
        current = 0
    return {
        'program_instance_id': item.get('instance_id'),
        'catalog_item_id': catalog_item_id_for_entry(item),
        'deck_instance_id': deck_instance_id,
        'modification_id': modification_id,
        'category': category, 'status': status,
        'rez_current': current, 'rez_max': maximum,
        'run_count': max(0, int(_num(existing.get('run_count')) or 0)),
        'last_run_at': existing.get('last_run_at'),
    }


NET_ENTITY_STATUSES = {
    'lying_in_wait', 'hunting', 'derezzed', 'deactivated', 'destroyed',
}


BLACK_ICE_ANTI_PROGRAM_DAMAGE = {
    'Dragon': 6, 'Killer': 4, 'Sabertooth': 6,
}
ATTACKER_PROGRAM_BLACK_ICE_DAMAGE = {'Sword': 3, 'Banhammer': 2}
BLACK_ICE_STAT_EFFECT_TARGETS = {
    'Liche': ('INT', 'REF', 'DEX'),
    'Scorpion': ('MOVE',),
}


def black_ice_effect_profile(item):
    catalog_item = item_by_id(catalog_item_id_for_entry(item)) or item or {}
    name = str(catalog_item.get('name') or '')
    dice = BLACK_ICE_ANTI_PROGRAM_DAMAGE.get(name)
    if name == 'Asp':
        resolution = 'automated_random_destroy'
    elif name == 'Raven':
        resolution = 'automated_random_derez_plus_manual'
    elif name in BLACK_ICE_STAT_EFFECT_TARGETS:
        resolution = 'automated_stat_penalty'
    else:
        resolution = 'automated_rez_damage' if dice else 'manual_effect'
    return {
        'resolution': resolution,
        'damage_dice': dice, 'damage_sides': 6 if dice else None,
        'destroy_on_derez': bool(dice),
        'source': catalog_item.get('source'),
        'manual_effect': '' if resolution == 'automated_stat_penalty' else
            str(catalog_item.get('desc') or '')[:2000],
    }


def instantiate_black_ice_stat_effects(conn, character_id, actor_user_id,
                                       source_program, session_id, now=None,
                                       penalty_roll=None):
    """Create allowlisted one-hour STAT penalties for Liche or Scorpion.

    The duration uses the existing campaign-time/manual-clock lifecycle: the
    numerical penalty is authoritative immediately, while advancing the one-hour
    campaign clock remains an explicit table action.
    """
    now = time.time() if now is None else now
    catalog_item = item_by_id(catalog_item_id_for_entry(source_program)) or source_program or {}
    name = str(catalog_item.get('name') or '')
    targets = BLACK_ICE_STAT_EFFECT_TARGETS.get(name)
    if not targets:
        raise ApiError(409, 'Black ICE не имеет curated STAT effect')
    if penalty_roll is None:
        penalty_roll = secrets.randbelow(6) + 1
    if (not isinstance(penalty_roll, int) or isinstance(penalty_roll, bool) or
            not 1 <= penalty_roll <= 6):
        raise ApiError(400, 'Black ICE STAT penalty roll должен быть от 1 до 6')
    effect_group_id = secrets.token_hex(16)
    created = []
    for stat in targets:
        effect_id = secrets.token_hex(16)
        definition = {
            'id': f'black-ice-{name.lower()}-{effect_id}',
            'target': f'character.stat.{stat}',
            'operation': 'add', 'value': -penalty_roll,
            'minimum_value': 1,
            'stack_group': f'black_ice_{name.lower()}_{effect_group_id}_{stat.lower()}',
            'stack_policy': 'stack', 'priority': 400,
            'source': str(catalog_item.get('source') or 'CP:R 371')[:120],
        }
        validate_effect_definition(definition)
        label = f'{name}: {stat} −{penalty_roll}'
        context = {
            'effect_group_id': effect_group_id,
            'automated_effect': True,
            'manual_expiry': True,
            'campaign_minutes': 60,
            'campaign_clock_manual': True,
            'penalty_roll': penalty_roll,
            'minimum_stat': 1,
            'source_program_instance_id': source_program.get('instance_id'),
            'source_catalog_item_id': catalog_item_id_for_entry(source_program),
            'source': catalog_item.get('source') or 'CP:R 371',
        }
        conn.execute(
            'INSERT INTO active_effect_instances(effect_id,character_id,source_type,'
            'source_item_instance_id,preset_id,label,definition_json,context_json,'
            'duration_type,started_at,session_id,active,created_by,reason,created,updated) '
            'VALUES(?,?,?,?,?,?,?,?,?,?,?,1,?,?,?,?)',
            (effect_id, int(character_id), 'black_ice',
             source_program.get('instance_id'),
             f'black-ice-{name.lower()}-stat-penalty', label,
             json.dumps(definition, ensure_ascii=False),
             json.dumps(context, ensure_ascii=False), 'campaign_time', now,
             int(session_id), int(actor_user_id),
             f'Automated {name} effect · manual 1-hour campaign expiry', now, now))
        row = conn.execute(
            'SELECT e.*,u.display_name actor FROM active_effect_instances e '
            'JOIN users u ON u.id=e.created_by WHERE e.effect_id=?',
            (effect_id,)).fetchone()
        created.append(effect_instance_payload(row, now))
    return {
        'name': name, 'penalty_roll': penalty_roll,
        'targets': list(targets), 'created': created,
        'effect_group_id': effect_group_id,
    }


def roll_dice(count, sides=6):
    count = max(0, min(100, int(count or 0)))
    sides = max(2, min(100, int(sides or 6)))
    rolls = [secrets.randbelow(sides) + 1 for _ in range(count)]
    return {'rolls': rolls, 'total': sum(rolls)}


def black_ice_target_type(item):
    program_class = str((item.get('mechanics') or {}).get('program_class') or '')
    return 'enemy_program_source' if 'Anti Program Black ICE' in program_class \
        else 'enemy_netrunner'


def active_black_ice_entity(character, program_instance_id):
    entities = character.get('net_entities') or {}
    return next((copy.deepcopy(entity) for entity in entities.values()
                 if isinstance(entity, dict) and
                 entity.get('source_program_instance_id') == program_instance_id and
                 entity.get('status') in ('lying_in_wait', 'hunting', 'derezzed')), None)


def initial_black_ice_entity(item, deck_instance_id, character_id, mode,
                             floor_label, target_label=None):
    mechanics = item.get('mechanics') or {}
    maximum = max(1, int(_num(mechanics.get('rez')) or 1))
    status = 'lying_in_wait' if mode == 'lie_in_wait' else 'hunting'
    roll = secrets.randbelow(10) + 1 if status == 'hunting' else None
    speed = max(0, int(_num(mechanics.get('spd')) or 0))
    return {
        'net_entity_id': secrets.token_hex(16),
        'source_program_instance_id': item.get('instance_id'),
        'deck_instance_id': deck_instance_id,
        'owner_character_id': int(character_id),
        'type': 'black_ice', 'name': item.get('custom_name') or item.get('name'),
        'program_class': mechanics.get('program_class'),
        'target_type': black_ice_target_type(item),
        'floor_label': floor_label,
        'target_label': target_label if status == 'hunting' else None,
        'per': max(0, int(_num(mechanics.get('per')) or 0)),
        'spd': speed, 'atk': max(0, int(_num(mechanics.get('atk')) or 0)),
        'def': max(0, int(_num(mechanics.get('def')) or 0)),
        'rez_current': maximum, 'rez_max': maximum,
        'initiative_roll': roll,
        'initiative': speed + roll if roll is not None else None,
        'status': status, 'activated_at': time.time(),
        'updated_at': time.time(), 'archived_at': None,
        'manual_resolution_required': True,
    }


def evaluate_effective_cyberdeck(host, modifications, owned_by_id, character=None):
    character = character or {}
    usage = cyberdeck_slot_usage(host, modifications, owned_by_id)
    hardware = []
    programs = []
    for modification in modifications:
        item = owned_by_id.get(modification.get('upgrade_instance_id')) or {}
        payload = {
            'modification_id': modification.get('modification_id'),
            'instance_id': item.get('instance_id'),
            'catalog_item_id': catalog_item_id_for_entry(item),
            'name': item.get('custom_name') or item.get('name'),
            'slots': next((row['slots'] for row in usage['program_weights']
                           if row['instance_id'] == item.get('instance_id')),
                          max(1, int(item.get('slots_used') or 1))),
            'source': item.get('source'),
            'manual_resolution_required': True,
        }
        if item.get('modification_kind') == 'cyberdeck_hardware':
            hardware_state = copy.deepcopy((character.get('modification_state') or {}).get(
                modification.get('modification_id')) or {})
            if hardware_state:
                payload['runtime_state'] = hardware_state
                if (item.get('name') == 'Defense Sequencer' and
                        hardware_state.get('pending_armor_rez')):
                    payload['eligible_armor_programs'] = [
                        {
                            'instance_id': program_id,
                            'name': (owned_by_id.get(program_id) or {}).get(
                                'custom_name') or (owned_by_id.get(program_id) or {}).get(
                                'name') or 'Armor',
                        }
                        for program_id in
                        hardware_state.get('eligible_armor_instance_ids') or []
                        if program_id in owned_by_id]
            if item.get('name') == 'Backup Drive':
                payload['backup_state'] = hardware_state or {
                    'resource_type': 'backup_drive', 'saved_programs': []}
            hardware.append(payload)
        elif item.get('modification_kind') == 'cyberdeck_program':
            payload['program_class'] = (item.get('mechanics') or {}).get('program_class')
            payload['mechanics'] = copy.deepcopy(item.get('mechanics') or {})
            payload['runtime'] = initial_program_runtime_state(
                item, host.get('instance_id'), modification.get('modification_id'),
                (character.get('program_state') or {}).get(item.get('instance_id')))
            if cyberdeck_program_category(item) == 'black_ice':
                payload['net_entity'] = active_black_ice_entity(
                    character, item.get('instance_id'))
            programs.append(payload)
    return {
        'instance_id': host.get('instance_id'),
        'profile': cyberdeck_profile_for_host(host),
        **usage, 'hardware': hardware, 'programs': programs,
    }


def character_effective_cyberdecks(character, modifications):
    owned = {item.get('instance_id'): item for item in character.get('inventory') or []
             if isinstance(item, dict) and item.get('instance_id')}
    result = {}
    for host in (item for item in character.get('inventory') or []
                 if isinstance(item, dict) and item.get('cat') == 'net_stuff' and
                 (item.get('mechanics') or {}).get('type') == 'Cyberdeck'):
        host_modifications = [mod for mod in modifications
                              if mod.get('host_instance_id') == host.get('instance_id')]
        result[host['instance_id']] = evaluate_effective_cyberdeck(
            host, host_modifications, owned, character)
    return result


def vehicle_classification(host):
    name = str(host.get('name') or '').lower()
    catalog_item = item_by_id(catalog_item_id_for_entry(host)) or {}
    description = str(catalog_item.get('desc') or '').lower()
    combined = f'{name} {description}'
    if name == 'bicycle' or 'bicycle' in name:
        return {'bicycle', 'bike', 'land'}
    if 'bike' in name or 'motorcycle' in name:
        return {'bike', 'land'}
    if 'jetski' in name:
        return {'jetski', 'sea'}
    if 'gyrocopter' in name:
        return {'gyrocopter', 'air'}
    if 'cabin cruiser' in combined:
        return {'sea', 'rooms', 'cabin_cruiser'}
    if 'yacht' in combined:
        return {'sea', 'rooms', 'yacht'}
    if 'aerozep' in combined:
        return {'air', 'rooms', 'aerozep'}
    if 'av-4' in combined:
        return {'air', 'av4'}
    if any(token in name for token in ('speedboat', 'boat', 'submarine')):
        return {'sea'}
    if any(token in name for token in ('helicopter', 'aerodyne', 'av-')):
        return {'air'}
    return {'land', 'groundcar'}


VEHICLE_REPAIR_RULES = {
    'minor': {'dv': 9, 'duration_key': '3_hours', 'duration_en': '3 hours',
              'duration_ru': '3 часа'},
    'major': {'dv': 13, 'duration_key': '1_day', 'duration_en': '1 day',
              'duration_ru': '1 день'},
    'destroyed': {'dv': 17, 'duration_key': '1_week', 'duration_en': '1 week',
                  'duration_ru': '1 неделя'},
}


def vehicle_repair_severity(current, maximum):
    current = max(0, _num(current) or 0)
    maximum = max(0, _num(maximum) or 0)
    if current <= 0:
        return 'destroyed'
    if current < maximum / 2:
        return 'major'
    return 'minor'


def vehicle_repair_skill(host):
    classes = vehicle_classification(host)
    if 'bicycle' in classes:
        return 'Basic Tech'
    if 'air' in classes:
        return 'Air Vehicle Tech'
    if 'sea' in classes:
        return 'Sea Vehicle Tech'
    return 'Land Vehicle Tech'


def character_nomad_rank(character):
    return max([_num(role.get('rank')) or 0 for role in character.get('roles') or []
                if isinstance(role, dict) and role.get('name') == 'Nomad'] or [0])


def vehicle_interior_capacity_for_compatibility(host, active_modifications, owned_by_id):
    interior = vehicle_base_interior(host)
    installed = [owned_by_id.get(mod.get('upgrade_instance_id')) or {}
                 for mod in active_modifications]
    names = [str(item.get('name') or '') for item in installed]
    has_housing = any(name == 'Housing Capacity' for name in names)
    if has_housing:
        interior['rooms_total'] += 1
        if not interior['base_rooms']:
            interior['rooms_total'] = 1
            interior['kombi'] = True
    interior['luxury_rooms'] = sum(name == 'Luxury Vehicle Room' for name in names)
    interior['complex_rooms'] = sum(name == 'Complex Vehicle Room' for name in names)
    interior['upgraded_rooms'] = interior['luxury_rooms'] + interior['complex_rooms']
    interior['has_housing'] = has_housing
    return interior


def vehicle_upgrade_compatibility(host, upgrade, active_modifications=None,
                                  owned_by_id=None, character=None):
    active_modifications = active_modifications or []
    owned_by_id = owned_by_id or {}
    character = character or {}
    reasons = []
    manual = bool(upgrade.get('compatibility_manual'))
    if host.get('cat') != 'vehicles':
        reasons.append('Host is not a vehicle')
    if upgrade.get('cat') != 'vehicles_upgrades' or upgrade.get('host_type') != 'vehicle':
        reasons.append('Item is not a vehicle upgrade')
    classes = vehicle_classification(host)
    availability = str(upgrade.get('availability_text') or '').strip()
    low = availability.lower()
    if 'except bikes, jetskis, gyrocopters' in low:
        if classes & {'bike', 'jetski', 'gyrocopter'}:
            reasons.append('Unavailable for Bikes, Jetskis, or Gyrocopters')
    elif 'all land and sea vehicles except bikes and jetski' in low:
        if not classes & {'land', 'sea'} or classes & {'bike', 'jetski'}:
            reasons.append('Requires a non-Bike Land or Sea vehicle')
    elif low == 'all land and sea vehicles' and not classes & {'land', 'sea'}:
        reasons.append('Requires a Land or Sea vehicle')
    elif low == 'all land vehicles' and 'land' not in classes:
        reasons.append('Requires a Land vehicle')
    elif low == 'all bikes' and 'bike' not in classes:
        reasons.append('Requires a Bike')
    elif low in ('all groundcars', 'all groundcards') and 'groundcar' not in classes:
        reasons.append('Requires a Groundcar')
    elif low == 'bicycle' and 'bicycle' not in classes:
        reasons.append('Requires a Bicycle')
    elif low not in ('', 'all vehicles') and ',' in availability and not any(
            (token.strip().lower() in str(host.get('name') or '').lower() or
             (token.strip().lower() == 'groundcars' and 'groundcar' in classes))
            for token in availability.split(',')):
        reasons.append('Vehicle is not in the named availability list')
    elif low == 'vehicles with rooms':
        interior_capacity = vehicle_interior_capacity_for_compatibility(
            host, active_modifications, owned_by_id)
        if interior_capacity['rooms_total'] <= 0:
            reasons.append('Requires a vehicle with at least one room')
    elif low not in ('', 'all vehicles') and not any(token in low for token in (
            'except bikes', 'land and sea', 'land vehicles', 'all bikes',
            'groundcar', 'bicycle', ',')):
        if low not in str(host.get('name') or '').lower():
            reasons.append('Vehicle does not match named availability')

    installed_upgrades = [owned_by_id.get(mod.get('upgrade_instance_id')) or {}
                          for mod in active_modifications]
    installed_names = {str(item.get('name') or '') for item in installed_upgrades}
    has_named_upgrade = lambda expected: any(
        name == expected or name.startswith(expected + ' (') for name in installed_names)
    prerequisite_host_names = upgrade.get('prerequisite_host_names') or {}
    for prerequisite in upgrade.get('prerequisite_upgrades') or []:
        host_names = prerequisite_host_names.get(prerequisite) or []
        applies = not host_names or str(host.get('name') or '') in host_names
        if applies and not has_named_upgrade(prerequisite):
            reasons.append(f'Requires installed {prerequisite}')
    for conflict in upgrade.get('conflicting_upgrades') or []:
        if has_named_upgrade(conflict):
            reasons.append(f'Conflicts with installed {conflict}')
    same_count = sum(1 for item in installed_upgrades
                     if catalog_item_id_for_entry(item) == catalog_item_id_for_entry(upgrade))
    repeatable_max = max(1, int(upgrade.get('repeatable_max') or 1))
    if same_count >= repeatable_max:
        reasons.append(f'Upgrade limit reached ({same_count}/{repeatable_max})')

    upgrade_name = str(upgrade.get('name') or '')
    interior_capacity = vehicle_interior_capacity_for_compatibility(
        host, active_modifications, owned_by_id)
    if upgrade_name in ('Luxury Vehicle Room', 'Complex Vehicle Room'):
        if interior_capacity['upgraded_rooms'] >= interior_capacity['rooms_total']:
            reasons.append('All vehicle rooms already have a room upgrade')
    if upgrade_name == 'Vehicle Heavy Weapon Mount':
        if same_count >= 1:
            multiple_allowed = bool(
                classes & {'cabin_cruiser', 'yacht', 'aerozep'} or
                ('groundcar' in classes and interior_capacity['has_housing']))
            if not multiple_allowed:
                reasons.append(
                    'Additional Heavy Weapon Mounts require a room vehicle or a Housing Groundcar')
        base_seats = _num((host.get('mechanics') or {}).get('seats'))
        seating_upgrades = sum(name == 'Seating Upgrade' for name in installed_names)
        if base_seats is not None:
            available_seats = int(base_seats) + seating_upgrades * 2 - same_count
        else:
            available_seats = (
                interior_capacity['rooms_total'] * interior_capacity['seats_per_room'] +
                interior_capacity['complex_rooms'] *
                interior_capacity['seats_per_room'] * 2 - same_count)
        if available_seats <= 0:
            reasons.append('Vehicle has no seat available for another Heavy Weapon Mount')

    access_required = _num(upgrade.get('nomad_access_required'))
    nomad_rank = character_nomad_rank(character)
    role_access = upgrade.get('acquisition_source') == 'role_access'
    access_met = not role_access or access_required is None or nomad_rank >= access_required
    if not access_met:
        reasons.append(f'Nomad Access {access_required} requires Nomad Rank {access_required}')
    return {
        'allowed': not reasons,
        'manual_resolution_required': manual,
        'reasons': reasons,
        'availability_text': availability,
        'nomad_access_required': access_required,
        'nomad_rank': nomad_rank,
        'role_access_item': role_access,
        'nomad_access_met': access_met,
        'repeatable_max': repeatable_max,
        'installed_count': same_count,
        'prerequisite_upgrades': copy.deepcopy(upgrade.get('prerequisite_upgrades') or []),
        'conflicting_upgrades': copy.deepcopy(upgrade.get('conflicting_upgrades') or []),
    }


def validate_active_modification_references(conn, character_id, data):
    owned = {entry.get('instance_id'): entry for bucket in ('inventory', 'cyberware')
             for entry in data.get(bucket) or [] if isinstance(entry, dict) and entry.get('instance_id')}
    modifications = character_modifications(conn, character_id)
    modification_by_id = {item['modification_id']: item for item in modifications}
    bound_weapon_ids = set()
    states = data.get('modification_state') or {}
    for modification in modifications:
        host = owned.get(modification['host_instance_id'])
        upgrade = owned.get(modification['upgrade_instance_id'])
        if not host or not upgrade:
            raise ApiError(409, 'Сначала снимите установленные модификации')
        if upgrade.get('state') != 'installed' or upgrade.get('host_instance_id') != host.get('instance_id'):
            raise ApiError(409, 'Повреждена связь установленной модификации')
        state = states.get(modification['modification_id']) or {}
        if state.get('resource_type') != 'heavy_weapon_mount':
            continue
        weapon_instance_id = str(state.get('weapon_instance_id') or '')
        if not weapon_instance_id:
            continue
        weapon = owned.get(weapon_instance_id)
        mechanics = (item_by_id(catalog_item_id_for_entry(weapon)) or {}).get('mechanics') or {}
        valid = bool(
            weapon and weapon.get('cat') == 'guns' and
            _num(mechanics.get('hands')) == 2 and
            weapon.get('state') == 'installed' and
            weapon.get('mounted_modification_id') == modification['modification_id'] and
            weapon.get('mounted_vehicle_id') == modification['host_instance_id'] and
            weapon_instance_id not in bound_weapon_ids)
        if not valid:
            raise ApiError(409, 'Повреждена связь Vehicle Heavy Weapon Mount')
        bound_weapon_ids.add(weapon_instance_id)
    for weapon in owned.values():
        mount_id = str(weapon.get('mounted_modification_id') or '')
        if not mount_id:
            continue
        modification = modification_by_id.get(mount_id)
        state = states.get(mount_id) or {}
        if (not modification or state.get('weapon_instance_id') != weapon.get('instance_id') or
                weapon.get('instance_id') not in bound_weapon_ids):
            raise ApiError(409, 'Повреждена связь Vehicle Heavy Weapon Mount')


def sync_weapon_states_with_modifications(conn, character_id, data):
    ensure_progression(data)
    modifications = character_modifications(conn, character_id)
    effective_weapons = character_effective_weapons(data, modifications)
    states = data.setdefault('weapon_state', {})
    for instance_id, weapon in effective_weapons.items():
        effective_max = max(0, _num((weapon.get('effective') or {}).get('magazine')) or 0)
        state = states.setdefault(instance_id, {
            'magazine': effective_max, 'magazine_max': effective_max, 'reserve': 0,
        })
        state['magazine_max'] = effective_max
        state['magazine'] = max(0, min(effective_max, _num(state.get('magazine')) or 0))
        state['reserve'] = 0
        clear_loaded_ammo_if_empty(state)
    ensure_shared_ammo_state(data)
    return effective_weapons


def sync_vehicle_states_with_modifications(conn, character_id, data):
    modifications = character_modifications(conn, character_id)
    vehicles = {item.get('instance_id'): item for item in data.get('inventory') or []
                if isinstance(item, dict) and item.get('cat') == 'vehicles'}
    owned = {item.get('instance_id'): item for item in data.get('inventory') or []
             if isinstance(item, dict) and item.get('instance_id')}
    modification_states = data.setdefault('modification_state', {})
    for modification in modifications:
        if modification.get('host_type') != 'vehicle' or \
                modification.get('host_instance_id') not in vehicles:
            continue
        config = modification.get('configuration') or {}
        rules = config.get('effect_rules')
        upgrade = owned.get(modification.get('upgrade_instance_id')) or {}
        if not isinstance(rules, list) or not rules:
            rules = vehicle_modification_rules_for_catalog(
                catalog_item_id_for_entry(upgrade) or
                config.get('upgrade_catalog_item_id'))
        initial = initial_vehicle_modification_state(
            rules, data, config.get('choices') or {})
        if initial:
            modification_states[modification['modification_id']] = \
                normalize_vehicle_modification_state(
                    modification_states.get(modification['modification_id']), initial)
    effective_vehicles = character_effective_vehicles(data, modifications)
    states = data.setdefault('vehicle_state', {})
    for instance_id, vehicle in effective_vehicles.items():
        new_max = max(0, _num((vehicle.get('effective') or {}).get('sdp')) or 0)
        base_max = max(0, _num((vehicles.get(instance_id, {}).get('mechanics') or {}).get('sdp')) or 0)
        state = states.setdefault(instance_id, {'sdp_current': base_max, 'sdp_max': base_max})
        old_max = max(0, _num(state.get('sdp_max')) or base_max)
        old_current = max(0, min(old_max, _num(state.get('sdp_current'))
                                 if _num(state.get('sdp_current')) is not None else old_max))
        damage = max(0, old_max - old_current)
        state['sdp_max'] = new_max
        state['sdp_current'] = max(0, new_max - damage)
        vehicle['state'] = copy.deepcopy(state)
    return effective_vehicles


def backfill_character_item_instances(conn):
    """One-time, idempotent migration of legacy JSON stacks to stable instances."""
    if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='characters'").fetchone():
        return
    rows = conn.execute('SELECT id,data,created FROM characters ORDER BY id').fetchall()
    for row in rows:
        try:
            data = json.loads(row['data'])
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        original = copy.deepcopy(data)
        changed = ensure_character_item_instances(data)
        ensure_progression(data)
        changed = changed or data != original
        persist_character_item_instances(
            conn, row['id'], data, 'legacy_migration', acquired_at=row['created'], prune=True)
        if changed:
            conn.execute('UPDATE characters SET data=? WHERE id=?',
                         (json.dumps(data, ensure_ascii=False), row['id']))


def apply_schema_migrations(conn, make_backup=True):
    """Idempotently upgrade legacy databases without resetting campaign data."""
    conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations('
                 'version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied REAL NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS account_role_audit('
                 'id INTEGER PRIMARY KEY AUTOINCREMENT, target_user_id INTEGER NOT NULL, '
                 'actor_user_id INTEGER, role_before TEXT NOT NULL, role_after TEXT NOT NULL, '
                 'reason TEXT NOT NULL, created REAL NOT NULL)')
    conn.executescript("""
      CREATE TABLE IF NOT EXISTS sessions(
        token TEXT PRIMARY KEY,user_id INTEGER NOT NULL,created REAL NOT NULL,expires REAL NOT NULL,
        last_seen REAL,ip_address TEXT,user_agent TEXT
      );
      CREATE TABLE IF NOT EXISTS account_security_audit(
        id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,actor_user_id INTEGER,
        event_type TEXT NOT NULL,detail TEXT NOT NULL DEFAULT '',created REAL NOT NULL
      );
      CREATE TABLE IF NOT EXISTS registration_invites(
        id INTEGER PRIMARY KEY AUTOINCREMENT,code_hash TEXT UNIQUE NOT NULL,
        label TEXT NOT NULL DEFAULT '',created_by INTEGER NOT NULL,max_uses INTEGER NOT NULL DEFAULT 1,
        uses INTEGER NOT NULL DEFAULT 0,expires_at REAL,disabled_at REAL,created REAL NOT NULL
      );
    """)
    applied = {row['version'] for row in conn.execute('SELECT version FROM schema_migrations')}
    migrations = [
        (MIGRATION_ACCOUNT_ROLES, 'account roles and privacy foundation'),
        (MIGRATION_NETWORK_CORE, 'personas storylines and contracts'),
        (MIGRATION_CITY_FEED, 'city feed posts comments and revisions'),
        (MIGRATION_OPERATIONS, 'character ledger and session operations'),
        (MIGRATION_NOTIFICATIONS, 'site notifications and VK outbox'),
        (MIGRATION_TACTICAL_PROFILES, 'profile media and tactical session resources'),
        (MIGRATION_ITEM_INSTANCES, 'stable character item instances'),
        (MIGRATION_ACTIVE_EFFECTS, 'active character effect instances'),
        (MIGRATION_EFFECT_PRESETS, 'effect preset snapshots'),
        (MIGRATION_ITEM_MODIFICATIONS, 'host item modifications'),
        (MIGRATION_SESSION_NET, 'live session NET context'),
        (MIGRATION_CAMPAIGN_CLOCK, 'campaign clock and service timing'),
        (MIGRATION_CREW_STASH, 'crew stash and item transfers'),
        (MIGRATION_MARKET_STOCK, 'market finite stock and fixer requests'),
        (MIGRATION_NPC_STATBLOCKS, 'npc full statblocks and session snapshots'),
        (MIGRATION_SESSION_RECAPS, 'session recaps and campaign chronicle'),
        (MIGRATION_LOCATIONS, 'map points of interest and key locations'),
        (MIGRATION_MEMORIAL, 'fallen edgerunners memorial and afterlife legacy'),
        (MIGRATION_MEMORIAL_DRAFT, 'collaborative memorial draft state'),
        (MIGRATION_MARKET_PERMANENT, 'permanent market supply'),
        (MIGRATION_ORGANIZATIONS, 'organization memberships and reputation'),
        (MIGRATION_FEED_SINGLE_FORMAT, 'city feed single post type'),
    ]
    pending = [version for version, _ in migrations if version not in applied]
    if make_backup and pending:
        backup_database(conn, f'v{min(pending)}-v{max(pending)}')
    if MIGRATION_ACCOUNT_ROLES not in applied:
        columns = {row['name'] for row in conn.execute('PRAGMA table_info(users)')}
        additions = {
            'account_role': "TEXT NOT NULL DEFAULT 'player'",
            'show_display_name': 'INTEGER NOT NULL DEFAULT 0',
            'vk_user_id': 'TEXT',
            'vk_linked_at': 'REAL',
            'notification_prefs': "TEXT NOT NULL DEFAULT '{}'",
            'theme_json': "TEXT NOT NULL DEFAULT '{}'",
        }
        for name, definition in additions.items():
            if name not in columns:
                conn.execute(f'ALTER TABLE users ADD COLUMN {name} {definition}')
        conn.execute("UPDATE users SET account_role='gm' WHERE is_gm=1 "
                     "AND account_role!='admin'")
        conn.execute("UPDATE users SET account_role='player' "
                     "WHERE account_role IS NULL OR account_role NOT IN ('player','gm','admin')")
    if MIGRATION_NETWORK_CORE not in applied:
        conn.executescript(NETWORK_SCHEMA)
    if MIGRATION_CITY_FEED not in applied:
        conn.executescript(FEED_SCHEMA)
    if MIGRATION_OPERATIONS not in applied:
        conn.executescript(OPERATIONS_SCHEMA)
    if MIGRATION_NOTIFICATIONS not in applied:
        conn.executescript(NOTIFICATION_SCHEMA)
    if MIGRATION_TACTICAL_PROFILES not in applied:
        ensure_column(conn, 'users', 'avatar_media_id', 'TEXT')
        ensure_column(conn, 'npc_templates', 'archived', 'INTEGER NOT NULL DEFAULT 0')
        ensure_column(conn, 'session_combatants', 'sp_head_max', 'INTEGER NOT NULL DEFAULT 0')
        ensure_column(conn, 'session_combatants', 'sp_body_max', 'INTEGER NOT NULL DEFAULT 0')
        ensure_column(conn, 'session_combatants', 'shield_max', 'INTEGER NOT NULL DEFAULT 0')
        ensure_column(conn, 'session_combatants', 'ammo_max', 'INTEGER NOT NULL DEFAULT 0')
        ensure_column(conn, 'session_combatants', 'luck_current', 'INTEGER NOT NULL DEFAULT 0')
        ensure_column(conn, 'session_combatants', 'luck_max', 'INTEGER NOT NULL DEFAULT 0')
    if MIGRATION_ITEM_INSTANCES not in applied:
        conn.executescript(ITEM_INSTANCE_SCHEMA)
        backfill_character_item_instances(conn)
    if MIGRATION_ACTIVE_EFFECTS not in applied:
        conn.executescript(ACTIVE_EFFECT_SCHEMA)
    if MIGRATION_EFFECT_PRESETS not in applied:
        ensure_column(conn, 'active_effect_instances', 'preset_id', 'TEXT')
        ensure_column(conn, 'active_effect_instances', 'context_json', "TEXT NOT NULL DEFAULT '{}'")
    if MIGRATION_ITEM_MODIFICATIONS not in applied:
        conn.executescript(ITEM_MODIFICATION_SCHEMA)
    if MIGRATION_SESSION_NET not in applied:
        ensure_column(conn, 'nc_sessions', 'net_state_json', "TEXT NOT NULL DEFAULT '{}'")
    if MIGRATION_CAMPAIGN_CLOCK not in applied:
        conn.executescript(CAMPAIGN_CLOCK_SCHEMA)
    if MIGRATION_CREW_STASH not in applied:
        conn.executescript(CREW_STASH_SCHEMA)
    if MIGRATION_MARKET_STOCK not in applied:
        conn.executescript(MARKET_STOCK_SCHEMA)
    if MIGRATION_NPC_STATBLOCKS not in applied:
        ensure_column(conn, 'session_combatants', 'statblock_json', "TEXT NOT NULL DEFAULT '{}'")
    if MIGRATION_SESSION_RECAPS not in applied:
        conn.executescript(SESSION_RECAP_SCHEMA)
    if MIGRATION_LOCATIONS not in applied:
        conn.executescript(LOCATION_SCHEMA)
    if MIGRATION_MEMORIAL not in applied:
        conn.executescript(MEMORIAL_SCHEMA)
    if MIGRATION_MEMORIAL_DRAFT not in applied:
        ensure_column(conn, 'memorials', 'draft_state', "TEXT NOT NULL DEFAULT 'published'")
    if MIGRATION_MARKET_PERMANENT not in applied:
        conn.executescript(MARKET_PERMANENT_SCHEMA)
    if MIGRATION_ORGANIZATIONS not in applied:
        conn.executescript(ORGANIZATION_SCHEMA)
    # Crew reputation (additive to organizations migration).
    try:
        conn.execute('''CREATE TABLE IF NOT EXISTS crew_reputation(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  organization_persona_id INTEGER NOT NULL,
  reputation INTEGER NOT NULL DEFAULT 0,
  favor INTEGER NOT NULL DEFAULT 0,
  heat INTEGER NOT NULL DEFAULT 0,
  standing TEXT NOT NULL DEFAULT 'neutral',
  note TEXT NOT NULL DEFAULT '',
  created_by INTEGER,
  created REAL NOT NULL,
  updated REAL NOT NULL,
  UNIQUE(organization_persona_id))''')
    except Exception:
        pass
    # Personal stash (additive to crew_stash migration).
    try:
        conn.executescript('''CREATE TABLE IF NOT EXISTS personal_stash(
  instance_id TEXT PRIMARY KEY,
  character_id INTEGER NOT NULL,
  catalog_item_id TEXT,
  custom_name TEXT,
  state TEXT NOT NULL DEFAULT 'stored',
  quantity INTEGER NOT NULL DEFAULT 1,
  notes TEXT NOT NULL DEFAULT '',
  stored_at REAL NOT NULL,
  data_json TEXT NOT NULL DEFAULT '{}',
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_personal_stash_char ON personal_stash(character_id);''')
    except Exception:
        pass
    # Re-run additive CREATE IF NOT EXISTS blocks so patch-level tables added to an
    # already-applied migration remain safe during development and rolling deploys.
    conn.executescript(NETWORK_SCHEMA)
    conn.executescript(FEED_SCHEMA)
    conn.executescript(OPERATIONS_SCHEMA)
    conn.executescript(NOTIFICATION_SCHEMA)
    conn.executescript(ITEM_INSTANCE_SCHEMA)
    conn.executescript(ACTIVE_EFFECT_SCHEMA)
    conn.executescript(ITEM_MODIFICATION_SCHEMA)
    conn.executescript(CAMPAIGN_CLOCK_SCHEMA)
    conn.executescript(CREW_STASH_SCHEMA)
    conn.executescript(MARKET_STOCK_SCHEMA)
    conn.executescript(SESSION_RECAP_SCHEMA)
    conn.executescript(LOCATION_SCHEMA)
    conn.executescript(MEMORIAL_SCHEMA)
    # Recover safely if a rolling/patch deployment recorded the migration before
    # every additive column reached a particular database.
    ensure_column(conn, 'users', 'avatar_media_id', 'TEXT')
    ensure_column(conn, 'users', 'disabled_at', 'REAL')
    ensure_column(conn, 'users', 'disabled_reason', 'TEXT')
    ensure_column(conn, 'users', 'disabled_by', 'INTEGER')
    ensure_column(conn, 'sessions', 'last_seen', 'REAL')
    ensure_column(conn, 'sessions', 'ip_address', 'TEXT')
    ensure_column(conn, 'sessions', 'user_agent', 'TEXT')
    if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='characters'").fetchone():
        ensure_column(conn, 'characters', 'revision', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(conn, 'nc_sessions', 'safety_config', "TEXT NOT NULL DEFAULT '{}'")
    ensure_column(conn, 'nc_sessions', 'net_state_json', "TEXT NOT NULL DEFAULT '{}'")
    ensure_column(conn, 'session_combatants', 'statblock_json', "TEXT NOT NULL DEFAULT '{}'")
    ensure_column(conn, 'npc_templates', 'archived', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(conn, 'session_combatants', 'sp_head_max', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(conn, 'session_combatants', 'sp_body_max', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(conn, 'session_combatants', 'shield_max', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(conn, 'session_combatants', 'ammo_max', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(conn, 'session_combatants', 'luck_current', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(conn, 'session_combatants', 'luck_max', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(conn, 'active_effect_instances', 'preset_id', 'TEXT')
    ensure_column(conn, 'active_effect_instances', 'context_json', "TEXT NOT NULL DEFAULT '{}'")
    conn.execute('UPDATE session_combatants SET sp_head_max=sp_head '
                 'WHERE sp_head_max=0 AND sp_head>0')
    conn.execute('UPDATE session_combatants SET sp_body_max=sp_body '
                 'WHERE sp_body_max=0 AND sp_body>0')
    conn.execute('UPDATE session_combatants SET shield_max=shield_current '
                 'WHERE shield_max=0 AND shield_current>0')
    conn.execute('UPDATE session_combatants SET ammo_max=ammo_current '
                 'WHERE ammo_max=0 AND ammo_current>0')
    if MIGRATION_FEED_SINGLE_FORMAT not in applied:
        conn.execute("UPDATE feed_posts SET format='post' WHERE format <> 'post'")
    for version, name in migrations:
        if version not in applied:
            conn.execute(
                'INSERT INTO schema_migrations(version,name,applied) VALUES(?,?,?)',
                (version, name, time.time()))
    conn.execute("UPDATE users SET is_gm=CASE WHEN account_role IN ('gm','admin') "
                 "THEN 1 ELSE 0 END")
    conn.execute('CREATE INDEX IF NOT EXISTS idx_role_audit_target '
                 'ON account_role_audit(target_user_id, created)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_registration_invites_active '
                 'ON registration_invites(disabled_at,expires_at,uses,max_uses)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_account_security_audit '
                 'ON account_security_audit(user_id,created)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id,expires)')
    conn.commit()


def apply_admin_bootstrap(conn):
    """Promote only explicitly configured existing users; never auto-promote registration."""
    usernames = configured_admin_usernames()
    if not usernames:
        return []
    promoted = []
    for username in sorted(usernames):
        row = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        if not row:
            continue
        before = user_account_role(row)
        if before == 'admin':
            continue
        conn.execute("UPDATE users SET account_role='admin', is_gm=1 WHERE id=?", (row['id'],))
        conn.execute(
            'INSERT INTO account_role_audit(target_user_id,actor_user_id,role_before,'
            'role_after,reason,created) VALUES(?,NULL,?,?,?,?)',
            (row['id'], before, 'admin', 'CBPR_ADMIN_USERS bootstrap', time.time()))
        promoted.append(username)
    conn.commit()
    return promoted


PERSONA_ACCESS = {'private', 'shared', 'system'}
PERSONA_KINDS = {'person', 'organization', 'outlet', 'gang', 'corporation', 'government', 'anonymous'}
PERSONA_STATUSES = {'active', 'missing', 'dead', 'dissolved', 'destroyed', 'archived'}
STORYLINE_STATUSES = {'active', 'paused', 'completed', 'archived'}
CONTRACT_STATUSES = {'draft', 'open', 'crew_full', 'in_progress', 'completed', 'failed', 'cancelled', 'archived'}
CONTRACT_REWARD_MODES = {'exact', 'range', 'negotiable', 'hidden'}
CONTRACT_RISKS = {'low', 'moderate', 'high', 'extreme', 'classified'}
NC_LOCATION_IDS = {
    'watson', 'watson-arasaka-waterfront', 'watson-northside-industrial',
    'watson-little-china', 'watson-kabuki',
    'westbrook', 'westbrook-japantown', 'westbrook-north-oak', 'westbrook-charter-hill',
    'city-center', 'city-center-downtown', 'city-center-corpo-plaza',
    'heywood', 'heywood-wellsprings', 'heywood-vista-del-rey', 'heywood-the-glen',
    'santo-domingo', 'santo-domingo-arroyo', 'santo-domingo-rancho-coronado',
    'pacifica', 'pacifica-coastview', 'pacifica-west-wind-estate',
    'badlands', 'badlands-near-westbrook', 'badlands-near-santo-domingo',
    'badlands-near-pacifica', 'orbital-air-space-center',
}
FEED_FORMATS = {'post'}
# 23.1: единый тип публикации City Feed; старые форматы склеиваются в 'post' миграцией 22
FEED_DEFAULT_FORMAT = 'post'
FEED_TRUTH = {'true', 'partially_true', 'false', 'propaganda', 'unknown'}
SESSION_VIEW_DEFAULTS = {
    'show_initiative': True,
    'show_ally_hp': True,
    'show_armor': True,
    'show_shield': True,
    'show_ammo': False,
    'show_move': True,
    'show_luck': True,
    'show_conditions': True,
    'show_injuries': True,
    'show_npc_stats': False,
}
SESSION_ACCESS_ROLES = {'co_gm', 'assistant', 'rules_helper', 'observer'}
SESSION_ROLE_CAPABILITIES = {
    'owner': {'view_gm', 'view_secrets', 'edit_session', 'edit_combatants', 'manage_access', 'manage_safety'},
    'co_gm': {'view_gm', 'view_secrets', 'edit_session', 'edit_combatants', 'manage_safety'},
    'assistant': {'view_gm', 'view_secrets', 'edit_combatants'},
    'rules_helper': {'view_gm'},
    'observer': {'view_player'},
    'crew': {'view_player'},
}
SESSION_SAFETY_DEFAULTS = {
    'content_notes': '',
    'lines': [],
    'veils': [],
    'pause_enabled': True,
}
SAFETY_SIGNAL_KINDS = {'pause', 'x_card', 'check_in'}
SAFETY_SIGNAL_STATUSES = {'open', 'acknowledged', 'resolved'}
SESSION_NET_NODE_TYPES = {
    'access_point', 'password', 'file', 'control', 'black_ice', 'objective',
}
SESSION_NET_PATH_DIRECTIONS = {'bidirectional', 'one_way'}


def parse_json_list(value):
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value or '[]')
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []


def clean_location_id(value):
    location_id = str(value or '').strip().lower()[:80]
    if location_id and location_id not in NC_LOCATION_IDS:
        raise ApiError(400, 'Некорректная локация Night City')
    return location_id or None


def optional_timestamp(value, fallback=None):
    if value is None or value == '':
        return fallback
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        raise ApiError(400, 'Некорректное время события')
    if not math.isfinite(timestamp) or abs(timestamp) > 8_640_000_000_000:
        raise ApiError(400, 'Некорректное время события')
    return timestamp


def session_view_config(value):
    raw = parse_json_object(value)
    return {
        key: raw[key] if isinstance(raw.get(key), bool) else default
        for key, default in SESSION_VIEW_DEFAULTS.items()
    }


def session_safety_config(value):
    raw = parse_json_object(value)
    lines = raw.get('lines') if isinstance(raw.get('lines'), list) else []
    veils = raw.get('veils') if isinstance(raw.get('veils'), list) else []
    return {
        'content_notes': str(raw.get('content_notes') or '')[:5000],
        'lines': [str(item).strip()[:200] for item in lines[:50] if str(item).strip()],
        'veils': [str(item).strip()[:200] for item in veils[:50] if str(item).strip()],
        'pause_enabled': raw.get('pause_enabled') is not False,
    }


def session_net_state(value):
    raw = parse_json_object(value)
    floors = []
    seen_floors = set()
    for item in raw.get('floors') or []:
        if not isinstance(item, dict):
            continue
        floor_id = str(item.get('floor_id') or '').lower()
        label = str(item.get('label') or '').strip()[:120]
        if (not INSTANCE_ID_RE.fullmatch(floor_id) or floor_id in seen_floors or
                not label or len(floors) >= 100):
            continue
        seen_floors.add(floor_id)
        floors.append({'floor_id': floor_id, 'label': label,
                       'sort_order': len(floors)})
    nodes = []
    seen_nodes = set()
    for item in raw.get('nodes') or []:
        if not isinstance(item, dict):
            continue
        node_id = str(item.get('node_id') or '').lower()
        floor_id = str(item.get('floor_id') or '').lower()
        node_type = str(item.get('type') or '').lower()
        label = str(item.get('label') or '').strip()[:120]
        if (not INSTANCE_ID_RE.fullmatch(node_id) or node_id in seen_nodes or
                floor_id not in seen_floors or node_type not in SESSION_NET_NODE_TYPES or
                not label or len(nodes) >= 500):
            continue
        seen_nodes.add(node_id)
        nodes.append({
            'node_id': node_id, 'floor_id': floor_id, 'type': node_type,
            'label': label, 'dv': max(0, min(29, int(_num(item.get('dv')) or 0))),
            'defense': max(0, min(29, int(_num(item.get('defense')) or 0))),
            'visible': item.get('visible') is True,
            'resolved': item.get('resolved') is True,
            'controlled_by_combatant_id': int(item['controlled_by_combatant_id'])
                if isinstance(item.get('controlled_by_combatant_id'), int) and
                item['controlled_by_combatant_id'] > 0 else None,
            'gm_note': str(item.get('gm_note') or '')[:2000],
            'sort_order': len(nodes),
        })
    paths = []
    seen_paths = set()
    seen_pairs = set()
    for item in raw.get('paths') or []:
        if not isinstance(item, dict):
            continue
        path_id = str(item.get('path_id') or '').lower()
        from_node_id = str(item.get('from_node_id') or '').lower()
        to_node_id = str(item.get('to_node_id') or '').lower()
        direction = str(item.get('direction') or 'bidirectional').lower()
        pair = (from_node_id, to_node_id, direction)
        if (not INSTANCE_ID_RE.fullmatch(path_id) or path_id in seen_paths or
                from_node_id not in seen_nodes or to_node_id not in seen_nodes or
                from_node_id == to_node_id or direction not in SESSION_NET_PATH_DIRECTIONS or
                pair in seen_pairs or len(paths) >= 1000):
            continue
        seen_paths.add(path_id)
        seen_pairs.add(pair)
        if direction == 'bidirectional':
            seen_pairs.add((to_node_id, from_node_id, direction))
        paths.append({
            'path_id': path_id, 'from_node_id': from_node_id,
            'to_node_id': to_node_id, 'direction': direction,
            'label': str(item.get('label') or '')[:120],
            'visible': item.get('visible') is True,
        })
    links = []
    seen_entities = set()
    for item in raw.get('links') or []:
        if not isinstance(item, dict):
            continue
        entity_id = str(item.get('net_entity_id') or '').lower()
        floor_id = str(item.get('floor_id') or '').lower()
        node_id = str(item.get('node_id') or '').lower()
        character_id = _num(item.get('character_id'))
        target_id = _num(item.get('target_combatant_id'))
        if (not INSTANCE_ID_RE.fullmatch(entity_id) or entity_id in seen_entities or
                not isinstance(character_id, int) or character_id < 1 or
                floor_id not in seen_floors or len(links) >= 200 or
                (node_id and node_id not in seen_nodes)):
            continue
        if node_id:
            node_floor = next((node['floor_id'] for node in nodes
                               if node['node_id'] == node_id), None)
            if node_floor != floor_id:
                continue
        seen_entities.add(entity_id)
        links.append({
            'net_entity_id': entity_id, 'character_id': character_id,
            'floor_id': floor_id, 'node_id': node_id or None,
            'target_combatant_id': int(target_id) if isinstance(target_id, int) and target_id > 0 else None,
            'initiative': max(-1000, min(1000, _num(item.get('initiative')) or 0)),
            'active': item.get('active') is not False,
            'visible': item.get('visible') is not False,
            'linked_at': _num(item.get('linked_at')) or 0,
        })
    runners = []
    seen_combatants = set()
    for item in raw.get('runners') or []:
        if not isinstance(item, dict):
            continue
        combatant_id = _num(item.get('combatant_id'))
        character_id = _num(item.get('character_id'))
        node_id = str(item.get('node_id') or '').lower()
        previous_node_id = str(item.get('previous_node_id') or '').lower()
        if (not isinstance(combatant_id, int) or combatant_id < 1 or
                combatant_id in seen_combatants or
                not isinstance(character_id, int) or character_id < 1 or
                (node_id and node_id not in seen_nodes) or
                (previous_node_id and previous_node_id not in seen_nodes) or
                len(runners) >= 100):
            continue
        seen_combatants.add(combatant_id)
        runners.append({
            'combatant_id': combatant_id, 'character_id': character_id,
            'node_id': node_id or None,
            'previous_node_id': previous_node_id or None,
            'jacked_in': item.get('jacked_in') is True,
            'interface_rank': max(0, min(10, int(_num(item.get('interface_rank')) or 0))),
            'actions_recorded': max(0, int(_num(item.get('actions_recorded')) or 0)),
            'action_round': max(0, int(_num(item.get('action_round')) or 0)),
            'actions_used': max(0, int(_num(item.get('actions_used')) or 0)),
            'action_penalty': max(0, min(3, int(_num(
                item.get('action_penalty')) or 0))),
            'next_action_penalty': max(0, min(3, int(_num(
                item.get('next_action_penalty')) or 0))),
            'last_action_at': _num(item.get('last_action_at')),
        })
    action_log = []
    for item in raw.get('action_log') or []:
        if not isinstance(item, dict):
            continue
        action_id = str(item.get('action_id') or '').lower()
        if not INSTANCE_ID_RE.fullmatch(action_id):
            continue
        action_log.append({
            'action_id': action_id,
            'combatant_id': int(item['combatant_id'])
                if isinstance(item.get('combatant_id'), int) else None,
            'actor_entity_id': str(item.get('actor_entity_id') or '') or None,
            'action': str(item.get('action') or '')[:40],
            'target_node_id': str(item.get('target_node_id') or '') or None,
            'target_entity_id': str(item.get('target_entity_id') or '') or None,
            'target_program_instance_id': str(
                item.get('target_program_instance_id') or '') or None,
            'success': item.get('success') if isinstance(item.get('success'), bool) else None,
            'actor_total': _num(item.get('actor_total')),
            'defense_total': _num(item.get('defense_total')),
            'created': _num(item.get('created')) or 0,
            'summary': str(item.get('summary') or '')[:500],
        })
        if len(action_log) >= 100:
            break
    return {
        'round': max(0, int(_num(raw.get('round')) or 0)),
        'active_turn': max(0, int(_num(raw.get('active_turn')) or 0)),
        'floors': floors, 'nodes': nodes, 'paths': paths, 'links': links,
        'runners': runners, 'action_log': action_log,
    }


def character_interface_rank(data):
    return max([int(_num(role.get('rank')) or 0)
                for role in data.get('roles') or []
                if isinstance(role, dict) and role.get('name') == 'Netrunner'] or [0])


def net_actions_for_interface(rank):
    rank = max(0, min(10, int(_num(rank) or 0)))
    if rank <= 0:
        return 0
    if rank <= 3:
        return 2
    if rank <= 6:
        return 3
    if rank <= 9:
        return 4
    return 5


def session_net_path_between(state, from_node_id, to_node_id, *, require_visible=True):
    for path in state.get('paths') or []:
        if require_visible and not path.get('visible'):
            continue
        if path['from_node_id'] == from_node_id and path['to_node_id'] == to_node_id:
            return path
        if (path['direction'] == 'bidirectional' and
                path['from_node_id'] == to_node_id and
                path['to_node_id'] == from_node_id):
            return path
    return None


def clean_npc_template_input(body, existing=None):
    base = dict(existing or {})
    name = str((body or {}).get('name', base.get('name', '')) or '').strip()[:120]
    if not name:
        raise ApiError(400, 'NPC template нужно имя')
    access = str((body or {}).get('access', base.get('access', 'private'))).lower()
    if access not in ('private', 'shared'):
        raise ApiError(400, 'Некорректный NPC template')
    existing_data = parse_json_object(base.get('data_json'))
    source = (body or {}).get('data')
    if source is None:
        source = existing_data
    if not isinstance(source, dict):
        raise ApiError(400, 'Некорректный NPC template')
    data = {**existing_data, **source}
    provided_keys = set(data)
    numeric = ('initiative', 'hp_current', 'hp_max', 'sp_head', 'sp_head_max',
               'sp_body', 'sp_body_max', 'shield_current', 'shield_max', 'ammo_current', 'ammo_max',
               'luck_current', 'luck_max', 'move', 'death_penalty')
    for key in numeric:
        value = _num(data.get(key)) or 0
        data[key] = max(-1000, min(1000, value)) if key == 'initiative' else max(0, value)
    for current_key, maximum_key in (('hp_current', 'hp_max'),
                                     ('sp_head', 'sp_head_max'),
                                     ('sp_body', 'sp_body_max'),
                                     ('shield_current', 'shield_max'),
                                     ('ammo_current', 'ammo_max'),
                                     ('luck_current', 'luck_max')):
        maximum = data[maximum_key]
        if current_key not in provided_keys and maximum:
            data[current_key] = maximum
        if not maximum and data[current_key]:
            maximum = data[current_key]
            data[maximum_key] = maximum
        if maximum:
            data[current_key] = min(maximum, data[current_key])
    for key in ('conditions', 'injuries'):
        values = data.get(key) or []
        if not isinstance(values, list):
            raise ApiError(400, 'Некорректный NPC template')
        data[key] = [str(value)[:120] for value in values[:20]]
    secret = data.get('secret') or {}
    if not isinstance(secret, dict):
        raise ApiError(400, 'Некорректный NPC template')
    data['secret'] = secret
    data['visible'] = data.get('visible') is not False
    data['statblock'] = clean_npc_statblock(data.get('statblock'))
    if len(json.dumps(data, ensure_ascii=False)) > 40000:
        raise ApiError(400, 'Некорректный NPC template')
    return {
        'name': name,
        'access': access,
        'role': str((body or {}).get('role', base.get('role', '')) or '')[:80],
        'data': data,
    }


NPC_STAT_MAX = 20
NPC_SKILL_MAX = 10


def clean_npc_statblock(source):
    """Validate the full-statblock portion of an NPC (STATs, Skills, Weapons, Notes)."""
    if source is None:
        source = {}
    if not isinstance(source, dict):
        raise ApiError(400, 'NPC statblock должен быть объектом')
    stats = source.get('stats') if isinstance(source.get('stats'), dict) else {}
    clean_stats = {}
    for stat in STATS:
        value = _num(stats.get(stat))
        if value is not None:
            clean_stats[stat] = max(0, min(NPC_STAT_MAX, value))
    skills = source.get('skills') if isinstance(source.get('skills'), dict) else {}
    if len(skills) > 200:
        raise ApiError(400, 'NPC skills должен быть объектом до 200 записей')
    clean_skills = {}
    for name, value in skills.items():
        name = str(name).strip()[:120]
        if not skill_base(name):
            raise ApiError(400, f'Неизвестный NPC Skill: {name}')
        clean_skills[name] = max(0, min(NPC_SKILL_MAX, _num(value) or 0))
    weapons = source.get('weapons') if isinstance(source.get('weapons'), list) else []
    if len(weapons) > 30:
        raise ApiError(400, 'NPC weapons должен быть списком до 30 записей')
    clean_weapons = []
    for weapon in weapons:
        if not isinstance(weapon, dict):
            raise ApiError(400, 'NPC weapon должен быть объектом')
        weapon_name = str(weapon.get('name') or '').strip()[:120]
        if not weapon_name:
            raise ApiError(400, 'NPC weapon требует имя')
        clean_weapons.append({
            'name': weapon_name,
            'skill': str(weapon.get('skill') or '').strip()[:120],
            'damage': str(weapon.get('damage') or '')[:80],
            'rof': str(weapon.get('rof') or '')[:20],
            'notes': str(weapon.get('notes') or '')[:400],
        })
    return {
        'stats': clean_stats,
        'skills': clean_skills,
        'weapons': clean_weapons,
        'notes': str(source.get('notes') or '')[:4000],
    }


def npc_statblock_derived(statblock):
    """Compute readable attack/skill bases from a validated NPC statblock."""
    statblock = statblock if isinstance(statblock, dict) else {}
    stats = statblock.get('stats') if isinstance(statblock.get('stats'), dict) else {}
    skills = statblock.get('skills') if isinstance(statblock.get('skills'), dict) else {}
    attacks = []
    for weapon in statblock.get('weapons') or []:
        if not isinstance(weapon, dict):
            continue
        skill_name = str(weapon.get('skill') or '')
        base_name = skill_base(skill_name)
        stat = SKILL_BY_NAME[base_name][2] if base_name else 'REF'
        stat_value = _num(stats.get(stat)) or 0
        skill_level = _num(skills.get(skill_name)) or 0
        attacks.append({
            'name': weapon.get('name'),
            'skill': skill_name, 'stat': stat,
            'stat_value': stat_value, 'skill_level': skill_level,
            'base': stat_value + skill_level,
            'damage': weapon.get('damage'), 'rof': weapon.get('rof'),
            'notes': weapon.get('notes'),
        })
    skill_bases = []
    for name, level in sorted(skills.items()):
        base_name = skill_base(name)
        if not base_name:
            continue
        stat = SKILL_BY_NAME[base_name][2]
        stat_value = _num(stats.get(stat)) or 0
        skill_bases.append({
            'name': name, 'stat': stat, 'level': level,
            'base': stat_value + level,
        })
    return {
        'attacks': attacks,
        'skills': skill_bases,
        'death_save': _num(stats.get('BODY')) or 0,
        'evasion_base': (_num(stats.get('DEX')) or 0) + (_num(skills.get('Evasion')) or 0),
    }

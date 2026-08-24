"""Pure-stdlib PDF AcroForm field extractor for the RTG Cyberpunk RED fillable character sheet.

No external dependencies — reads /T (name) and /V (value) field pairs directly
from the PDF binary. Designed for the official R. Talsorian Games fillable form
(RTG-CPR-CharacterSheet-Fillable.pdf) but works with any AcroForm PDF.
"""
import re

# Known field name → character data key mappings for the RTG CPR form.
# The official form uses human-readable field names. This table maps them to
# our canonical character data structure. Unknown fields are ignored.
FIELD_MAP = {
    # Identity
    'Character Name': 'handle',
    'Role': 'role',
    'Rank': 'role_rank',
    'Handle': 'handle',
    'Real Name': lambda v, out: _split_name(v, out),
    'Player': 'player',
    # Stats (case-insensitive — the form may use different cases)
    'INT': ('stats', 'INT'), 'REF': ('stats', 'REF'), 'DEX': ('stats', 'DEX'),
    'TECH': ('stats', 'TECH'), 'COOL': ('stats', 'COOL'), 'WILL': ('stats', 'WILL'),
    'LUCK': ('stats', 'LUCK'), 'MOVE': ('stats', 'MOVE'), 'BODY': ('stats', 'BODY'),
    'EMP': ('stats', 'EMP'),
    # Derived
    'HP': 'hp_cur',
    'Humanity': 'humanity_cur',
    # Resources
    'Cash': 'cash',
}


def _split_name(value, out):
    """Split a full name into first/last."""
    parts = str(value or '').strip().split(None, 1)
    if parts:
        out['first_name'] = parts[0]
    if len(parts) > 1:
        out['last_name'] = parts[1]


def extract_acroform_fields(pdf_bytes):
    """Extract AcroForm field name/value pairs from raw PDF bytes.

    Returns a dict {field_name: field_value}. Uses regex to find /T and /V
    operators in PDF objects. This is a simplified parser — it handles the
    common patterns used by the RTG fillable form.
    """
    if not pdf_bytes or not pdf_bytes[:5].startswith(b'%PDF'):
        return {}
    # Decode as latin-1 to preserve all bytes as characters
    raw = pdf_bytes.decode('latin-1', errors='replace')

    # Strategy: find all /T (title) and /V (value) pairs within PDF objects.
    # PDF form fields look like: /T (FieldName) /V (FieldValue)
    # Values can be strings in parentheses, hex strings, or names.
    fields = {}
    # Find field objects: sequences containing /T(...) /V(...)
    # Pattern handles parenthesized strings with escaped parens
    pattern = re.compile(
        r'/T\s*\(([^)]*(?:\([^)]*\)[^)]*)*)\)'  # /T (name) with nested parens
        r'[\s\S]{0,500}?'  # up to 500 chars between T and V
        r'/V\s*\(([^)]*(?:\([^)]*\)[^)]*)*)\)',  # /V (value)
        re.MULTILINE
    )
    for match in pattern.finditer(raw):
        name = match.group(1).strip()
        value = match.group(2).strip()
        if name and value:
            # Unescape PDF string escapes
            value = value.replace('\\(', '(').replace('\\)', ')').replace('\\\\', '\\')
            fields[name] = value

    # Also try hex string values: /V <hex>
    hex_pattern = re.compile(
        r'/T\s*\(([^)]*(?:\([^)]*\)[^)]*)*)\)'
        r'[\s\S]{0,500}?'
        r'/V\s*<([0-9A-Fa-f\s]+)>',
        re.MULTILINE
    )
    for match in hex_pattern.finditer(raw):
        name = match.group(1).strip()
        hex_val = match.group(2).strip()
        if name and hex_val:
            try:
                value = bytes.fromhex(hex_val.replace(' ', '')).decode('utf-16-be', errors='replace').strip('\x00')
                if value and name not in fields:
                    fields[name] = value
            except (ValueError, UnicodeDecodeError):
                pass

    return fields


def map_fields_to_character(fields):
    """Map extracted AcroForm fields to our canonical character data structure."""
    out = {
        'handle': '', 'role': 'Solo', 'role_rank': 4,
        'stats': {}, 'skills': {}, 'inventory': [], 'cyberware': [],
        'armor': {}, 'cash': 0, 'hp_cur': None, 'humanity_cur': None,
        'ip_available': 0, 'ip_total_earned': 0, 'ip_total_spent': 0,
        'luck_cur': None, 'reputation': 0,
    }
    stats_lower = {k.lower(): k for k in ['INT', 'REF', 'DEX', 'TECH', 'COOL', 'WILL', 'LUCK', 'MOVE', 'BODY', 'EMP']}
    skill_names = {
        'concentration', 'conceal/reveal object', 'lip reading', 'perception', 'tracking',
        'athletics', 'contortionist', 'dance', 'endurance', 'resist torture/drugs', 'stealth',
        'drive land vehicle', 'pilot air vehicle', 'pilot sea vehicle', 'riding',
        'accounting', 'animal handling', 'bureaucracy', 'business', 'composition',
        'criminology', 'cryptography', 'deduction', 'education', 'gamble',
        'library search', 'local expert', 'science', 'tactics', 'wilderness survival',
        'brawling', 'evasion', 'martial arts', 'melee weapon',
        'acting', 'play instrument',
        'archery', 'autofire', 'handgun', 'heavy weapons', 'shoulder arms',
        'bribery', 'conversation', 'human perception', 'interrogation',
        'persuasion', 'personal grooming', 'streetwise', 'trading', 'wardrobe & style',
        'air vehicle tech', 'basic tech', 'cybertech', 'demolitions',
        'electronics/security tech', 'first aid', 'forgery', 'land vehicle tech',
        'paint/draw/sculpt', 'paramedic', 'photography/film', 'pick lock', 'pick pocket',
        'sea vehicle tech', 'weaponstech',
    }

    for name, value in fields.items():
        key_lower = name.lower().strip()

        # Direct field map
        if name in FIELD_MAP:
            mapping = FIELD_MAP[name]
            if callable(mapping):
                mapping(value, out)
            elif isinstance(mapping, tuple):
                out.setdefault(mapping[0], {})[mapping[1]] = _parse_num(value)
            elif mapping == 'role_rank':
                out[mapping] = _parse_num(value) or 4
            elif mapping == 'cash':
                out[mapping] = _parse_num(value) or 0
            elif mapping == 'hp_cur':
                out[mapping] = _parse_num(value)
            elif mapping == 'humanity_cur':
                out[mapping] = _parse_num(value)
            else:
                out[mapping] = str(value).strip()
            continue

        # Stats by lowercase name
        if key_lower in stats_lower:
            stat_name = stats_lower[key_lower]
            out['stats'][stat_name] = _parse_num(value) or 5
            continue

        # Skills (case-insensitive match)
        if key_lower in skill_names:
            # Find the canonical skill name from our list
            canonical = next((s for s in skill_names if s == key_lower), None)
            if canonical:
                # Title-case it for our format
                titled = ' '.join(w.capitalize() if w not in ('and', 'or', '/') else w for w in canonical.split())
                out['skills'][titled] = _parse_num(value) or 0
            continue

        # LUCK current
        if key_lower == 'luck':
            n = _parse_num(value)
            if n is not None:
                out['luck_cur'] = n
            continue

    # Ensure all 10 stats are present
    for stat in ['INT', 'REF', 'DEX', 'TECH', 'COOL', 'WILL', 'LUCK', 'MOVE', 'BODY', 'EMP']:
        if stat not in out['stats']:
            out['stats'][stat] = 5

    return out


def _parse_num(value):
    """Parse a numeric value from a PDF field string."""
    s = str(value or '').strip()
    if not s:
        return None
    # Remove common non-numeric suffixes
    s = re.sub(r'[^\d.\-]', '', s)
    if not s:
        return None
    try:
        n = int(float(s))
        return n
    except (TypeError, ValueError):
        return None


def import_pdf(pdf_bytes):
    """Main entry point: extract fields from PDF and map to character data.

    Returns {'character': {...}, 'fields': {...}, 'unmapped': [...]}.
    """
    fields = extract_acroform_fields(pdf_bytes)
    if not fields:
        raise ValueError('Не найдено AcroForm полей в PDF. Убедитесь, что это заполняемая (fillable) форма.')
    character = map_fields_to_character(fields)
    return {'character': character, 'fields': fields, 'field_count': len(fields)}

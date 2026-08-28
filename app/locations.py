"""Map POIs / Key Locations: точки карты Найт-Сити (итерация P1-9, выделено из app/server.py, логика не менялась)."""
import math
import time

from core import ApiError, user_is_gm
from db import NC_LOCATION_IDS



LOCATION_KINDS = {
    'bar', 'club', 'clinic', 'market', 'restaurant', 'corporate',
    'gang', 'landmark', 'service', 'other',
}

# Seed points of interest for the 2070s campaign. Coordinates use the same
# 0..1000 viewBox as the client-side NC_MAP_COORDS overlay. Source metadata is
# explicit so the GM can tell canonical landmarks from campaign inventions.
NC_SEED_LOCATIONS = [
    {'id': 'afterlife', 'name_en': 'Afterlife', 'name_ru': 'Afterlife', 'kind': 'bar',
     'district_id': 'heywood-the-glen', 'x': 530, 'y': 640,
     'description_en': 'The legendary edgerunner bar where mercs drink to their fallen.',
     'description_ru': 'Легендарный бар эджраннеров, где наёмники пьют за павших.',
     'source': 'Cyberpunk 2077'},
    {'id': 'lizzies-bar', 'name_en': "Lizzie's Bar", 'name_ru': 'Бар Лиззи', 'kind': 'club',
     'district_id': 'watson-kabuki', 'x': 600, 'y': 265,
     'description_en': 'Mox-owned club and braindance den in Kabuki.',
     'description_ru': 'Клуб Mox и точка брейнданса в Кабуки.',
     'source': 'Cyberpunk 2077'},
    {'id': 'clouds', 'name_en': 'Clouds', 'name_ru': 'Clouds', 'kind': 'club',
     'district_id': 'westbrook-japantown', 'x': 668, 'y': 340,
     'description_en': 'High-end dolls club above Japantown.',
     'description_ru': 'Элитный клуб кукол над Джапантауном.',
     'source': 'Cyberpunk 2077'},
    {'id': 'totentanz', 'name_en': 'Totentanz', 'name_ru': 'Totentanz', 'kind': 'club',
     'district_id': 'watson', 'x': 555, 'y': 175,
     'description_en': 'Maelstrom-run industrial club in Watson.',
     'description_ru': 'Индустриальный клуб Maelstrom в Уотсоне.',
     'source': 'Cyberpunk 2077'},
    {'id': 'riot', 'name_en': 'Riot', 'name_ru': 'Riot', 'kind': 'club',
     'district_id': 'westbrook-japantown', 'x': 645, 'y': 372,
     'description_en': 'Music club where the top edgerunners perform.',
     'description_ru': 'Музыкальный клуб, где выступают топовые эджраннеры.',
     'source': 'Cyberpunk 2077'},
    {'id': 'embers', 'name_en': 'Embers', 'name_ru': 'Embers', 'kind': 'club',
     'district_id': 'westbrook-charter-hill', 'x': 782, 'y': 512,
     'description_en': 'Exclusive Charter Hill lounge with a view.',
     'description_ru': 'Эксклюзивный лаунж в Чартер-Хилл с видом.',
     'source': 'Cyberpunk 2077'},
    {'id': 'konpeki-plaza', 'name_en': 'Konpeki Plaza', 'name_ru': 'Конпеки-Плаза', 'kind': 'corporate',
     'district_id': 'city-center-downtown', 'x': 425, 'y': 452,
     'description_en': 'Arasaka luxury hotel and corpo fortress.',
     'description_ru': 'Люксовый отель Arasaka и корпоративная крепость.',
     'source': 'Cyberpunk 2077'},
    {'id': 'arasaka-tower', 'name_en': 'Arasaka Tower', 'name_ru': 'Башня Арасака', 'kind': 'corporate',
     'district_id': 'city-center-corpo-plaza', 'x': 558, 'y': 486,
     'description_en': 'The monolithic heart of Arasaka in Night City.',
     'description_ru': 'Монолитное сердце Arasaka в Найт-Сити.',
     'source': 'Cyberpunk 2077'},
    {'id': 'megabuilding-h10', 'name_en': 'Megabuilding H10', 'name_ru': 'Мегаздание H10', 'kind': 'landmark',
     'district_id': 'watson-little-china', 'x': 520, 'y': 280,
     'description_en': 'Residential megabuilding in Little China.',
     'description_ru': 'Жилое мегаздание в Маленьком Китае.',
     'source': 'Cyberpunk 2077'},
    {'id': 'megabuilding-h8', 'name_en': 'Megabuilding H8', 'name_ru': 'Мегаздание H8', 'kind': 'landmark',
     'district_id': 'heywood-vista-del-rey', 'x': 610, 'y': 550,
     'description_en': 'Residential megabuilding in Vista del Rey.',
     'description_ru': 'Жилое мегаздание в Виста-дель-Рей.',
     'source': 'Cyberpunk 2077'},
    {'id': 'grand-imperial-mall', 'name_en': 'Grand Imperial Mall', 'name_ru': 'Гранд Империал Молл', 'kind': 'market',
     'district_id': 'pacifica-coastview', 'x': 485, 'y': 705,
     'description_en': 'Ruined Pacifica mall taken over by the Voodoo Boys.',
     'description_ru': 'Разрушенный молл Пасифики под контролем Voodoo Boys.',
     'source': 'Cyberpunk 2077'},
    {'id': 'viktor-clinic', 'name_en': "Viktor's Clinic", 'name_ru': 'Клиника Виктора', 'kind': 'clinic',
     'district_id': 'watson-little-china', 'x': 508, 'y': 300,
     'description_en': 'Ripperdoc clinic trusted by local mercs.',
     'description_ru': 'Клиника риппердока, которой доверяют местные наёмники.',
     'source': 'Cyberpunk 2077'},
    {'id': 'mistys-esoterica', 'name_en': "Misty's Esoterica", 'name_ru': 'Эзотерика Мисти', 'kind': 'service',
     'district_id': 'watson-little-china', 'x': 535, 'y': 288,
     'description_en': 'Occult shop and tarot readings.',
     'description_ru': 'Оккультная лавка и расклады Таро.',
     'source': 'Cyberpunk 2077'},
    {'id': 'no-tell-motel', 'name_en': 'No-Tell Motel', 'name_ru': 'Мотель No-Tell', 'kind': 'service',
     'district_id': 'watson-northside-industrial', 'x': 640, 'y': 120,
     'description_en': 'Cheap no-questions-asked motel.',
     'description_ru': 'Дешёвый мотель без лишних вопросов.',
     'source': 'Cyberpunk 2077'},
    {'id': 'delamain-hq', 'name_en': 'Delamain HQ', 'name_ru': 'Штаб Delamain', 'kind': 'service',
     'district_id': 'city-center-downtown', 'x': 450, 'y': 470,
     'description_en': 'Delamain taxi corporation headquarters.',
     'description_ru': 'Штаб корпорации такси Delamain.',
     'source': 'Cyberpunk 2077'},
    {'id': 'biotechnica-flats', 'name_en': 'Biotechnica Flats', 'name_ru': 'Поля Biotechnica', 'kind': 'corporate',
     'district_id': 'badlands-near-santo-domingo', 'x': 885, 'y': 700,
     'description_en': 'Biotechnica protein farms in the Badlands.',
     'description_ru': 'Протеиновые фермы Biotechnica в Пустошах.',
     'source': 'Cyberpunk 2077'},
    {'id': 'maelstrom-hangout', 'name_en': 'Maelstrom Hangout', 'name_ru': 'База Maelstrom', 'kind': 'gang',
     'district_id': 'watson-northside-industrial', 'x': 600, 'y': 150,
     'description_en': 'Chrome-obsessed Maelstrom turf in Northside.',
     'description_ru': 'Территория помешанных на хроме Maelstrom в Нортсайде.',
     'source': 'Campaign seed'},
    {'id': 'tyger-claws-den', 'name_en': 'Tyger Claws Den', 'name_ru': 'Логово Tyger Claws', 'kind': 'gang',
     'district_id': 'westbrook-japantown', 'x': 675, 'y': 360,
     'description_en': 'Tyger Claws operation in Japantown.',
     'description_ru': 'Точка Tyger Claws в Джапантауне.',
     'source': 'Campaign seed'},
    {'id': 'voodoo-boys-temple', 'name_en': 'Voodoo Boys Temple', 'name_ru': 'Храм Voodoo Boys', 'kind': 'gang',
     'district_id': 'pacifica-west-wind-estate', 'x': 435, 'y': 820,
     'description_en': 'The Voodoo Boys hold their turf in Pacifica.',
     'description_ru': 'Voodoo Boys держат свою территорию в Пасифике.',
     'source': 'Campaign seed'},
    {'id': 'dynalar-clinic', 'name_en': 'Dynalar Clinic', 'name_ru': 'Клиника Dynalar', 'kind': 'clinic',
     'district_id': 'city-center-corpo-plaza', 'x': 545, 'y': 505,
     'description_en': 'Corporate-grade ripperdoc services.',
     'description_ru': 'Риппердок-услуги корпоративного уровня.',
     'source': 'Campaign seed'},
]


def ensure_seed_locations(conn):
    """Idempotently seed canonical Night City points of interest."""
    now = time.time()
    for item in NC_SEED_LOCATIONS:
        conn.execute(
            'INSERT OR IGNORE INTO locations(id,name_en,name_ru,kind,district_id,x,y,'
            'description_en,description_ru,source,custom,owner_user_id,archived,created,updated) '
            'VALUES(?,?,?,?,?,?,?,?,?,?,0,NULL,0,?,?)',
            (item['id'], item['name_en'], item['name_ru'], item['kind'],
             item['district_id'], item['x'], item['y'],
             item['description_en'], item['description_ru'], item['source'], now, now))


def clean_location_input(body, existing=None):
    base = dict(existing or {})
    get = lambda key, default='': (body or {}).get(key, base.get(key, default))
    name_en = str(get('name_en') or '').strip()[:120]
    if len(name_en) < 2:
        raise ApiError(400, 'Локации нужно название')
    kind = str(get('kind') or 'other').strip().lower()
    if kind not in LOCATION_KINDS:
        raise ApiError(400, 'Неизвестный тип локации')
    district_id = str(get('district_id') or '').strip().lower()
    if district_id and district_id not in NC_LOCATION_IDS:
        raise ApiError(400, 'Некорректная локация Night City')
    try:
        x = float(get('x', 500))
        y = float(get('y', 500))
    except (TypeError, ValueError):
        raise ApiError(400, 'Некорректные координаты локации')
    if not math.isfinite(x) or not math.isfinite(y):
        raise ApiError(400, 'Некорректные координаты локации')
    return {
        'name_en': name_en,
        'name_ru': str(get('name_ru') or '').strip()[:120],
        'kind': kind,
        'district_id': district_id,
        'x': max(0.0, min(1000.0, x)),
        'y': max(0.0, min(1000.0, y)),
        'description_en': str(get('description_en') or '').strip()[:5000],
        'description_ru': str(get('description_ru') or '').strip()[:5000],
        'source': str(get('source') or '').strip()[:160],
    }


def location_payload(row, user):
    return {
        'id': row['id'], 'name_en': row['name_en'], 'name_ru': row['name_ru'],
        'kind': row['kind'], 'district_id': row['district_id'],
        'x': row['x'], 'y': row['y'],
        'description_en': row['description_en'], 'description_ru': row['description_ru'],
        'source': row['source'], 'custom': bool(row['custom']),
        'archived': bool(row['archived']),
        'can_edit': bool(user and user_is_gm(user) and row['custom']),
        'can_delete': bool(user and user_is_gm(user) and not row['archived']),
        'created': row['created'], 'updated': row['updated'],
    }

#!/usr/bin/env python3
"""NC//NET · генератор листа персонажа Cyberpunk RED / CEMK 2070

Версия 2 (2026-09, редизайн с нуля):
- 01 ДОСЬЕ — досье от фиксера: кто это, как выглядит, что внутри, откуда, как работает, связи, приводы, оценка фиксера, автосводка, заметки
- 02 ИГРА — всё для стола на одном листе: статы (62), производные, быстрый бой, оружие в руках (4), навыки (66+6) с проверками
- 03 КАМПАНИЯ — учёт: хром детально, оружие/броня мастер, инвентарь 20, касса 20, крит-травмы 10, зависимости/репутация/IP, улучшения IP, лог дел 14, долги/цели/табу
- КАТАЛОГ / СПРАВКА / ПРАВИЛА — скрытые служебные, на них ссылаются формулы (1092 позиции)

Два файла:
- NC-NET_CharSheet_2070.xlsx — пустой универсальный
- NC-NET_CharSheet_2070_EXAMPLE_Lawman.xlsx — пример (законник Dose, бывший NCPD, сейчас решает вопросы в Хейвуде)

Дизайн: HUD Night City, чёрный #0B0B0E, красный #FF003C, янтарь #FFB100/#FFD24A, белый.
Шрифты: Oswald, Roboto, Roboto Mono. Альбомная, печать по ширине.
"""
import json
import os
import re
import shutil
import sys
import tempfile

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app'))
import rules as RULES  # noqa: E402

# ---------------- палитра HUD
PAL = dict(
    ink='FFFFFF', muted='A6ABB2', accent='FF003C',
    banner_bg='0A0A0C', banner2_bg='141419',
    h1_bg='3A0512', h2_bg='141419', head_bg='0A0A0C', head_fg='FFB100',
    label_bg='141419', label_fg='A6ABB2', text_bg='0B0B0E', text_fg='FFFFFF',
    input_bg='1F1706', input_fg='FFD24A', auto_bg='101017', auto_fg='FFFFFF',
    cell_bg='0B0B0E', cell_fg='FFFFFF', note_fg='8F959C',
    kv_bg='1B1B22', border='2E2E38', input_edge='FFB100',
    ok_bg='241C00', ok_fg='FFC94D', warn_bg='3A0512', warn_fg='FF5C78',
    tab='FF003C', gold='FFB100',
)
DISPLAY='Oswald'; MONO='Roboto Mono'; SANS='Roboto'
CASH_FMT='#,##0" €$"'

def make_styles():
    thin = Side(style='thin', color=PAL['border'])
    cell_edge = Border(left=thin, right=thin, top=thin, bottom=thin)
    input_edge = Border(bottom=Side(style='thin', color=PAL['input_edge']),
                        left=Side(style='medium', color=PAL['input_edge']),
                        right=thin, top=thin)
    return {
        'banner': dict(font=Font(name=DISPLAY, size=15, bold=True, color=PAL['ink']),
                       fill=PatternFill('solid', start_color=PAL['banner_bg']),
                       align=Alignment(horizontal='center', vertical='center', wrap_text=True),
                       border=Border(bottom=Side(style='medium', color=PAL['accent']))),
        'banner2': dict(font=Font(name=DISPLAY, size=11, color=PAL['ink']),
                        fill=PatternFill('solid', start_color=PAL['banner2_bg']),
                        align=Alignment(horizontal='center', vertical='center', wrap_text=True)),
        'title': dict(font=Font(name=DISPLAY, size=24, bold=True, color=PAL['ink']),
                      align=Alignment(horizontal='left', vertical='center')),
        'h1': dict(font=Font(name=DISPLAY, size=13, bold=True, color=PAL['ink']),
                   fill=PatternFill('solid', start_color=PAL['h1_bg']),
                   align=Alignment(horizontal='left', vertical='center'),
                   border=Border(left=Side(style='medium', color=PAL['accent']))),
        'h2': dict(font=Font(name=DISPLAY, size=11, bold=True, color=PAL['gold']),
                   fill=PatternFill('solid', start_color=PAL['h2_bg']),
                   align=Alignment(horizontal='left', vertical='center')),
        'head': dict(font=Font(name=DISPLAY, size=10, bold=True, color=PAL['head_fg']),
                     fill=PatternFill('solid', start_color=PAL['head_bg']),
                     align=Alignment(horizontal='center', vertical='center', wrap_text=True),
                     border=Border(bottom=Side(style='thin', color=PAL['accent']))),
        'label': dict(font=Font(name=MONO, size=10, bold=True, color=PAL['label_fg']),
                      fill=PatternFill('solid', start_color=PAL['label_bg']),
                      align=Alignment(horizontal='left', vertical='center', wrap_text=True)),
        'text': dict(font=Font(name=SANS, size=11, color=PAL['text_fg']),
                     fill=PatternFill('solid', start_color=PAL['text_bg']),
                     align=Alignment(horizontal='left', vertical='top', wrap_text=True)),
        'input': dict(font=Font(name=SANS, size=11, color=PAL['input_fg']),
                      fill=PatternFill('solid', start_color=PAL['input_bg']),
                      align=Alignment(horizontal='left', vertical='center', wrap_text=True),
                      border=input_edge),
        'inputc': dict(font=Font(name=MONO, size=11, bold=True, color=PAL['input_fg']),
                       fill=PatternFill('solid', start_color=PAL['input_bg']),
                       align=Alignment(horizontal='center', vertical='center'),
                       border=input_edge),
        'auto': dict(font=Font(name=MONO, size=11, bold=True, color=PAL['auto_fg']),
                     fill=PatternFill('solid', start_color=PAL['auto_bg']),
                     align=Alignment(horizontal='center', vertical='center'),
                     border=cell_edge),
        'auto_l': dict(font=Font(name=MONO, size=10, color=PAL['auto_fg']),
                       fill=PatternFill('solid', start_color=PAL['auto_bg']),
                       align=Alignment(horizontal='left', vertical='center', wrap_text=True),
                       border=cell_edge),
        'cell': dict(font=Font(name=SANS, size=10, color=PAL['cell_fg']),
                     fill=PatternFill('solid', start_color=PAL['cell_bg']),
                     align=Alignment(horizontal='left', vertical='center', wrap_text=True),
                     border=cell_edge),
        'cellc': dict(font=Font(name=MONO, size=10, color=PAL['cell_fg']),
                      fill=PatternFill('solid', start_color=PAL['cell_bg']),
                      align=Alignment(horizontal='center', vertical='center'),
                      border=cell_edge),
        'note': dict(font=Font(name=SANS, size=10, italic=True, color=PAL['note_fg']),
                     fill=PatternFill('solid', start_color=PAL['text_bg']),
                     align=Alignment(horizontal='left', vertical='center', wrap_text=True)),
        'kv': dict(font=Font(name=MONO, size=10, bold=True, color=PAL['ink']),
                   fill=PatternFill('solid', start_color=PAL['kv_bg']),
                   align=Alignment(horizontal='left', vertical='center', wrap_text=True),
                   border=cell_edge),
    }

STYLES = make_styles()
THIN = Side(style='thin', color=PAL['border'])

def put(ws, ref, value=None, *, kind='cell', fmt=None):
    cell = ws[ref]
    # never write into merged non-top-left — skip silently
    if type(cell).__name__ == 'MergedCell':
        return cell
    if value is not None:
        cell.value = value
    s = STYLES[kind]
    if 'font' in s: cell.font = s['font']
    if 'fill' in s: cell.fill = s['fill']
    if 'align' in s: cell.alignment = s['align']
    if 'border' in s: cell.border = s['border']
    if fmt: cell.number_format = fmt
    return cell

def mput(ws, rng, value=None, *, kind='cell', fmt=None):
    # unmerge overlapping first to avoid MergedCell error
    to_unmerge = []
    for mr in list(ws.merged_cells.ranges):
        if mr.coord == rng:
            to_unmerge.append(mr.coord)
    for c in to_unmerge:
        try: ws.unmerge_cells(c)
        except: pass
    if ':' in rng:
        start, end = rng.split(':')
        from openpyxl.utils import range_boundaries
        min_col, min_row, max_col, max_row = range_boundaries(rng)
        for r in range(min_row, max_row+1):
            for cc in range(min_col, max_col+1):
                ref = f"{get_column_letter(cc)}{r}"
                if ref == start:
                    continue
                c = ws[ref]
                if type(c).__name__ == 'MergedCell':
                    continue
                s = STYLES[kind]
                if 'font' in s: c.font = s['font']
                if 'fill' in s: c.fill = s['fill']
                if 'align' in s: c.alignment = s['align']
                if 'border' in s: c.border = s['border']
        ws.merge_cells(rng)
    return put(ws, rng.split(':')[0], value, kind=kind, fmt=fmt)

def box(ws, rng, color=PAL['ink'], weight='thin'):
    side = Side(style=weight, color=color)
    from openpyxl.utils import range_boundaries
    min_col, min_row, max_col, max_row = range_boundaries(rng)
    for r in range(min_row, max_row+1):
        for c in range(min_col, max_col+1):
            cell = ws.cell(row=r, column=c)
            b = cell.border
            cell.border = Border(left=side if c==min_col else b.left,
                                 right=side if c==max_col else b.right,
                                 top=side if r==min_row else b.top,
                                 bottom=side if r==max_row else b.bottom)

def widths(ws, mapping):
    for col, w in mapping.items(): ws.column_dimensions[col].width = w
def heights(ws, mapping):
    for row, h in mapping.items(): ws.row_dimensions[row].height = h

def dv_list(ws, rng, values):
    clean = [v.replace('"','') for v in values if v]
    if not clean: return
    dv = DataValidation(type='list', formula1='"' + ','.join(clean) + '"', allow_blank=True, showDropDown=False)
    ws.add_data_validation(dv); dv.add(rng)
def dv_catalog(ws, rng, last):
    dv = DataValidation(type='list', formula1=f"='КАТАЛОГ'!$A$2:$A${last}", allow_blank=True, showDropDown=False, showErrorMessage=False)
    ws.add_data_validation(dv); dv.add(rng)
def dv_num(ws, rng, mn, mx):
    dv = DataValidation(type='whole', operator='between', formula1=str(mn), formula2=str(mx), allow_blank=True)
    ws.add_data_validation(dv); dv.add(rng)
def cf(ws, rng, formula, bg, fg):
    ws.conditional_formatting.add(rng, FormulaRule(formula=[formula], fill=PatternFill('solid', start_color=bg), font=Font(name=MONO, bold=True, color=fg)))

def sheet_setup(ws, tab_color, freeze=None):
    ws.sheet_view.showGridLines=False
    ws.sheet_properties.tabColor=tab_color
    if freeze: ws.freeze_panes=freeze
    ws.page_setup.orientation='landscape'
    ws.sheet_properties.pageSetUpPr.fitToPage=True
    ws.page_setup.fitToWidth=1; ws.page_setup.fitToHeight=0
    ws.sheet_view.zoomScale=95

# ---------------- sheet names & constants
S_DOC="'01 ДОСЬЕ'"; S_PLAY="'02 ИГРА'"; S_CAMP="'03 КАМПАНИЯ'"; S_CAT="'КАТАЛОГ'"; S_REF="'СПРАВКА'"; S_RUL="'ПРАВИЛА'"
NAMES={'doc':'01 ДОСЬЕ','play':'02 ИГРА','camp':'03 КАМПАНИЯ','cat':'КАТАЛОГ','ref':'СПРАВКА','rul':'ПРАВИЛА'}

PLAY_STAT_FIRST=7; PLAY_STAT_LAST=16
CAMP_CHR_FIRST=9; CAMP_CHR_LAST=22
CAMP_W_FIRST=48; CAMP_W_LAST=55
CAMP_A_FIRST=60; CAMP_A_LAST=65
CAMP_I_FIRST=72; CAMP_I_LAST=91
CAMP_CASH_FIRST=96; CAMP_CASH_LAST=115
CAMP_CRIT_FIRST=120; CAMP_CRIT_LAST=129
CAT_LAST=1

def set_ranges():
    global BASEB, BASEF, SKLC, SKLI, CATA, CATB, CATC, CATD, CATE, CATF, CATG, CATH, CATI, CATJ, CATK, CATL, CATM, CATN, CATR, CATT
    BASEB=f"{S_PLAY}!$B${PLAY_STAT_FIRST}:$B${PLAY_STAT_LAST}"
    BASEF=f"{S_PLAY}!$F${PLAY_STAT_FIRST}:$F${PLAY_STAT_LAST}"
    SKLC=f"{S_PLAY}!$C$35:$C$100"
    SKLI=f"{S_PLAY}!$I$35:$I$100"
    for letter in 'ABCDEFGHIJKLMNOPQRST':
        globals()['CAT'+letter]=f"{S_CAT}!${letter}$2:${letter}${CAT_LAST}"

# ---------------- catalog helpers
CAT_HEAD=['НАЗВАНИЕ','КАТЕГОРИЯ','ПОДТИП (TYPE)','НАВЫК','УРОН','ROF','МАГ.','SP','HP','ШТРАФ REF','ШТРАФ DEX','ШТРАФ MOVE','HL','УСТАНОВКА','РУКИ','СКРЫТНОСТЬ','КАЧЕСТВО','ЦЕНА €$','ИСТОЧНИК','ОПИСАНИЕ']
def _num_first(t):
    if t is None: return None
    import re
    m=re.search(r'-?\d+(?:[.,]\d+)?', str(t)); return float(m.group(0).replace(',','.')) if m else None
def _penalty(fields, stat):
    import re
    m=re.search(r'(-?\d+)\s*'+stat, str(fields.get('Penalty') or '')); return int(m.group(1)) if m else 0
def _sp_hp(fields):
    import re
    raw=str(fields.get('SP') or ''); sp=re.search(r'(\d+)\s*SP', raw); hp=re.search(r'(\d+)\s*HP', raw)
    return (int(sp.group(1)) if sp else None, int(hp.group(1)) if hp else None)
def skill_for_item(item):
    mech=item.get('mechanics') or {}; s=mech.get('skill'); 
    if s: return s
    sub=str((item.get('fields') or {}).get('Type') or '')
    if 'Melee' in sub: return 'Melee Weapon'
    if 'Bow' in sub or 'Crossbow' in sub: return 'Archery'
    return ''
def catalog_rows(data):
    cats={c['id']:c for c in data['cats']}; rows=[]
    for it in data['items']:
        f=it.get('fields') or {}; m=it.get('mechanics') or {}; cat=cats.get(it['cat'],{})
        sp,hp=_sp_hp(f)
        desc=re.sub(r'\s+',' ', str(it.get('desc') or '')).strip()
        rows.append([it['name'], cat.get('ru') or it['cat'], str(f.get('Type') or '').replace('\n',' · '),
                     skill_for_item(it),
                     m.get('damage',{}).get('notation') if isinstance(m.get('damage'),dict) else (it.get('damage') or f.get('Damage') or ''),
                     m.get('rof') or '', m.get('magazine') or f.get('Mag') or '',
                     sp if sp is not None else '', hp if hp is not None else '',
                     _penalty(f,'REF'), _penalty(f,'DEX'), _penalty(f,'MOVE'),
                     _num_first(f.get('HL')) or 0, f.get('Install') or '',
                     m.get('hands') or f.get('Hands') or '', m.get('concealable') or f.get('Conceal') or '',
                     m.get('quality') or f.get('Quality') or '',
                     it.get('price') if it.get('price') is not None else '',
                     str(it.get('source') or '').replace('\n',' · '), desc[:220]])
    rows.sort(key=lambda r:(r[1], r[0]))
    # dedupe
    seen={}; out=[]
    for row in rows:
        name=row[0]
        if name in seen:
            tag=f"{name} ({row[1]})"
            n=2
            while tag in seen:
                tag=f"{name} ({row[1]} {n})"
                n+=1
            row[0]=tag
        seen[row[0]]=True
        out.append(row)
    return out

# ---------------- example data — fixer style
EXAMPLE_DOSSIER={
    'handle':'Дозе / Dose',
    'real_name':'Джек Моррисон',
    'role':'Законник (ex-NCPD) — сейчас решает вопросы в Хейвуде',
    'rank':'Ранг 4 · Backup: вызов 1d10 ≤4',
    'player':'Алексей',
    'age':'34 / 12.03.2036',
    'native_lang':'Английский (родной 4) + Streetslang',
    'cultural':'Северная Америка, Найт-Сити',
    'district':'Хейвуд — боевые зоны',
    'clothing':'Nomad Leathers — куртка детектива, зеркальные очки, всё поверх Light Armorjack',
    'height':'180 / 78 / худощавый, подтянутый',
    'visible_chrome':'Тату-значок NCPD на предплечье (выцветшая), биомонитор, остальное внутри',
    'marks':'Шрам через левую бровь, сломанный нос, сухая правая кисть — старая холодовая травма',
    'voice':'Низкий, ровный, «голос протокола» — короткими фразами',
    'contact':'Agent (Standard): отвечает всегда, номер дают только свои',
    'housing':'Грузовой контейнер в боевых зонах Хейвуда · Kibble Lifestyle · 1100 к 1-му числу',
    'personality':'Старый коп с протоколом вместо сердца. Говорит тихо, смотрит в глаза, не повышает голос. Сначала слушает, потом решает.',
    'values':'Порядок. Не закон — порядок: чтобы человек мог дойти до дома по своей улице.',
    'attitude':'Считает, что большинство не злые, а испуганные. Ошибается реже, чем боится.',
    'moral':'5 — ЖЁСТКИЙ: гнёт правила ради результата. Лишнего не делает, но и не мучается.',
    'goal':'Закрыть дело о корпоративном складе, из-за которого вылетел из управления, и вернуть имя.',
    'never':'Не тронет ребёнка. Не сдаст того, кто доверился — даже если стоило значка.',
    'flaw':'Старые связи: звонок «Джек, надо» — и он едет, даже если чует подставу.',
    'family':'Вырос в боевых зонах Хейвуда: мать — медсестра в бесплатной клинике, отец ушёл в банду и не вернулся.',
    'crisis':'Мать погибла от шальной пули в перекрёстном огне — в тот год подал в академию NCPD.',
    'friends':'Двое: сержант из архива, который всё ещё берёт трубку, и брат бывшего напарника, который его ненавидит.',
    'romance':'Разведён. Жена не выдержала графика и того, что приносил работу домой.',
    'enemies':'СБ корпы со склада и бустерганг «Ржавые Псы», которых не смог закрыть по закону.',
    'turning':'День, когда вышел из кабинета начальника после приказа закрыть дело — и понял, что обратно нет.',
    'position':'Бывший уголовный следователь',
    'jurisdiction':'Боевые зоны',
    'corruption':'Честная, но суровая — за это и выкинули',
    'hunted_by':'Организованная преступность',
    'goal_dept':'Организованная преступность',
    'left_service':'Вёл поставки оружия в боевые зоны, докопался до корпоративного склада. Сверху приказали закрыть — отказался. Через месяц «по собственному», без значка.',
    'hidden':'Знает, чем торговал склад и чья фамилия в деле из управления. Доказательств нет — молчит и ищет.',
    'connections':'Сержант из архива — копии закрытых дел за бутылку. Медэксперт — осмотрит тихо, без следа в системе.',
    'subscriptions':'Наличных на старте 0. Контейнер 1000 + Kibble 100 = 1100 к 1-му. Trauma Team не по карману.',
    'hunting_you':'СБ того склада — умеет ждать. «Ржавые Псы», которых тогда не закрыл.',
    'reputation':'В боевых зонах знают как копа, который не брал процент и не сдавал своих. Надёжный, но упрямый.',
    'employer':'Работает через фиксера средней руки (имя впиши). Берёт «левые» дела, если понимает, кто пострадает.',
    'work_rules':'Три вопроса перед делом: кто пострадает, кто платит, что будет если откажется. Детей и копов не трогает.',
    'takes':'Дела про порядок на улицах, пропавших, корпоративные хвосты, которые копы не закроют. Не берёт заказы на детей и на своих.',
    'price':'Дороже, если надо идти против бывших. Дешевле, если дело про Хейвуд.',
    'reliability':'Высокая. Если сказал «буду» — приедет. Если сказал «нет» — не переубедишь.',
    'contacts':[
        ('Сержант в архиве NCPD','Старый сослуживец','Бар «У Дока», Хейвуд · вторники','Копии закрытых дел, адреса'),
        ('Медэксперт со старых дел','Должник','Клиника в Хейвуде, без записи','Осмотрит, зашьёт, без следа'),
        ('Фиксер средней руки','Работодатель','Через Агента','Контракты, наводки'),
        ('Информатор «Птица»','Осведомитель','Уотсон, у рынка','Кто где стоит, кто кого заказал'),
    ],
    'incidents':[
        ('12.03.2068','Превышение полномочий','Задержал корпората без ордера','Выговор','Архив'),
        ('08.11.2069','Дело о складе #77-Б','Поставки оружия, связь с корпой','Дело изъято','NCPD IA / В работе'),
        ('15.01.2070','Отставка','По собственному желанию','Без значка','NCPD HR'),
    ],
    'threat_level':'СРЕДНИЙ · Вооружён, обучен, доступ к архивам',
    'threat_armed':'Unity (Heavy Pistol), Satara (Shotgun) · Light Armorjack + Shield',
    'threat_chrome':'Neuroport, Cyberaudio Suite + стресс-анализатор, усилитель слуха, токсин-байдеры · Biomonitor, тату, EMP Threading',
    'threat_psych':'Стабилен, на грани. Триггер: сирена + запах горелого пластика — переулок, где погиб напарник.',
    'threat_affil':'Бывший NCPD, связи в архиве, работает через фиксера · В бандах не состоит',
    'notes':'Рекомендация фиксера: можно давать дела, где нужен порядок, а не резня. Не провоцировать, не давить на тему склада. При задержании — вызывать C-SWAT только если совсем припрёт.',
}
EXAMPLE_STATS={'INT':8,'WILL':7,'COOL':7,'EMP':5,'TECH':3,'REF':8,'LUCK':2,'BODY':8,'DEX':8,'MOVE':6}
EXAMPLE_SKILLS={'Concentration':2,'Perception':6,'Tracking':4,'Athletics':2,'Criminology':5,'Deduction':5,'Education':2,'Language':2,'Local Expert':2,'Brawling':5,'Evasion':6,'Martial Arts':5,'Autofire':2,'Handgun':6,'Shoulder Arms':5,'Conversation':2,'Human Perception':2,'Interrogation':5,'Persuasion':5,'Streetwise':2,'First Aid':2}
EXAMPLE_SKILL_SPECS={'Language':'Streetslang','Local Expert':'Хейвуд','Martial Arts':'Thamoc'}
EXAMPLE_CHROME=['Neuroport','Cyberaudio Suite','Voice Stress Analyzer','Amplified Hearing','Toxin Binders','Biomonitor','Radio Communicator','Light Tattoo','EMP Threading']
EXAMPLE_WEAPONS=[('Con Arms Unity','Basic ×40','Standard','1'),('Rostović DB-2 Satara','Basic ×20','Standard','2')]
EXAMPLE_ARMOR=[('Light Armorjack','Тело','Да'),('Light Armorjack','Голова','Да'),('Bulletproof Shield','Щит','Да')]
EXAMPLE_INVENTORY=[
    ('Con Arms Unity','в кобуре','',''),('Rostović DB-2 Satara','за спиной','',''),('Handcuffs','на поясе','',''),
    ('Basic','подсумок','6','40 пист + 20 картечи'),('Agent (Standard)','карман','',''),('Medtech Bag','в багажнике','',''),
    ('Flashlight','на поясе','',''),('Duct Tape','на поясе','',''),('Bulletproof Shield','в руке','',''),
    ('Nomad Leathers Jacket','детектив','',''),('Nomad Leathers Bottoms','детектив','',''),('Nomad Leathers Footwear','детектив','',''),
    ('Nomad Leathers Top','детектив','',''),('Nomad Leathers Mirrorshades','детектив','',''),
    ('Generic Chic Jacket','рабочий','',''),('Generic Chic Bottoms','рабочий','',''),('Generic Chic Top','рабочий','',''),
    ('Generic Chic Footwear','рабочий','',''),('Generic Chic Hats','рабочий','',''),
]

STAT_INFO=[
    ('INT','Интеллект','Ум, восприятие, обучение. База для Perception, Education, Local Expert и ещё 20+ навыков.'),
    ('WILL','Воля','Решимость и стрессоустойчивость. Входит в HP. База Concentration, Endurance.'),
    ('COOL','Хладнокровие','Характер и харизма. База Persuasion, Streetwise, Interrogation.'),
    ('EMP','Эмпатия','Сопереживание. Humanity = EMP×10. Падает десятками.'),
    ('TECH','Техника','Инструменты и электроника: Basic Tech, Cybertech, First Aid.'),
    ('REF','Реакция','Координация и прицеливание. Инициатива, дальние атаки. Штраф брони сюда.'),
    ('LUCK','Удача','Пул на любой бросок до броска. Восстанавливается в начале партии.'),
    ('BODY','Тело','Сила и живучесть. Входит в HP, спасбросок смерти.'),
    ('DEX','Ловкость','Баланс, прыжки, ближний бой, уклонение. Штраф брони сюда.'),
    ('MOVE','Скорость','MOVE×2 м за Move Action. Штраф брони сюда.'),
]

# ================================================= 01 ДОСЬЕ — FIXER
def build_dossier(wb, example=False, cat_last=1):
    ws = wb.create_sheet(NAMES['doc'])
    widths(ws, {'A':2,'B':22,'C':34,'D':20,'E':34,'F':22,'G':38,'H':2})
    sheet_setup(ws, PAL['accent'], freeze='A4')
    mput(ws,'B1:G1','NC-NET  ▚  FIXER DATABASE  ▚  ДОСЬЕ ЭДЖРАННЕРА  ▚  2070  ▚  ДОСТУП: ОГРАНИЧЕННЫЙ', kind='banner'); heights(ws,{1:30})
    mput(ws,'B2:G2','Фиксер: смотри, кого берёшь на дело. Это не резюме — это то, как человек работает на улице.', kind='banner2'); heights(ws,{2:18})
    mput(ws,'B3:C3','Д О С Ь Е  ·  FIXER', kind='title')
    put(ws,'D3','СТАТУС:',kind='kv'); put(ws,'E3','АКТИВЕН' if not example else 'АКТИВЕН',kind='inputc'); dv_list(ws,'E3',['АКТИВЕН','НАБЛЮДЕНИЕ','ПРОВЕРИТЬ','В ЧЁРНОМ СПИСКЕ','МЁРТВ'])
    put(ws,'F3','ДЕЛО №',kind='kv'); put(ws,'G3','NC-2070-' if not example else 'NC-2070-DOSE-04',kind='input'); heights(ws,{3:32})
    mput(ws,'F4:G12','ФОТО ОБЪЕКТА\n\n(правый клик → Заменить изображение)\nРекоменд. 460×250',kind='note'); box(ws,'F4:G12',color=PAL['accent'],weight='medium')

    ex = EXAMPLE_DOSSIER if example else {}
    ident=[
        ('ПОЗЫВНОЙ / HANDLE','handle','ИМЯ / ФАМИЛИЯ','real_name'),
        ('РОЛЬ / ЧЕМ ЖИВЁТ','role','РАНГ / ЧТО УМЕЕТ','rank'),
        ('ИГРОК','player','ВОЗРАСТ / ДАТА РОЖДЕНИЯ','age'),
        ('РОДНОЙ ЯЗЫК (4 БЕСПЛ.)','native_lang','КОРНИ','cultural'),
        ('РАЙОН (LOCAL EXPERT)','district','СТИЛЬ ОДЕЖДЫ','clothing'),
        ('РОСТ / ВЕС / СЛОЖЕНИЕ','height','ХРОМ НА ВИДУ','visible_chrome'),
        ('ОСОБЫЕ ПРИМЕТЫ','marks','ГОЛОС / МАНЕРА','voice'),
        ('СВЯЗЬ / HOLOPHONE','contact','ЖИЛЬЁ / LIFESTYLE','housing'),
    ]
    r=4
    for left,kl,right,kr in ident:
        put(ws,f'B{r}',left,kind='kv'); put(ws,f'C{r}',ex.get(kl) if example else None,kind='input')
        put(ws,f'D{r}',right,kind='kv'); put(ws,f'E{r}',ex.get(kr) if example else None,kind='input')
        heights(ws,{r:26}); r+=1

    r=14
    mput(ws,f'B{r}:D{r}','I · КТО ЭТО — ПСИХОПОРТРЕТ',kind='h1')
    mput(ws,f'E{r}:G{r}','II · ОТКУДА — GENERAL LIFEPATH',kind='h1')
    left_psy=[('ЛИЧНОСТЬ','personality'),('ЧТО ЦЕНИТ','values'),('ОТНОШЕНИЕ К ЛЮДЯМ','attitude'),('МОРАЛЬНЫЙ КОМПАС','moral'),('ЦЕЛЬ ЖИЗНИ','goal'),('ЧЕГО НИКОГДА НЕ СДЕЛАЕТ','never'),('СЛАБОСТЬ / КРЮЧОК','flaw')]
    right_bio=[('СЕМЬЯ / ДЕТСТВО','family'),('СЕМЕЙНЫЙ КРИЗИС','crisis'),('ДРУЗЬЯ','friends'),('РОМАНТИКА','romance'),('ВРАГИ','enemies'),('ПЕРЕЛОМНЫЙ МОМЕНТ','turning')]
    for i in range(max(len(left_psy), len(right_bio))):
        rr=r+1+i
        if i < len(left_psy):
            put(ws,f'B{rr}',left_psy[i][0],kind='kv'); mput(ws,f'C{rr}:D{rr}',ex.get(left_psy[i][1]) if example else None,kind='input')
        if i < len(right_bio):
            put(ws,f'E{rr}',right_bio[i][0],kind='kv'); mput(ws,f'F{rr}:G{rr}',ex.get(right_bio[i][1]) if example else None,kind='input')
        heights(ws,{rr:30})
    r+=1+max(len(left_psy), len(right_bio))

    r+=1
    mput(ws,f'B{r}:G{r}','III · КАК РАБОТАЕТ — ОЦЕНКА ФИКСЕРА · УНИВЕРСАЛЬНО ДЛЯ ЛЮБОЙ РОЛИ (ПРИМЕР: LAWMAN EX-NCPD)',kind='h1'); r+=1
    # universal role lifepath but fixer wording
    lawman=[
        ('КЕМ БЫЛ / ДОЛЖНОСТЬ','position','Охранник','Патрульный','Уголовный следователь','Спецназ','Мотопатруль','Внутр. безопасность'),
        ('ГДЕ РАБОТАЛ / ЗОНА','jurisdiction','Корп зоны','Городской патруль','Боевые зоны','Окраины','Зоны восстановления','Шоссе'),
        ('ЧЕСТНОСТЬ ОТДЕЛА','corruption','Честная и этичная','Честная, но суровая','Редкие нарушения','Нарушает ради дела','Жёсткий контроль','Полностью коррумпирована'),
        ('КТО ДАВИЛ НА ОТДЕЛ','hunted_by','Органайзед','Бустерганги','Контроль полиции','Грязные политики','Контрабандисты','Уличные'),
        ('НАД ЧЕМ РАБОТАЛИ','goal_dept','Органайзед','Бустерганги','Наркоторговцы','Грязные политики','Контрабандисты','Уличная преступность'),
    ]
    for idx,(label,key,*opts) in enumerate(lawman):
        rr=r+idx//2
        if idx%2==0:
            put(ws,f'B{rr}',label,kind='kv'); put(ws,f'C{rr}',ex.get(key) if example else opts[2] if idx==0 else opts[0],kind='input'); dv_list(ws,f'C{rr}',opts)
        else:
            put(ws,f'D{rr}',label,kind='kv'); mput(ws,f'E{rr}:G{rr}',ex.get(key) if example else opts[0],kind='input'); dv_list(ws,f'E{rr}',opts)
        heights(ws,{rr:24})
    r+= (len(lawman)+1)//2 +1

    texts=[
        ('ЗА ЧТО УШЁЛ / ЧТО СЛУЧИЛОСЬ','left_service'),
        ('ЧТО СКРЫВАЕТ','hidden'),
        ('СВЯЗИ В УПРАВЛЕНИИ / НА УЛИЦЕ','connections'),
        ('ПОДПИСКИ И ТРАТЫ','subscriptions'),
        ('КТО НА НЕГО ОХОТИТСЯ','hunting_you'),
        ('РЕПУТАЦИЯ НА УЛИЦАХ','reputation'),
        ('ТЕКУЩИЙ ФИКСЕР / РАБОТОДАТЕЛЬ','employer'),
        ('ПРАВИЛА РАБОТЫ / БЕРЁТ-НЕ БЕРЁТ','work_rules'),
        ('ЧТО БЕРЁТ / НЕ БЕРЁТ','takes'),
        ('ЦЕНА ВОПРОСА','price'),
        ('НАДЁЖНОСТЬ','reliability'),
    ]
    for idx,(label,key) in enumerate(texts):
        rr=r+idx//2
        if idx%2==0:
            put(ws,f'B{rr}',label,kind='kv'); mput(ws,f'C{rr}:D{rr}',ex.get(key) if example else None,kind='input')
        else:
            put(ws,f'E{rr}',label,kind='kv'); mput(ws,f'F{rr}:G{rr}',ex.get(key) if example else None,kind='input')
        heights(ws,{rr:30})
    r+= (len(texts)+1)//2 +1

    mput(ws,f'B{r}:G{r}','IV · СВЯЗИ / КОГО ЗНАЕТ / ЧЕРЕЗ КОГО НАЙТИ',kind='h1'); r+=1
    put(ws,f'B{r}','КТО',kind='head'); put(ws,f'C{r}','РОЛЬ В ЖИЗНИ',kind='head'); mput(ws,f'D{r}:E{r}','КАК НАЙТИ',kind='head'); mput(ws,f'F{r}:G{r}','ЧЕМ ПОЛЕЗЕН / РИСК',kind='head'); r+=1
    for i in range(6):
        c = ex.get('contacts',[])[i] if example and i < len(ex.get('contacts',[])) else (None,None,None,None)
        put(ws,f'B{r}',c[0],kind='input'); put(ws,f'C{r}',c[1],kind='input'); mput(ws,f'D{r}:E{r}',c[2],kind='input'); mput(ws,f'F{r}:G{r}',c[3],kind='input'); heights(ws,{r:22}); r+=1
    r+=1
    mput(ws,f'B{r}:G{r}','V · ПРИВОДЫ / ДЕЛА — ЧТО ЗНАЕТ УЛИЦА',kind='h1'); r+=1
    put(ws,f'B{r}','ДАТА',kind='head'); put(ws,f'C{r}','СТАТЬЯ / ДЕЛО',kind='head'); mput(ws,f'D{r}:E{r}','ОБСТОЯТЕЛЬСТВА',kind='head'); put(ws,f'F{r}','РЕЗУЛЬТАТ',kind='head'); put(ws,f'G{r}','СТАТУС',kind='head'); r+=1
    for i in range(5):
        inc = ex.get('incidents',[])[i] if example and i < len(ex.get('incidents',[])) else (None,None,None,None,None)
        put(ws,f'B{r}',inc[0],kind='input'); put(ws,f'C{r}',inc[1],kind='input'); mput(ws,f'D{r}:E{r}',inc[2],kind='input'); put(ws,f'F{r}',inc[3],kind='input'); put(ws,f'G{r}',inc[4],kind='input'); heights(ws,{r:22}); r+=1
    r+=1
    mput(ws,f'B{r}:G{r}','VI · ОЦЕНКА ФИКСЕРА — МОЖНО ЛИ ДАВАТЬ ДЕЛО',kind='h1'); r+=1
    put(ws,f'B{r}','УРОВЕНЬ УГРОЗЫ',kind='kv'); put(ws,f'C{r}',ex.get('threat_level') if example else 'СРЕДНИЙ',kind='input'); dv_list(ws,f'C{r}',['НИЗКИЙ','СРЕДНИЙ','ВЫСОКИЙ','КРИТИЧЕСКИЙ','НЕИЗВЕСТЕН'])
    put(ws,f'D{r}','ВООРУЖЕНИЕ',kind='kv'); mput(ws,f'E{r}:G{r}',ex.get('threat_armed') if example else None,kind='input'); heights(ws,{r:24}); r+=1
    put(ws,f'B{r}','КИБЕРНЕТИКА',kind='kv'); mput(ws,f'C{r}:G{r}',ex.get('threat_chrome') if example else None,kind='input'); heights(ws,{r:24}); r+=1
    put(ws,f'B{r}','ПСИХО-ОЦЕНКА',kind='kv'); mput(ws,f'C{r}:G{r}',ex.get('threat_psych') if example else None,kind='input'); heights(ws,{r:24}); r+=1
    put(ws,f'B{r}','ПРИНАДЛЕЖНОСТЬ',kind='kv'); mput(ws,f'C{r}:G{r}',ex.get('threat_affil') if example else None,kind='input'); heights(ws,{r:24}); r+=1
    put(ws,f'B{r}','ЗАМЕТКА ФИКСЕРА',kind='kv'); mput(ws,f'C{r}:G{r}',ex.get('notes') if example else None,kind='input'); heights(ws,{r:24}); r+=2

    mput(ws,f'B{r}:G{r}','VII · СВОДКА С ИГРОВЫХ ЛИСТОВ — СЧИТАЕТСЯ АВТОМАТИЧЕСКИ',kind='h1'); r+=1
    summary=[
        ('HP ТЕКУЩИЕ / МАКС', f"={S_PLAY}!$I$8&\" / \"&{S_PLAY}!$I$7", 'ПОРОГ СЕРЬЁЗНО РАНЕН', f"={S_PLAY}!$I$9"),
        ('СПАСБРОСОК СМЕРТИ', f"={S_PLAY}!$I$10&\" − \"&{S_PLAY}!$I$11&\" штраф\"", 'HUMANITY ТЕКУЩАЯ / МАКС', f"={S_PLAY}!$I$18&\" / \"&{S_PLAY}!$I$16"),
        ('EMP ТЕКУЩАЯ', f"={S_PLAY}!$I$19", 'СОСТОЯНИЕ РАН', f"={S_PLAY}!$C$24"),
        ('БРОНЯ ГОЛОВА / ТЕЛО', f"={S_CAMP}!$D$66&\" / \"&{S_CAMP}!$D$67", 'ЩИТ HP', f"={S_CAMP}!$D$68"),
        ('ОСНОВНОЕ ОРУЖИЕ СЛОТ 1', f"=IFERROR(INDEX({S_CAMP}!$C$48:$C$55,MATCH(1,{S_CAMP}!$K$48:$K$55,0)),\"—\")", 'БАЗА АТАКИ', f"=IFERROR(INDEX({S_CAMP}!$L$48:$L$55,MATCH(1,{S_CAMP}!$K$48:$K$55,0)),\"—\")"),
        ('КРИТ-ТРАВМ АКТИВНО', f"=COUNTIF({S_CAMP}!$I$120:$I$129,\"Активна\")", 'НАЛИЧНЫЕ', f"={S_CAMP}!$D$5"),
        ('IP ЗАРАБОТАНО / СВОБОДНО', f"={S_CAMP}!$D$133&\" / \"&{S_CAMP}!$D$135", 'BACKUP РАНГ', f"={S_PLAY}!$J$2"),
    ]
    for lf,lv,rf,rv in summary:
        mput(ws,f'B{r}:C{r}',lf,kind='kv'); put(ws,f'D{r}',lv,kind='auto_l')
        mput(ws,f'E{r}:F{r}',rf,kind='kv'); put(ws,f'G{r}',rv,kind='auto_l'); heights(ws,{r:22}); r+=1
    r+=1
    mput(ws,f'B{r}:G{r}','VIII · ЗАМЕТКИ ФИКСЕРА / GM — СВОБОДНАЯ ЗАПИСЬ',kind='h1'); r+=1
    mput(ws,f'B{r}:G{r+2}',ex.get('notes') if example else None,kind='input'); heights(ws,{r:24,r+1:24,r+2:24}); r+=4
    mput(ws,f'B{r}:G{r}','IX · ГРАНИЦЫ БЕЗОПАСНОСТИ (LINES / VEILS / X-CARD)',kind='h1'); r+=1
    put(ws,f'B{r}','СТОП-ТЕМЫ',kind='kv'); mput(ws,f'C{r}:D{r}',None,kind='input'); put(ws,f'E{r}','УВОДИМ БЕЗ ДЕТАЛЕЙ',kind='kv'); mput(ws,f'F{r}:G{r}',None,kind='input'); heights(ws,{r:26}); r+=2
    mput(ws,f'B{r}:G{r}','ЗАПИСЬ ВЁЛ: ________________     ПЕЧАТЬ: NC//NET · 2070     ПОДПИСЬ GM: ________________',kind='note')
    mput(ws,f'B{r+1}:G{r+1}','ИСТОЧНИКИ: Cyberpunk RED Corebook · CEMK 2070 · Spes Desperata · NC-NET',kind='note')
    return ws

# ================================================= 02 ИГРА
def build_play(wb, example=False, cat_last=1):
    ws = wb.create_sheet(NAMES['play'])
    widths(ws, {'A':2,'B':9,'C':20,'D':8,'E':8,'F':8,'G':34,'H':24,'I':10,'J':34,'K':2,'L':20,'M':10,'N':6,'O':8,'P':12,'Q':14,'R':10,'S':28,'T':2})
    sheet_setup(ws, PAL['accent'], freeze='A7')
    mput(ws,'B1:S1','ИГРА  ▚  CYBERPUNK RED / CEMK 2070  ▚  ВСЁ ДЛЯ СТОЛА НА ОДНОМ ЛИСТЕ',kind='banner'); heights(ws,{1:28})
    mput(ws,'B2:C2','ПОЗЫВНОЙ',kind='kv'); put(ws,'D2',f"={S_DOC}!$C$4",kind='auto_l')
    mput(ws,'E2:F2','РОЛЬ',kind='kv'); mput(ws,'G2:H2',f"={S_DOC}!$C$5",kind='auto_l')
    put(ws,'I2','РАНГ',kind='kv'); put(ws,'J2',4 if example else None,kind='inputc'); dv_num(ws,'J2',1,10)
    mput(ws,'L2:M2','ИГРОК / СТАТУС',kind='kv'); mput(ws,'N2:S2',f"={S_DOC}!$C$6&\" · \"&{S_DOC}!$E$3",kind='auto_l'); heights(ws,{2:22})
    mput(ws,'B3:C3','СВЯЗЬ',kind='kv'); mput(ws,'D3:H3',f"={S_DOC}!$C$11",kind='auto_l')
    mput(ws,'I3:J3','ДЕЛО №',kind='kv'); mput(ws,'K3:S3',f"={S_DOC}!$G$3",kind='auto_l'); heights(ws,{3:22})
    mput(ws,'B4:S4','ЯНТАРНЫЕ — ВВОД · ТЁМНЫЕ — АВТО · ШТРАФ БРОНИ С 03 КАМПАНИЯ · БАЗА НАВЫКА = УР.+СТАТА',kind='note'); heights(ws,{4:16})
    # section titles
    mput(ws,'B5:G5','I · ХАРАКТЕРИСТИКИ · 62 ОЧКА · 2–8',kind='h1')
    mput(ws,'H5:J5','II · ПРОИЗВОДНЫЕ',kind='h1')
    mput(ws,'L5:S5','III · БЫСТРЫЙ БОЙ · АВТО ИЗ КАМПАНИИ',kind='h1')
    heights(ws,{5:22})
    # heads row6
    heads=[('B','КОД'),('C','СТАТА'),('D','ЗНАЧ.'),('E','БРОНЯ'),('F','ИТОГ'),('G','НА ЧТО ВЛИЯЕТ'),('H','ПОКАЗАТЕЛЬ'),('I','ЗНАЧ.'),('J','ПРАВИЛО'),('L','ПАРАМЕТР'),('M','ЗНАЧ.'),('N','ЗНАЧ.2'),('O','ЗНАЧ.3')]
    for col,txt in heads:
        put(ws,f'{col}6',txt,kind='head')
    mput(ws,'P6:S6','ПРИМЕЧАНИЕ',kind='head')
    heights(ws,{6:18})

    # stats 7-16
    stat_rows={'INT':7,'WILL':8,'COOL':9,'EMP':10,'TECH':11,'REF':12,'LUCK':13,'BODY':14,'DEX':15,'MOVE':16}
    for code,ru,eff in STAT_INFO:
        r=stat_rows[code]
        put(ws,f'B{r}',code,kind='cellc'); put(ws,f'C{r}',ru,kind='cell')
        val = EXAMPLE_STATS.get(code) if example else (5 if code!='LUCK' else 2)
        if not example and code=='MOVE': val=6
        put(ws,f'D{r}',val,kind='inputc')
        if code in ('REF','DEX','MOVE'):
            pen_col = {'REF':'$H$66','DEX':'$I$66','MOVE':'$J$66'}[code]
            put(ws,f'E{r}',f"={S_CAMP}!{pen_col}",kind='auto')
        else:
            put(ws,f'E{r}',0,kind='auto')
        if code=='EMP':
            put(ws,f'F{r}',f"=IF(D{r}=\"\",\"\",MIN(MAX(0,D{r}+E{r}),{S_PLAY}!$I$19))",kind='auto')
        else:
            put(ws,f'F{r}',f"=IF(D{r}=\"\",\"\",MAX(0,D{r}+E{r}))",kind='auto')
        put(ws,f'G{r}',eff,kind='cell'); heights(ws,{r:18})
    dv_num(ws,f'D{PLAY_STAT_FIRST}:D{PLAY_STAT_LAST}',2,8)

    # derived 7-21
    derived=[
        (7,'HP МАКС',' =10+5*ROUNDUP((F14+F8)/2,0)','HP = 10+5×⌈(BODY+WILL)/2⌉'),
        (8,'HP ТЕКУЩИЕ',None,'Вписывай текущие HP. 0 и ниже — смертельно.'),
        (9,'ПОРОГ СЕРЬЁЗНО РАНЕН','=ROUNDUP(I7/2,0)','Половина HP вверх → −2 ко всем.'),
        (10,'СПАСБРОСОК СМЕРТИ (BODY)','=F14','1d10 ≤ BODY − штраф. 10 — провал.'),
        (11,'ШТРАФ К СПАСБРОСКАМ',None,'Крит-травмы (+1) + урон.'),
        (12,'ИНИЦИАТИВА','=F12','1d10 + это число.'),
        (13,'MOVE ACTION','=F16*2','MOVE×2 м за Move Action.'),
        (14,'HUMANITY БАЗА','=D10*10','От исходной EMP (ЗНАЧ.).'),
        (15,'СРЕЗ МАКСИМУМА',f"={S_CAMP}!$I$23",'−2 обычный, −4 боргвар. Fashionware и Neuroport старт не режут.'),
        (16,'HUMANITY МАКСИМУМ','=I14-I15','База − срез.'),
        (17,'HL ВСЕГО',f"={S_CAMP}!$H$23",'Сумма средних HL.'),
        (18,'ВОССТАНОВЛЕНО',None,'Терапия + Humanity Gain CEMK.'),
        (19,'HUMANITY ТЕКУЩАЯ','=MIN(I16,I14-I17+I18)','Не выше максимума. <0 — киберпсихоз.'),
        (20,'EMP ТЕКУЩАЯ','=MAX(0,ROUNDDOWN(I19/10,0))','Десяток Humanity → −1 EMP.'),
        (21,'СТАТУС HUMANITY','=IF(AND(I20=0,I19<0),"⚠ ЭКСТРЕМАЛЬНЫЙ — лист забирает GM",IF(I20=0,"⚠ КИБЕРПСИХОЗ",IF(I19<20,"ПОНИЖЕННАЯ","В НОРМЕ")))', '0 Humanity = киберпсихоз.'),
    ]
    for r,label,form,note in derived:
        mput(ws,f'H{r}',label,kind='kv')
        if form is None:
            if 'ТЕКУЩИЕ' in label: put(ws,f'I{r}',50 if example else None,kind='inputc')
            elif 'ШТРАФ' in label: put(ws,f'I{r}',0,kind='inputc')
            elif 'ВОССТАНОВЛЕНО' in label: put(ws,f'I{r}',0,kind='inputc')
            else: put(ws,f'I{r}',None,kind='inputc')
        else:
            # form already starts with = maybe with space
            fstr=form.strip()
            if not fstr.startswith('='): fstr='='+fstr
            put(ws,f'I{r}',fstr,kind='auto')
        mput(ws,f'J{r}',note,kind='cell'); heights(ws,{r:18})

    # quick combat L-S 7-16
    put(ws,'L7','SP ГОЛОВЫ',kind='kv'); put(ws,'M7',f"={S_CAMP}!$D$66",kind='auto'); mput(ws,'N7:S7','Лучший SP в локации — не складывается.',kind='note')
    put(ws,'L8','SP ТЕЛА',kind='kv'); put(ws,'M8',f"={S_CAMP}!$D$67",kind='auto'); mput(ws,'N8:S8','Вся броня локации аблейтится одновременно.',kind='note')
    put(ws,'L9','ЩИТ HP',kind='kv'); put(ws,'M9',f"={S_CAMP}!$D$68",kind='auto'); mput(ws,'N9:S9','Щит: 10 HP обычный, 15 усиленный.',kind='note')
    put(ws,'L10','ШТРАФ REF/DEX/MOVE',kind='kv'); put(ws,'M10',f"={S_CAMP}!$H$66",kind='auto'); put(ws,'N10',f"={S_CAMP}!$I$66",kind='auto'); put(ws,'O10',f"={S_CAMP}!$J$66",kind='auto'); mput(ws,'P10:S10','Самый строгий, один раз.',kind='note')
    put(ws,'L11','УКЛОНЕНИЕ',kind='kv'); mput(ws,'M11:S11',f"=IF(F12<8,\"✖ нельзя: REF \"&F12&\" <8\",\"✔ можно: Evasion \"&IFERROR(INDEX({SKLI},MATCH(\"Evasion\",{SKLC},0)),F15)&\" + 1d10\")",kind='auto_l')
    put(ws,'L12','СОСТОЯНИЕ РАН',kind='kv'); mput(ws,'M12:S12','=IF(I8="","—",IF(I8<1,"СМЕРТЕЛЬНО: −4 ко всем, −6 MOVE, спасбросок",IF(I8<=I9,"СЕРЬЁЗНО: −2 ко всем",IF(I8<I7,"ЛЁГКО","В НОРМЕ"))))',kind='auto_l')
    put(ws,'L13','LUCK ТЕКУЩАЯ / МАКС',kind='kv'); put(ws,'M13','=F13',kind='auto'); put(ws,'N13','ТЕКУЩАЯ',kind='kv'); put(ws,'O13',None,kind='inputc'); mput(ws,'P13:S13','Пул на любой бросок до броска.',kind='note')
    put(ws,'L14','НАЛИЧНЫЕ',kind='kv'); put(ws,'M14',f"={S_CAMP}!$D$5",kind='auto',fmt=CASH_FMT); mput(ws,'N14:S14','Остаток бюджета + оборот кассы.',kind='note')
    put(ws,'L15','HUMANITY / EMP',kind='kv'); put(ws,'M15','=I19&" / "&I20',kind='auto'); mput(ws,'N15:S15','=J21',kind='auto_l')
    put(ws,'L16','КРИТ-ТРАВМ АКТИВНО',kind='kv'); put(ws,'M16',f"=COUNTIF({S_CAMP}!$I$120:$I$129,\"Активна\")",kind='auto'); mput(ws,'N16:S16','Считается с КАМПАНИЯ.',kind='note')

    # 62 check
    mput(ws,'B17:C17','РАСКИДАНО / НОРМА 62',kind='kv'); put(ws,'D17',f"=SUM(D{PLAY_STAT_FIRST}:D{PLAY_STAT_LAST})",kind='auto'); put(ws,'E17','ОСТАТОК',kind='kv'); put(ws,'F17','=62-D17',kind='auto'); mput(ws,'G17:J17','=IF(AND(D17=62,MIN(D7:D16)>=2,MAX(D7:D16)<=8),"✔ 62 очка, диапазон 2–8","✖ сумма 62, каждая 2–8")',kind='auto_l'); heights(ws,{17:20})

    # weapons
    r=19
    mput(ws,f'B{r}:S{r}','IV · ОРУЖИЕ В РУКАХ · АВТО ИЗ КАМПАНИИ (СЛОТ 1–4)',kind='h1'); r+=1
    for col,txt in (('B','№'),('C','НАЗВАНИЕ'),('D','УРОН'),('E','ROF'),('F','МАГ.'),('G','ПАТРОНЫ'),('H','НАВЫК'),('I','БАЗА АТАКИ'),('J','ЗАМЕТКИ')):
        put(ws,f'{col}{r}',txt,kind='head')
    mput(ws,f'K{r}:S{r}','ЭФФЕКТ ИЗ КАТАЛОГА',kind='head'); heights(ws,{r:18}); r+=1
    for i in range(4):
        rr=r+i
        put(ws,f'B{rr}',i+1,kind='cellc')
        put(ws,f'C{rr}',f"=IFERROR(INDEX({S_CAMP}!$C${CAMP_W_FIRST}:$C${CAMP_W_LAST},MATCH({i+1},{S_CAMP}!$K${CAMP_W_FIRST}:$K${CAMP_W_LAST},0)),\"—\")",kind='auto_l')
        put(ws,f'D{rr}',f"=IFERROR(INDEX({S_CAMP}!$F${CAMP_W_FIRST}:$F${CAMP_W_LAST},MATCH({i+1},{S_CAMP}!$K${CAMP_W_FIRST}:$K${CAMP_W_LAST},0)),\"—\")",kind='auto')
        put(ws,f'E{rr}',f"=IFERROR(INDEX({S_CAMP}!$G${CAMP_W_FIRST}:$G${CAMP_W_LAST},MATCH({i+1},{S_CAMP}!$K${CAMP_W_FIRST}:$K${CAMP_W_LAST},0)),\"—\")",kind='auto')
        put(ws,f'F{rr}',f"=IFERROR(INDEX({S_CAMP}!$H${CAMP_W_FIRST}:$H${CAMP_W_LAST},MATCH({i+1},{S_CAMP}!$K${CAMP_W_FIRST}:$K${CAMP_W_LAST},0)),\"—\")",kind='auto')
        put(ws,f'G{rr}',f"=IFERROR(INDEX({S_CAMP}!$I${CAMP_W_FIRST}:$I${CAMP_W_LAST},MATCH({i+1},{S_CAMP}!$K${CAMP_W_FIRST}:$K${CAMP_W_LAST},0)),\"—\")",kind='auto')
        put(ws,f'H{rr}',f"=IFERROR(INDEX({S_CAMP}!$E${CAMP_W_FIRST}:$E${CAMP_W_LAST},MATCH({i+1},{S_CAMP}!$K${CAMP_W_FIRST}:$K${CAMP_W_LAST},0)),\"—\")",kind='auto_l')
        put(ws,f'I{rr}',f"=IFERROR(INDEX({S_CAMP}!$L${CAMP_W_FIRST}:$L${CAMP_W_LAST},MATCH({i+1},{S_CAMP}!$K${CAMP_W_FIRST}:$K${CAMP_W_LAST},0)),\"—\")",kind='auto')
        put(ws,f'J{rr}',f"=IFERROR(INDEX({S_CAMP}!$M${CAMP_W_FIRST}:$M${CAMP_W_LAST},MATCH({i+1},{S_CAMP}!$K${CAMP_W_FIRST}:$K${CAMP_W_LAST},0)),\"—\")",kind='cell')
        mput(ws,f'K{rr}:S{rr}',f"=IFERROR(INDEX({S_CAMP}!$R${CAMP_W_FIRST}:$R${CAMP_W_LAST},MATCH({i+1},{S_CAMP}!$K${CAMP_W_FIRST}:$K${CAMP_W_LAST},0)),\"\")",kind='cell'); heights(ws,{rr:18})
    r+=5
    mput(ws,f'B{r}:S{r}','Атака = 1d10 + БАЗА АТАКИ (навык + стата с штрафом брони).',kind='note'); r+=2

    # V skills
    mput(ws,f'B{r}:K{r}','V · НАВЫКИ · 66 + 6 СВОБОДНЫХ · ЗАПОЛНЯЙ ТОЛЬКО УР. · БАЗА = УР.+СТАТА',kind='h1')
    mput(ws,f'L{r}:S{r}','ПРОВЕРКИ · ПАКЕТЫ РОЛИ · БЫСТРЫЙ ХРОМ И ТРАВМЫ',kind='h1'); heights(ws,{r:22}); r+=1
    mput(ws,f'B{r}:K{r}','★ — пакет роли (мин.2), ☆ — пакет Solo, ×2 — стоит 2 очка за уровень',kind='note')
    mput(ws,f'L{r}:S{r}',f"=IF(I35=0,\"✔ 86 очков\",IF(I35>0,\"свободно: \"&I35&\" очков\",\"✖ перебор на \"&-I35&\" очков\"))",kind='auto_l'); r+=1
    for col,txt in (('B','ГРУППА'),('C','НАВЫК'),('D','СТАТА'),('E','×2'),('F','РОЛЬ'),('G','УР.'),('H','СТАТА'),('I','БАЗА'),('J','ОЧКИ'),('K','СПЕЦ.')):
        put(ws,f'{col}{r}',txt,kind='head')
    mput(ws,f'L{r}:M{r}','ПОКАЗАТЕЛЬ',kind='head'); put(ws,f'N{r}','ЗНАЧ.',kind='head'); mput(ws,f'O{r}:S{r}','ПРИМЕЧАНИЕ',kind='head'); heights(ws,{r:18}); r+=1

    first_skill_row=r
    groups=[]
    for cat,name,stat,x2 in RULES.SKILLS:
        if cat not in groups: groups.append(cat)
        shade = PAL['text_bg'] if groups.index(cat)%2==0 else PAL['kv_bg']
        from openpyxl.styles import PatternFill
        fill = PatternFill('solid', start_color=shade)
        is_must = name in RULES.MUST_SKILLS
        put(ws,f'B{r}',cat,kind='cell'); ws[f'B{r}'].fill=fill
        put(ws,f'C{r}',name,kind='cell'); ws[f'C{r}'].fill=fill
        if is_must: ws[f'C{r}'].font = Font(name=SANS, size=10, bold=True, color=PAL['ink'])
        put(ws,f'D{r}',stat,kind='cellc'); ws[f'D{r}'].fill=fill
        put(ws,f'E{r}','×2' if x2 else '',kind='cellc'); ws[f'E{r}'].fill=fill
        role_mark = '★' if name in RULES.ROLE_MUST_SKILLS.get('Lawman',[]) else ('☆' if name in ['Athletics','Brawling','Concentration','Conversation','Education','Evasion','First Aid','Human Perception','Language','Local Expert','Perception','Persuasion','Stealth','Autofire','Handgun','Interrogation','Melee Weapon','Resist Torture/Drugs','Shoulder Arms','Tactics'] else '')
        put(ws,f'F{r}',role_mark,kind='cellc'); ws[f'F{r}'].fill=fill
        lvl = EXAMPLE_SKILLS.get(name) if example else None
        put(ws,f'G{r}',lvl,kind='inputc')
        put(ws,f'H{r}',f"=IFERROR(INDEX({BASEF},MATCH($D{r},{BASEB},0)),\"\")",kind='auto')
        put(ws,f'I{r}',f"=IF($G{r}=\"\",\"\",$G{r}+IFERROR($H{r},0))",kind='auto')
        put(ws,f'J{r}',f"=IF($G{r}=\"\",\"\",IF($E{r}=\"×2\",$G{r}*2,$G{r}))",kind='auto')
        spec = EXAMPLE_SKILL_SPECS.get(name) if example else None
        put(ws,f'K{r}',spec,kind='input'); heights(ws,{r:16}); r+=1
    last_skill_row=r-1
    cust_first=r
    for i in range(6):
        put(ws,f'B{r}','СВОЙ',kind='cell'); put(ws,f'C{r}',None,kind='input'); put(ws,f'D{r}',None,kind='inputc'); dv_list(ws,f'D{r}',list({'INT':0,'WILL':0,'COOL':0,'EMP':0,'TECH':0,'REF':0,'LUCK':0,'BODY':0,'DEX':0,'MOVE':0}.keys()))
        put(ws,f'E{r}',None,kind='inputc'); put(ws,f'F{r}',None,kind='inputc'); put(ws,f'G{r}',None,kind='inputc')
        put(ws,f'H{r}',f"=IFERROR(INDEX({BASEF},MATCH($D{r},{BASEB},0)),\"\")",kind='auto')
        put(ws,f'I{r}',f"=IF($G{r}=\"\",\"\",$G{r}+IFERROR($H{r},0))",kind='auto')
        put(ws,f'J{r}',f"=IF($G{r}=\"\",\"\",IF($E{r}=\"×2\",$G{r}*2,$G{r}))",kind='auto')
        put(ws,f'K{r}',None,kind='input'); heights(ws,{r:16}); r+=1
    cust_last=r-1

    cr=first_skill_row
    put(ws,f'L{cr}','РАСКИДАНО ОЧКОВ',kind='kv'); put(ws,f'N{cr}',f"=SUM($J${first_skill_row}:$J${cust_last})",kind='auto'); mput(ws,f'O{cr}:S{cr}','норма — ровно 86',kind='note'); cr+=1
    put(ws,f'L{cr}','ОСТАТОК ОЧКОВ',kind='kv'); put(ws,f'N{cr}',f"=86-N{cr-1}",kind='auto'); mput(ws,f'O{cr}:S{cr}','0 = всё раздано',kind='note'); cr+=1
    put(ws,f'L{cr}','МАКСИМУМ НАВЫКА',kind='kv'); put(ws,f'N{cr}',f"=MAX($G${first_skill_row}:$G${cust_last})",kind='auto'); mput(ws,f'O{cr}:S{cr}','на старте — не выше 6',kind='note'); cr+=2
    mput(ws,f'L{cr}:S{cr}','13 ОБЯЗАТЕЛЬНЫХ НАВЫКОВ (МИН. 2)',kind='h2'); cr+=1
    put(ws,f'L{cr}','НАВЫК',kind='head'); put(ws,f'M{cr}','УР.',kind='head'); put(ws,f'N{cr}','ГОДЕН',kind='head'); mput(ws,f'O{cr}:S{cr}','ЧТО ДАЁТ',kind='head'); cr+=1
    must_first=cr
    must_notes={'Athletics':'Прыжки, лазание','Brawling':'Драка, Grab','Concentration':'Фокус','Conversation':'Вытягивать инфо','Education':'Эрудиция','Evasion':'Уклонение','First Aid':'Стабилизация','Human Perception':'Читать лица','Language':'Streetslang мин.2, родной 4 беспл.','Local Expert':'Свой район','Perception':'Замечать засады','Persuasion':'Убеждать','Stealth':'Подход, засада'}
    for name in RULES.MUST_SKILLS:
        put(ws,f'L{cr}',name,kind='cell'); put(ws,f'M{cr}',f"=IFERROR(INDEX($G${first_skill_row}:$G${cust_last},MATCH(\"{name}\",$C${first_skill_row}:$C${cust_last},0)),0)",kind='auto')
        put(ws,f'N{cr}',f"=IF($M{cr}>=2,\"✔\",\"✖ мал\")",kind='auto'); mput(ws,f'O{cr}:S{cr}',must_notes.get(name,''),kind='note'); cr+=1
    must_last=cr-1
    mput(ws,f'L{cr}:M{cr}','ИТОГО ОБЯЗАТЕЛЬНЫХ',kind='kv'); put(ws,f'N{cr}',f"=COUNTIF($N${must_first}:$N${must_last},\"✔\")",kind='auto'); put(ws,f'O{cr}',f"=IF($N{cr}=13,\"✔ все 13\",\"✖ не закрыто\")",kind='auto_l'); cr+=2

    mput(ws,f'L{cr}:S{cr}','ПАКЕТ РОЛИ LAWMAN (МИН. 2) — УНИВЕРСАЛЬНО',kind='h2'); cr+=1
    put(ws,f'L{cr}','НАВЫК РОЛИ',kind='head'); put(ws,f'M{cr}','УР.',kind='head'); put(ws,f'N{cr}','ГОДЕН',kind='head'); mput(ws,f'O{cr}:S{cr}','ЗАЧЕМ',kind='head'); cr+=1
    role_start=cr
    role_notes={'Autofire':'Очереди 10 патр','Criminology':'Место преступления','Deduction':'Выводы','Handgun':'Табельный','Interrogation':'Допрос','Shoulder Arms':'Винтовки, дробовики','Tracking':'По следу'}
    for name in RULES.ROLE_MUST_SKILLS.get('Lawman',[]):
        put(ws,f'L{cr}',name,kind='cell'); put(ws,f'M{cr}',f"=IFERROR(INDEX($G${first_skill_row}:$G${cust_last},MATCH(\"{name}\",$C${first_skill_row}:$C${cust_last},0)),0)",kind='auto')
        put(ws,f'N{cr}',f"=IF($M{cr}>=2,\"✔\",\"✖ мал\")",kind='auto'); mput(ws,f'O{cr}:S{cr}',role_notes.get(name,''),kind='note'); cr+=1
    role_last=cr-1
    mput(ws,f'L{cr}:M{cr}','ИТОГО ПО РОЛИ',kind='kv'); put(ws,f'N{cr}',f"=COUNTIF($N${role_start}:$N${role_last},\"✔\")",kind='auto'); put(ws,f'O{cr}',f"=IF($N{cr}=7,\"✔ пакет закрыт\",\"✖\")",kind='auto_l'); cr+=2

    mput(ws,f'L{cr}:S{cr}','БЫСТРЫЙ ХРОМ · АВТО ИЗ КАМПАНИИ',kind='h2'); cr+=1
    put(ws,f'L{cr}','ХРОМ',kind='head'); mput(ws,f'M{cr}:S{cr}','ЭФФЕКТ',kind='head'); cr+=1
    for i in range(6):
        rr=cr+i
        put(ws,f'L{rr}',f"=IFERROR(INDEX({S_CAMP}!$C${CAMP_CHR_FIRST}:$C${CAMP_CHR_LAST},SMALL(IF({S_CAMP}!$J${CAMP_CHR_FIRST}:$J${CAMP_CHR_LAST}=\"Да\",ROW({S_CAMP}!$J${CAMP_CHR_FIRST}:$J${CAMP_CHR_LAST})-ROW({S_CAMP}!$J${CAMP_CHR_FIRST})+1),{i+1})),\"—\")",kind='auto_l')
        mput(ws,f'M{rr}:S{rr}',f"=IF(L{rr}=\"—\",\"\",IFERROR(INDEX({S_CAMP}!$L${CAMP_CHR_FIRST}:$L${CAMP_CHR_LAST},MATCH(L{rr},{S_CAMP}!$C${CAMP_CHR_FIRST}:$C${CAMP_CHR_LAST},0)),\"\"))",kind='cell')
    cr+=7
    mput(ws,f'L{cr}:S{cr}','КРИТ-ТРАВМЫ АКТИВНЫЕ',kind='h2'); cr+=1
    put(ws,f'L{cr}','ЛОКАЦИЯ',kind='head'); put(ws,f'M{cr}','2D6',kind='head'); mput(ws,f'N{cr}:S{cr}','ТРАВМА / ЭФФЕКТ',kind='head'); cr+=1
    for i in range(3):
        put(ws,f'L{cr}',f"=IFERROR(INDEX({S_CAMP}!$C${CAMP_CRIT_FIRST}:$C${CAMP_CRIT_LAST},SMALL(IF({S_CAMP}!$I${CAMP_CRIT_FIRST}:$I${CAMP_CRIT_LAST}=\"Активна\",ROW({S_CAMP}!$I${CAMP_CRIT_FIRST}:$I${CAMP_CRIT_LAST})-ROW({S_CAMP}!$I${CAMP_CRIT_FIRST})+1),{i+1})),\"—\")",kind='auto')
        put(ws,f'M{cr}',f"=IF(L{cr}=\"—\",\"\",IFERROR(INDEX({S_CAMP}!$D${CAMP_CRIT_FIRST}:$D${CAMP_CRIT_LAST},MATCH(L{cr},{S_CAMP}!$C${CAMP_CRIT_FIRST}:$C${CAMP_CRIT_LAST},0)),\"\"))",kind='auto')
        mput(ws,f'N{cr}:S{cr}',f"=IF(L{cr}=\"—\",\"\",IFERROR(INDEX({S_CAMP}!$E${CAMP_CRIT_FIRST}:$E${CAMP_CRIT_LAST},MATCH(L{cr},{S_CAMP}!$C${CAMP_CRIT_FIRST}:$C${CAMP_CRIT_LAST},0)),\"\"))",kind='cell'); cr+=1
    cr+=1
    mput(ws,f'L{cr}:S{cr}','ПАМЯТКА БОЙЦА · 2070',kind='h1'); cr+=1
    for txt in ['Ход: 1 Move Action (MOVE×2 м) + 1 действие. Инициатива = REF+1d10.',
                'Серьёзно ранен (HP≤½): −2 ко всем. Смертельно (HP<1): −4 ко всем, −6 MOVE, спасбросок.',
                'Крит (2+ шестёрок урона): +5 урона в HP (SP не гасит) + эффект с КАМПАНИИ.',
                'Прицельный в голову: −8, урон ×2 (треснувший череп ×3). В оружие/ногу: −4.',
                'Укрытие бинарно. Щит — подвижное укрытие, но без уклонения.',
                'Броня аблейтится (−1 SP) когда урон прошёл. Backup ранг = ранг роли.']:
        mput(ws,f'L{cr}:S{cr}','▪ '+txt,kind='text'); heights(ws,{cr:22}); cr+=1

    cf(ws,f'G{first_skill_row}:G{cust_last}',f'$G{first_skill_row}>6', PAL['warn_bg'], PAL['warn_fg'])
    return ws

# ================================================= 03 КАМПАНИЯ
def build_campaign(wb, example=False, cat_last=1):
    ws = wb.create_sheet(NAMES['camp'])
    widths(ws, {'A':2,'B':4,'C':32,'D':16,'E':14,'F':18,'G':10,'H':8,'I':8,'J':10,'K':12,'L':10,'M':46,'N':12,'O':12,'P':12,'Q':12,'R':56,'S':2})
    sheet_setup(ws, PAL['gold'], freeze='A9')
    mput(ws,'B1:R1','КАМПАНИЯ  ▚  ХРОМ · ОРУЖИЕ · БРОНЯ · ИНВЕНТАРЬ · КАССА · ТРАВМЫ · IP · ЛОГ ДЕЛ',kind='banner'); heights(ws,{1:26})
    mput(ws,'B2:R2','НАЗВАНИЯ ИЗ КАТАЛОГА — ЦЕНА, УРОН, SP, HL ПОДТЯНУТСЯ САМИ. ПИШИ ТОЛЬКО В ЯНТАРНЫЕ.',kind='note')

    mput(ws,'B3:D3','СТАРТ: ОРУЖИЕ, БРОНЯ, СНАРЯЖЕНИЕ, ХРОМ',kind='kv'); put(ws,'E3',2550,kind='inputc',fmt=CASH_FMT)
    put(ws,'F3','ПОТРАЧЕНО',kind='kv'); put(ws,'G3',f"=$I$92+$O$56+$O$69+$M$23-($G$4-$N$23)",kind='auto',fmt=CASH_FMT)
    put(ws,'H3','ОСТАТОК',kind='kv'); put(ws,'I3','=E3-G3',kind='auto',fmt=CASH_FMT)
    mput(ws,'J3:R3','Траты: инвентарь + броня + хром. Fashionware из хрома — в стиле.',kind='note')
    mput(ws,'B4:D4','СТАРТ: СТИЛЬ — FASHION И FASHIONWARE',kind='kv'); put(ws,'E4',800,kind='inputc',fmt=CASH_FMT)
    put(ws,'F4','ПОТРАЧЕНО',kind='kv'); put(ws,'G4',f"=SUMPRODUCT(($D${CAMP_I_FIRST}:$D${CAMP_I_LAST}=\"Мода\")*$I${CAMP_I_FIRST}:$I${CAMP_I_LAST})+SUMPRODUCT(($E${CAMP_I_FIRST}:$E${CAMP_I_LAST}=\"Fashionware\")*$I${CAMP_I_FIRST}:$I${CAMP_I_LAST})+$N$23",kind='auto',fmt=CASH_FMT)
    put(ws,'H4','ОСТАТОК',kind='kv'); put(ws,'I4','=E4-G4',kind='auto',fmt=CASH_FMT)
    mput(ws,'J4:R4','Одежда (Мода) + Fashionware инвентаря + Fashionware-хром.',kind='note')
    mput(ws,'B5:C5','НАЛИЧНЫЕ АВТО',kind='kv'); put(ws,'D5',f"=I3+SUM($E${CAMP_CASH_FIRST}:$E${CAMP_CASH_LAST})",kind='auto',fmt=CASH_FMT)
    put(ws,'E5','ПРОВЕРКА',kind='kv'); mput(ws,'F5:H5','=IF(OR(I3<0,I4<0),"✖ бюджеты превышены","✔ в рамках")',kind='auto_l')
    mput(ws,'I5:R5','Остаток 2550 остаётся наличными (CP:R 104), 800 на моду сгорает.',kind='note')

    mput(ws,'B7:R7','I · КИБЕРНЕТИКА · 2070: ВЕСЬ НЕМЕДИЦИНСКИЙ ХРОМ ТРЕБУЕТ NEUROPORT',kind='h1')
    for col,txt in (('B','№'),('C','НАЗВАНИЕ (КАК В КАТАЛОГЕ)'),('D','КАТЕГОРИЯ'),('E','ПОДТИП'),('F','СЛОТ'),('G','ЦЕНА'),('H','HL'),('I','СРЕЗ'),('J','УСТАНОВЛЕН'),('K','КЛИНИКА'),('L','ЭФФЕКТ'),('M','В БЮДЖЕТ'),('N','СТИЛЬ')):
        put(ws,f'{col}8',txt,kind='head')
    mput(ws,'O8:R8','ОПИСАНИЕ',kind='head')
    for i in range(CAMP_CHR_LAST-CAMP_CHR_FIRST+1):
        r=CAMP_CHR_FIRST+i
        put(ws,f'B{r}',i+1,kind='cellc')
        name = EXAMPLE_CHROME[i] if example and i < len(EXAMPLE_CHROME) else None
        put(ws,f'C{r}',name,kind='input'); dv_catalog(ws,f'C{r}',cat_last)
        put(ws,f'D{r}',f"=IFERROR(INDEX({CATB},MATCH($C{r},{CATA},0)),\"\")",kind='auto_l')
        put(ws,f'E{r}',f"=IFERROR(INDEX({CATC},MATCH($C{r},{CATA},0)),\"\")",kind='auto_l')
        put(ws,f'F{r}',None,kind='input')
        put(ws,f'G{r}',f"=IF($C{r}=\"\",\"\",IF(ISNUMBER(SEARCH(\"Neuroport\",$C{r})),0,IFERROR(INDEX({CATR},MATCH($C{r},{CATA},0)),0)))",kind='auto',fmt=CASH_FMT)
        put(ws,f'H{r}',f"=IF($C{r}=\"\",\"\",IF(ISNUMBER(SEARCH(\"Neuroport\",$C{r})),0,IFERROR(INDEX({CATM},MATCH($C{r},{CATA},0)),0)))",kind='auto')
        put(ws,f'I{r}',f"=IF($C{r}=\"\",\"\",IF(OR(N($H{r})=0,ISNUMBER(SEARCH(\"Fashionware\",$E{r}))),0,IF(ISNUMBER(SEARCH(\"Borgware\",$E{r})),4,2)))",kind='auto')
        put(ws,f'J{r}','Да' if example and i < len(EXAMPLE_CHROME) else 'Нет',kind='inputc'); dv_list(ws,f'J{r}',['Да','Нет'])
        put(ws,f'K{r}',f"=IFERROR(INDEX({CATN},MATCH($C{r},{CATA},0)),\"\")",kind='auto_l')
        put(ws,f'L{r}',f"=IFERROR(LEFT(INDEX({CATT},MATCH($C{r},{CATA},0)),80),\"\")",kind='cell')
        put(ws,f'M{r}',f"=IF($C{r}=\"\",\"\",IF($J{r}<>\"Да\",0,IF(ISNUMBER(SEARCH(\"Fashionware\",$E{r})),0,$G{r})))",kind='auto',fmt=CASH_FMT)
        put(ws,f'N{r}',f"=IF($C{r}=\"\",\"\",IF($J{r}<>\"Да\",0,IF(ISNUMBER(SEARCH(\"Fashionware\",$E{r})),$G{r},0)))",kind='auto',fmt=CASH_FMT)
        put(ws,f'O{r}',f"=IFERROR(LEFT(INDEX({CATT},MATCH($C{r},{CATA},0)),90),\"\")",kind='cell')
        mput(ws,f'P{r}:R{r}',f"=IFERROR(INDEX({CATT},MATCH($C{r},{CATA},0)),\"\")",kind='cell'); heights(ws,{r:18})
    mput(ws,f'B{CAMP_CHR_LAST+1}:F{CAMP_CHR_LAST+1}','ИТОГО (ТОЛЬКО «ДА»)',kind='kv')
    put(ws,f'G{CAMP_CHR_LAST+1}',f"=SUM($M${CAMP_CHR_FIRST}:$M${CAMP_CHR_LAST})+SUM($N${CAMP_CHR_FIRST}:$N${CAMP_CHR_LAST})",kind='auto',fmt=CASH_FMT)
    put(ws,f'H{CAMP_CHR_LAST+1}',f"=SUMIF($J${CAMP_CHR_FIRST}:$J${CAMP_CHR_LAST},\"Да\",$H${CAMP_CHR_FIRST}:$H${CAMP_CHR_LAST})",kind='auto')
    put(ws,f'I{CAMP_CHR_LAST+1}',f"=SUMIF($J${CAMP_CHR_FIRST}:$J${CAMP_CHR_LAST},\"Да\",$I${CAMP_CHR_FIRST}:$I${CAMP_CHR_LAST})",kind='auto')
    put(ws,f'M{CAMP_CHR_LAST+1}',f"=SUM($M${CAMP_CHR_FIRST}:$M${CAMP_CHR_LAST})",kind='auto',fmt=CASH_FMT)
    put(ws,f'N{CAMP_CHR_LAST+1}',f"=SUM($N${CAMP_CHR_FIRST}:$N${CAMP_CHR_LAST})",kind='auto',fmt=CASH_FMT)
    r=CAMP_CHR_LAST+2
    mput(ws,f'B{r}:D{r}','NEUROPORT УСТАНОВЛЕН',kind='kv'); put(ws,f'E{r}','Да',kind='inputc'); dv_list(ws,f'E{r}',['Да','Нет'])
    mput(ws,f'F{r}:R{r}',f"=IF(AND($E${r}=\"Нет\",COUNTIF($J${CAMP_CHR_FIRST}:$J${CAMP_CHR_LAST},\"Да\")>0),\"⚠ Любой немедицинский хром требует Neuroport (CEMK 26)\",\"✔ ок. При создании: 0 €$, 0 HL, макс Humanity не режется\")",kind='auto_l'); heights(ws,{r:20}); r+=1
    mput(ws,f'B{r}:R{r}','NEUROPORT ДАЁТ: Neural Link (5 слотов) · Holophone · Biomonitor · Virtu · HUD/Chyron · 2 чип-слота · Personal Link. Порт под кибердеку — 100 €$ и 3 (1d6) HL.',kind='cell'); r+=1
    mput(ws,f'B{r}:R{r}','ЛИМИТЫ: одно Speedware · один Cyberdeck за раз · кибер-оружие в руке требует слот киберруки.',kind='note'); r+=2

    mput(ws,f'B{r}:R{r}','II · HUMANITY · ЧЕЛОВЕЧНОСТЬ (ДУБЛЬ С 02 ИГРА)',kind='h1'); r+=1
    mput(ws,f'B{r}:C{r}','ПОКАЗАТЕЛЬ',kind='head'); put(ws,f'D{r}','ЗНАЧЕНИЕ',kind='head'); mput(ws,f'E{r}:R{r}','ПРАВИЛО',kind='head'); r+=1
    hum=[
        ('БАЗА (EMP×10)',f"={S_PLAY}!$I$14",'От исходной EMP (02).'),
        ('СРЕЗ МАКСИМУМА',f"={S_PLAY}!$I$15",'Сумма среза «Да». Fashionware и старт Neuroport не режут.'),
        ('HUMANITY МАКСИМУМ',f"={S_PLAY}!$I$16",'База − срез. Выше не поднять — только снимать хром.'),
        ('HL ВСЕГО',f"={S_PLAY}!$I$17",'Сумма средних HL установленного хрома.'),
        ('ВОССТАНОВЛЕНО',f"={S_PLAY}!$I$18",'Терапия + Humanity Gain CEMK.'),
        ('HUMANITY ТЕКУЩАЯ',f"={S_PLAY}!$I$19",'База − HL + восстановленное, но не выше максимума.'),
        ('EMP ТЕКУЩАЯ',f"={S_PLAY}!$I$20",'Каждый десяток Humanity → −1 EMP.'),
        ('СТАТУС',f"={S_PLAY}!$I$21",'Humanity <0 = киберпсихоз.'),
    ]
    for label,form,note in hum:
        mput(ws,f'B{r}:C{r}',label,kind='kv'); put(ws,f'D{r}',form,kind='auto'); mput(ws,f'E{r}:R{r}',note,kind='cell'); heights(ws,{r:20}); r+=1
    mput(ws,f'B{r}:C{r}','ШКАЛА HUMANITY',kind='kv'); put(ws,f'D{r}',f"={S_PLAY}!$I$19",kind='auto'); mput(ws,f'E{r}:R{r}',f"=REPT(\"█\",MAX(0,MIN(40,ROUND($D${r}/2,0))))&REPT(\"░\",MAX(0,40-MIN(40,ROUND($D${r}/2,0))))",kind='auto_l'); r+=2

    mput(ws,f'B{r}:R{r}','III · ТЕРАПИЯ · 1 НЕДЕЛЯ ЗА СЕАНС (CP:R 229)',kind='h1'); r+=1
    mput(ws,f'B{r}:C{r}','ТИП',kind='head'); put(ws,f'D{r}','ЦЕНА',kind='head'); mput(ws,f'E{r}:F{r}','DV / МАТЕРИАЛЫ',kind='head'); mput(ws,f'G{r}:R{r}','ЭФФЕКТ',kind='head'); r+=1
    for name,cost,dv,eff in [('Standard','500 €$','Medical Tech DV15 · материалы 100 €$','Возврат 2d6 Humanity (ср. 7).'),('Extreme','1 000 €$','Medical Tech DV17 · материалы 500 €$','Возврат 4d6 Humanity (ср. 14).'),('Addiction','1 000 €$','Medical Tech DV15 · материалы 500 €$','Снимает одну зависимость.')]:
        mput(ws,f'B{r}:C{r}',name,kind='cell'); put(ws,f'D{r}',cost,kind='cellc'); mput(ws,f'E{r}:F{r}',dv,kind='cell'); mput(ws,f'G{r}:R{r}',eff,kind='cell'); heights(ws,{r:20}); r+=1
    r+=1

    mput(ws,f'B{r}:R{r}','IV · ОРУЖИЕ · МАСТЕР-СПИСОК (8) · СТОЛБЕЦ «В РУКАХ 1–4» ВЫНОСИТ НА 02',kind='h1'); r+=1
    for col,txt in (('B','№'),('C','НАЗВАНИЕ'),('D','ТИП'),('E','НАВЫК'),('F','УРОН'),('G','ROF'),('H','МАГ.'),('I','ПАТРОНЫ'),('J','КАЧЕСТВО'),('K','В РУКАХ'),('L','БАЗА АТАКИ'),('M','ЗАМЕТКИ'),('N','ЦЕНА'),('O','В БЮДЖЕТ'),('R','ЭФФЕКТ')):
        put(ws,f'{col}{r}',txt,kind='head')
    r+=1
    for i in range(CAMP_W_LAST-CAMP_W_FIRST+1):
        rr=CAMP_W_FIRST+i
        put(ws,f'B{rr}',i+1,kind='cellc')
        wname = EXAMPLE_WEAPONS[i][0] if example and i < len(EXAMPLE_WEAPONS) else None
        put(ws,f'C{rr}',wname,kind='input'); dv_catalog(ws,f'C{rr}',cat_last)
        put(ws,f'D{rr}',f"=IFERROR(INDEX({CATC},MATCH($C{rr},{CATA},0)),\"\")",kind='auto_l')
        put(ws,f'E{rr}',f"=IFERROR(INDEX({CATD},MATCH($C{rr},{CATA},0)),\"\")",kind='auto_l')
        put(ws,f'F{rr}',f"=IFERROR(INDEX({CATE},MATCH($C{rr},{CATA},0)),\"\")",kind='auto')
        put(ws,f'G{rr}',f"=IFERROR(INDEX({CATF},MATCH($C{rr},{CATA},0)),\"\")",kind='auto')
        put(ws,f'H{rr}',f"=IFERROR(INDEX({CATG},MATCH($C{rr},{CATA},0)),\"\")",kind='auto')
        put(ws,f'I{rr}',EXAMPLE_WEAPONS[i][1] if example and i < len(EXAMPLE_WEAPONS) else None,kind='input')
        put(ws,f'J{rr}',EXAMPLE_WEAPONS[i][2] if example and i < len(EXAMPLE_WEAPONS) else 'Standard',kind='inputc'); dv_list(ws,f'J{rr}',['Standard','Excellent','Poor'])
        put(ws,f'K{rr}',EXAMPLE_WEAPONS[i][3] if example and i < len(EXAMPLE_WEAPONS) else None,kind='inputc'); dv_list(ws,f'K{rr}',['1','2','3','4'])
        put(ws,f'L{rr}',f"=IF($C{rr}=\"\",\"\",IFERROR(INDEX({S_PLAY}!$I$35:$I$100,MATCH($E{rr},{S_PLAY}!$C$35:$C$100,0))+IF($J{rr}=\"Excellent\",1,IF($J{rr}=\"Poor\",-1,0)),0))",kind='auto')
        put(ws,f'M{rr}',None,kind='input')
        put(ws,f'N{rr}',f"=IF($C{rr}=\"\",\"\",IFERROR(INDEX({CATR},MATCH($C{rr},{CATA},0)),0))",kind='auto',fmt=CASH_FMT)
        put(ws,f'O{rr}',f"=IF($C{rr}=\"\",\"\",IF(COUNTIF($C${CAMP_I_FIRST}:$C${CAMP_I_LAST},$C{rr})>0,0,$N{rr}))",kind='auto',fmt=CASH_FMT)
        put(ws,f'R{rr}',f"=IFERROR(INDEX({CATT},MATCH($C{rr},{CATA},0)),\"\")",kind='cell'); heights(ws,{rr:16})
    r=CAMP_W_LAST+1
    mput(ws,f'B{r}:R{r}','Атака = 1d10 + БАЗА АТАКИ (навык + стата с штрафом брони).',kind='note'); r+=2

    mput(ws,f'B{r}:R{r}','V · БРОНЯ И ЩИТ · ЛУЧШИЙ SP В ЛОКАЦИИ, ШТРАФ ОДИН РАЗ',kind='h1'); r+=1
    for col,txt in (('B','№'),('C','НАЗВАНИЕ'),('D','ЛОКАЦИЯ'),('E','НАДЕТО'),('F','SP'),('G','HP (ЩИТ)'),('H','ШТРАФ REF'),('I','ШТРАФ DEX'),('J','ШТРАФ MOVE'),('K','SP СЕЙЧАС'),('L','ЭФФ. SP'),('M','ЗАМЕТКИ'),('N','ЦЕНА'),('O','В БЮДЖЕТ')):
        put(ws,f'{col}{r}',txt,kind='head')
    r+=1
    for i in range(CAMP_A_LAST-CAMP_A_FIRST+1):
        rr=CAMP_A_FIRST+i
        put(ws,f'B{rr}',i+1,kind='cellc')
        aname = EXAMPLE_ARMOR[i][0] if example and i < len(EXAMPLE_ARMOR) else None
        put(ws,f'C{rr}',aname,kind='input'); dv_catalog(ws,f'C{rr}',cat_last)
        put(ws,f'D{rr}',EXAMPLE_ARMOR[i][1] if example and i < len(EXAMPLE_ARMOR) else 'Тело',kind='inputc'); dv_list(ws,f'D{rr}',['Голова','Тело','Щит'])
        put(ws,f'E{rr}',EXAMPLE_ARMOR[i][2] if example and i < len(EXAMPLE_ARMOR) else 'Нет',kind='inputc'); dv_list(ws,f'E{rr}',['Да','Нет'])
        put(ws,f'F{rr}',f"=IFERROR(INDEX({CATH},MATCH($C{rr},{CATA},0)),0)",kind='auto')
        put(ws,f'G{rr}',f"=IFERROR(INDEX({CATI},MATCH($C{rr},{CATA},0)),0)",kind='auto')
        put(ws,f'H{rr}',f"=IFERROR(INDEX({CATJ},MATCH($C{rr},{CATA},0)),0)",kind='auto')
        put(ws,f'I{rr}',f"=IFERROR(INDEX({CATK},MATCH($C{rr},{CATA},0)),0)",kind='auto')
        put(ws,f'J{rr}',f"=IFERROR(INDEX({CATL},MATCH($C{rr},{CATA},0)),0)",kind='auto')
        put(ws,f'K{rr}',None,kind='inputc')
        put(ws,f'L{rr}',f"=IF($E{rr}<>\"Да\",0,IF($K{rr}<>\"\",$K{rr},$F{rr}))",kind='auto')
        put(ws,f'M{rr}',None,kind='input')
        put(ws,f'N{rr}',f"=IF($C{rr}=\"\",\"\",IFERROR(INDEX({CATR},MATCH($C{rr},{CATA},0)),0))",kind='auto',fmt=CASH_FMT)
        put(ws,f'O{rr}',f"=IF($C{rr}=\"\",\"\",IF(COUNTIF($C${CAMP_I_FIRST}:$C${CAMP_I_LAST},$C{rr})>0,0,$N{rr}))",kind='auto',fmt=CASH_FMT); heights(ws,{rr:16})
    r=CAMP_A_LAST+1
    mput(ws,f'B{r}:C{r}','SP ГОЛОВЫ',kind='kv'); put(ws,f'D{r}',f"=MAX(IF($D${CAMP_A_FIRST}:$D${CAMP_A_LAST}=\"Голова\",IF($E${CAMP_A_FIRST}:$E${CAMP_A_LAST}=\"Да\",$L${CAMP_A_FIRST}:$L${CAMP_A_LAST},0),0))",kind='auto'); mput(ws,f'E{r}:R{r}','Лучший SP в локации.',kind='cell'); r+=1
    mput(ws,f'B{r}:C{r}','SP ТЕЛА',kind='kv'); put(ws,f'D{r}',f"=MAX(IF($D${CAMP_A_FIRST}:$D${CAMP_A_LAST}=\"Тело\",IF($E${CAMP_A_FIRST}:$E${CAMP_A_LAST}=\"Да\",$L${CAMP_A_FIRST}:$L${CAMP_A_LAST},0),0))",kind='auto'); mput(ws,f'E{r}:R{r}','Вся броня локации аблейтится одновременно.',kind='cell'); r+=1
    mput(ws,f'B{r}:C{r}','ЩИТ HP',kind='kv'); put(ws,f'D{r}',f"=MAX(IF($D${CAMP_A_FIRST}:$D${CAMP_A_LAST}=\"Щит\",IF($E${CAMP_A_FIRST}:$E${CAMP_A_LAST}=\"Да\",$G${CAMP_A_FIRST}:$G${CAMP_A_LAST},0),0))",kind='auto'); mput(ws,f'E{r}:R{r}','Обычный 10 HP, усиленный 15 HP.',kind='cell'); r+=1
    mput(ws,f'B{r}:C{r}','ШТРАФ БРОНИ REF/DEX/MOVE',kind='kv')
    put(ws,f'H{r}',f"=MIN(IF($E${CAMP_A_FIRST}:$E${CAMP_A_LAST}=\"Да\",$H${CAMP_A_FIRST}:$H${CAMP_A_LAST},0))",kind='auto')
    put(ws,f'I{r}',f"=MIN(IF($E${CAMP_A_FIRST}:$E${CAMP_A_LAST}=\"Да\",$I${CAMP_A_FIRST}:$I${CAMP_A_LAST},0))",kind='auto')
    put(ws,f'J{r}',f"=MIN(IF($E${CAMP_A_FIRST}:$E${CAMP_A_LAST}=\"Да\",$J${CAMP_A_FIRST}:$J${CAMP_A_LAST},0))",kind='auto')
    mput(ws,f'K{r}:R{r}','Самый строгий штраф, один раз — уже вычтен в 02.',kind='note'); r+=2

    mput(ws,f'B{r}:R{r}','VI · ИНВЕНТАРЬ · 20 СЛОТОВ',kind='h1'); r+=1
    for col,txt in (('B','№'),('C','НАЗВАНИЕ'),('D','КАТЕГОРИЯ'),('E','ПОДТИП'),('F','КОЛ-ВО'),('G','ЦЕНА'),('H','ЦЕНА СВОЯ'),('I','СУММА'),('J','ГДЕ НОСИТ'),('K','ЗАМЕТКА'),('R','ОПИСАНИЕ')):
        put(ws,f'{col}{r}',txt,kind='head')
    r+=1
    for i in range(CAMP_I_LAST-CAMP_I_FIRST+1):
        rr=CAMP_I_FIRST+i
        put(ws,f'B{rr}',i+1,kind='cellc')
        inv = EXAMPLE_INVENTORY[i] if example and i < len(EXAMPLE_INVENTORY) else (None,None,None,None)
        iname = inv[0] if isinstance(inv,tuple) else None
        iwhere = inv[1] if isinstance(inv,tuple) and len(inv)>1 else None
        iqty = inv[2] if isinstance(inv,tuple) and len(inv)>2 and inv[2]!='' else None
        inote = inv[3] if isinstance(inv,tuple) and len(inv)>3 else None
        put(ws,f'C{rr}',iname,kind='input'); dv_catalog(ws,f'C{rr}',cat_last)
        put(ws,f'D{rr}',f"=IFERROR(INDEX({CATB},MATCH($C{rr},{CATA},0)),\"\")",kind='auto_l')
        put(ws,f'E{rr}',f"=IFERROR(INDEX({CATC},MATCH($C{rr},{CATA},0)),\"\")",kind='auto_l')
        put(ws,f'F{rr}',6 if i==3 and example else (iqty if isinstance(iqty,int) or (isinstance(iqty,str) and iqty.isdigit()) else None),kind='inputc')
        put(ws,f'G{rr}',f"=IFERROR(INDEX({CATR},MATCH($C{rr},{CATA},0)),\"\")",kind='auto',fmt=CASH_FMT)
        put(ws,f'H{rr}',None,kind='inputc',fmt=CASH_FMT)
        put(ws,f'I{rr}',f"=IF($C{rr}=\"\",\"\",IF($H{rr}<>\"\",$H{rr},IF(ISNUMBER($G{rr}),$G{rr},0))*IF($F{rr}=\"\",1,$F{rr}))",kind='auto',fmt=CASH_FMT)
        put(ws,f'J{rr}',iwhere,kind='input'); put(ws,f'K{rr}',inote,kind='input')
        put(ws,f'R{rr}',f"=IFERROR(LEFT(INDEX({CATT},MATCH($C{rr},{CATA},0)),90),\"\")",kind='cell'); heights(ws,{rr:16})
    r=CAMP_I_LAST+1
    mput(ws,f'B{r}:D{r}','ИТОГО ИНВЕНТАРЬ',kind='kv'); put(ws,f'I{r}',f"=SUM($I${CAMP_I_FIRST}:$I${CAMP_I_LAST})",kind='auto',fmt=CASH_FMT); r+=2

    mput(ws,f'B{r}:R{r}','VII · КАССА · ДОХОДЫ И ТРАТЫ В ИГРЕ',kind='h1'); r+=1
    put(ws,f'B{r}','ДАТА',kind='head'); mput(ws,f'C{r}:D{r}','ЧТО',kind='head'); put(ws,f'E{r}','ОБОРОТ ±',kind='head'); put(ws,f'F{r}','БАЛАНС',kind='head'); mput(ws,f'G{r}:R{r}','ЗАМЕТКА',kind='head'); r+=1
    for i in range(CAMP_CASH_LAST-CAMP_CASH_FIRST+1):
        rr=CAMP_CASH_FIRST+i
        put(ws,f'B{rr}',None,kind='input'); mput(ws,f'C{rr}:D{rr}',None,kind='input'); put(ws,f'E{rr}',None,kind='inputc',fmt=CASH_FMT)
        put(ws,f'F{rr}',f"=$I$3+SUM($E${CAMP_CASH_FIRST}:$E{rr})",kind='auto',fmt=CASH_FMT); mput(ws,f'G{rr}:R{rr}',None,kind='input'); heights(ws,{rr:16})
    r=CAMP_CASH_LAST+1
    mput(ws,f'B{r}:D{r}','ИТОГО ОБОРОТ / БАЛАНС',kind='kv'); put(ws,f'E{r}',f"=SUM($E${CAMP_CASH_FIRST}:$E${CAMP_CASH_LAST})",kind='auto',fmt=CASH_FMT); put(ws,f'F{r}',f"=$I$3+SUM($E${CAMP_CASH_FIRST}:$E${CAMP_CASH_LAST})",kind='auto',fmt=CASH_FMT); r+=2

    mput(ws,f'B{r}:R{r}','VIII · КРИТ-ТРАВМЫ · ВЫБЕРИ ЛОКАЦИЮ И 2D6',kind='h1'); r+=1
    for col,txt in (('B','№'),('C','ЛОКАЦИЯ'),('D','2D6'),('E','ТРАВМА (АВТО)'),('F','ЭФФЕКТ'),('G','БЫСТРЫЙ ФИКС'),('H','ЛЕЧЕНИЕ'),('I','СТАТУС')):
        put(ws,f'{col}{r}',txt,kind='head')
    mput(ws,f'J{r}:R{r}','ЗАМЕТКИ',kind='head'); r+=1
    for i in range(CAMP_CRIT_LAST-CAMP_CRIT_FIRST+1):
        rr=CAMP_CRIT_FIRST+i
        put(ws,f'B{rr}',i+1,kind='cellc'); put(ws,f'C{rr}','Тело',kind='inputc'); dv_list(ws,f'C{rr}',['Тело','Голова'])
        put(ws,f'D{rr}',None,kind='inputc'); dv_num(ws,f'D{rr}',2,12)
        put(ws,f'E{rr}',f"=IF($D{rr}=\"\",\"\",IF($C{rr}=\"Тело\",IFERROR(INDEX({S_REF}!$C$22:$C$32,MATCH($D{rr},{S_REF}!$B$22:$B$32,0)),\"—\"),IF($C{rr}=\"Голова\",IFERROR(INDEX({S_REF}!$C$37:$C$47,MATCH($D{rr},{S_REF}!$B$37:$B$47,0)),\"—\"),\"—\")))",kind='auto_l')
        put(ws,f'F{rr}',f"=IF($D{rr}=\"\",\"\",IF($C{rr}=\"Тело\",IFERROR(INDEX({S_REF}!$D$22:$D$32,MATCH($D{rr},{S_REF}!$B$22:$B$32,0)),\"—\"),IF($C{rr}=\"Голова\",IFERROR(INDEX({S_REF}!$D$37:$D$47,MATCH($D{rr},{S_REF}!$B$37:$B$47,0)),\"—\"),\"—\")))",kind='cell')
        put(ws,f'G{rr}',f"=IF($D{rr}=\"\",\"\",IF($C{rr}=\"Тело\",IFERROR(INDEX({S_REF}!$I$22:$I$32,MATCH($D{rr},{S_REF}!$B$22:$B$32,0)),\"—\"),IF($C{rr}=\"Голова\",IFERROR(INDEX({S_REF}!$I$37:$I$47,MATCH($D{rr},{S_REF}!$B$37:$B$47,0)),\"—\"),\"—\")))",kind='cellc')
        put(ws,f'H{rr}',f"=IF($D{rr}=\"\",\"\",IF($C{rr}=\"Тело\",IFERROR(INDEX({S_REF}!$L$22:$L$32,MATCH($D{rr},{S_REF}!$B$22:$B$32,0)),\"—\"),IF($C{rr}=\"Голова\",IFERROR(INDEX({S_REF}!$L$37:$L$47,MATCH($D{rr},{S_REF}!$B$37:$B$47,0)),\"—\"),\"—\")))",kind='cellc')
        put(ws,f'I{rr}','Нет',kind='inputc'); dv_list(ws,f'I{rr}',['Активна','Вылечена','Нет'])
        mput(ws,f'J{rr}:R{rr}',None,kind='input'); heights(ws,{rr:20})
    r=CAMP_CRIT_LAST+1
    mput(ws,f'B{r}:R{r}','Крит = 2+ шестёрок на кубах урона: +5 урона напрямую в HP.',kind='note'); r+=2

    r=130
    mput(ws,f'B{r}:R{r}','IX · ЗАВИСИМОСТИ, РЕПУТАЦИЯ, IP',kind='h1'); r+=1
    mput(ws,f'B{r}:C{r}','ПОКАЗАТЕЛЬ',kind='head'); put(ws,f'D{r}','ЗНАЧЕНИЕ',kind='head'); mput(ws,f'E{r}:R{r}','ПРАВИЛО',kind='head'); r+=1
    put(ws,f'B{r}','ЗАВИСИМОСТИ (ВВОД)',kind='kv'); mput(ws,f'C{r}:R{r}','Нет. Пьёт, но не запойно.' if example else None,kind='input'); r+=1
    put(ws,f'B{r}','ТРИГГЕРЫ / АБСТИНЕНЦИЯ',kind='kv'); mput(ws,f'C{r}:R{r}','Триггер: сирена + запах горелого пластика — переулок, где погиб напарник.' if example else None,kind='input'); r+=1
    put(ws,f'B{r}','СНЯТИЕ ЗАВИСИМОСТИ',kind='kv'); mput(ws,f'C{r}:R{r}','Терапия: 1 неделя, 1000 €$ + материалы 500 €$, Medical Tech DV15',kind='cell'); r+=1
    mput(ws,f'B{r}:C{r}','РЕПУТАЦИЯ',kind='kv'); put(ws,f'D{r}',0,kind='inputc'); mput(ws,f'E{r}:R{r}','Растёт за громкие дела.',kind='cell'); r+=1
    mput(ws,f'B{r}:C{r}','IP ЗАРАБОТАНО',kind='kv'); put(ws,f'D{r}',0,kind='inputc'); mput(ws,f'E{r}:R{r}','GM выдаёт после сессии.',kind='cell'); r+=1
    mput(ws,f'B{r}:C{r}','IP ПОТРАЧЕНО (АВТО)',kind='kv'); put(ws,f'D{r}',f"=SUM($F$141:$F$150)",kind='auto'); mput(ws,f'E{r}:R{r}','Сумма по таблице X ниже.',kind='cell'); r+=1
    mput(ws,f'B{r}:C{r}','IP СВОБОДНО',kind='kv'); put(ws,f'D{r}',f"=D133-D134",kind='auto'); mput(ws,f'E{r}:R{r}','Заработано минус потрачено.',kind='cell'); r+=2

    mput(ws,f'B{r}:R{r}','X · ЧТО УЛУЧШИЛИ ЗА IP',kind='h1'); r+=1
    put(ws,f'B{r}','ДАТА',kind='head'); put(ws,f'C{r}','ЧТО УЛУЧШИЛИ',kind='head'); put(ws,f'D{r}','ТИП',kind='head'); put(ws,f'E{r}','НОВЫЙ УР.',kind='head'); put(ws,f'F{r}','СТОИМОСТЬ IP',kind='head'); mput(ws,f'G{r}:R{r}','ЗАМЕТКА',kind='head'); r+=1
    ex_ip=[
        ('','Evasion → 5','НАВЫК','','100 IP'),
        ('','Evasion → 6','НАВЫК','','120 IP'),
        ('','Martial Arts (Thamoc) → 6','НАВЫК ×2','','240 IP'),
        ('','Brawling → 6','НАВЫК','','120 IP'),
        ('','Shoulder Arms → 6','НАВЫК','','120 IP'),
        ('','Tactics → 2','НАВЫК','','60 IP'),
        ('','Human Perception → 3','НАВЫК','','60 IP'),
        ('','First Aid → 3','НАВЫК','','60 IP'),
        ('','РАНГ Lawman → 5','РОЛЬ','','300 IP'),
    ] if example else []
    for i in range(10):
        rr=141+i
        put(ws,f'B{rr}',None,kind='input')
        put(ws,f'C{rr}',ex_ip[i][1] if i < len(ex_ip) else None,kind='input')
        put(ws,f'D{rr}',ex_ip[i][2] if i < len(ex_ip) else 'НАВЫК',kind='inputc'); dv_list(ws,f'D{rr}',['НАВЫК','НАВЫК ×2','РОЛЬ','СТАТА (GM)'])
        put(ws,f'E{rr}',None,kind='inputc')
        put(ws,f'F{rr}',f"=IF(OR($E{rr}=\"\",$D{rr}=\"\"),\"\",IF($D{rr}=\"РОЛЬ\",60*$E{rr},IF($D{rr}=\"НАВЫК ×2\",40*$E{rr},IF($D{rr}=\"НАВЫК\",20*$E{rr},\"\"))))",kind='auto')
        mput(ws,f'G{rr}:R{rr}',ex_ip[i][4] if i < len(ex_ip) else None,kind='input')
    r=151
    mput(ws,f'B{r}:E{r}','ИТОГО ПОТРАЧЕНО IP',kind='kv'); put(ws,f'F{r}',f"=SUM($F$141:$F$150)",kind='auto'); mput(ws,f'G{r}:R{r}','20×ур — обычный, 40× — ×2, 60×ранг — роль.',kind='note'); r+=2

    mput(ws,f'B{r}:R{r}','XI · ЛОГ ДЕЛ (СЕССИИ)',kind='h1'); r+=1
    put(ws,f'B{r}','ДАТА',kind='head'); mput(ws,f'C{r}:D{r}','ДЕЛО / СЕССИЯ',kind='head'); put(ws,f'E{r}','РОЛЬ В ДЕЛЕ',kind='head'); put(ws,f'F{r}','НАГРАДА €$',kind='head'); put(ws,f'G{r}','IP',kind='head'); mput(ws,f'H{r}:R{r}','ИТОГ / ЗАМЕТКА',kind='head'); r+=1
    for i in range(14):
        rr=155+i
        put(ws,f'B{rr}',None,kind='input'); mput(ws,f'C{rr}:D{rr}',None,kind='input'); put(ws,f'E{rr}',None,kind='input'); put(ws,f'F{rr}',None,kind='inputc',fmt=CASH_FMT); put(ws,f'G{rr}',None,kind='inputc'); mput(ws,f'H{rr}:R{rr}',None,kind='input'); heights(ws,{rr:16})
    r=169
    mput(ws,f'B{r}:E{r}','ИТОГО ЗА КАМПАНИЮ',kind='kv'); put(ws,f'F{r}',f"=SUM($F$155:$F$168)",kind='auto',fmt=CASH_FMT); put(ws,f'G{r}',f"=SUM($G$155:$G$168)",kind='auto'); r+=2

    mput(ws,f'B{r}:R{r}','XII · ДОЛГИ, ЦЕЛИ И КРЮЧКИ',kind='h1'); r+=1
    put(ws,f'B{r}','ДОЛГИ И ОБЯЗАТЕЛЬСТВА',kind='kv'); mput(ws,f'C{r}:R{r+1}',EXAMPLE_DOSSIER.get('subscriptions') if example else None,kind='input'); heights(ws,{r:20,r+1:20}); r+=2
    put(ws,f'B{r}','ЖИЗНЕННЫЕ ЦЕЛИ / КРЮЧКИ ДЛЯ GM',kind='kv'); mput(ws,f'C{r}:R{r+1}','Закрыть дело о складе и вернуть имя. Найти, кому в управлении это было выгодно.' if example else None,kind='input'); heights(ws,{r:20,r+1:20}); r+=2
    put(ws,f'B{r}','ТАБУ И ТРИГГЕРЫ',kind='kv'); mput(ws,f'C{r}:R{r+1}','Не трогает детей. Не работает против копов — даже тех, кто его выкинул.' if example else None,kind='input'); heights(ws,{r:20,r+1:20}); r+=3
    mput(ws,f'B{r}:R{r}','Источники: Cyberpunk RED Corebook (79,129,186–190,223,229,408), CEMK (26–30), Spes Desperata.',kind='note')
    return ws

# ---------------- КАТАЛОГ
def build_catalog(wb, rows):
    ws = wb.create_sheet(NAMES['cat'])
    widths(ws, {'A':38,'B':22,'C':26,'D':16,'E':10,'F':6,'G':7,'H':6,'I':6,'J':10,'K':10,'L':10,'M':6,'N':12,'O':6,'P':10,'Q':12,'R':12,'S':22,'T':80})
    sheet_setup(ws, PAL['muted'], freeze='A3')
    mput(ws,'A1:T1',f'КАТАЛОГ  ▚  {len(rows)} ПОЗИЦИЙ  ▚  НЕ ПРАВЬ — НА НЕГО ССЫЛАЮТСЯ ФОРМУЛЫ',kind='banner'); heights(ws,{1:18})
    for idx,txt in enumerate(CAT_HEAD, start=1): put(ws,f'{get_column_letter(idx)}2',txt,kind='head')
    for i,row in enumerate(rows):
        r=3+i
        for idx,val in enumerate(row, start=1):
            col=get_column_letter(idx)
            if idx==18: put(ws,f'{col}{r}',val,kind='auto',fmt=CASH_FMT)
            elif idx in (8,9,10,11,12,13,6,7): put(ws,f'{col}{r}',val if val!='' else None,kind='cellc')
            else: put(ws,f'{col}{r}',val,kind='cell')
    ws.auto_filter.ref=f'A2:T{3+len(rows)-1}'
    return ws

# ---------------- СПРАВКА + ПРАВИЛА (сокращённо, как раньше но без багов)
def build_reference(wb, data):
    ws = wb.create_sheet(NAMES['ref'])
    widths(ws, {'A':2,'B':26,'C':16,'D':16,'E':16,'F':16,'G':16,'H':16,'I':16,'J':16,'K':16,'L':16,'M':16,'N':40,'O':2})
    sheet_setup(ws, PAL['gold'])
    mput(ws,'B1:N1','СПРАВКА  ▚  DV · ДИСТАНЦИИ · УКРЫТИЯ · РАНЫ · IP · 2070',kind='banner'); heights(ws,{1:18})
    r=3
    mput(ws,f'B{r}:N{r}','I · СЛОЖНОСТЬ ПРОВЕРОК (DV) · CP:R 130',kind='h1'); r+=1
    put(ws,f'B{r}','СЛОЖНОСТЬ',kind='head'); put(ws,f'C{r}','DV',kind='head'); mput(ws,f'D{r}:N{r}','КОГДА БРОСАТЬ',kind='head')
    for name,dv in RULES.GENERAL_DV:
        r+=1; put(ws,f'B{r}',name,kind='cell'); put(ws,f'C{r}',dv,kind='auto'); mput(ws,f'D{r}:N{r}',{'Simple':'Плюнуть в урну.','Everyday':'Рутинная работа.','Difficult':'Проф задача.','Professional':'Работа специалиста.','Heroic':'На грани.','Incredible':'Легендарно.','Legendary':'Почти невозможно.'}.get(name,''),kind='cell')
    r+=2
    mput(ws,f'B{r}:N{r}','II · ДИСТАНЦИЯ DV ПО ТИПУ ОРУЖИЯ · CP:R 172–173',kind='h1'); r+=1
    for idx,head in enumerate(data['range_table'][0]): put(ws,f'{get_column_letter(2+idx)}{r}',head,kind='head')
    for row in data['range_table'][1:]:
        r+=1
        for idx,val in enumerate(row): put(ws,f'{get_column_letter(2+idx)}{r}',val if val not in ('N/A','') else '—',kind='cellc' if idx else 'cell')
    r+=2
    mput(ws,f'B{r}:N{r}','III · АВТООГОНЬ',kind='h1'); r+=1
    for idx,head in enumerate(data['autofire_table'][0]): put(ws,f'{get_column_letter(2+idx)}{r}',head,kind='head')
    put(ws,f'{get_column_letter(2+len(data["autofire_table"][0]))}{r}','МАКС. МНОЖИТЕЛЬ',kind='head')
    mult={'Machine Pistol':'×3','SMGs':'×3','Assault Rifle':'×4','Machine Gun':'×4'}
    for row in data['autofire_table'][1:]:
        r+=1
        for idx,val in enumerate(row): put(ws,f'{get_column_letter(2+idx)}{r}',val,kind='cellc' if idx else 'cell')
        put(ws,f'{get_column_letter(2+len(row))}{r}',mult.get(row[0],'×3'),kind='cellc')
    r+=1; mput(ws,f'B{r}:N{r}','Урон = 2d6 × (превышение DV), макс множитель оружия.',kind='note')
    r+=2
    mput(ws,f'B{r}:N{r}','IV · ПРИЦЕЛЬНЫЕ, УКРЫТИЯ',kind='h1'); r+=1
    put(ws,f'B{r}','СИТУАЦИЯ',kind='head'); put(ws,f'C{r}','МОДИФ.',kind='head'); mput(ws,f'D{r}:N{r}','ЧТО ПРОИСХОДИТ',kind='head')
    for label,mod,text in [('Прицельный (ROF1)','−8','Одна атака, эффект по локации.'),('…в голову','×2 урона','Прошедший урон ×2 (треснувший череп ×3).'),('…в предмет','роняет','≥1 урона — роняет.'),('…в ногу','Broken Leg','≥1 урона — Broken Leg.'),('Подавление','WILL+Concentration','Действие +10 пуль.'),('Картечь','DV13','Все цели впереди 6 м, 3d6.'),('Взрывчатка','10×10 м','Один бросок на всех.')]:
        r+=1; put(ws,f'B{r}',label,kind='cell'); put(ws,f'C{r}',mod,kind='cellc'); mput(ws,f'D{r}:N{r}',text,kind='cell')
    r+=1; put(ws,f'B{r}','МАТЕРИАЛ УКРЫТИЯ',kind='head'); put(ws,f'C{r}','ТОНКОЕ',kind='head'); put(ws,f'D{r}','ТОЛСТОЕ',kind='head'); mput(ws,f'E{r}:N{r}','ПРИМЕРЫ',kind='head')
    for mat,thin,thick,ex in [('Сталь','25 HP','50 HP','Дверь машины.'),('Камень','20 HP','40 HP','Кирпичная кладка.'),('Бронестекло','15 HP','30 HP','Витрина банка.'),('Бетон','10 HP','25 HP','Парапет.'),('Дерево','5 HP','20 HP','Стол.'),('Гипс','0 HP','15 HP','Перегородка.')]:
        r+=1; put(ws,f'B{r}',mat,kind='cell'); put(ws,f'C{r}',thin,kind='cellc'); put(ws,f'D{r}',thick,kind='cellc'); mput(ws,f'E{r}:N{r}',ex,kind='cell')
    r+=2; mput(ws,f'B{r}:N{r}','V · ДЕЙСТВИЯ В ХОДЕ',kind='h1'); r+=1
    put(ws,f'B{r}','ДЕЙСТВИЕ',kind='head'); mput(ws,f'C{r}:N{r}','ЧТО ДЕЛАЕТ',kind='head')
    for name,text in [('Move Action','MOVE×2 м.'),('Attack','Атака.'),('Choke','Только против схваченного.'),('Equip/Drop Shield','Взять/бросить щит.'),('Grab','Схватить.'),('Hold Action','Отложить.'),('Reload','Перезарядить.'),('Run','Доп. Move.'),('Stabilize','Стабилизировать.'),('Use Skill','Быстрая проверка.')]:
        r+=1; put(ws,f'B{r}',name,kind='cell'); mput(ws,f'C{r}:N{r}',text,kind='cell')
    r+=2; mput(ws,f'B{r}:N{r}','VI · РАНЫ, СМЕРТЬ',kind='h1'); r+=1
    put(ws,f'B{r}','СОСТОЯНИЕ',kind='head'); put(ws,f'C{r}','ПОРОГ',kind='head'); mput(ws,f'D{r}:N{r}','ЭФФЕКТ',kind='head')
    for name,thr,eff,stab in RULES.WOUND_STATES:
        r+=1; put(ws,f'B{r}',name,kind='cell'); put(ws,f'C{r}',thr,kind='cellc'); mput(ws,f'D{r}:N{r}',f'{eff} · {stab}',kind='cell')
    r+=2; mput(ws,f'B{r}:N{r}','VII · IP СТОИМОСТЬ',kind='h1'); r+=1
    put(ws,f'B{r}','ЧТО УЛУЧШАЕМ',kind='head')
    for i in range(10): put(ws,f'{get_column_letter(3+i)}{r}',f'{i+1}',kind='head')
    for label,values in (('НАВЫК 20×', ['20','40','60','80','100','120','140','160','180','200']),('НАВЫК ×2 40×', ['40','80','120','160','200','240','280','320','360','400']),('РОЛЬ 60×', ['60','120','180','240','300','360','420','480','540','600'])):
        r+=1; put(ws,f'B{r}',label,kind='cell')
        for i,val in enumerate(values): put(ws,f'{get_column_letter(3+i)}{r}',int(val),kind='auto')
    r+=2; mput(ws,f'B{r}:N{r}','VIII · LAWMAN BACKUP',kind='h1'); r+=1
    for idx,head in enumerate(['РАНГ','БОЕВОЙ №','SP','HP','MOVE/BODY','КТО ПРИЕДЕТ']): put(ws,f'{get_column_letter(2+idx)}{r}',head,kind='head')
    for rank,cn,sp,hp,mb,who in [('1–2','8','7','20','4/4','Корп охрана: 4 копа.'),('3–4','10','7','25','5/5','Патрульные: 4 копа.'),('5–7','14','13','35','4/4','Шериф: 2 маунти.'),('8','16','15','50','6/6','Маршал: Superbike.'),('9','15','18','35','4/4','C-SWAT: 2 бойца.'),('10','14','11','35','6/6','Нац. силы: 2 агента.')]:
        r+=1
        for idx,val in enumerate([rank,cn,sp,hp,mb]): put(ws,f'{get_column_letter(2+idx)}{r}',val,kind='cellc' if idx else 'cell')
        mput(ws,f'G{r}:N{r}',who,kind='cell')
    r+=2; mput(ws,f'B{r}:N{r}','IX · КРИТ-ТРАВМЫ ТЕЛА · 2D6 · CP:R 187–188',kind='h1'); r+=1
    put(ws,f'B{r}','2D6',kind='head'); put(ws,f'C{r}','ТРАВМА ТЕЛА',kind='head'); mput(ws,f'D{r}:H{r}','ЭФФЕКТ',kind='head'); mput(ws,f'I{r}:K{r}','БЫСТРЫЙ ФИКС',kind='head'); mput(ws,f'L{r}:N{r}','ЛЕЧЕНИЕ',kind='head')
    for idx,row in enumerate(RULES.CRIT_BODY):
        rr=r+1+idx; put(ws,f'B{rr}',row[0],kind='cellc'); put(ws,f'C{rr}',row[1],kind='cell'); mput(ws,f'D{rr}:H{rr}',row[2],kind='cell'); mput(ws,f'I{rr}:K{rr}',row[3],kind='cellc'); mput(ws,f'L{rr}:N{rr}',row[4],kind='cellc')
    r+=1+len(RULES.CRIT_BODY)
    r+=2; mput(ws,f'B{r}:N{r}','X · КРИТ-ТРАВМЫ ГОЛОВЫ',kind='h1'); r+=1
    put(ws,f'B{r}','2D6',kind='head'); put(ws,f'C{r}','ТРАВМА ГОЛОВЫ',kind='head'); mput(ws,f'D{r}:H{r}','ЭФФЕКТ',kind='head'); mput(ws,f'I{r}:K{r}','БЫСТРЫЙ ФИКС',kind='head'); mput(ws,f'L{r}:N{r}','ЛЕЧЕНИЕ',kind='head')
    for idx,row in enumerate(RULES.CRIT_HEAD):
        rr=r+1+idx; put(ws,f'B{rr}',row[0],kind='cellc'); put(ws,f'C{rr}',row[1],kind='cell'); mput(ws,f'D{rr}:H{rr}',row[2],kind='cell'); mput(ws,f'I{rr}:K{rr}',row[3],kind='cellc'); mput(ws,f'L{rr}:N{rr}',row[4],kind='cellc')
    return ws

def build_rules(wb):
    ws = wb.create_sheet(NAMES['rul'])
    widths(ws, {'A':2,'B':28,'C':120,'D':2})
    sheet_setup(ws, PAL['banner_bg'])
    mput(ws,'B1:C1','КАК ПОЛЬЗОВАТЬСЯ ЭТИМ ЛИСТОМ · NC//NET · FIXER EDITION · 2070',kind='banner'); heights(ws,{1:28})
    r=3
    blocks=[
        ('I · ЦВЕТА И ЛОГИКА',[('Янтарные поля','Сюда пишешь ты: имена, отыгрыш, уровни, оружие, патроны, даты.'),('Тёмные поля','Считается само. Можно перебить цифрой — формула заменится.'),('Красный и «⚠»','Проверки: перерасход бюджета, лишние очки, киберпсихоз.'),('Шрифты','Oswald — заголовки, Roboto — текст, Roboto Mono — цифры. Есть в Google Таблицах.'),('Альбомная','Все листы альбомные и печатаются по ширине.')]),
        ('II · ГДЕ ЧТО ЛЕЖИТ',[('01 ДОСЬЕ — FIXER','Кто персонаж глазами фиксера: ID, как выглядит, что внутри, откуда, как работает, связи, приводы, оценка фиксера, автосводка, заметки, Lines/Veils. Фото — правый верхний угол.'),('02 ИГРА','Всё для стола: статы 62, производные HP/Humanity/инициатива, быстрый бой SP/щит/штрафы/уклонение/состояние ран/LUCK/наличные, оружие в руках 4 слота, навыки 66+6 с проверками 86/13/пакет роли, быстрый хром и крит-травмы, памятка.'),('03 КАМПАНИЯ','Учёт между сессиями: хром детально, оружие 8 и броня 6 мастер, инвентарь 20, касса 20, крит-травмы 10, зависимости/репутация/IP, улучшения IP, лог дел 14, долги/цели/табу.'),('КАТАЛОГ / СПРАВКА / ПРАВИЛА','Каталог 1092 позиций, справочник DV/укрытий/крит-травм/IP и эта инструкция. Скрыты, но на них ссылаются формулы — не переименовывай листы.')]),
        ('III · ШАГИ СОЗДАНИЯ',[('1. Роль','Выбери роль (10). Пакет роли — 7 навыков мин.2. Lawman — Backup, Solo — Combat Awareness и т.д.'),('2. Lifepath','Общий + ролевой. Результаты — на 01 ДОСЬЕ. Универсальные 5 полей подходят любой роли.'),('3. Характеристики','62 очка на 10 стат, каждая 2–8. Приём: по 6 везде, потом 2 лишних по вкусу. LUCK 2 ок.'),('4. Производные','HP = 10+5×⌈(BODY+WILL)/2⌉, порог серьёзного — половина HP вверх, спасбросок = BODY, Humanity = EMP×10. Всё считается в 02.'),('5. Навыки','86 очков: 26 в 13 обязательных (по 2) + 60 свободных, макс 6. Родной язык 4 бесплатно. ×2 стоят 2 очка.'),('6. Закупка','2550 €$ на оружие/броню/снаряжение/хром + 800 €$ на Fashion/Fashionware. Neuroport при создании бесплатен (0 €$, 0 HL).'),('7. Lifestyle','Жильё 1000 + Kibble 100 = 1100 к 1-му, первый месяц покрыт.')]),
        ('IV · КАК ИГРАТЬ',[('На сессии открой 02 ИГРА','Вверху статы и производные, чуть ниже оружие и броня. Навыки ниже, но проверки справа всегда видны.'),('Между сессиями открой 03 КАМПАНИЯ','Там детальный хром, весь инвентарь, касса, IP и лог. После покупок проверь бюджеты.'),('Фото в досье','Правый клик по заглушке → Заменить изображение. Рекоменд. 460×250 (~1.84:1).'),('Если сломалось','Не удаляй строки внутри блоков — формулы считают фикс диапазоны. Не переименовывай листы.')]),
        ('V · ИСТОЧНИКИ',[('Cyberpunk RED Corebook','Создание (73–89), навыки (86–90), броня/оружие (340–351), бой (170–190), терапия (229), крит (187–188), IP (408), Lifestyle (377).'),('CEMK Rule Book','2070-е: Neuroport (26,35), твики ролей, доступность, ментальная травма (28–30).'),('Spes Desperata','Порядок создания, 62/86, must-have навыки по ролям, закупка, Lifestyle.'),('Дисклеймер','Домашний лист для кампании. Если у стола дом-правила — правь смело.')]),
    ]
    for title,rows in blocks:
        r+=1; mput(ws,f'B{r}:C{r}',title,kind='h1')
        for label,text in rows:
            r+=1; put(ws,f'B{r}',label,kind='kv'); put(ws,f'C{r}',text,kind='text'); ws.row_dimensions[r].height=max(26, 14*(len(text)//90+1))
        r+=1
    return ws

# ---------------- photo placeholder
def make_photo_placeholder(path, width=640, height=380):
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (width, height), (10,10,12))
    draw = ImageDraw.Draw(img)
    for x in range(0,width,18): draw.line([(x,0),(x+height,height)], fill=(26,26,32), width=5)
    draw.rectangle([6,6,width-7,height-7], outline=(255,0,60), width=4)
    draw.text((26,26),'FIXER DB  ·  FILE PHOTO', fill=(255,177,0))
    draw.text((26,height-62),'ФОТО ОБЪЕКТА', fill=(255,255,255))
    draw.text((26,height-40),'вставь портрет — правый клик → Заменить', fill=(166,171,178))
    draw.line([(26,height-74),(width-26,height-74)], fill=(255,0,60), width=2)
    img.save(path); return path

def build_workbook(rows, data, example=False, cat_last=1):
    wb = Workbook(); wb.remove(wb.active)
    set_ranges()
    build_catalog(wb, rows)
    build_reference(wb, data)
    build_dossier(wb, example=example, cat_last=cat_last)
    build_play(wb, example=example, cat_last=cat_last)
    build_campaign(wb, example=example, cat_last=cat_last)
    build_rules(wb)
    order=[NAMES['doc'],NAMES['play'],NAMES['camp'],NAMES['cat'],NAMES['ref'],NAMES['rul']]
    wb._sheets=[wb[name] for name in order]
    for name in [NAMES['cat'],NAMES['ref'],NAMES['rul']]:
        wb[name].sheet_state='hidden'
    tmpdir=tempfile.mkdtemp(prefix='ncnet-sheet-')
    try:
        from openpyxl.drawing.image import Image as XLImage
        ws=wb[NAMES['doc']]
        photo=make_photo_placeholder(os.path.join(tmpdir,'photo.png'))
        img=XLImage(photo); img.width,img.height=460,250
        ws.add_image(img,'F4')
    except Exception as exc:
        print('фото-заглушка не добавлена:', exc)
    return wb, tmpdir

def main():
    out = sys.argv[1] if len(sys.argv)>1 else os.path.join(ROOT, 'sheets', 'NC-NET_CharSheet_2070.xlsx')
    out_example = os.path.join(ROOT, 'sheets', 'NC-NET_CharSheet_2070_EXAMPLE_Lawman.xlsx')
    with open(os.path.join(ROOT, 'app', 'data', 'items.json'), encoding='utf-8') as fh:
        data=json.load(fh)
    rows=catalog_rows(data)
    global CAT_LAST
    CAT_LAST=3+len(rows)-1
    set_ranges()
    wb, tmpdir = build_workbook(rows, data, example=False, cat_last=CAT_LAST)
    wb.save(out)
    print(f'готово (пустой): {out} ({os.path.getsize(out)/1024:.0f} КБ) · листов: {len(wb.sheetnames)} · каталог: {len(rows)}')
    shutil.rmtree(tmpdir, ignore_errors=True)
    set_ranges()
    wb2, tmpdir2 = build_workbook(rows, data, example=True, cat_last=CAT_LAST)
    wb2.save(out_example)
    print(f'готово (пример): {out_example} ({os.path.getsize(out_example)/1024:.0f} КБ)')
    shutil.rmtree(tmpdir2, ignore_errors=True)
    root_copy=os.path.join(ROOT, 'NC-NET_CharSheet_2070.xlsx')
    try:
        shutil.copyfile(out, root_copy)
        print(f'копия в корне: {root_copy}')
    except: pass

if __name__=='__main__':
    main()

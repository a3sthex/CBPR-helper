#!/usr/bin/env python3
"""NC//NET · генератор «необычного» листа персонажа для Cyberpunk RED / CEMK (2070-е).

Собирает .xlsx для загрузки в Google Таблицы / Excel Online. Оформление — HUD Night City:
чёрный фон, красный #FF003C, белый текст и оранжево-жёлтый #FFB100 для наведения/ввода.
Шрифты: Oswald (заголовки), Roboto (текст), Roboto Mono (цифры). Все листы альбомные.
  01 ДОСЬЕ      — дело объекта в две колонки: личность, служба, прошлое, связи, сводка
  02 ОСНОВА     — характеристики, производные, Backup (Lawman), оружие/броня, памятка
  03 НАВЫКИ     — 66 навыков, 86 очков, панель проверок справа (13 обязательных + пакет роли)
  04 ХРОМ       — импланты, HL, срез максимума Humanity, терапия, жизнь и Humanity
  05 СНАРЯЖЕНИЕ — бюджеты 2550/800, оружие, броня, инвентарь, касса
  06 СОСТОЯНИЕ  — трекер крит-травм, зависимости, IP, лог дел
  КАТАЛОГ       — выжимка из app/data/items.json (Data Pool) для автоподстановки
  СПРАВКА       — DV, укрытия, раны, IP, 2070-е и таблицы крит-травм (на них ссылается лист 06)
  ПРАВИЛА       — как пользоваться таблицей

Правила и цены берутся из репозитория: app/rules.py, app/data/items.json,
гайды «Spes Desperata» (app/static/guides-data.js), extracted/text/*.md.

Запуск:  PYTHONPATH=<deps> python3 tools/build_character_sheet_xlsx.py [out.xlsx]
"""
import json
import math
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

import rules as RULES  # noqa: E402  (проектные правила: статы, навыки, крит-травмы)

# ---------------------------------------------------------------- палитра ----
# Единое оформление «HUD Night City»: чёрный фон + красный (сигнатура CP2077)
# + оранжево-жёлтый как цвет наведения/полей ввода и белый как основной текст.
PAL_HUD = dict(
    ink='FFFFFF', muted='A6ABB2', accent='FF003C',
    st_title='FFFFFF', st_banner_bg='0A0A0C', st_banner2_bg='141419',
    st_h1_bg='3A0512', st_h2_bg='141419', st_head_bg='0A0A0C', st_head_fg='FFB100',
    st_label_bg='141419', st_label_fg='A6ABB2', st_text_bg='0B0B0E', st_text_fg='FFFFFF',
    st_input_bg='1F1706', st_input_fg='FFD24A', st_auto_bg='101017', st_auto_fg='FFFFFF',
    st_cell_bg='0B0B0E', st_cell_fg='FFFFFF', st_note_fg='8F959C',
    st_kvlabel_bg='1B1B22', st_stamp_fg='FF003C', st_big_fg='FFFFFF',
    st_border='2E2E38', st_border2='4A4A56', st_input_edge='FFB100',
    banner_fg='FFFFFF', h1_fg='FFFFFF', head_fg='FFB100', h2_fg='FFB100', title_fg='FFFFFF',
    cf_ok_bg='241C00', cf_ok_fg='FFC94D', cf_warn_bg='3A0512', cf_warn_fg='FF5C78',
    tab='FF003C', cyan='FFB100', gold='FFB100',
)
PAL_NCPD = PAL_HUD          # совместимость со старыми вызовами
PAL_DARK = PAL_HUD
PALETTES = {'hud': PAL_HUD, 'ncpd': PAL_HUD, 'dark': PAL_HUD}
THEME = 'hud'

# Шрифты: Oswald (крупные технические заголовки, HUD-стиль), Roboto (текст),
# Roboto Mono (цифры, метки, служебные значения). Все три есть в Google Таблицах;
# Excel без них подставит свой системный шрифт — читаемость не страдает.
DISPLAY = 'Oswald'
MONO = 'Roboto Mono'
SANS = 'Roboto'
CASH_FMT = '#,##0" €$"'


def make_styles(p):
    """Пресеты стилей для выбранной палитры."""
    thin = Side(style='thin', color=p['st_border'])
    med = Side(style='medium', color=p['st_border'])
    dot = Side(style='dotted', color=p['st_border2'])
    cell_edge = Border(left=thin, right=thin, top=thin, bottom=thin)
    input_edge = Border(bottom=Side(style='thin', color=p['st_input_edge']),
                        left=Side(style='medium', color=p['st_input_edge']),
                        right=thin, top=thin)
    return {
        'banner': dict(font=Font(name=DISPLAY, size=15, bold=True, color=p['banner_fg']),
                       fill=PatternFill('solid', start_color=p['st_banner_bg']),
                       align=Alignment(horizontal='center', vertical='center', wrap_text=True),
                       border=Border(bottom=Side(style='medium', color=p['accent']))),
        'banner2': dict(font=Font(name=DISPLAY, size=11, color=p['banner_fg']),
                        fill=PatternFill('solid', start_color=p['st_banner2_bg']),
                        align=Alignment(horizontal='center', vertical='center', wrap_text=True)),
        'title': dict(font=Font(name=DISPLAY, size=26, bold=True, color=p['title_fg']),
                      align=Alignment(horizontal='left', vertical='center')),
        'h1': dict(font=Font(name=DISPLAY, size=14, bold=True, color=p['h1_fg']),
                   fill=PatternFill('solid', start_color=p['st_h1_bg']),
                   align=Alignment(horizontal='left', vertical='center'),
                   border=Border(left=Side(style='medium', color=p['accent']))),
        'h2': dict(font=Font(name=DISPLAY, size=11, bold=True, color=p['h2_fg']),
                   fill=PatternFill('solid', start_color=p['st_h2_bg']),
                   align=Alignment(horizontal='left', vertical='center')),
        'head': dict(font=Font(name=DISPLAY, size=11, bold=True, color=p['st_head_fg']),
                     fill=PatternFill('solid', start_color=p['st_head_bg']),
                     align=Alignment(horizontal='center', vertical='center', wrap_text=True),
                     border=Border(bottom=Side(style='thin', color=p['accent']))),
        'label': dict(font=Font(name=MONO, size=11, bold=True, color=p['st_label_fg']),
                      fill=PatternFill('solid', start_color=p['st_label_bg']),
                      align=Alignment(horizontal='left', vertical='center', wrap_text=True)),
        'text': dict(font=Font(name=SANS, size=12, color=p['st_text_fg']),
                     fill=PatternFill('solid', start_color=p['st_text_bg']),
                     align=Alignment(horizontal='left', vertical='top', wrap_text=True)),
        'input': dict(font=Font(name=SANS, size=12, color=p['st_input_fg']),
                      fill=PatternFill('solid', start_color=p['st_input_bg']),
                      align=Alignment(horizontal='left', vertical='center', wrap_text=True),
                      border=input_edge),
        'inputc': dict(font=Font(name=MONO, size=12, bold=True, color=p['st_input_fg']),
                       fill=PatternFill('solid', start_color=p['st_input_bg']),
                       align=Alignment(horizontal='center', vertical='center'),
                       border=input_edge),
        'auto': dict(font=Font(name=MONO, size=12, bold=True, color=p['st_auto_fg']),
                     fill=PatternFill('solid', start_color=p['st_auto_bg']),
                     align=Alignment(horizontal='center', vertical='center'),
                     border=cell_edge),
        'auto_l': dict(font=Font(name=MONO, size=11, color=p['st_auto_fg']),
                       fill=PatternFill('solid', start_color=p['st_auto_bg']),
                       align=Alignment(horizontal='left', vertical='center', wrap_text=True),
                       border=cell_edge),
        'cell': dict(font=Font(name=SANS, size=11, color=p['st_cell_fg']),
                     fill=PatternFill('solid', start_color=p['st_cell_bg']),
                     align=Alignment(horizontal='left', vertical='center', wrap_text=True),
                     border=cell_edge),
        'cellc': dict(font=Font(name=MONO, size=11, color=p['st_cell_fg']),
                      fill=PatternFill('solid', start_color=p['st_cell_bg']),
                      align=Alignment(horizontal='center', vertical='center'),
                      border=cell_edge),
        'note': dict(font=Font(name=SANS, size=11, italic=True, color=p['st_note_fg']),
                     fill=PatternFill('solid', start_color=p['st_text_bg']),
                     align=Alignment(horizontal='left', vertical='center', wrap_text=True)),
        'stamp': dict(font=Font(name=DISPLAY, size=13, bold=True, color=p['st_stamp_fg']),
                      fill=PatternFill('solid', start_color=p['st_text_bg']),
                      align=Alignment(horizontal='center', vertical='center', wrap_text=True)),
        'big': dict(font=Font(name=DISPLAY, size=16, bold=True, color=p['st_big_fg']),
                    align=Alignment(horizontal='center', vertical='center')),
        'kv_label': dict(font=Font(name=MONO, size=11, bold=True, color=p['st_text_fg']),
                         fill=PatternFill('solid', start_color=p['st_kvlabel_bg']),
                         align=Alignment(horizontal='left', vertical='center', wrap_text=True),
                         border=cell_edge),
    }


def use_theme(name='hud'):
    """Переключить палитру (сейчас одна — 'hud': чёрный/красный/янтарный)."""
    global THEME, STYLES, INK, ACCENT, MUTED, PAPER, PAPER_D, INPUT, AUTO, BAND, BAND2, WHITE, CYAN, GOLD
    global THIN, MED, DOT, OK_BG, BAD_BG, WARN_BG, ACCENT_D
    global CF_OK_BG, CF_OK_FG, CF_WARN_BG, CF_WARN_FG
    p = PALETTES.get(name, PAL_HUD)
    THEME = 'hud'
    STYLES = make_styles(p)
    INK = p['ink']
    MUTED = p['muted']
    ACCENT = p['accent']
    ACCENT_D = p['cf_warn_fg']
    BAND = p['st_banner_bg']
    BAND2 = p['st_h1_bg']
    PAPER = p['st_text_bg']
    PAPER_D = p['st_kvlabel_bg']
    INPUT = p['st_input_bg']
    AUTO = p['st_auto_bg']
    WHITE = p['st_cell_bg']
    CYAN = p['cyan']
    GOLD = p['gold']
    OK_BG, BAD_BG, WARN_BG = p['cf_ok_bg'], p['cf_warn_bg'], p['cf_warn_bg']
    CF_OK_BG, CF_OK_FG = p['cf_ok_bg'], p['cf_ok_fg']
    CF_WARN_BG, CF_WARN_FG = p['cf_warn_bg'], p['cf_warn_fg']
    THIN = Side(style='thin', color=p['st_border'])
    MED = Side(style='medium', color=p['st_border'])
    DOT = Side(style='dotted', color=p['st_border2'])


use_theme('hud')


def put(ws, ref, value=None, *, kind='cell', fmt=None, border=None, align=None,
        font=None, fill=None):
    """Записать значение и применить пресет стиля."""
    cell = ws[ref]
    if value is not None:
        cell.value = value
    preset = dict(STYLES[kind])
    if font:
        preset['font'] = font
    if fill:
        preset['fill'] = fill
    if align:
        preset['align'] = align
    cell.font = preset.get('font', Font())
    cell.fill = preset.get('fill', PatternFill())
    cell.alignment = preset.get('align', Alignment())
    cell.border = border if border is not None else preset.get('border', Border())
    if fmt:
        cell.number_format = fmt
    return cell


def paint(ws, rng, *, kind='cell', border=None, fill=None, font=None, align=None):
    """Применить стиль ко всем ячейкам диапазона (до merge)."""
    target = ws[rng]
    if not isinstance(target, tuple):
        target = ((target,),)
    for row in target:
        for cell in row:
            put(ws, cell.coordinate, None, kind=kind, border=border, fill=fill,
                font=font, align=align)


def mput(ws, rng, value=None, *, kind='cell', **kw):
    """Стилизовать диапазон, объединить (если это диапазон) и записать значение."""
    paint(ws, rng, kind=kind, **kw)
    first = rng.split(':')[0]
    if ':' in rng:
        ws.merge_cells(rng)
    put(ws, first, value, kind=kind, **kw)
    return ws[first]


def box(ws, rng, *, color=INK, weight='thin'):
    side = Side(style=weight, color=color)
    target = ws[rng]
    if not isinstance(target, tuple):
        target = ((target,),)
    rows = list(target)
    r1, c1 = rows[0][0].row, rows[0][0].column
    r2, c2 = rows[-1][-1].row, rows[-1][-1].column
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            cell = ws.cell(row=r, column=c)
            b = cell.border
            left = side if c == c1 else b.left
            right = side if c == c2 else b.right
            top = side if r == r1 else b.top
            bottom = side if r == r2 else b.bottom
            cell.border = Border(left=left, right=right, top=top, bottom=bottom)


def widths(ws, mapping):
    for col, width in mapping.items():
        ws.column_dimensions[col].width = width


def heights(ws, mapping):
    for row, height in mapping.items():
        ws.row_dimensions[row].height = height


def dv_list(ws, rng, values):
    dv = DataValidation(type='list', formula1='"' + ','.join(values) + '"',
                        allow_blank=True, showDropDown=False)
    ws.add_data_validation(dv)
    dv.add(rng)


def dv_catalog(ws, rng):
    """Выпадающий список названий из КАТАЛОГА. Ошибку не блокируем — можно вписать своё."""
    dv = DataValidation(type='list', formula1=f'={S_CAT}!$A$2:$A${CAT_LAST}',
                        allow_blank=True, showDropDown=False, showErrorMessage=False)
    ws.add_data_validation(dv)
    dv.add(rng)


def dv_num(ws, rng, mn, mx, integer=True):
    dv = DataValidation(type='whole' if integer else 'decimal',
                        operator='between', formula1=str(mn), formula2=str(mx),
                        allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(rng)


def cf_warn(ws, rng, formula, bg=None, color=None):
    ws.conditional_formatting.add(rng, FormulaRule(
        formula=[formula], fill=PatternFill('solid', start_color=bg or CF_WARN_BG),
        font=Font(name=MONO, bold=True, color=color or CF_WARN_FG), stopIfTrue=False))


def cf_ok(ws, rng, formula, bg=None, color=None):
    ws.conditional_formatting.add(rng, FormulaRule(
        formula=[formula], fill=PatternFill('solid', start_color=bg or CF_OK_BG),
        font=Font(name=MONO, bold=True, color=color or CF_OK_FG), stopIfTrue=False))


def sheet_setup(ws, tab_color, freeze=None, cols=None, landscape=True):
    """Оформление листа: без сетки, альбомная ориентация, всё по ширине страницы."""
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = tab_color
    if freeze:
        ws.freeze_panes = freeze
    ws.page_setup.orientation = 'landscape' if landscape else 'portrait'
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_view.zoomScale = 100


# ------------------------------------------------------------- ссылки листов --
S_DOC = "'01 ДОСЬЕ'"
# ключевые ячейки досье, на которые ссылаются игровые листы
DOC_HANDLE = '$C$4'
DOC_ROLE = '$C$5'
DOC_PLAYER = '$C$6'
DOC_CONTACT = '$C$11'
DOC_STATUS = '$E$3'
DOC_CASE = '$G$3'
S_BASE = "'02 ОСНОВА'"
S_SKL = "'03 НАВЫКИ'"
S_CHR = "'04 ХРОМ'"
S_GEAR = "'05 СНАРЯЖЕНИЕ'"
S_STA = "'06 СОСТОЯНИЕ'"
S_CAT = "'КАТАЛОГ'"
S_REF = "'СПРАВКА'"
S_RUL = "'ПРАВИЛА'"

NAMES = {'doc': '01 ДОСЬЕ', 'base': '02 ОСНОВА', 'skl': '03 НАВЫКИ', 'chr': '04 ХРОМ',
         'gear': '05 СНАРЯЖЕНИЕ', 'sta': '06 СОСТОЯНИЕ', 'cat': 'КАТАЛОГ',
         'ref': 'СПРАВКА', 'rul': 'ПРАВИЛА'}

# --- адреса, на которые ссылаются формулы с других листов (менять только вместе с вёрсткой) ---
BASE_HP_MAX = '$D$22'
BASE_HP_CUR = '$D$23'
BASE_SW = '$D$24'
BASE_DS = '$D$25'
BASE_DS_PEN = '$D$26'
BASE_INIT = '$D$27'
BASE_MOVE = '$D$28'
BASE_HUM_BASE = '$D$29'
BASE_HUM_CUT = '$D$30'
BASE_HUM_MAX = '$D$31'
BASE_HL = '$D$32'
BASE_HUM_RESTORED = '$D$33'
BASE_HUM_CUR = '$D$34'
BASE_EMP_CUR = '$D$35'
BASE_HUM_STATE = '$D$36'
BASE_WOUND = '$G$3'
BASE_PSY = '$G$4'
BASE_RANK = '$G$2'
BASE_STAT_FIRST, BASE_STAT_LAST = 8, 17

CHR_HL_TOTAL = '$H$19'
CHR_HUM_CUT = '$I$19'

GEAR_CASH = '$D$5'
GEAR_W_NAME = '$C$9:$C$16'
GEAR_W_SLOT = '$K$9:$K$16'
GEAR_W_ATTACK = '$L$9:$L$16'
GEAR_SP_HEAD = '$D$27'
GEAR_SP_BODY = '$D$28'
GEAR_SP_SHIELD = '$D$29'
GEAR_PEN = {'REF': '$D$30', 'DEX': '$E$30', 'MOVE': '$F$30'}

STA_CRIT_STATUS = '$I$7:$I$16'
STA_IP_FREE = '$D$32'
STA_IP_SPENT = '$D$31'
STA_IP_EARNED = '$D$30'


CAT_LAST = 1


def set_ranges():
    """Разложить ограниченные диапазоны в глобальные имена для f-строк с формулами."""
    globals()['BASEB'] = f'{S_BASE}!$B$8:$B$17'
    globals()['BASEF'] = f'{S_BASE}!$F$8:$F$17'
    globals()['SKLC'] = f'{S_SKL}!$C$5:$C$76'
    globals()['SKLI'] = f'{S_SKL}!$I$5:$I$76'
    for letter in 'ABCDEFGHIJKLMNOPQRST':
        globals()['CAT' + letter] = f'{S_CAT}!${letter}$2:${letter}${CAT_LAST}'


def skill_notes():
    """Описания навыков из гайда «Spes Desperata» (app/static/guides-data.js)."""
    path = os.path.join(ROOT, 'app', 'static', 'guides-data.js')
    try:
        text = open(path, encoding='utf-8').read()
    except OSError:
        return {}
    pattern = re.compile(r"\['([^']*)',\s*'([^']*)',\s*'(?:INT|WILL|COOL|EMP|TECH|REF|LUCK|BODY|DEX|MOVE)',\s*'([^']*)'\]")
    return {name: desc for _, name, desc in pattern.findall(text)}


SKILL_NOTES = skill_notes()

# ------------------------------------------------------------------ каталог ----
CAT_HEAD = ['НАЗВАНИЕ', 'КАТЕГОРИЯ', 'ПОДТИП (TYPE)', 'НАВЫК', 'УРОН', 'ROF', 'МАГ.',
            'SP', 'HP', 'ШТРАФ REF', 'ШТРАФ DEX', 'ШТРАФ MOVE', 'HL', 'УСТАНОВКА',
            'РУКИ', 'СКРЫТНОСТЬ', 'КАЧЕСТВО', 'ЦЕНА €$', 'ИСТОЧНИК', 'ОПИСАНИЕ']
# индексы колонок каталога (1-based)
C_NAME, C_CAT, C_SUB, C_SKILL, C_DMG, C_ROF, C_MAG = 1, 2, 3, 4, 5, 6, 7
C_SP, C_HP, C_PREF, C_PDEX, C_PMOVE, C_HL, C_INST = 8, 9, 10, 11, 12, 13, 14
C_HANDS, C_CONCEAL, C_QUAL, C_PRICE, C_SRC, C_DESC = 15, 16, 17, 18, 19, 20
CAT_FIRST_ROW = 2


def _num_first(text):
    if text is None:
        return None
    m = re.search(r'-?\d+(?:[.,]\d+)?', str(text))
    return float(m.group(0).replace(',', '.')) if m else None


def _penalty(fields, stat):
    raw = str(fields.get('Penalty') or '')
    m = re.search(r'(-?\d+)\s*' + stat, raw)
    return int(m.group(1)) if m else 0


def _sp_hp(fields):
    raw = str(fields.get('SP') or '')
    sp = re.search(r'(\d+)\s*SP', raw)
    hp = re.search(r'(\d+)\s*HP', raw)
    return (int(sp.group(1)) if sp else None,
            int(hp.group(1)) if hp else None)


def skill_for_item(item):
    mech = item.get('mechanics') or {}
    skill = mech.get('skill')
    if skill:
        return skill
    sub = str((item.get('fields') or {}).get('Type') or '')
    if 'Melee' in sub:
        return 'Melee Weapon'
    if 'Bow' in sub or 'Crossbow' in sub:
        return 'Archery'
    return ''


def catalog_rows(data):
    cats = {c['id']: c for c in data['cats']}
    rows = []
    for item in data['items']:
        fields = item.get('fields') or {}
        mech = item.get('mechanics') or {}
        cat = cats.get(item['cat'], {})
        sp, hp = _sp_hp(fields)
        desc = re.sub(r'\s+', ' ', str(item.get('desc') or '')).strip()
        rows.append([
            item['name'],
            cat.get('ru') or item['cat'],
            str(fields.get('Type') or '').replace('\n', ' · '),
            skill_for_item(item),
            mech.get('damage', {}).get('notation') if isinstance(mech.get('damage'), dict)
            else (item.get('damage') or fields.get('Damage') or ''),
            mech.get('rof') or '',
            mech.get('magazine') or fields.get('Mag') or '',
            sp if sp is not None else '',
            hp if hp is not None else '',
            _penalty(fields, 'REF'),
            _penalty(fields, 'DEX'),
            _penalty(fields, 'MOVE'),
            _num_first(fields.get('HL')) or 0,
            fields.get('Install') or '',
            mech.get('hands') or fields.get('Hands') or '',
            mech.get('concealable') or fields.get('Conceal') or '',
            mech.get('quality') or fields.get('Quality') or '',
            item.get('price') if item.get('price') is not None else '',
            str(item.get('source') or '').replace('\n', ' · '),
            desc[:220],
        ])
    rows.sort(key=lambda r: (r[C_CAT], r[C_NAME]))
    return dedupe_names(rows)


def dedupe_names(rows):
    """Разводит одинаковые названия из разных категорий (напр. Bug Detector — хром 100 и
    гарнитура 500 €$). Первое вхождение сохраняет чистое имя — на него ссылаются уже
    заполненные ячейки; каждое следующее получает уточнение «(категория)», чтобы
    подстановка цены/HL брала свою строку, а не первую попавшуюся."""
    seen, out = {}, []
    for row in rows:
        row = list(row)
        name, cat = row[C_NAME - 1], row[C_CAT - 1]
        title = str(name)
        if title in seen:
            tag, n = f'{title} ({cat})', 2
            while tag in seen:
                tag, n = f'{title} ({cat} {n})', n + 1
            row[C_NAME - 1], title = tag, tag
        seen[title] = True
        out.append(row)
    return out


# ============================================================== 01 ДОСЬЕ ====
def build_dossier(wb):
    """01 ДОСЬЕ — альбомная папка дела: личность, служба, прошлое, связи, сводка."""
    ws = wb.create_sheet(NAMES['doc'])
    widths(ws, {'A': 2, 'B': 24, 'C': 40, 'D': 24, 'E': 40, 'F': 26, 'G': 46, 'H': 2})
    sheet_setup(ws, ACCENT, landscape=True)

    mput(ws, 'B1:G1', 'NCPD  ▚  NIGHT CITY POLICE DEPARTMENT  ▚  ДЕЛО ОБЪЕКТА  ▚  2070', kind='banner')
    heights(ws, {1: 32})
    mput(ws, 'B2:G2', 'ФОРМА NCPD-77/Б · ДОСТУП: ОГРАНИЧЕННЫЙ · КОПИРОВАНИЕ БЕЗ ШТАМПА НЕДОПУСТИМО', kind='banner2')
    heights(ws, {2: 20})

    mput(ws, 'B3:C3', 'Д О С Ь Е', kind='title')
    put(ws, 'D3', 'СТАТУС:', kind='kv_label')
    put(ws, 'E3', 'АКТИВЕН', kind='inputc')
    dv_list(ws, 'E3', ['АКТИВЕН', 'НАБЛЮДЕНИЕ', 'РАЗЫСКИВАЕТСЯ', 'АРХИВ', 'МЁРТВ'])
    put(ws, 'F3', 'ДЕЛО №', kind='kv_label')
    put(ws, 'G3', 'NC-2070-', kind='input')
    heights(ws, {3: 36})

    # фото объекта — правый верхний угол, рядом с блоком данных
    mput(ws, 'F4:G13', 'ФОТО ОБЪЕКТА\n\n(правый клик → «Заменить изображение»)', kind='note')
    box(ws, 'F4:G13', color=ACCENT, weight='medium')

    ident = [
        ('ПОЗЫВНОЙ (HANDLE)', 'ИМЯ / ФАМИЛИЯ'),
        ('РОЛЬ / АРХЕТИП', 'РАНГ РОЛИ'),
        ('ИГРОК', 'ВОЗРАСТ / ДАТА РОЖДЕНИЯ'),
        ('РОДНОЙ ЯЗЫК (4 БЕСПЛ.)', 'КУЛЬТУРНЫЕ КОРНИ'),
        ('РАЙОН (LOCAL EXPERT)', 'СТИЛЬ ОДЕЖДЫ'),
        ('РОСТ / ВЕС / СЛОЖЕНИЕ', 'ХРОМ НА ВИДУ'),
        ('ОСОБЫЕ ПРИМЕТЫ', 'ГОЛОС / МАНЕРА'),
        ('СВЯЗЬ / HOLOPHONE', 'ЖИЛЬЁ / LIFESTYLE'),
    ]
    r = 4
    for idx, (left, right) in enumerate(ident):
        put(ws, f'B{r}', left, kind='kv_label')
        put(ws, f'C{r}', None, kind='input')
        put(ws, f'D{r}', right, kind='kv_label')
        put(ws, f'E{r}', None, kind='input')
        heights(ws, {r: 28})
        r += 1

    # Ⅰ личность и Ⅲ прошлое — в две колонки, чтобы не тянуть лист вниз
    r = 15
    mput(ws, f'B{r}:D{r}', 'Ⅰ · ЛИЧНОСТЬ И МОТИВАЦИЯ', kind='h1')
    mput(ws, f'E{r}:G{r}', 'Ⅲ · ПРОШЛОЕ  ·  GENERAL LIFEPATH', kind='h1')
    left_items = ['ЛИЧНОСТЬ (PERSONALITY)', 'ЧТО ЦЕНИТ БОЛЬШЕ ВСЕГО', 'КАК ОТНОСИТСЯ К ЛЮДЯМ',
                  'МОРАЛЬНЫЙ КОМПАС (ПО ЛАЙФПАТУ)', 'ЦЕЛЬ ЖИЗНИ / ЗАЧЕМ ОН В ЭТОМ',
                  'ЧЕГО НИКОГДА НЕ СДЕЛАЕТ', 'СЛАБОСТЬ / НА ЧЁМ ЕГО ВЗЯТЬ']
    right_items = ['СЕМЬЯ / ДЕТСТВО', 'СЕМЕЙНЫЙ КРИЗИС', 'ДРУЗЬЯ', 'РОМАНТИЧЕСКИЕ СВЯЗИ',
                   'ВРАГИ', 'ПЕРЕЛОМНЫЙ МОМЕНТ']
    for idx in range(max(len(left_items), len(right_items))):
        rr = r + 1 + idx
        put(ws, f'B{rr}', left_items[idx] if idx < len(left_items) else '', kind='kv_label')
        mput(ws, f'C{rr}:D{rr}', None, kind='input' if idx < len(left_items) else 'cell')
        put(ws, f'E{rr}', right_items[idx] if idx < len(right_items) else '', kind='kv_label')
        mput(ws, f'F{rr}:G{rr}', None, kind='input' if idx < len(right_items) else 'cell')
        heights(ws, {rr: 30})
    r += 1 + max(len(left_items), len(right_items))

    # Ⅱ служба: пять дропдаунов в две колонки + восемь текстов по два в ряд
    r += 1
    mput(ws, f'B{r}:G{r}', 'Ⅱ · СЛУЖБА  ·  ROLE LIFEPATH (LAWMAN / NCPD — В ОТСТАВКЕ)', kind='h1')
    lawman = [
        ('ДОЛЖНОСТЬ В ПОДРАЗДЕЛЕНИИ', 'Охранник', 'Патрульный', 'Уголовный следователь',
         'Спецназ', 'Мотопатруль', 'Внутренняя безопасность'),
        ('ЮРИСДИКЦИЯ ПОДРАЗДЕЛЕНИЯ', 'Корпоративные зоны', 'Городской патрульный район',
         'Боевые зоны', 'Окраины города', 'Зоны восстановления', 'Открытые шоссе'),
        ('КОРРУМПИРОВАННОСТЬ ПОДРАЗДЕЛЕНИЯ', 'Честная и этичная служба', 'Честная, но суровая',
         'Редкие нарушения', 'Нарушает правила ради дела', 'Безжалостно контролирует Улицу',
         'Полностью коррумпировано'),
        ('КТО ОХОТИТСЯ НА ПОДРАЗДЕЛЕНИЕ', 'Организованная преступность', 'Бустерганги',
         'Группа контроля полиции', 'Грязные политики', 'Контрабандисты', 'Уличные преступники'),
        ('ГЛАВНАЯ ЦЕЛЬ ПОДРАЗДЕЛЕНИЯ', 'Организованная преступность', 'Бустерганги',
         'Наркоторговцы', 'Грязные политики', 'Контрабандисты', 'Уличная преступность'),
    ]
    for idx, (label, *options) in enumerate(lawman):
        rr = r + 1 + idx // 2
        col = 'B' if idx % 2 == 0 else 'D'
        vcol = 'C' if idx % 2 == 0 else ('E' if idx % 2 == 0 else 'E')
        put(ws, f'{col}{rr}', label, kind='kv_label')
        vref = f'C{rr}' if idx % 2 == 0 else f'E{rr}'
        mput(ws, f'{vref}' if idx % 2 else f'C{rr}', options[0], kind='input')
        dv_list(ws, vref if idx % 2 else f'C{rr}', options)
        heights(ws, {rr: 26})
    r += 1 + (len(lawman) + 1) // 2
    texts = ['ЗА ЧТО УШЁЛ СО СЛУЖБЫ / ЧТО СЛУЧИЛОСЬ (ЕГО ВЕРСИЯ)',
             'ЧТО ОН НА САМОМ ДЕЛЕ СКРЫВАЕТ О ТОМ ДЕЛЕ',
             'КАКИЕ СВЯЗИ В УПРАВЛЕНИИ ОСТАЛИСЬ (ЗВОНИТЬ МОЖНО КОМУ)',
             'ПОДПИСКИ И РЕГУЛЯРНЫЕ ТРАТЫ (TRAUMA TEAM, ЖИЛЬЁ, ДОЛГИ)',
             'КТО НА НЕГО ОХОТИТСЯ (WHO\'S GUNNING FOR YOU)',
             'РЕПУТАЦИЯ НА УЛИЦАХ / ЧЕМ ИЗВЕСТЕН',
             'ТЕКУЩИЙ РАБОТОДАТЕЛЬ / ФИКСЕР',
             'ПРАВИЛА РАБОТЫ (КАК БЕРЁТ КОНТРАКТЫ)']
    for idx, label in enumerate(texts):
        rr = r + 1 + idx // 2
        if idx % 2 == 0:
            put(ws, f'B{rr}', label, kind='kv_label')
            mput(ws, f'C{rr}:D{rr}', None, kind='input')
        else:
            put(ws, f'E{rr}', label, kind='kv_label')
            mput(ws, f'F{rr}:G{rr}', None, kind='input')
        heights(ws, {rr: 32})
    r += 1 + (len(texts) + 1) // 2

    # Ⅳ связи — компактная таблица из четырёх колонок
    r += 1
    mput(ws, f'B{r}:G{r}', 'Ⅳ · СВЯЗИ  ·  КТО МОЖЕТ ПОМОЧЬ ИЛИ ПОДСТАВИТЬ', kind='h1')
    heads = [('B', 'КТО'), ('C', 'РОЛЬ В ЖИЗНИ'), ('D:E', 'КАК НАЙТИ / КОНТАКТ'),
             ('F:G', 'ЧЕМ ПОЛЕЗЕН / ЧЕМ ОПАСЕН')]
    for col, text in heads:
        rng = col if ':' not in col else f'{col[0]}{r + 1}:{col[2]}{r + 1}'
        pass
    for col, text in heads:
        rr = r + 1
        if ':' in col:
            mput(ws, f'{col.split(":")[0]}{rr}:{col.split(":")[1]}{rr}', text, kind='head')
        else:
            put(ws, f'{col}{rr}', text, kind='head')
    for i in range(6):
        rr = r + 2 + i
        put(ws, f'B{rr}', None, kind='input')
        put(ws, f'C{rr}', None, kind='input')
        mput(ws, f'D{rr}:E{rr}', None, kind='input')
        mput(ws, f'F{rr}:G{rr}', None, kind='input')
        heights(ws, {rr: 24})
    r += 2 + 6

    # Ⅴ сводка — тянется с игровых листов, по два показателя в ряд
    r += 1
    mput(ws, f'B{r}:G{r}', 'Ⅴ · СЛУЖЕБНАЯ СВОДКА  ·  СЧИТАЕТСЯ АВТОМАТИЧЕСКИ', kind='h1')
    summary = [
        ('HP (ТЕКУЩИЕ / МАКСИМУМ)', f'={S_BASE}!{BASE_HP_CUR}&" / "&{S_BASE}!{BASE_HP_MAX}'),
        ('ПОРОГ «СЕРЬЁЗНО РАНЕН»', f'={S_BASE}!{BASE_SW}'),
        ('СПАСБРОСОК СМЕРТИ (BODY)', f'={S_BASE}!{BASE_DS}&" − "&{S_BASE}!{BASE_DS_PEN}&" штраф"'),
        ('HUMANITY (ТЕКУЩАЯ / МАКСИМУМ)', f'={S_BASE}!{BASE_HUM_CUR}&" / "&{S_BASE}!{BASE_HUM_MAX}'),
        ('EMP ТЕКУЩАЯ', f'={S_BASE}!{BASE_EMP_CUR}'),
        ('СОСТОЯНИЕ РАН', f'={S_BASE}!{BASE_WOUND}'),
        ('БРОНЯ: SP ГОЛОВЫ / ТЕЛА', f'={S_GEAR}!{GEAR_SP_HEAD}&" / "&{S_GEAR}!{GEAR_SP_BODY}'),
        ('ЩИТ (HP)', f'={S_GEAR}!{GEAR_SP_SHIELD}'),
        ('ОСНОВНОЕ ОРУЖИЕ (СЛОТ 1)', f'=IFERROR(INDEX({S_GEAR}!{GEAR_W_NAME},MATCH(1,{S_GEAR}!{GEAR_W_SLOT},0)),"—")'),
        ('БАЗА АТАКИ ОСНОВНОГО (+1D10)', f'=IFERROR(INDEX({S_GEAR}!{GEAR_W_ATTACK},MATCH(1,{S_GEAR}!{GEAR_W_SLOT},0)),"—")'),
        ('АКТИВНЫХ КРИТ-ТРАВМ', f'=COUNTIF({S_STA}!{STA_CRIT_STATUS},"Активна")'),
        ('НАЛИЧНЫЕ €$ (СТАРТ + ИГРА)', f'={S_GEAR}!{GEAR_CASH}'),
        ('IP: ЗАРАБОТАНО / СВОБОДНО', f'={S_STA}!{STA_IP_EARNED}&" / "&{S_STA}!{STA_IP_FREE}'),
        ('BACKUP: РАНГ · ТИР ПОДКРЕПЛЕНИЯ',
         f'={S_BASE}!$G$2&" → вызов 1d10 ≤ "&{S_BASE}!$G$2&"; тир: "&'
         f'IF({S_BASE}!$G$2<=2,"1–2 · корпоративная охрана",'
         f'IF({S_BASE}!$G$2<=4,"3–4 · патрульные",'
         f'IF({S_BASE}!$G$2<=7,"5–7 · департамент шерифа",'
         f'IF({S_BASE}!$G$2=8,"8 · маршал зоны восстановления",'
         f'IF({S_BASE}!$G$2=9,"9 · C-SWAT","10 · национальные силы")))))'),
    ]
    for idx, (label, formula) in enumerate(summary):
        rr = r + 1 + idx // 2
        if idx % 2 == 0:
            mput(ws, f'B{rr}:C{rr}', label, kind='kv_label')
            mput(ws, f'D{rr}', formula, kind='auto_l')
        else:
            mput(ws, f'E{rr}:F{rr}', label, kind='kv_label')
            mput(ws, f'G{rr}', formula, kind='auto_l')
        heights(ws, {rr: 24})
    r += 1 + (len(summary) + 1) // 2

    # Ⅵ заметки и Ⅶ границы безопасности
    r += 1
    mput(ws, f'B{r}:G{r}', 'Ⅵ · ЗАМЕТКИ ОТДЕЛА  ·  СВОБОДНАЯ ЗАПИСЬ GM И ИГРОКА', kind='h1')
    mput(ws, f'B{r + 1}:G{r + 3}', None, kind='input')
    for rr in range(r + 1, r + 4):
        heights(ws, {rr: 26})
    r += 4
    mput(ws, f'B{r}:G{r}', 'Ⅶ · ГРАНИЦЫ БЕЗОПАСНОСТИ (LINES / VEILS / X-CARD)', kind='h1')
    r += 1
    put(ws, f'B{r}', 'СТОП-ТЕМЫ (LINES)', kind='kv_label')
    mput(ws, f'C{r}:D{r}', None, kind='input')
    put(ws, f'E{r}', 'УВОДИМ БЕЗ ДЕТАЛЕЙ (VEILS)', kind='kv_label')
    mput(ws, f'F{r}:G{r}', None, kind='input')
    heights(ws, {r: 28})
    r += 2
    mput(ws, f'B{r}:G{r}', 'ЗАПИСЬ ВЁЛ: ________________     ПЕЧАТЬ: NC//NET · 2070     ПОДПИСЬ GM: ________________', kind='note')
    mput(ws, f'B{r + 1}:G{r + 1}', 'ИСТОЧНИКИ: Cyberpunk RED Corebook · CEMK (2070-е) · гайд «Spes Desperata»', kind='note')
    cf_ok(ws, 'E3', '$E$3="АКТИВЕН"', bg=WARN_BG, color=ACCENT_D)
    cf_warn(ws, 'E3', 'OR($E$3="АРХИВ",$E$3="МЁРТВ",$E$3="РАЗЫСКИВАЕТСЯ")')
    return ws

# ============================================================== 02 ОСНОВА ===
STAT_ROWS = {'INT': 8, 'WILL': 9, 'COOL': 10, 'EMP': 11, 'TECH': 12,
             'REF': 13, 'LUCK': 14, 'BODY': 15, 'DEX': 16, 'MOVE': 17}

STAT_INFO = [
    ('INT', 'Интеллект', 'Ум, восприятие, обучение. База для Perception, Education, Local Expert и ещё 20+ навыков.'),
    ('WILL', 'Воля', 'Решимость и стрессоустойчивость. Входит в расчёт HP. База для Concentration, Endurance.'),
    ('COOL', 'Хладнокровие', 'Характер и харизма. База для Persuasion, Streetwise, Acting, Interrogation.'),
    ('EMP', 'Эмпатия', 'Сопереживание. База Humanity (EMP × 10) и EMP-навыков. Падает вместе с десятками Humanity: ИТОГ = минимум из введённой EMP и Humanity/10.'),
    ('TECH', 'Техника', 'Работа с инструментами и электроникой: Basic Tech, Cybertech, Weaponstech, First Aid.'),
    ('REF', 'Реакция', 'Координация и прицеливание. Инициатива, все дальние атаки. Штраф брони бьёт сюда.'),
    ('LUCK', 'Удача', 'Пул на любой бросок (до броска). Восстанавливается в начале следующей партии.'),
    ('BODY', 'Телосложение', 'Сила и живучесть. Входит в HP, задаёт спасбросок смерти. Штраф брони не влияет.'),
    ('DEX', 'Ловкость', 'Баланс, прыжки, ближний бой, уклонение. Штраф брони бьёт сюда.'),
    ('MOVE', 'Скорость', 'Перемещение: MOVE × 2 м за Move Action. Штраф брони бьёт сюда (может упасть до 0).'),
]


def build_base(wb):
    """02 ОСНОВА — характеристики, производные, Backup (Lawman), оружие, броня, памятка."""
    ws = wb.create_sheet(NAMES['base'])
    widths(ws, {'A': 2, 'B': 9, 'C': 17, 'D': 10, 'E': 10, 'F': 10, 'G': 78, 'H': 2})
    sheet_setup(ws, BAND, freeze='A8')
    # B — код статы, C — название, D — значение, E — штраф брони, F — итог, G — правила.

    mput(ws, 'B1:G1', 'ЛИСТ ПЕРСОНАЖА  ▚  ОСНОВА  ▚  CYBERPUNK RED / CEMK · НАЙТ-СИТИ, 2070-е', kind='banner')
    heights(ws, {1: 32})
    mput(ws, 'B2:D2', 'ПОЗЫВНОЙ / РОЛЬ  ·  РАНГ РОЛИ →', kind='kv_label')
    mput(ws, 'E2:F2', f'={S_DOC}!{DOC_HANDLE}&" · "&{S_DOC}!{DOC_ROLE}', kind='auto_l')
    put(ws, 'G2', 4, kind='inputc')
    ws['G2'].number_format = '"РАНГ "0'   # значение остаётся числом для формулы Backup
    dv_num(ws, 'G2', 1, 10)
    mput(ws, 'B3:D3', 'ИГРОК / СТАТУС ДЕЛА', kind='kv_label')
    mput(ws, 'E3:F3', f'={S_DOC}!{DOC_PLAYER}&" · "&{S_DOC}!{DOC_STATUS}', kind='auto_l')
    put(ws, 'G3', '="СОСТОЯНИЕ: "&IF(D23="","—",IF(D23<1,"СМЕРТЕЛЬНО РАНЕН",IF(D23<=D24,"СЕРЬЁЗНО РАНЕН",'
                  'IF(D23<D22,"ЛЁГКОЕ РАНЕНИЕ","В НОРМЕ"))))', kind='auto')
    mput(ws, 'B4:D4', 'КОНТАКТ / HOLOPHONE', kind='kv_label')
    mput(ws, 'E4:F4', f'={S_DOC}!{DOC_CONTACT}', kind='auto_l')
    put(ws, 'G4', '="КИБЕРПСИХОЗ: "&IF(AND($D$35=0,$D$34<0),"⚠ ЭКСТРЕМАЛЬНЫЙ — лист забирает GM",'
                   'IF($D$35=0,"⚠ КИБЕРПСИХОЗ",IF($D$35=1,"⚠ диссоциативное расстройство",'
                   'IF($D$35=2,"⚠ пограничное состояние","—"))))', kind='auto')
    mput(ws, 'B5:G5', 'ЯНТАРНЫЕ ПОЛЯ — ВВОД · ТЁМНЫЕ — СЧИТАЕТСЯ АВТОМАТИЧЕСКИ · '
                      'СТАТЫ ДАЮТ ИТОГ С УЧЁТОМ ШТРАФА БРОНИ (ЛИСТ 05)', kind='note')
    heights(ws, {2: 26, 3: 26, 4: 26, 5: 20})

    mput(ws, 'B6:G6', 'Ⅰ · ХАРАКТЕРИСТИКИ  ·  62 ОЧКА НА 10 СТАТ  ·  КАЖДАЯ ОТ 2 ДО 8', kind='h1')
    heights(ws, {6: 26})
    for col, text in (('B', 'КОД'), ('C', 'СТАТА'), ('D', 'ЗНАЧ.'), ('E', 'БРОНЯ'),
                      ('F', 'ИТОГ'), ('G', 'НА ЧТО ВЛИЯЕТ')):
        put(ws, f'{col}7', text, kind='head')
    for code, ru, effect in STAT_INFO:
        r = STAT_ROWS[code]
        put(ws, f'B{r}', code, kind='cellc')
        put(ws, f'C{r}', ru, kind='cell')
        put(ws, f'D{r}', None, kind='inputc')
        if code in ('REF', 'DEX', 'MOVE'):
            put(ws, f'E{r}', f'={S_GEAR}!{GEAR_PEN[code]}', kind='auto')
        else:
            put(ws, f'E{r}', 0, kind='auto')
        if code == 'EMP':
            put(ws, f'F{r}', f'=IF(D{r}="",0,MIN(MAX(0,D{r}-E{r}),$D$35))', kind='auto')
        else:
            put(ws, f'F{r}', f'=IF(D{r}="",0,MAX(0,D{r}-E{r}))', kind='auto')
        put(ws, f'G{r}', effect, kind='cell')
        ws.row_dimensions[r].height = 22
    dv_num(ws, 'D8:D17', 2, 8)
    mput(ws, 'B18:C18', 'РАСКИДАНО / НОРМА 62', kind='kv_label')
    put(ws, 'D18', '=SUM(D8:D17)', kind='auto')
    put(ws, 'E18', 'ОСТАТОК', kind='kv_label')
    put(ws, 'F18', '=62-SUM(D8:D17)', kind='auto')
    put(ws, 'G18', '=IF(AND(SUM(D8:D17)=62,MIN(D8:D17)>=2,MAX(D8:D17)<=8),'
                   '"✔ 62 очка, диапазон 2–8 соблюдён","✖ ПРОВЕРЬ: сумма должна быть 62, каждая стата 2–8")',
        kind='auto_l')
    mput(ws, 'B19:G19', 'Штраф брони вычитается из REF, DEX и MOVE один раз — берётся самый строгий из надетого (лист 05). '
                        'Броня режет и навыки на этих статах автоматически (лист 03).', kind='note')
    heights(ws, {18: 24, 19: 22})

    mput(ws, 'B20:G20', 'Ⅱ · ПРОИЗВОДНЫЕ  ·  HP, ЧЕЛОВЕЧНОСТЬ, ИНИЦИАТИВА', kind='h1')
    mput(ws, 'B21:C21', 'ПОКАЗАТЕЛЬ', kind='head')
    put(ws, 'D21', 'ЗНАЧЕНИЕ', kind='head')
    mput(ws, 'E21:G21', 'ФОРМУЛА / ПРАВИЛО', kind='head')
    rows = [
        (22, 'HP МАКСИМУМ', '=10+5*ROUNDUP((F15+F9)/2,0)', None,
         'HP = 10 + 5 × ⌈(BODY+WILL)/2⌉. Считается по итоговым статам; броня на них не влияет.'),
        (23, 'HP ТЕКУЩИЕ (ВВОД)', None, 'input',
         'Просто вписывай текущие HP. Ноль и ниже — смертельное состояние.'),
        (24, 'ПОРОГ «СЕРЬЁЗНО РАНЕН»', '=ROUNDUP(D22/2,0)', None,
         'Половина максимума, округление вверх → −2 ко всем действиям.'),
        (25, 'СПАСБРОСОК СМЕРТИ (BODY)', '=F15', None,
         '1d10 ≤ BODY − штраф. Выпало 10 — провал. Провал = смерть.'),
        (26, 'ШТРАФ К СПАСБРОСКАМ (ВВОД)', None, 'input',
         'Складывается с крит-травмами (+1 за каждую такую травму) и уроном.'),
        (27, 'ИНИЦИАТИВА (REF + 1D10)', '=F13', None,
         'Бросок 1d10 + это число.'),
        (28, 'MOVE ACTION (МЕТРЫ)', '=F17*2', None,
         'За Move Action персонаж двигается на MOVE × 2 м. Ход = Move Action + одно действие.'),
        (29, 'HUMANITY: БАЗА (EMP × 10)', '=D11*10', None,
         'Считается от исходной EMP (колонка «ЗНАЧ.»), не от текущей.'),
        (30, 'СРЕЗ МАКСИМУМА ЗА ХРОМ', f'={S_CHR}!$I$19', None,
         '−2 за обычный имплант, −4 за боргвар; Fashionware и стартовый Neuroport не режут максимум (лист 04).'),
        (31, 'HUMANITY МАКСИМУМ', '=D29-D30', None,
         'Максимум Humanity = база − срез. Полностью вернуть можно только сняв хром.'),
        (32, 'HL ВСЕГО (СРЕДНЕЕ)', f'={S_CHR}!$H$19', None,
         'Среднее значение HL каждого установленного импланта (дом-правило: «7 (2d6)» = −7).'),
        (33, 'ВОССТАНОВЛЕНО (ТЕРАПИЯ/ОПЫТ)', None, 'input',
         'Сколько Humanity вернули терапией, опытом или событиями кампании (CEMK: Humanity Gain).'),
        (34, 'HUMANITY ТЕКУЩАЯ', '=MIN(D31,D29-D32+D33)', None,
         'Не может превышать максимум. Ниже 0 — киберпсихоз, лист уходит GM.'),
        (35, 'EMP ТЕКУЩАЯ', '=MAX(0,ROUNDDOWN(D34/10,0))', None,
         'Каждый раз, когда десяток Humanity падает, падает и EMP.'),
        (36, 'СТАТУС HUMANITY', '=IF(AND($D$35=0,$D$34<0),"⚠ ЭКСТРЕМАЛЬНЫЙ — лист забирает GM",'
                               'IF($D$35=0,"⚠ КИБЕРПСИХОЗ",IF(D34<20,"ПОНИЖЕННАЯ","В НОРМЕ")))', None,
         'Порог киберпсихоза: 0 Humanity. EMP 0 = отстранённость, диссоциация, «люди — детали».'),
    ]
    for r, label, formula, kind, note in rows:
        mput(ws, f'B{r}:C{r}', label, kind='kv_label')
        if kind == 'input':
            put(ws, f'D{r}', 0 if 'ШТРАФ' in label else None, kind='inputc')
        else:
            put(ws, f'D{r}', formula, kind='auto')
        mput(ws, f'E{r}:G{r}', note, kind='cell')
        ws.row_dimensions[r].height = 24

    mput(ws, 'B37:G37', 'Ⅲ · LAWMAN · BACKUP  ·  ВЫЗОВ ПОДКРЕПЛЕНИЯ (РАНГ = РАНГ РОЛИ)', kind='h1')
    mput(ws, 'B38:C38', 'РАНГ BACKUP', kind='head')
    put(ws, 'D38', 'БОЕВОЙ № · SP · HP', kind='head')
    mput(ws, 'E38:G38', 'КТО ПРИЕДЕТ И НА ЧЁМ', kind='head')
    backup_rows = [
        ('1–2', '8 · 7 · 20', 'Корпоративная охрана: 4 местных прокат-копа пешком. Heavy Pistols, Kevlar.'),
        ('3–4', '10 · 7 · 25', 'Патрульные: 4 копа с района на двух Compact Groundcar. Heavy Pistols, Kevlar.'),
        ('5–7', '14 · 13 · 35', 'Департамент шерифа: 2 «маунти» на High Performance Groundcar. Heavy Pistols + Assault Rifles, Heavy Armorjack.'),
        ('8', '16 · 15 · 50', 'Маршал зоны восстановления: один, на Superbike. Very Heavy Pistol, Assault Rifle, Grenade Launcher, Flak.'),
        ('9', '15 · 18 · 35', 'C-SWAT: 2 бойца Psycho Squad с воздуха, на AV-4. Assault Rifles + Rocket Launchers, Metalgear.'),
        ('10', '14 · 11 · 35', 'Национальные силы / Интерпол / Netwatch: 2 агента с AV-4. Very Heavy Pistols + Assault Rifles, Light Armorjack. '
                               'Считают по боевому номеру навыки Criminology, Deduction, Interrogation, Paramedic, Perception, Stealth, Tracking.'),
    ]
    r = 39
    for rank, stats, who in backup_rows:
        mput(ws, f'B{r}:C{r}', rank, kind='cellc')
        put(ws, f'D{r}', stats, kind='cellc')
        mput(ws, f'E{r}:G{r}', who, kind='cell')
        ws.row_dimensions[r].height = 24
        r += 1
    mput(ws, 'B45:G45', '▪ ВЫЗОВ: Действие → 1d10 ≤ ранга Backup. Приезд — через 1d6 раундов; выпало 6 — тир на уровень выше '
                        '(на 10-м ранге — две группы). Не ответили — зови в следующем ходу. Злоупотребление = штраф или разжалование.', kind='cell')
    mput(ws, 'B46:G46', '▪ Backup атакует и защищается боевым номером (стат + навык), но НЕ уклоняется от пуль. Отставной коп зовёт только тех, '
                        'с кем сохранил отношения, — решает GM.', kind='cell')
    heights(ws, {45: 26, 46: 26})

    mput(ws, 'B48:G48', 'Ⅳ · ОРУЖИЕ В РУКАХ  ·  АВТО ИЗ ЛИСТА 05 (СЛОТ 1–4)', kind='h1')
    for col, text in (('B', 'ОРУЖИЕ'), ('C', 'УРОН'), ('D', 'ROF'), ('E', 'МАГ.'),
                      ('F', 'НАВЫК'), ('G', 'БАЗА АТАКИ (+1D10)')):
        put(ws, f'{col}49', text, kind='head')
    for i in range(4):
        r = 50 + i
        put(ws, f'B{r}', f'=IFERROR(INDEX({S_GEAR}!{GEAR_W_NAME},MATCH({i+1},{S_GEAR}!{GEAR_W_SLOT},0)),"—")', kind='auto_l')
        for col, src in (('C', 'F'), ('D', 'G'), ('E', 'H'), ('F', 'E')):
            put(ws, f'{col}{r}', f'=IFERROR(INDEX({S_GEAR}!${src}$9:${src}$16,MATCH({i+1},{S_GEAR}!{GEAR_W_SLOT},0)),"—")',
                kind='auto')
        put(ws, f'G{r}', f'=IFERROR(INDEX({S_GEAR}!{GEAR_W_ATTACK},MATCH({i+1},{S_GEAR}!{GEAR_W_SLOT},0)),"—")', kind='auto')
        ws.row_dimensions[r].height = 22

    mput(ws, 'B54:G54', 'Ⅴ · БРОНЯ И ЗАЩИТА  ·  АВТО ИЗ ЛИСТА 05', kind='h1')
    for i, (label, formula, note) in enumerate([
        ('SP ГОЛОВЫ (НАДЕТОЕ)', f'={S_GEAR}!$D$27', 'В локации работает только лучший SP — он не складывается.'),
        ('SP ТЕЛА (НАДЕТОЕ)', f'={S_GEAR}!$D$28', 'При попадании вся надетая броня в локации аблейтится одновременно.'),
        ('ЩИТ (HP)', f'={S_GEAR}!$D$29', 'Щит держится на HP: 10 HP у обычного, 15 у усиленного.'),
    ]):
        r = 55 + i
        mput(ws, f'B{r}:C{r}', label, kind='kv_label')
        put(ws, f'D{r}', formula, kind='auto')
        mput(ws, f'E{r}:G{r}', note, kind='cell')
        ws.row_dimensions[r].height = 22
    mput(ws, 'B58:C58', 'ШТРАФ БРОНИ REF / DEX / MOVE', kind='kv_label')
    for col, key in (('D', 'REF'), ('E', 'DEX'), ('F', 'MOVE')):
        put(ws, f'{col}58', f'={S_GEAR}!{GEAR_PEN[key]}', kind='auto')
    mput(ws, 'G58:G58', 'применяется один раз, самый строгий', kind='note')
    mput(ws, 'B59:C59', 'УКЛОНЕНИЕ ОТ ВЫСТРЕЛОВ (REF ≥ 8)', kind='kv_label')
    put(ws, 'D59', f'=IF($F$13<8,"✖ нельзя: REF "&$F$13&" < 8 после штрафа брони",'
                   f'"✔ можно: Evasion "&IFERROR(INDEX({S_SKL}!$I$5:$I$76,MATCH("Evasion",{S_SKL}!$C$5:$C$76,0)),'
                   f'$F$16)&" + 1d10")', kind='auto_l')
    mput(ws, 'E59:G59', 'Уклонение от дальних атак — только при REF 8+ ПОСЛЕ штрафа брони: DEX + Evasion + 1d10 против атаки.', kind='note')
    heights(ws, {59: 24})

    mput(ws, 'B61:G61', 'Ⅵ · ПАМЯТКА БОЙЦА  ·  2070', kind='h1')
    memo = [
        'Ход: 1 Move Action (MOVE × 2 м) + 1 действие. Инициатива = REF + 1d10.',
        'Серьёзно ранен (HP ≤ ½): −2 ко всем действиям. Смертельно ранен (HP < 1): −4 ко всем действиям, −6 MOVE, спасбросок смерти в начале хода.',
        'Крит-травма (два и более «6» на кубах урона): +5 урона НАПРЯМУЮ в HP — SP не гасит — и эффект с листа 06.',
        'Прицельный выстрел в голову: −8 к атаке, урон ×2 (при треснувшем черепе ×3). Прицельный в оружие/ногу: −4 (см. СПРАВКА).',
        'Укрытие бинарно: либо урон уходит в укрытие, либо тебя видно. Щит — подвижное укрытие: принимает урон в свои HP, но уклоняться с ним нельзя.',
        'Броня аблейтится (−1 SP) только когда урон ПРОШЁЛ: если SP погасил всё, броня не портится (CP:R стр. 186). '
        'LAWMAN: ранг Backup = ранг роли, вызов — Действие.',
    ]
    r = 62
    for text in memo:
        mput(ws, f'B{r}:G{r}', '▪ ' + text, kind='text')
        ws.row_dimensions[r].height = 26
        r += 1
    cf_ok(ws, 'G18', 'LEFT($G$18,1)="✔"')
    cf_warn(ws, 'G18', 'LEFT($G$18,1)="✖"')
    cf_warn(ws, 'D36', 'LEFT($D$36,1)="⚠"')
    cf_warn(ws, 'G4', 'LEFT($G$4,1)="⚠"')
    cf_warn(ws, 'D34', 'OR($D$35=0,$D$34<0)')
    return ws

# ============================================================== 03 НАВЫКИ ===
SOLO_SKILLS = ['Athletics', 'Brawling', 'Concentration', 'Conversation', 'Education',
               'Evasion', 'First Aid', 'Human Perception', 'Language', 'Local Expert',
               'Perception', 'Persuasion', 'Stealth', 'Autofire', 'Handgun',
               'Interrogation', 'Melee Weapon', 'Resist Torture/Drugs', 'Shoulder Arms',
               'Tactics']


def build_skills(wb):
    ws = wb.create_sheet(NAMES['skl'])
    widths(ws, {'A': 2, 'B': 18, 'C': 30, 'D': 7, 'E': 6, 'F': 6, 'G': 8, 'H': 7,
                'I': 8, 'J': 8, 'K': 20, 'L': 42, 'M': 2, 'N': 26, 'O': 7, 'P': 7, 'Q': 54})
    sheet_setup(ws, CYAN, freeze='A5', landscape=True)
    first, last = 5, 70
    custom_first, custom_last = 71, 76

    mput(ws, 'B1:L1', 'НАВЫКИ  ▚  86 ОЧКОВ  ▚  МАКСИМУМ 6 ПРИ СОЗДАНИИ  ▚  МИН. 2 В 13 ОБЯЗАТЕЛЬНЫХ', kind='banner')
    heights(ws, {1: 32})
    mput(ws, 'B2:E2', 'ЗАПОЛНЯЙ ТОЛЬКО СТОЛБЕЦ «УР.» — СТАТА, БАЗА И ОЧКИ ПОСЧИТАЮТСЯ САМИ', kind='kv_label')
    put(ws, 'F2', 'РАСКИДАНО', kind='head')
    put(ws, 'G2', f'=SUM($J${first}:$J${custom_last})', kind='auto')
    put(ws, 'H2', 'ОСТАТОК', kind='head')
    put(ws, 'I2', f'=86-$G$2', kind='auto')
    mput(ws, 'J2:L2', f'=IF($I$2=0,"✔ 86 очков распределены полностью",IF($I$2>0,"свободно: "&$I$2&" очков","✖ перебор на "&-$I$2&" очков"))',
         kind='auto_l')
    mput(ws, 'B3:L3', '★ — обязательный пакет роли LAWMAN (мин. 2 каждому) · ☆ — пакет Solo на случай смены роли · '
                      '×2 — навык стоит 2 очка за уровень · список проверок — в панели справа.', kind='note')
    heights(ws, {3: 22})
    for col, text in (('B', 'ГРУППА'), ('C', 'НАВЫК'), ('D', 'СТАТА'), ('E', '×2'),
                      ('F', 'РОЛЬ'), ('G', 'УР.'), ('H', 'СТАТА'), ('I', 'БАЗА'),
                      ('J', 'ОЧКИ'), ('K', 'СПЕЦИАЛИЗАЦИЯ'), ('L', 'ЧТО ЭТО / ЗАМЕТКА')):
        put(ws, f'{col}4', text, kind='head')

    groups = []
    r = first
    for cat, name, stat, x2 in RULES.SKILLS:
        if cat not in groups:
            groups.append(cat)
        shade = PAPER if groups.index(cat) % 2 == 0 else WHITE
        fill = PatternFill('solid', start_color=shade)
        is_must = name in RULES.MUST_SKILLS
        put(ws, f'B{r}', cat, kind='cell', fill=fill)
        put(ws, f'C{r}', name, kind='cell', fill=fill,
            font=Font(name=SANS, size=10, bold=is_must, color=INK))
        put(ws, f'D{r}', stat, kind='cellc', fill=fill)
        put(ws, f'E{r}', '×2' if x2 else '', kind='cellc', fill=fill)
        role_mark = '★' if name in RULES.ROLE_MUST_SKILLS.get('Lawman', []) else (
            '☆' if name in SOLO_SKILLS else '')
        put(ws, f'F{r}', role_mark, kind='cellc', fill=fill,
            font=Font(name=MONO, size=10, bold=True, color=ACCENT))
        put(ws, f'G{r}', None, kind='inputc')
        put(ws, f'H{r}', f'=IFERROR(INDEX({BASEF},MATCH($D{r},{BASEB},0)),"")', kind='auto')
        put(ws, f'I{r}', f'=IF($G{r}="","",$G{r}+IFERROR($H{r},0))', kind='auto')
        put(ws, f'J{r}', f'=IF($G{r}="",0,IF($E{r}="×2",$G{r}*2,$G{r}))', kind='auto')
        sp_note = ''
        if name in RULES.SPECIALIZED_SKILLS:
            sp_note = 'выбери язык' if name == 'Language' else (
                'выбери район' if name == 'Local Expert' else 'выбери вариант')
        put(ws, f'K{r}', None, kind='input')
        put(ws, f'L{r}',
            ('ОБЯЗАТЕЛЬНЫЙ: минимум 2. ' if is_must else '') + SKILL_NOTES.get(name, sp_note),
            kind='cell')
        ws.row_dimensions[r].height = 20
        r += 1
    for i in range(custom_last - custom_first + 1):
        rr = custom_first + i
        put(ws, f'B{rr}', 'СВОЙ', kind='cell', fill=PatternFill('solid', start_color=PAPER_D))
        put(ws, f'C{rr}', None, kind='input')
        put(ws, f'D{rr}', None, kind='inputc')
        dv_list(ws, f'D{rr}', list(STAT_ROWS.keys()))
        put(ws, f'E{rr}', None, kind='inputc')
        put(ws, f'F{rr}', None, kind='inputc')
        put(ws, f'G{rr}', None, kind='inputc')
        put(ws, f'H{rr}', f'=IFERROR(INDEX({BASEF},MATCH($D{rr},{BASEB},0)),"")', kind='auto')
        put(ws, f'I{rr}', f'=IF($G{rr}="","",$G{rr}+IFERROR($H{rr},0))', kind='auto')
        put(ws, f'J{rr}', f'=IF($G{rr}="",0,IF($E{rr}="×2",$G{rr}*2,$G{rr}))', kind='auto')
        put(ws, f'K{rr}', None, kind='input')
        put(ws, f'L{rr}', 'свободная строка: домашние навыки, арт-скиллы, хобби', kind='note')
    dv_num(ws, f'G{first}:G{custom_last}', 0, 10)

    # --- панель проверок: справа от таблицы, чтобы лист не уезжал вниз ----------
    mput(ws, 'N5:Q5', 'ПРОВЕРКИ', kind='h1')
    checks = [
        ('РАСПРЕДЕЛЕНО ОЧКОВ', f'=$G$2', 'норма — ровно 86'),
        ('ОСТАТОК ОЧКОВ', f'=$I$2', '0 = всё раздано'),
        ('МАКСИМУМ НАВЫКА', f'=MAX($G${first}:$G${custom_last})', 'на старте — не выше 6'),
    ]
    r = 6
    for label, formula, note in checks:
        mput(ws, f'N{r}:O{r}', label, kind='kv_label')
        put(ws, f'P{r}', formula, kind='auto')
        mput(ws, f'Q{r}', note, kind='note')
        ws.row_dimensions[r].height = 22
        r += 1
    cf_ok(ws, 'P6', '$P$6=86')
    cf_warn(ws, 'P6', '$P$6<>86')
    cf_warn(ws, 'P8', '$P$8>6')

    r += 1
    mput(ws, f'N{r}:Q{r}', '13 ОБЯЗАТЕЛЬНЫХ НАВЫКОВ (МИН. 2)', kind='h2')
    r += 1
    put(ws, f'N{r}', 'НАВЫК', kind='head')
    put(ws, f'O{r}', 'УР.', kind='head')
    put(ws, f'P{r}', 'ГОДЕН', kind='head')
    mput(ws, f'Q{r}', 'ЧТО ДАЁТ / НАПОМИНАНИЕ', kind='head')
    must_notes = {
        'Athletics': 'Прыжки, лазание, броски, плавание — половина трюков вне боя.',
        'Brawling': 'Драка руками и ногами, Grab, Choke. Нужен даже «стрелку».',
        'Concentration': 'Фокус, память, сопротивление подавлению.',
        'Conversation': 'Вытягивать информацию, не выдавая себя.',
        'Education': 'Эрудиция: чтение, письмо, история, счёт.',
        'Evasion': 'Уклонение. С REF 8+ — и от дальних атак.',
        'First Aid': 'Стабилизация ран, простые крит-травмы.',
        'Human Perception': 'Читать лица, ловить ложь — рабочий навык копа.',
        'Language': 'Streetslang — минимум 2. Родной язык обычно 4 бесплатно.',
        'Local Expert': 'Свой район: кто держит улицу, где пересидеть.',
        'Perception': 'Замечать засады, скрытое, слежку.',
        'Persuasion': 'Убеждать, договариваться, выкручиваться.',
        'Stealth': 'Подход, засада, уход с места работы.',
    }
    must_first = r + 1
    for idx, name in enumerate(RULES.MUST_SKILLS):
        rr = must_first + idx
        put(ws, f'N{rr}', name, kind='cell')
        put(ws, f'O{rr}', f'=IFERROR(INDEX($G${first}:$G${custom_last},MATCH("{name}",$C${first}:$C${custom_last},0)),0)', kind='auto')
        put(ws, f'P{rr}', f'=IF($O{rr}>=2,"✔","✖ мал")', kind='auto')
        put(ws, f'Q{rr}', must_notes.get(name, ''), kind='note')
        ws.row_dimensions[rr].height = 20
    must_last = must_first + len(RULES.MUST_SKILLS) - 1
    rr = must_last + 1
    mput(ws, f'N{rr}:O{rr}', 'ИТОГО ОБЯЗАТЕЛЬНЫХ', kind='kv_label')
    put(ws, f'P{rr}', f'=COUNTIF($P${must_first}:$P${must_last},"✔")', kind='auto')
    put(ws, f'Q{rr}', f'=IF($P${rr}=13,"✔ все 13 закрыты","✖ не закрыто: "&(13-$P${rr}))', kind='auto_l')
    cf_warn(ws, f'P{must_first}:P{must_last}', f'$P{must_first}="✖ мал"')

    role_start = rr + 3
    mput(ws, f'N{role_start - 2}:Q{role_start - 2}', 'ПАКЕТ РОЛИ LAWMAN (МИН. 2)', kind='h2')
    put(ws, f'N{role_start - 1}', 'НАВЫК РОЛИ', kind='head')
    put(ws, f'O{role_start - 1}', 'УР.', kind='head')
    put(ws, f'P{role_start - 1}', 'ГОДЕН', kind='head')
    mput(ws, f'Q{role_start - 1}', 'ЗАЧЕМ КОПУ', kind='head')
    role_notes = {
        'Autofire (×2)': 'Очереди: 10 патронов, 2d6 × превышение DV.',
        'Criminology': 'Место преступления, улики, «почерки» банд.',
        'Deduction': 'Выводы из мелочей: допросы, логи, камеры.',
        'Handgun': 'Табельный пистолет — всегда с собой.',
        'Interrogation': 'Разговорить задержанного: запугать, припереть к фактам.',
        'Shoulder Arms': 'Винтовки, дробовики, пулемёты — ствол из оружейки.',
        'Tracking': 'Идти по следу: камеры, свидетели, отпечатки.',
    }
    role_names = RULES.ROLE_MUST_SKILLS.get('Lawman', [])
    for idx, name in enumerate(role_names):
        rr2 = role_start + idx
        put(ws, f'N{rr2}', name, kind='cell')
        put(ws, f'O{rr2}', f'=IFERROR(INDEX($G${first}:$G${custom_last},MATCH("{name}",$C${first}:$C${custom_last},0)),0)', kind='auto')
        put(ws, f'P{rr2}', f'=IF($O{rr2}>=2,"✔","✖ мал")', kind='auto')
        put(ws, f'Q{rr2}', role_notes.get(name, ''), kind='note')
        ws.row_dimensions[rr2].height = 20
    role_last = role_start + len(role_names) - 1
    rr2 = role_last + 1
    mput(ws, f'N{rr2}:O{rr2}', 'ИТОГО ПО РОЛИ', kind='kv_label')
    put(ws, f'P{rr2}', f'=COUNTIF($P${role_start}:$P${role_last},"✔")', kind='auto')
    put(ws, f'Q{rr2}', f'=IF($P${rr2}={len(role_names)},"✔ пакет законника закрыт","✖ не закрыто: "&({len(role_names)}-$P${rr2}))', kind='auto_l')
    cf_warn(ws, f'P{role_start}:P{role_last}', f'$P${role_start}="✖ мал"')

    r = rr2 + 2
    mput(ws, f'N{r}:Q{r}', '▪ ★ — пакет LAWMAN (мин. 2 каждому): Autofire (×2), Criminology, Deduction, Handgun, Interrogation, '
                           'Shoulder Arms, Tracking.', kind='note')
    mput(ws, f'N{r + 1}:Q{r + 1}', '▪ ☆ — пакет Solo на случай смены роли. Навыки с ×2 стоят 2 очка за уровень — и при подъёме за IP тоже.',
         kind='note')
    mput(ws, f'N{r + 2}:Q{r + 2}', '▪ Штраф брони уже вычтен в колонке «СТАТА»: база = УР. + СТАТА, считать вручную не нужно.',
         kind='note')
    for k in range(3):
        heights(ws, {r + k: 22})
    cf_ok(ws, 'J2', 'LEFT($J$2,1)="✔"')
    cf_warn(ws, 'J2', 'LEFT($J$2,1)="✖"')
    cf_warn(ws, f'G{first}:G{custom_last}', f'$G{first}>6')
    return ws


# ================================================================ 04 ХРОМ ===
def build_chrome(wb):
    """04 ХРОМ — импланты, HL, срез максимума Humanity, терапия, жизнь и Humanity."""
    ws = wb.create_sheet(NAMES['chr'])
    widths(ws, {'A': 2, 'B': 4, 'C': 34, 'D': 20, 'E': 16, 'F': 20, 'G': 11, 'H': 8,
                'I': 8, 'J': 12, 'K': 12, 'L': 60, 'M': 12, 'N': 12, 'O': 2})
    sheet_setup(ws, ACCENT, freeze='A5', landscape=True)
    first, last = 5, 18

    mput(ws, 'B1:N1', 'КИБЕРНЕТИКА  ▚  ЮГАС / ХРОМ  ▚  2070: ВЕСЬ НЕМЕДИЦИНСКИЙ ХРОМ ТРЕБУЕТ NEUROPORT', kind='banner')
    heights(ws, {1: 32})
    mput(ws, 'B2:F2', 'СРЕДНИЙ HL (7 (2D6) → 7) · СРЕЗ: −2 ОБЫЧНЫЙ, −4 БОРГВАР', kind='kv_label')
    put(ws, 'G2', 'HL:', kind='kv_label')
    put(ws, 'H2', f'=$H${last+1}', kind='auto')
    put(ws, 'I2', 'СРЕЗ:', kind='kv_label')
    put(ws, 'J2', f'=$I${last+1}', kind='auto')
    put(ws, 'K2', '€$:', kind='kv_label')
    put(ws, 'L2', f'=SUM($M${first}:$M${last})+SUM($N${first}:$N${last})', kind='auto', fmt=CASH_FMT)
    mput(ws, 'B3:N3', 'Пиши название как в КАТАЛОГЕ — категория, цена, HL, срез и клиника подтянутся сами. «СЛОТ» — куда ставится. '
                      'В бюджет листа 05 попадают только отмеченные «Да»: «В БЮДЖЕТ €$» — в стартовые 2550, «СТИЛЬ €$» — в 800 на моду.', kind='note')
    heights(ws, {3: 24})
    heads = [('B', '№'), ('C', 'НАЗВАНИЕ (КАК В КАТАЛОГЕ)'), ('D', 'КАТЕГОРИЯ'),
             ('E', 'ПОДТИП'), ('F', 'СЛОТ / КУДА'), ('G', 'ЦЕНА €$'), ('H', 'HL'),
             ('I', 'СРЕЗ'), ('J', 'УСТАНОВЛЕН'), ('K', 'КЛИНИКА'), ('L', 'ЭФФЕКТ / ЗАМЕТКА'),
             ('M', 'В БЮДЖЕТ €$'), ('N', 'СТИЛЬ €$')]
    for col, text in heads:
        put(ws, f'{col}4', text, kind='head')
    for i in range(last - first + 1):
        r = first + i
        put(ws, f'B{r}', i + 1, kind='cellc')
        put(ws, f'C{r}', None, kind='input')
        dv_catalog(ws, f'C{r}')
        put(ws, f'D{r}', f'=IFERROR(INDEX({CATB},MATCH($C{r},{CATA},0)),"")', kind='auto_l')
        put(ws, f'E{r}', f'=IFERROR(INDEX({CATC},MATCH($C{r},{CATA},0)),"")', kind='auto_l')
        put(ws, f'F{r}', None, kind='input')
        put(ws, f'G{r}', f'=IF($C{r}="",0,IF(ISNUMBER(SEARCH("Neuroport",$C{r})),0,'
                         f'IFERROR(INDEX({CATR},MATCH($C{r},{CATA},0)),0)))', kind='auto', fmt=CASH_FMT)
        put(ws, f'H{r}', f'=IF($C{r}="",0,IF(ISNUMBER(SEARCH("Neuroport",$C{r})),0,'
                         f'IFERROR(INDEX({CATM},MATCH($C{r},{CATA},0)),0)))', kind='auto')
        put(ws, f'I{r}', f'=IF($C{r}="",0,IF(OR(N($H{r})=0,ISNUMBER(SEARCH("Fashionware",$E{r}))),0,'
                         f'IF(ISNUMBER(SEARCH("Borgware",$E{r})),4,2)))', kind='auto')
        put(ws, f'J{r}', 'Нет', kind='inputc')
        dv_list(ws, f'J{r}', ['Да', 'Нет'])
        put(ws, f'K{r}', f'=IFERROR(INDEX({CATN},MATCH($C{r},{CATA},0)),"")', kind='auto_l')
        put(ws, f'L{r}', f'=IFERROR(LEFT(INDEX({CATT},MATCH($C{r},{CATA},0)),80),"")', kind='cell')
        put(ws, f'M{r}', f'=IF($C{r}="",0,IF($J{r}<>"Да",0,IF(ISNUMBER(SEARCH("Fashionware",$E{r})),0,'
                         f'IF(COUNTIF({S_GEAR}!$C$34:$C$53,$C{r})>0,0,$G{r}))))', kind='auto', fmt=CASH_FMT)
        put(ws, f'N{r}', f'=IF($C{r}="",0,IF($J{r}<>"Да",0,IF(ISNUMBER(SEARCH("Fashionware",$E{r})),$G{r},0)))',
            kind='auto', fmt=CASH_FMT)
        ws.row_dimensions[r].height = 20
    mput(ws, f'B{last+1}:F{last+1}', 'ИТОГО (ТОЛЬКО ОТМЕЧЕННЫЕ «ДА»)', kind='kv_label')
    put(ws, f'G{last+1}', f'=SUM($M${first}:$M${last})+SUM($N${first}:$N${last})', kind='auto', fmt=CASH_FMT)
    put(ws, f'M{last+1}', f'=SUM($M${first}:$M${last})', kind='auto', fmt=CASH_FMT)
    put(ws, f'N{last+1}', f'=SUM($N${first}:$N${last})', kind='auto', fmt=CASH_FMT)
    put(ws, f'H{last+1}', f'=SUMIF($J${first}:$J${last},"Да",$H${first}:$H${last})', kind='auto')
    put(ws, f'I{last+1}', f'=SUMIF($J${first}:$J${last},"Да",$I${first}:$I${last})', kind='auto')
    put(ws, f'J{last+1}', 'HL / срез', kind='note')
    mput(ws, f'K{last+1}:L{last+1}', '→ переносится в Humanity на листе 02', kind='note')

    r = last + 2
    mput(ws, f'B{r}:D{r}', 'NEUROPORT УСТАНОВЛЕН (2070)', kind='kv_label')
    put(ws, f'E{r}', 'Да', kind='inputc')
    dv_list(ws, f'E{r}', ['Да', 'Нет'])
    mput(ws, f'F{r}:L{r}', f'=IF(AND($E${r}="Нет",COUNTIF($J${first}:$J${last},"Да")>0),'
                           f'"⚠ По правилам 2070-х любой немедицинский хром требует Neuroport (CEMK стр. 26)",'
                           f'"✔ ок. При создании: 0 €$, 0 HL, максимум Humanity не режется (в игре — 1000 €$ и 7 HL)")', kind='auto_l')
    heights(ws, {r: 22})
    r += 1
    mput(ws, f'B{r}:L{r}', 'NEUROPORT ДАЁТ: Neural Link (5 слотов Neuralware Options) · Holophone · Biomonitor · Virtu · HUD/Chyron · '
                           '2 чип-слота · Personal Link. Порт под кибердеку — 100 €$ и 3 (1d6) HL. Диапазон сети 20 м, между нейропортами — 50 м.', kind='cell')
    heights(ws, {r: 22})
    r += 1
    mput(ws, f'B{r}:L{r}', 'ЛИМИТЫ: одно Speedware на пользователя · один Cyberdeck за раз · кибер-оружие в руке требует слот(ы) киберруки.', kind='note')
    heights(ws, {r: 22})

    r += 2
    mput(ws, f'B{r}:L{r}', 'Ⅰ · HUMANITY  ·  ЧЕЛОВЕЧНОСТЬ, HL, ТЕРАПИЯ', kind='h1')
    r += 1
    mput(ws, f'B{r}:C{r}', 'ПОКАЗАТЕЛЬ', kind='head')
    put(ws, f'D{r}', 'ЗНАЧЕНИЕ', kind='head')
    mput(ws, f'E{r}:L{r}', 'КАК СЧИТАЕТСЯ / ПРАВИЛО', kind='head')
    human_rows = [
        ('БАЗА (EMP × 10)', f'={S_BASE}!$D$29', 'От исходной EMP (лист 02, колонка «ЗНАЧ.»).'),
        ('СРЕЗ МАКСИМУМА ЗА ХРОМ', f'={S_BASE}!$D$30', 'Сумма среза отмеченных «Да». Fashionware и стартовый Neuroport не режут максимум.'),
        ('HUMANITY МАКСИМУМ', f'={S_BASE}!$D$31', 'База минус срез. Вернуть выше максимума нельзя — только снимать хром.'),
        ('HL ВСЕГО (СРЕДНЕЕ)', f'={S_BASE}!$D$32', 'Сумма средних HL установленного хрома. Дом-правило: 7 (2d6) = −7.'),
        ('ВОССТАНОВЛЕНО (ТЕРАПИЯ/ОПЫТ)', f'={S_BASE}!$D$33', 'Правится на листе 02, ячейка D33: терапия + Humanity Gain по CEMK.'),
        ('HUMANITY ТЕКУЩАЯ', f'={S_BASE}!$D$34', 'База − HL + восстановленное, но не выше максимума.'),
        ('EMP ТЕКУЩАЯ', f'={S_BASE}!$D$35', 'Каждый раз, когда десяток Humanity падает — падает и EMP.'),
        ('СТАТУС', f'={S_BASE}!$D$36', 'Humanity < 0 = киберпсихоз: лист забирает GM.'),
    ]
    for label, formula, note in human_rows:
        mput(ws, f'B{r}:C{r}', label, kind='kv_label')
        if r == last + 9:
            label = label
        put(ws, f'D{r}', formula, kind='auto')
        mput(ws, f'E{r}:L{r}', note, kind='cell')
        ws.row_dimensions[r].height = 22
        r += 1
    # ввод «восстановлено» дублируем здесь, чтобы не уходить на 02
    mput(ws, f'B{r}:C{r}', 'ШКАЛА HUMANITY', kind='kv_label')
    put(ws, f'D{r}', f'={S_BASE}!$D$34', kind='auto')
    mput(ws, f'E{r}:L{r}', f'=REPT("█",MAX(0,MIN(40,ROUND($D${r}/2,0))))&REPT("░",MAX(0,40-MIN(40,ROUND($D${r}/2,0))))',
         kind='auto_l')
    ws.row_dimensions[r].height = 22
    r += 2
    mput(ws, f'B{r}:L{r}', 'Ⅱ · ТЕРАПИЯ  ·  1 НЕДЕЛЯ ЗА СЕАНС (CP:R СТР. 229) · MEDTECH НЕ ЛЕЧИТ СЕБЯ САМ', kind='h1')
    r += 1
    mput(ws, f'B{r}:C{r}', 'ТИП', kind='head')
    put(ws, f'D{r}', 'ЦЕНА', kind='head')
    mput(ws, f'E{r}:F{r}', 'DV / МАТЕРИАЛЫ', kind='head')
    mput(ws, f'G{r}:L{r}', 'ЭФФЕКТ', kind='head')
    for name, cost, dv, effect in [
        ('Standard Humanity Loss', '500 €$', 'Medical Tech DV15 · материалы 100 €$',
         'Возврат 2d6 Humanity (в среднем 7). Больше максимума не поднять.'),
        ('Extreme Humanity Loss', '1 000 €$', 'Medical Tech DV17 · материалы 500 €$',
         'Возврат 4d6 Humanity (в среднем 14). Только при серьёзных потерях.'),
        ('Addiction', '1 000 €$', 'Medical Tech DV15 · материалы 500 €$',
         'Снимает одну зависимость. Год авто-провалов на вторичный эффект источника.'),
    ]:
        r += 1
        mput(ws, f'B{r}:C{r}', name, kind='cell')
        put(ws, f'D{r}', cost, kind='cellc')
        mput(ws, f'E{r}:F{r}', dv, kind='cell')
        mput(ws, f'G{r}:L{r}', effect, kind='cell')
        ws.row_dimensions[r].height = 22

    r += 2
    mput(ws, f'B{r}:L{r}', 'Ⅲ · ЧТО РЕЖЕТ HUMANITY И ЧТО ВОЗВРАЩАЕТ  ·  ХРОМ, СОБЫТИЯ, ЖИЗНЬ (CEMK СТР. 28–30)', kind='h1')
    r += 1
    mput(ws, f'B{r}:C{r}', 'БРОСОК', kind='head')
    mput(ws, f'D{r}:L{r}', 'ЗА ЧТО — ПРИМЕРЫ (ПОТЕРИ — В КОНЦЕ СЕССИИ И КАЖДЫЙ МЕСЯЦ, ПРИБАВКИ — ТАМ ЖЕ)', kind='head')
    for roll, text in [
        ('ПОТЕРЯ 1d6', 'Пытки, угроза смерти, несправедливость системы · месяц на Kibble и Prepak-еде · месяц на корпорацию · смерть близкого без церемонии.'),
        ('ПОТЕРЯ 2d6', 'Зверское убийство на глазах · первое убийство · месяц побывал «смертельно ранен» · больше недели в тюрьме · голодал.'),
        ('ПОТЕРЯ 3d6', 'Участие в убийстве невиновного · смерть близкого на твоих глазах · больше недели в зоне боевых действий.'),
        ('ПРИБАВКА 1d6', 'Виделся с настоящим другом или семьёй · неделя отдыха без дел и травм · месяц вдали от мегаполиса без лишений.'),
        ('ПРИБАВКА 2d6', 'Месяц на Fresh Food Lifestyle · месяц в Corporate Conapt или лучше · спас чью-то жизнь.'),
        ('ПРИБАВКА 3d6', 'Свадьба, усыновление, рождение ребёнка, исполнение мечты · месяц, где прибавок больше, чем потерь.'),
    ]:
        r += 1
        mput(ws, f'B{r}:C{r}', roll, kind='cellc')
        mput(ws, f'D{r}:L{r}', text, kind='cell')
        ws.row_dimensions[r].height = 24
    r += 1
    mput(ws, f'B{r}:L{r}', 'ДЛЯ ЭТОГО ПЕРСОНАЖА: стартовое жильё — контейнер + Kibble, то есть 1d6 потери Humanity каждый месяц, пока не поднимешь '
                           'уровень жизни (лист СПРАВКА). Компенсируют настоящий друг, семья и неделя отдыха. Humanity ниже 0 — киберпсихоз: '
                           'в людях остались только детали, и GM играет персонажа по его худшим наклонностям.', kind='cell')
    ws.row_dimensions[r].height = 44

    for rng, formula in [(f'F{last+2}', f'LEFT($F${last+2},1)="⚠"'), ('D' + str(last + 10), f'$D${last+10}=0')]:
        cf_warn(ws, rng, formula)
    cf_warn(ws, f'D{last+11}', f'OR($D${last+10}=0,$D${last+11}<0)')
    return ws

# ========================================================= 05 СНАРЯЖЕНИЕ ===
W_FIRST, W_LAST = 9, 16      # оружие
A_FIRST, A_LAST = 21, 26     # броня
I_FIRST, I_LAST = 34, 53     # инвентарь
C_FIRST, C_LAST = 58, 77     # касса


def build_gear(wb):
    ws = wb.create_sheet(NAMES['gear'])
    widths(ws, {'A': 2, 'B': 4, 'C': 34, 'D': 22, 'E': 18, 'F': 9, 'G': 11, 'H': 9,
                'I': 12, 'J': 9, 'K': 11, 'L': 12, 'M': 30, 'N': 11, 'O': 15, 'P': 2})
    sheet_setup(ws, GOLD, freeze='A9', landscape=True)

    mput(ws, 'B1:M1', 'СНАРЯЖЕНИЕ  ▚  БЮДЖЕТ 2550 €$ + 800 €$ НА СТИЛЬ  ▚  ОРУЖИЕ · БРОНЯ · ИНВЕНТАРЬ · КАССА', kind='banner')
    heights(ws, {1: 20})
    mput(ws, 'B2:M2', 'НАЗВАНИЯ БЕРУТСЯ ИЗ КАТАЛОГА — ЦЕНА, УРОН И ШТРАФЫ ПОДТЯНУТСЯ САМИ. НЕТ В КАТАЛОГЕ — ВПИШИ СВОЮ ЦЕНУ В «ЦЕНА СВОЯ».', kind='note')

    mput(ws, 'B3:D3', 'СТАРТ: ОРУЖИЕ, БРОНЯ, СНАРЯЖЕНИЕ, ХРОМ (€$)', kind='kv_label')
    put(ws, 'E3', 2550, kind='inputc', fmt=CASH_FMT)
    put(ws, 'F3', 'ПОТРАЧЕНО', kind='kv_label')
    # из инвентаря вычитается только его собственная «модная» часть: Fashionware с листа 04
    # сидит в бюджете стиля и второй раз из снаряжения не вычитается
    put(ws, 'G3', f'=$H${I_LAST+1}+SUM({S_CHR}!$M$5:$M$18)+SUM($O${A_FIRST}:$O${A_LAST})'
                  f'-($G$4-SUM({S_CHR}!$N$5:$N$18))',
        kind='auto', fmt=CASH_FMT)
    put(ws, 'H3', 'ОСТАТОК', kind='kv_label')
    put(ws, 'I3', '=$E$3-$G$3', kind='auto', fmt=CASH_FMT)
    mput(ws, 'J3:M3', 'Копятся из трёх мест: инвентарь (Ⅲ), броня (Ⅱ) и установленный хром (лист 04). '
                      'Что уже вписано в инвентарь, второй раз не считается.', kind='note')

    mput(ws, 'B4:D4', 'СТАРТ: СТИЛЬ — FASHION И FASHIONWARE (€$)', kind='kv_label')
    put(ws, 'E4', 800, kind='inputc', fmt=CASH_FMT)
    put(ws, 'F4', 'ПОТРАЧЕНО', kind='kv_label')
    put(ws, 'G4', f'=SUMPRODUCT(($D${I_FIRST}:$D${I_LAST}="Мода")*$I${I_FIRST}:$I${I_LAST})'
                  f'+SUMPRODUCT(($E${I_FIRST}:$E${I_LAST}="Fashionware")*$I${I_FIRST}:$I${I_LAST})'
                  f'+SUM({S_CHR}!$N$5:$N$18)', kind='auto', fmt=CASH_FMT)
    put(ws, 'H4', 'ОСТАТОК', kind='kv_label')
    put(ws, 'I4', '=$E$4-$G$4', kind='auto', fmt=CASH_FMT)
    mput(ws, 'J4:M4', 'Одежда (категория «Мода»), Fashionware из инвентаря и Fashionware-хром с листа 04.', kind='note')

    mput(ws, 'B5:C5', 'НАЛИЧНЫЕ €$ (АВТО)', kind='kv_label')
    put(ws, 'D5', f'=$I$3+SUM($E${C_FIRST}:$E${C_LAST})', kind='auto', fmt=CASH_FMT)
    put(ws, 'E5', 'ПРОВЕРКА БЮДЖЕТА', kind='kv_label')
    mput(ws, 'F5:H5', '=IF(OR($I$3<0,$I$4<0),"✖ стартовые бюджеты превышены — согласуй с GM",'
                      '"✔ в рамках стартовых бюджетов: инвентарь + броня + хром")', kind='auto_l')
    mput(ws, 'I5:M5', 'Остаток бюджета снаряжения (2 550 €$) остаётся при тебе наличными (CP:R 104: «You keep anything you '
                      'don’t spend»), а остаток 800 €$ на моду и фэшн-хром сгорает. +1500 €$ «от корпорации» — только на импланты, '
                      'и вместе с обязательным Neural Link.', kind='note')

    mput(ws, 'B7:M7', 'Ⅰ · ОРУЖИЕ  ·  СТОЛБЕЦ «В РУКАХ 1–4» ВЫНОСИТ ОРУЖИЕ НА ЛИСТ 02', kind='h1')
    for col, text in (('B', '№'), ('C', 'НАЗВАНИЕ'), ('D', 'ТИП'), ('E', 'НАВЫК'), ('F', 'УРОН'),
                      ('G', 'ROF'), ('H', 'МАГ.'), ('I', 'ПАТРОНЫ'), ('J', 'КАЧЕСТВО'),
                      ('K', 'В РУКАХ 1–4'), ('L', 'БАЗА АТАКИ'), ('M', 'ЗАМЕТКИ')):
        put(ws, f'{col}8', text, kind='head')
    for i in range(W_LAST - W_FIRST + 1):
        r = W_FIRST + i
        put(ws, f'B{r}', i + 1, kind='cellc')
        put(ws, f'C{r}', None, kind='input')
        dv_catalog(ws, f'C{r}')
        put(ws, f'D{r}', f'=IFERROR(INDEX({CATC},MATCH($C{r},{CATA},0)),"")', kind='auto_l')
        put(ws, f'E{r}', f'=IFERROR(INDEX({CATD},MATCH($C{r},{CATA},0)),"")', kind='auto_l')
        put(ws, f'F{r}', f'=IFERROR(INDEX({CATE},MATCH($C{r},{CATA},0)),"")', kind='auto')
        put(ws, f'G{r}', f'=IFERROR(INDEX({CATF},MATCH($C{r},{CATA},0)),"")', kind='auto')
        put(ws, f'H{r}', f'=IFERROR(INDEX({CATG},MATCH($C{r},{CATA},0)),"")', kind='auto')
        put(ws, f'I{r}', None, kind='input')
        put(ws, f'J{r}', 'Standard', kind='inputc')
        dv_list(ws, f'J{r}', ['Standard', 'Excellent', 'Poor'])
        put(ws, f'K{r}', None, kind='inputc')
        dv_list(ws, f'K{r}', ['1', '2', '3', '4'])
        put(ws, f'L{r}', f'=IF($C{r}="","",IFERROR(INDEX({SKLI},MATCH($E{r},{SKLC},0))'
                         f'+IF($J{r}="Excellent",1,IF($J{r}="Poor",-1,0)),0))', kind='auto')
        put(ws, f'M{r}', None, kind='input')
        ws.row_dimensions[r].height = 18
    mput(ws, f'B{W_LAST+1}:M{W_LAST+1}', 'Атака = 1d10 + «БАЗА АТАКИ» (навык + стата со штрафом брони). Патроны пиши тут же: «AP ×24».', kind='note')
    mput(ws, f'B{W_LAST+2}:M{W_LAST+2}', 'УЧЁТ ДЕНЕГ: траты — из блока Ⅲ «ИНВЕНТАРЬ» (оружие и снаряжение впиши и сюда, и туда), '
                                        'броня — из блока Ⅱ (цена N, в бюджет O), хром — с листа 04. Броню и хром в инвентарь НЕ дублируй.', kind='note')

    mput(ws, 'B19:O19', 'Ⅱ · БРОНЯ И ЩИТ  ·  В ЛОКАЦИИ РАБОТАЕТ ТОЛЬКО ЛУЧШИЙ SP, ШТРАФ БЕРЁТСЯ ОДИН РАЗ  ·  '
                        'ЦЕНА И УЧЁТ В БЮДЖЕТЕ — КОЛОНКИ N И O', kind='h1')
    for col, text in (('B', '№'), ('C', 'НАЗВАНИЕ'), ('D', 'ЛОКАЦИЯ'), ('E', 'НАДЕТО'),
                      ('F', 'SP'), ('G', 'HP (ЩИТ)'), ('H', 'ШТРАФ REF'), ('I', 'ШТРАФ DEX'),
                      ('J', 'ШТРАФ MOVE'), ('K', 'SP СЕЙЧАС'), ('L', 'ЭФФ. SP'), ('M', 'ЗАМЕТКИ'),
                      ('N', 'ЦЕНА €$'), ('O', 'В БЮДЖЕТ €$')):
        put(ws, f'{col}20', text, kind='head')
    for i in range(A_LAST - A_FIRST + 1):
        r = A_FIRST + i
        put(ws, f'B{r}', i + 1, kind='cellc')
        put(ws, f'C{r}', None, kind='input')
        dv_catalog(ws, f'C{r}')
        put(ws, f'D{r}', 'Тело', kind='inputc')
        dv_list(ws, f'D{r}', ['Голова', 'Тело', 'Щит'])
        put(ws, f'E{r}', 'Нет', kind='inputc')
        dv_list(ws, f'E{r}', ['Да', 'Нет'])
        put(ws, f'F{r}', f'=IFERROR(INDEX({CATH},MATCH($C{r},{CATA},0)),0)', kind='auto')
        put(ws, f'G{r}', f'=IFERROR(INDEX({CATI},MATCH($C{r},{CATA},0)),0)', kind='auto')
        for col, src in (('H', 'J'), ('I', 'K'), ('J', 'L')):
            catrange = globals()['CAT' + src]
            put(ws, f'{col}{r}', f'=IFERROR(INDEX({catrange},MATCH($C{r},{CATA},0)),0)', kind='auto')
        put(ws, f'K{r}', None, kind='inputc')
        put(ws, f'L{r}', f'=IF($E{r}<>"Да",0,IF($K{r}<>"",$K{r},$F{r}))', kind='auto')
        put(ws, f'M{r}', None, kind='input')
        put(ws, f'N{r}', f'=IF($C{r}="",0,IFERROR(INDEX({CATR},MATCH($C{r},{CATA},0)),0))', kind='auto', fmt=CASH_FMT)
        put(ws, f'O{r}', f'=IF($C{r}="",0,IF(COUNTIF($C${I_FIRST}:$C${I_LAST},$C{r})>0,0,$N{r}))',
            kind='auto', fmt=CASH_FMT)
        ws.row_dimensions[r].height = 18
    for idx, (label, formula, note) in enumerate([
        ('SP ГОЛОВЫ (НАДЕТОЕ)',
         f'=SUMPRODUCT(MAX(($D${A_FIRST}:$D${A_LAST}="Голова")*($E${A_FIRST}:$E${A_LAST}="Да")*$L${A_FIRST}:$L${A_LAST}))',
         'Работает лучший SP в локации — второй слой не складывается.'),
        ('SP ТЕЛА (НАДЕТОЕ)',
         f'=SUMPRODUCT(MAX(($D${A_FIRST}:$D${A_LAST}="Тело")*($E${A_FIRST}:$E${A_LAST}="Да")*$L${A_FIRST}:$L${A_LAST}))',
         'Вся надетая броня локации аблейтится одновременно (−1 за каждое попадание).'),
        ('ЩИТ: HP',
         f'=SUMPRODUCT(MAX(($D${A_FIRST}:$D${A_LAST}="Щит")*($E${A_FIRST}:$E${A_LAST}="Да")*$G${A_FIRST}:$G${A_LAST}))',
         'Обычный щит 10 HP, усиленный 15 HP. Взять/бросить — Действие.'),
    ]):
        r = 27 + idx
        mput(ws, f'B{r}:C{r}', label, kind='kv_label')
        put(ws, f'D{r}', formula, kind='auto')
        mput(ws, f'E{r}:M{r}', note, kind='cell')
        ws.row_dimensions[r].height = 18
    mput(ws, 'B30:C30', 'ШТРАФ БРОНИ REF / DEX / MOVE (ПОЛОЖИТЕЛЬНЫЙ)', kind='kv_label')
    for col, src in (('D', 'H'), ('E', 'I'), ('F', 'J')):
        put(ws, f'{col}30', f'=-SUMPRODUCT(MIN(($E${A_FIRST}:$E${A_LAST}="Да")*${src}${A_FIRST}:${src}${A_LAST}))',
            kind='auto')
    mput(ws, 'G30:M30', 'Самый строгий штраф из надетого, применяется один раз — он уже вычтен из REF/DEX/MOVE на листе 02. '
                        'Хочешь ослабить броню — снимай вещи, а не правь эти цифры.', kind='note')

    mput(ws, 'B32:M32', 'Ⅲ · ИНВЕНТАРЬ  ·  СУММЫ ОТСЮДА ИДУТ В ОБА БЮДЖЕТА ВМЕСТЕ С БРОНЁЙ (Ⅱ) И ХРОМОМ (ЛИСТ 04)', kind='h1')
    for col, text in (('B', '№'), ('C', 'НАЗВАНИЕ'), ('D', 'КАТЕГОРИЯ'), ('E', 'ПОДТИП'),
                      ('F', 'КОЛ-ВО'), ('G', 'ЦЕНА €$'), ('H', 'ЦЕНА СВОЯ'), ('I', 'СУММА'),
                      ('J', 'ГДЕ НОСИТ')):
        put(ws, f'{col}33', text, kind='head')
    mput(ws, 'K33:L33', 'ЗАМЕТКА', kind='head')
    mput(ws, 'M33:M33', 'ОПИСАНИЕ ИЗ КАТАЛОГА', kind='head')
    for i in range(I_LAST - I_FIRST + 1):
        r = I_FIRST + i
        put(ws, f'B{r}', i + 1, kind='cellc')
        put(ws, f'C{r}', None, kind='input')
        dv_catalog(ws, f'C{r}')
        put(ws, f'D{r}', f'=IFERROR(INDEX({CATB},MATCH($C{r},{CATA},0)),"")', kind='auto_l')
        put(ws, f'E{r}', f'=IFERROR(INDEX({CATC},MATCH($C{r},{CATA},0)),"")', kind='auto_l')
        put(ws, f'F{r}', None, kind='inputc')
        put(ws, f'G{r}', f'=IFERROR(INDEX({CATR},MATCH($C{r},{CATA},0)),"")', kind='auto', fmt=CASH_FMT)
        put(ws, f'H{r}', None, kind='inputc', fmt=CASH_FMT)
        put(ws, f'I{r}', f'=IF($C{r}="",0,IF($H{r}<>"",$H{r},IF(ISNUMBER($G{r}),$G{r},0))*IF($F{r}="",1,$F{r}))', kind='auto', fmt=CASH_FMT)
        put(ws, f'J{r}', None, kind='input')
        mput(ws, f'K{r}:L{r}', None, kind='input')
        put(ws, f'M{r}', f'=IFERROR(LEFT(INDEX({CATT},MATCH($C{r},{CATA},0)),90),"")', kind='cell')
        ws.row_dimensions[r].height = 18
    tr = I_LAST + 1
    mput(ws, f'B{tr}:D{tr}', 'ИТОГО ПО ИНВЕНТАРЮ (€$)', kind='kv_label')
    put(ws, f'E{tr}', f'=SUM($I${I_FIRST}:$I${I_LAST})', kind='auto', fmt=CASH_FMT)
    put(ws, f'F{tr}', 'СНАРЯЖЕНИЕ + СТИЛЬ, ВСЁ', kind='note')
    put(ws, f'H{tr}', f'=SUM($I${I_FIRST}:$I${I_LAST})', kind='auto', fmt=CASH_FMT)
    mput(ws, f'I{tr}:M{tr}', f'=IF(($G$3+$G$4)>($E$3+$E$4),"⚠ потрачено больше стартовых 3350 €$ — часть вещей куплена уже в игре","")',
         kind='auto_l')

    mput(ws, 'B56:M56', 'Ⅳ · КАССА  ·  ДОХОДЫ И ТРАТЫ В ИГРЕ', kind='h1')
    put(ws, 'B57', 'ДАТА', kind='head')
    mput(ws, 'C57:D57', 'ЧТО (ДЕЛО / ПОКУПКА)', kind='head')
    put(ws, 'E57', 'ОБОРОТ ± €$', kind='head')
    put(ws, 'F57', 'БАЛАНС', kind='head')
    mput(ws, 'G57:M57', 'ЗАМЕТКА', kind='head')
    for r in range(C_FIRST, C_LAST + 1):
        put(ws, f'B{r}', None, kind='input')
        mput(ws, f'C{r}:D{r}', None, kind='input')
        put(ws, f'E{r}', None, kind='inputc', fmt=CASH_FMT)
        put(ws, f'F{r}', f'=$I$3+SUM($E${C_FIRST}:$E{r})', kind='auto', fmt=CASH_FMT)
        mput(ws, f'G{r}:M{r}', None, kind='input')
        ws.row_dimensions[r].height = 18
    tr = C_LAST + 1
    mput(ws, f'B{tr}:D{tr}', 'ИТОГО ОБОРОТ / БАЛАНС', kind='kv_label')
    put(ws, f'E{tr}', f'=SUM($E${C_FIRST}:$E${C_LAST})', kind='auto', fmt=CASH_FMT)
    put(ws, f'F{tr}', f'=$I$3+SUM($E${C_FIRST}:$E${C_LAST})', kind='auto', fmt=CASH_FMT)
    mput(ws, f'G{tr}:M{tr}', 'Наличные = стартовый остаток + оборот. Хочешь вести наличные вручную — перебей «БАЛАНС» цифрой.', kind='note')
    rr = tr + 2
    mput(ws, f'B{rr}:M{rr}', 'ДЕНЬГИ: 2550 €$ — оружие/броня/снаряжение/хром; 800 €$ — только Fashion + Fashionware; жильё 1 000 €$ + Kibble '
                             '100 €$/мес = 1 100 €$ к 1-му числу (первый месяц покрыт). В 2070-х почти всё можно купить напрямую у '
                             'производителя, но по двойной цене (CEMK: расширенная доступность).', kind='note')
    ws.row_dimensions[rr].height = 30
    cf_ok(ws, 'F5', 'LEFT($F$5,1)="✔"')
    cf_warn(ws, 'F5', 'LEFT($F$5,1)="✖"')
    cf_warn(ws, 'I3:I4', 'OR($I$3<0,$I$4<0)')
    cf_warn(ws, 'G3', '($G$3+$G$4)>($E$3+$E$4)')
    return ws


# ============================================================ 06 СОСТОЯНИЕ ===
CRIT_BODY_FIRST, CRIT_HEAD_FIRST = 22, 37  # пересчитываются при сборке СПРАВКИ (таблицы живут там)


def build_state(wb):
    """06 СОСТОЯНИЕ — раны, крит-травмы, зависимости, IP и лог дел."""
    ws = wb.create_sheet(NAMES['sta'])
    widths(ws, {'A': 2, 'B': 4, 'C': 16, 'D': 24, 'E': 30, 'F': 16, 'G': 16, 'H': 16,
                'I': 13, 'J': 22, 'K': 20, 'L': 20, 'M': 2})
    sheet_setup(ws, BAND, freeze='A7', landscape=True)
    body_last = CRIT_BODY_FIRST + len(RULES.CRIT_BODY) - 1
    head_last = CRIT_HEAD_FIRST + len(RULES.CRIT_HEAD) - 1

    mput(ws, 'B1:M1', 'СОСТОЯНИЕ  ▚  РАНЫ · КРИТ-ТРАВМЫ · ЗАВИСИМОСТИ · IP · ЛОГ ДЕЛ', kind='banner')
    heights(ws, {1: 32})
    mput(ws, 'B2:E2', 'ТЕКУЩЕЕ СОСТОЯНИЕ ОБЪЕКТА', kind='kv_label')
    put(ws, 'F2', 'HP', kind='kv_label')
    put(ws, 'G2', f'={S_BASE}!{BASE_HP_CUR}&" / "&{S_BASE}!{BASE_HP_MAX}', kind='auto')
    put(ws, 'H2', 'СОСТОЯНИЕ', kind='kv_label')
    put(ws, 'I2', f'={S_BASE}!{BASE_WOUND}', kind='auto')
    mput(ws, 'J2:M2', 'HP правится на листе 02 (ячейка D23) — здесь всё пересчитается.', kind='note')
    mput(ws, 'B3:C3', 'СПАСБРОСОК СМЕРТИ (BODY)', kind='kv_label')
    put(ws, 'D3', f'={S_BASE}!{BASE_DS}', kind='auto')
    put(ws, 'E3', 'ШТРАФ К СПАСБРОСКАМ', kind='kv_label')
    put(ws, 'F3', f'={S_BASE}!{BASE_DS_PEN}', kind='auto')
    put(ws, 'G3', 'ПРОВАЛЫ', kind='kv_label')
    mput(ws, 'H3:M3', None, kind='input')
    mput(ws, 'B4:M4', 'Смертельное состояние: HP < 1 → −4 ко всем действиям, −6 MOVE, спасбросок смерти каждый ход. Крит-травма даёт +5 урона '
                      'напрямую в HP (+1 к штрафу спасброска). Стабилизация: DV10 (лёгкое), DV13 (серьёзное), DV15 (смертельное → 1 HP).', kind='note')
    heights(ws, {2: 24, 3: 24, 4: 24})

    mput(ws, 'B5:M5', 'Ⅰ · КРИТ-ТРАВМЫ  ·  ВЫБЕРИ ЛОКАЦИЮ И БРОСОК 2D6 — ОСТАЛЬНОЕ ПОДТЯНЕТСЯ', kind='h1')
    heights(ws, {5: 26})
    for col, text in (('B', '№'), ('C', 'ЛОКАЦИЯ'), ('D', '2D6'), ('E', 'ТРАВМА (АВТО)'),
                      ('F', 'ЭФФЕКТ (АВТО)'), ('G', 'БЫСТРЫЙ ФИКС'), ('H', 'ЛЕЧЕНИЕ'), ('I', 'СТАТУС')):
        put(ws, f'{col}6', text, kind='head')
    mput(ws, 'J6:M6', 'ЗАМЕТКИ', kind='head')
    for i in range(10):
        r = 7 + i
        put(ws, f'B{r}', i + 1, kind='cellc')
        put(ws, f'C{r}', 'Тело', kind='inputc')
        dv_list(ws, f'C{r}', ['Тело', 'Голова'])
        put(ws, f'D{r}', None, kind='inputc')
        dv_num(ws, f'D{r}', 2, 12)
        put(ws, f'E{r}', f'=IF($D{r}="","",IF($C{r}="Тело",IFERROR(INDEX($C${CRIT_BODY_FIRST}:$C${body_last},MATCH($D{r},$B${CRIT_BODY_FIRST}:$B${body_last},0)),"—"),'
                         f'IF($C{r}="Голова",IFERROR(INDEX($C${CRIT_HEAD_FIRST}:$C${head_last},MATCH($D{r},$B${CRIT_HEAD_FIRST}:$B${head_last},0)),"—"),"—")))', kind='auto_l')
        put(ws, f'F{r}', f'=IF($D{r}="","",IF($C{r}="Тело",IFERROR(INDEX($D${CRIT_BODY_FIRST}:$D${body_last},MATCH($D{r},$B${CRIT_BODY_FIRST}:$B${body_last},0)),"—"),'
                         f'IF($C{r}="Голова",IFERROR(INDEX($D${CRIT_HEAD_FIRST}:$D${head_last},MATCH($D{r},$B${CRIT_HEAD_FIRST}:$B${head_last},0)),"—"),"—")))', kind='cell')
        put(ws, f'G{r}', f'=IF($D{r}="","",IF($C{r}="Тело",IFERROR(INDEX($I${CRIT_BODY_FIRST}:$I${body_last},MATCH($D{r},$B${CRIT_BODY_FIRST}:$B${body_last},0)),"—"),'
                         f'IF($C{r}="Голова",IFERROR(INDEX($I${CRIT_HEAD_FIRST}:$I${head_last},MATCH($D{r},$B${CRIT_HEAD_FIRST}:$B${head_last},0)),"—"),"—")))', kind='cellc')
        put(ws, f'H{r}', f'=IF($D{r}="","",IF($C{r}="Тело",IFERROR(INDEX($L${CRIT_BODY_FIRST}:$L${body_last},MATCH($D{r},$B${CRIT_BODY_FIRST}:$B${body_last},0)),"—"),'
                         f'IF($C{r}="Голова",IFERROR(INDEX($L${CRIT_HEAD_FIRST}:$L${head_last},MATCH($D{r},$B${CRIT_HEAD_FIRST}:$B${head_last},0)),"—"),"—")))', kind='cellc')
        put(ws, f'I{r}', 'Нет', kind='inputc')
        dv_list(ws, f'I{r}', ['Активна', 'Вылечена', 'Нет'])
        mput(ws, f'J{r}:M{r}', None, kind='input')
        heights(ws, {r: 24})
    mput(ws, 'B17:M17', 'Крит = два и более «6» на кубах урона: +5 урона напрямую в HP (SP не гасит). Без прицельного выстрела в голову — таблица тела. '
                        'Полные таблицы крит-травм — на листе СПРАВКА. Quick Fix лечит эффект, но не саму травму.', kind='note')
    heights(ws, {17: 24})

    mput(ws, 'B19:M19', 'Ⅱ · СМЕРТЬ, СТАБИЛИЗАЦИЯ, ЗАВИСИМОСТИ', kind='h1')
    r = 19
    for label, value in [
        ('СТАБИЛИЗАЦИЯ: DV', 'Лёгкое DV10 · Серьёзное DV13 · Смертельное DV15 (успех → 1 HP и минута без сознания)'),
        ('СПАСБРОСОК СМЕРТИ', 'В начале каждого хода при HP < 1: 1d10 ≤ BODY − штраф. Выпало 10 = провал = смерть.'),
        ('STIM / SPEEDHEAL', 'Stim снимает штрафы «серьёзно ранен» на час. Speedheal лечит BODY + WILL HP (1 раз в день).'),
        ('ЗАВИСИМОСТИ (ВВОД)', None),
        ('АБСТИНЕНЦИЯ И ТРИГГЕРЫ (ВВОД)', None),
        ('СНЯТИЕ ЗАВИСИМОСТИ', 'Терапия: 1 неделя, 1 000 €$ + материалы 500 €$, Medical Tech DV15 (лист 04).'),
    ]:
        r += 1
        mput(ws, f'B{r}:C{r}', label, kind='kv_label')
        mput(ws, f'D{r}:M{r}', value, kind='cell' if value else 'input')
        heights(ws, {r: 24 if value else 28})

    mput(ws, 'B27:M27', 'Ⅲ · РЕПУТАЦИЯ И УЛУЧШЕНИЯ (IP)', kind='h1')
    mput(ws, 'B28:C28', 'ПОКАЗАТЕЛЬ', kind='head')
    put(ws, 'D28', 'ЗНАЧЕНИЕ', kind='head')
    mput(ws, 'E28:M28', 'ПРАВИЛО', kind='head')
    ip_notes = [
        ('РЕПУТАЦИЯ', 'input', 'Растёт за громкие дела: реакция улиц, кто берёт твой звонок, кто хочет тебя снять.'),
        ('IP ЗАРАБОТАНО', 'input', 'GM выдаёт после сессии: 10–50 за стиль игры, больше — за выполненное дело (лист СПРАВКА).'),
        ('IP ПОТРАЧЕНО (АВТО)', 'auto_sum', 'Сумма по таблице Ⅳ ниже.'),
        ('IP СВОБОДНО', 'auto', 'Заработано минус потрачено.'),
    ]
    for idx, (label, kind, note) in enumerate(ip_notes):
        r = 29 + idx
        mput(ws, f'B{r}:C{r}', label, kind='kv_label')
        if kind == 'input':
            put(ws, f'D{r}', None, kind='inputc')
        elif kind == 'auto_sum':
            put(ws, f'D{r}', '=SUM($F$36:$F$45)', kind='auto')
        else:
            put(ws, f'D{r}', '=$D$30-$D$31', kind='auto')
        mput(ws, f'E{r}:M{r}', note, kind='cell')
        heights(ws, {r: 24})

    mput(ws, 'B34:M34', 'Ⅳ · ЧТО УЛУЧШИЛИ ЗА IP  ·  СТОИМОСТЬ СЧИТАЕТСЯ АВТОМАТИЧЕСКИ', kind='h1')
    put(ws, 'B35', 'ДАТА', kind='head')
    put(ws, 'C35', 'ЧТО УЛУЧШИЛИ', kind='head')
    put(ws, 'D35', 'ТИП', kind='head')
    put(ws, 'E35', 'НОВЫЙ УР.', kind='head')
    put(ws, 'F35', 'СТОИМОСТЬ IP', kind='head')
    mput(ws, 'G35:M35', 'ЗАМЕТКА', kind='head')
    for r in range(36, 46):
        put(ws, f'B{r}', None, kind='input')
        put(ws, f'C{r}', None, kind='input')
        put(ws, f'D{r}', 'НАВЫК', kind='inputc')
        dv_list(ws, f'D{r}', ['НАВЫК', 'НАВЫК ×2', 'РОЛЬ', 'СТАТА (GM)'])
        put(ws, f'E{r}', None, kind='inputc')
        put(ws, f'F{r}', f'=IF(OR($E{r}="",$D{r}=""),"",IF($D{r}="РОЛЬ",60*$E{r},'
                         f'IF($D{r}="НАВЫК ×2",40*$E{r},IF($D{r}="НАВЫК",20*$E{r},""))))', kind='auto')
        mput(ws, f'G{r}:M{r}', None, kind='input')
        heights(ws, {r: 22})
    mput(ws, 'B46:E46', 'ИТОГО ПОТРАЧЕНО IP', kind='kv_label')
    put(ws, 'F46', '=SUM($F$36:$F$45)', kind='auto')
    mput(ws, 'G46:M46', '20 × уровень — обычный навык · 40 × уровень — навык (×2) · 60 × ранг — ролевая способность. Уровни не перескакивают.', kind='note')
    heights(ws, {46: 24})

    mput(ws, 'B48:M48', 'Ⅴ · ЛОГ ДЕЛ (СЕССИИ)  ·  ЧТО БЫЛО И ЗА ЧТО ЗАПЛАТИЛИ', kind='h1')
    put(ws, 'B49', 'ДАТА', kind='head')
    mput(ws, 'C49:D49', 'ДЕЛО / СЕССИЯ', kind='head')
    put(ws, 'E49', 'РОЛЬ В ДЕЛЕ', kind='head')
    put(ws, 'F49', 'НАГРАДА €$', kind='head')
    put(ws, 'G49', 'IP', kind='head')
    mput(ws, 'H49:M49', 'ИТОГ / ЗАМЕТКА', kind='head')
    for r in range(50, 64):
        put(ws, f'B{r}', None, kind='input')
        mput(ws, f'C{r}:D{r}', None, kind='input')
        put(ws, f'E{r}', None, kind='input')
        put(ws, f'F{r}', None, kind='inputc', fmt=CASH_FMT)
        put(ws, f'G{r}', None, kind='inputc')
        mput(ws, f'H{r}:M{r}', None, kind='input')
        heights(ws, {r: 22})
    mput(ws, 'B64:E64', 'ИТОГО ЗА КАМПАНИЮ', kind='kv_label')
    put(ws, 'F64', '=SUM($F$50:$F$63)', kind='auto', fmt=CASH_FMT)
    put(ws, 'G64', '=SUM($G$50:$G$63)', kind='auto')
    mput(ws, 'H64:M64', 'Сверь IP с полем «IP заработано» выше.', kind='note')

    mput(ws, 'B66:M66', 'Ⅵ · ДОЛГИ, ЦЕЛИ И КРЮЧКИ', kind='h1')
    r = 66
    for label in ('ДОЛГИ И ОБЯЗАТЕЛЬСТВА (КОМУ, ЧТО, КОГДА)',
                  'ЖИЗНЕННЫЕ ЦЕЛИ / КРЮЧКИ ДЛЯ GM',
                  'ТАБУ И ТРИГГЕРЫ (ОТ ИГРОКА)'):
        r += 1
        mput(ws, f'B{r}:C{r}', label, kind='kv_label')
        mput(ws, f'D{r}:M{r+1}', None, kind='input')
        heights(ws, {r: 24, r + 1: 24})
        r += 1
    r += 2
    mput(ws, f'B{r}:M{r}', 'Источники: Cyberpunk RED Corebook (стр. 79, 129, 186–190, 223, 229, 408), '
                           'CEMK Rule Book (2070-е: стр. 26–30), гайд «Spes Desperata». Лист — домашний инструмент кампании.', kind='note')
    heights(ws, {r: 22})
    cf_warn(ws, 'I2', 'OR(LEFT($I$2,1)="С",LEFT($I$2,1)="М")')
    cf_warn(ws, 'D32', '$D$32<0')
    cf_warn(ws, 'I7:I16', '$I7="Активна"')
    return ws

# ============================================================== КАТАЛОГ ====
def build_catalog(wb, rows):
    ws = wb.create_sheet(NAMES['cat'])
    widths(ws, {'A': 38, 'B': 22, 'C': 26, 'D': 16, 'E': 10, 'F': 6, 'G': 7, 'H': 6,
                'I': 6, 'J': 10, 'K': 10, 'L': 10, 'M': 6, 'N': 12, 'O': 6, 'P': 10,
                'Q': 12, 'R': 12, 'S': 22, 'T': 80})
    sheet_setup(ws, MUTED, freeze='A3', landscape=True)
    mput(ws, 'A1:T1', f'КАТАЛОГ  ▚  {len(rows)} ПОЗИЦИЙ ИЗ DATA POOL (CYBERPUNK RED / CEMK / BLACK CHROME / INTERFACE RED)  ▚  '
                      'НЕ ПРАВЬ ЭТОТ ЛИСТ — НА НЕГО ССЫЛАЮТСЯ ФОРМУЛЫ ОСТАЛЬНЫХ', kind='banner')
    heights(ws, {1: 20})
    for idx, text in enumerate(CAT_HEAD, start=1):
        put(ws, f'{get_column_letter(idx)}2', text, kind='head')
    for i, row in enumerate(rows):
        r = CAT_FIRST_ROW + i
        for idx, value in enumerate(row, start=1):
            col = get_column_letter(idx)
            if idx == C_PRICE:
                put(ws, f'{col}{r}', value, kind='auto', fmt=CASH_FMT)
            elif idx in (C_SP, C_HP, C_PREF, C_PDEX, C_PMOVE, C_HL, C_ROF, C_MAG):
                put(ws, f'{col}{r}', value if value != '' else None, kind='cellc')
            else:
                put(ws, f'{col}{r}', value, kind='cell')
    ws.auto_filter.ref = f'A2:T{CAT_FIRST_ROW + len(rows) - 1}'
    return ws


# ============================================================== СПРАВКА ====
GENERAL_DV_RU = {
    'Simple': 'Плюнуть в урну, вспомнить вчерашний разговор, обычная бытовая задача.',
    'Everyday': 'Рутинная работа: дешёвый замок, слух на улице, починить провод.',
    'Difficult': 'Профессиональная задача: слежка, серьёзный ремонт, взлом двери.',
    'Professional': 'Работа специалиста: сложный ремонт, полевая хирургия, взлом системы.',
    'Heroic': 'На грани человеческого: выжить в падении, обыграть профи в его деле.',
    'Incredible': 'Легендарно: то, о чём будут рассказывать в барах.',
    'Legendary': 'Почти невозможно ни для кого.',
}
COVER = [
    ('Сталь', '25 HP', '50 HP', 'Дверь машины, грузовой контейнер (тонкий).'),
    ('Камень', '20 HP', '40 HP', 'Кирпичная кладка, бетонная тумба.'),
    ('Пуленепробиваемое стекло', '15 HP', '30 HP', 'Витрина банка, бронированное окно.'),
    ('Бетон', '10 HP', '25 HP', 'Уличный парапет, стена подъезда.'),
    ('Дерево', '5 HP', '20 HP', 'Перевёрнутый стол (тонкое), барная стойка (толстое).'),
    ('Гипс / пена / пластик', '0 HP (не укрытие)', '15 HP', 'Офисная перегородка.'),
]
ACTIONS = [
    ('Move Action', 'Переместиться на MOVE × 2 м (или на MOVE клеток).'),
    ('Attack', 'Ближняя или дальняя атака.'),
    ('Choke', 'Только против схваченного врага.'),
    ('Equip/Drop Shield', 'Взять или бросить щит — Действие.'),
    ('Get into a Vehicle', 'Сесть в транспорт.'),
    ('Get Up', 'Подняться из Prone. Пока не встанешь — не двигаешься.'),
    ('Grab', 'Схватить врага или предмет в его руках.'),
    ('Hold Action', 'Отложить действие: условие, номер инициативы, цель.'),
    ('Human Shield', 'Живой щит из схваченного врага (щит с HP = BODY).'),
    ('Reload', 'Перезарядить магазин одним типом патронов.'),
    ('Run', 'Дополнительное Move Action, если уже двигался в этом ходу.'),
    ('Start a Vehicle', 'Завести транспорт: его MOVE — твой, прыжок вверх по инициативе.'),
    ('Stabilize', 'Стабилизировать цель или вытащить из Mortally Wounded.'),
    ('Throw', 'Бросить врага в захвате или предмет.'),
    ('Use NET Actions', 'Сетевые действия (включая Quick Hacks).'),
    ('Use an Object', 'Использовать предмет без проверки навыка.'),
    ('Use a Skill', 'Быстрая проверка навыка (долгие задачи — несколько ходов).'),
    ('Vehicle Maneuver', 'Полная концентрация на сложном манёвре.'),
]
IP_SKILL = ['20', '40', '60', '80', '100', '120', '140', '160', '180', '200']
IP_SKILL_X2 = ['40', '80', '120', '160', '200', '240', '280', '320', '360', '400']
IP_ROLE = ['60', '120', '180', '240', '300', '360', '420', '480', '540', '600']


def build_reference(wb, data):
    ws = wb.create_sheet(NAMES['ref'])
    widths(ws, {'A': 2, 'B': 26, 'C': 16, 'D': 16, 'E': 16, 'F': 16, 'G': 16, 'H': 16,
                'I': 16, 'J': 16, 'K': 16, 'L': 16, 'M': 16, 'N': 40, 'O': 2})
    sheet_setup(ws, CYAN, landscape=True)
    mput(ws, 'B1:N1', 'СПРАВКА  ▚  DV · ДИСТАНЦИИ · УКРЫТИЯ · РАНЫ · IP · ЖИЗНЬ · 2070', kind='banner')
    heights(ws, {1: 20})

    r = 3
    mput(ws, f'B{r}:N{r}', 'Ⅰ · СЛОЖНОСТЬ ПРОВЕРОК (DV)  ·  CP:R СТР. 130', kind='h1')
    r += 1
    put(ws, f'B{r}', 'СЛОЖНОСТЬ', kind='head')
    put(ws, f'C{r}', 'DV', kind='head')
    mput(ws, f'D{r}:N{r}', 'КОГДА БРОСАТЬ', kind='head')
    for name, dv in RULES.GENERAL_DV:
        r += 1
        put(ws, f'B{r}', name, kind='cell')
        put(ws, f'C{r}', dv, kind='auto')
        mput(ws, f'D{r}:N{r}', GENERAL_DV_RU.get(name, ''), kind='cell')
        ws.row_dimensions[r].height = 18

    r += 2
    mput(ws, f'B{r}:N{r}', 'Ⅱ · ДИСТАНЦИЯ: DV ПО ТИПУ ОРУЖИЯ  ·  CP:R СТР. 172–173', kind='h1')
    r += 1
    for idx, head in enumerate(data['range_table'][0]):
        put(ws, f'{get_column_letter(2 + idx)}{r}', head, kind='head')
    for row in data['range_table'][1:]:
        r += 1
        for idx, value in enumerate(row):
            put(ws, f'{get_column_letter(2 + idx)}{r}',
                value if value not in ('N/A', '') else '—',
                kind='cellc' if idx else 'cell')
        ws.row_dimensions[r].height = 16

    r += 2
    mput(ws, f'B{r}:N{r}', 'Ⅲ · АВТООГОНЬ  ·  ДЕЙСТВИЕ + 10 ПАТРОНОВ + НАВЫК AUTOFIRE', kind='h1')
    r += 1
    for idx, head in enumerate(data['autofire_table'][0]):
        put(ws, f'{get_column_letter(2 + idx)}{r}', head, kind='head')
    put(ws, f'{get_column_letter(2 + len(data["autofire_table"][0]))}{r}', 'МАКС. МНОЖИТЕЛЬ', kind='head')
    mult = {'Machine Pistol': '×3', 'SMGs': '×3', 'Assault Rifle': '×4', 'Machine Gun': '×4'}
    for row in data['autofire_table'][1:]:
        r += 1
        for idx, value in enumerate(row):
            put(ws, f'{get_column_letter(2 + idx)}{r}', value, kind='cellc' if idx else 'cell')
        put(ws, f'{get_column_letter(2 + len(row))}{r}', mult.get(row[0], '×3'), kind='cellc')
    r += 1
    mput(ws, f'B{r}:N{r}', 'Урон = 2d6 × (насколько ты превысил DV), но не больше множителя оружия. Две «6» — ещё и крит-травма. '
                          'Броня гасит урон как обычно. Цели с REF 8+ могут уклоняться. Прицельный выстрел не совместим с автоогнём.',
         kind='note')
    ws.row_dimensions[r].height = 30

    r += 2
    mput(ws, f'B{r}:N{r}', 'Ⅳ · ПРИЦЕЛЬНЫЕ ВЫСТРЕЛЫ, УКРЫТИЯ, ПОДАВЛЕНИЕ', kind='h1')
    r += 1
    put(ws, f'B{r}', 'СИТУАЦИЯ', kind='head')
    put(ws, f'C{r}', 'МОДИФ.', kind='head')
    mput(ws, f'D{r}:N{r}', 'ЧТО ПРОИСХОДИТ', kind='head')
    for label, mod, text in [
        ('Прицельный выстрел (ROF 1, всё действие)', '−8', 'Только одна атака. Попадание — эффект по выбранной локации.'),
        ('…в голову', '×2 урона', 'Прошедший через броню урон умножается на 2 (при «треснувшем черепе» — на 3).'),
        ('…в предмет в руках', 'роняет', 'Если прошёл хотя бы 1 урон — цель роняет выбранный предмет.'),
        ('…в ногу', 'Broken Leg', 'Если прошёл хотя бы 1 урон — крит-травма «Broken Leg» (если есть целые ноги).'),
        ('Огонь на подавление', 'WILL+Concentration', 'Действие + 10 пуль. Провал — цель обязана уйти за укрытие (иначе Run).'),
        ('Картечь (Shells)', 'DV13', 'Один выстрел: все цели ВПЕРЕДИ в радиусе 6 м (3 клетки), которых видишь, получают 3d6 (урон бросается один раз).'),
        ('Взрывчатка', '10×10 м', 'Один бросок урона на всех в квадрате. Волна не бьёт за укрытием, если оно выдержало.'),
    ]:
        r += 1
        put(ws, f'B{r}', label, kind='cell')
        put(ws, f'C{r}', mod, kind='cellc')
        mput(ws, f'D{r}:N{r}', text, kind='cell')
        ws.row_dimensions[r].height = 18
    r += 1
    put(ws, f'B{r}', 'МАТЕРИАЛ УКРЫТИЯ', kind='head')
    put(ws, f'C{r}', 'ТОНКОЕ', kind='head')
    put(ws, f'D{r}', 'ТОЛСТОЕ', kind='head')
    mput(ws, f'E{r}:N{r}', 'ПРИМЕРЫ / КАК ЧИТАТЬ', kind='head')
    for material, thin, thick, example in COVER:
        r += 1
        put(ws, f'B{r}', material, kind='cell')
        put(ws, f'C{r}', thin, kind='cellc')
        put(ws, f'D{r}', thick, kind='cellc')
        mput(ws, f'E{r}:N{r}', example, kind='cell')
        ws.row_dimensions[r].height = 18
    r += 1
    mput(ws, f'B{r}:N{r}', 'УКРЫТИЕ НЕ ДАЁТ ШТРАФА К АТАКЕ (ни в Corebook, ни в CEMK): правило бинарное — «ты в укрытии, только если полностью '
                          'за тем, что может остановить пулю; если враг тебя видит, ты не в укрытии». Попадание уходит в укрытие: участок 2×2 м, '
                          'у него есть HP (см. таблицу выше). Разрушенное укрытие обрушивается, избыточный урон за ним не идёт (кроме взрывчатки). '
                          'ЩИТ — подвижное укрытие: пока у него есть HP, ты в укрытии, и весь урон атаки идёт в HP щита; но уклоняться с ним нельзя. '
                          'Живой щит не защищает от выстрелов в голову и ближнего боя.',
         kind='note')
    ws.row_dimensions[r].height = 46

    r += 2
    mput(ws, f'B{r}:N{r}', 'Ⅴ · ДЕЙСТВИЯ В ХОДЕ  ·  1 MOVE ACTION + 1 ДЕЙСТВИЕ', kind='h1')
    r += 1
    put(ws, f'B{r}', 'ДЕЙСТВИЕ', kind='head')
    mput(ws, f'C{r}:N{r}', 'ЧТО ДЕЛАЕТ', kind='head')
    for name, text in ACTIONS:
        r += 1
        put(ws, f'B{r}', name, kind='cell')
        mput(ws, f'C{r}:N{r}', text, kind='cell')
        ws.row_dimensions[r].height = 16

    r += 2
    mput(ws, f'B{r}:N{r}', 'Ⅵ · РАНЫ, СМЕРТЬ, СТАБИЛИЗАЦИЯ', kind='h1')
    r += 1
    put(ws, f'B{r}', 'СОСТОЯНИЕ', kind='head')
    put(ws, f'C{r}', 'ПОРОГ', kind='head')
    mput(ws, f'D{r}:N{r}', 'ЭФФЕКТ И СТАБИЛИЗАЦИЯ', kind='head')
    for name, threshold, effect, stab in RULES.WOUND_STATES:
        r += 1
        put(ws, f'B{r}', name, kind='cell')
        put(ws, f'C{r}', threshold, kind='cellc')
        mput(ws, f'D{r}:N{r}', f'{effect}  ·  {stab}', kind='cell')
        ws.row_dimensions[r].height = 30
    r += 1
    mput(ws, f'B{r}:N{r}', 'Смертельный спасбросок: 1d10 ≤ BODY − штраф. Выпало «10» — провал. Провал = смерть. '
                          'Крит-травма: два и более «6» на кубах урона → +5 урона напрямую в HP и эффект травмы (таблицы на листе 06).',
         kind='note')
    ws.row_dimensions[r].height = 30

    r += 2
    mput(ws, f'B{r}:N{r}', 'Ⅶ · IP: СКОЛЬКО СТОИТ РАЗВИТИЕ  ·  CP:R СТР. 408–410', kind='h1')
    r += 1
    put(ws, f'B{r}', 'ЧТО УЛУЧШАЕМ', kind='head')
    for i in range(10):
        put(ws, f'{get_column_letter(3 + i)}{r}', f'{i + 1}', kind='head')
    for label, values in (('НАВЫК (20 × уровень)', IP_SKILL),
                          ('НАВЫК ×2 (40 × уровень)', IP_SKILL_X2),
                          ('РОЛЕВАЯ СПОСОБНОСТЬ (60 × ранг)', IP_ROLE)):
        r += 1
        put(ws, f'B{r}', label, kind='cell')
        for i, value in enumerate(values):
            put(ws, f'{get_column_letter(3 + i)}{r}', int(value), kind='auto')
    r += 1
    mput(ws, f'B{r}:N{r}', 'Столбцы — НОВЫЙ уровень/ранг. Перескакивать уровни нельзя, даже если IP хватает: сначала надо отыграть на текущем. '
                          'Улучшения записывай на листе 06 — стоимость посчитается сама.', kind='note')
    ws.row_dimensions[r].height = 30
    r += 1
    mput(ws, f'B{r}:N{r}', 'ОПЫТ: 10 IP — «старались, но не вышло» / боевые навыки/поддержка/исследование/отыгрыш; 20 IP — дело выполнено еле-еле; '
                          '30–50 IP — уверенный успех, важные цели, выдающийся отыгрыш. GM выдаёт по стилю игры каждого.', kind='note')
    ws.row_dimensions[r].height = 30

    r += 2
    mput(ws, f'B{r}:N{r}', 'Ⅷ · ЖИЗНЬ, ЖИЛЬЁ, МЕДИЦИНА: ПОЧЁМ В 2070-Х', kind='h1')
    r += 1
    put(ws, f'B{r}', 'СТАТЬЯ', kind='head')
    put(ws, f'C{r}', 'ЦЕНА €$', kind='head')
    mput(ws, f'D{r}:N{r}', 'ПОЯСНЕНИЕ', kind='head')
    for label, price, note in [
        ('Lifestyle: Kibble', '100 / мес', 'Еда-пайка. Стартовый Lifestyle у всех покрыт.'),
        ('Lifestyle: Generic Prepak', '300 / мес', 'Нормальная еда, вечер в хорошем баре.'),
        ('Lifestyle: Good Prepak', '600 / мес', 'Еда как в ресторане, концерты раз в месяц.'),
        ('Lifestyle: Fresh Food', '1 500 / мес', 'Настоящая еда, отель без счёта, executive-бар.'),
        ('Жильё: Cube Hotel', '500 / мес', 'Капсула. Ежемесячный срез Humanity по CEMK.'),
        ('Жильё: Cargo Container', '1 000 / мес', 'Стартовое жильё (первый месяц бесплатно).'),
        ('Жильё: Studio Apartment', '1 500 / мес', 'Обычная квартира — как у команды в мегабашне VEX (Rent).'),
        ('Trauma Team Silver', '500 / мес', 'Подписка: привозят в больницу и стабилизируют. Хирургия — за свой счёт.'),
        ('Trauma Team Executive', '1 000 / мес', 'Хирургия входит в подписку; переводится на одного друга (1 к 1).'),
        ('Hospital Treatment DV10/13/15/17+', '50 / 100 / 500 / 1 000', 'Больничная помощь по сложности ранения.'),
        ('Терапия: Standard HL', '500 + 100 материалов', 'Неделя, Medical Tech DV15, возврат 2d6 Humanity.'),
        ('Терапия: Extreme HL', '1 000 + 500 материалов', 'Неделя, DV17, возврат 4d6 Humanity.'),
        ('Терапия: Addiction', '1 000 + 500 материалов', 'Неделя, DV15, снимает одну зависимость.'),
        ('Biosculpting', '500 / 1 000', 'Смена внешности: стандарт / экзотика.'),
        ('Установка найденного хрома', '100 / 500 / 1 000', 'Молл / клиника / больница.'),
        ('Продать лут (Streetwise)', '×½ цены', 'Скупка за половину; редкое — через Fixer.'),
    ]:
        r += 1
        put(ws, f'B{r}', label, kind='cell')
        put(ws, f'C{r}', price, kind='cellc')
        mput(ws, f'D{r}:N{r}', note, kind='cell')
        ws.row_dimensions[r].height = 16

    r += 2
    mput(ws, f'B{r}:N{r}', 'Ⅸ · 2070-Е: ЧТО РАБОТАЕТ ИНАЧЕ (CEMK «THE 2070s IN CYBERPUNK RED»)', kind='h1')
    r += 1
    for text in [
        '1. NEUROPORT: при создании можно поставить бесплатно — 0 €$, 0 HL, максимум Humanity не режется. Любой немедицинский хром требует Neuroport.',
        '2. РОЛИ В 2070-Х: Fixer достаёт дорогие вещи поштучно с ранга 1 (на ранге 4 — Very Expensive, 7 — Luxury, 9 — Super Luxury). Exec/Media/Rockerboy/Lawman — с ранга 4. Nomad — любые транспорт и апгрейды с ранга 1 (Moto).',
        '3. НЕТРАННЕРЫ: Quickhack по хрому — Simple (DV6) с ранга 1, Standard (DV8) — 2, Difficult (DV10) — 3, Advanced (DV12) — 4. Scanner стал NET-действием, а на ранге 3 Interface нейропорты вскрываются без проверки.',
        '4. ДОСТУПНОСТЬ: почти всё можно купить напрямую у производителя, но по двойной цене (кроме уникального/кастомного).',
        '5. МЕНТАЛЬНАЯ ТРАВМА: Humanity меняется не только от хрома — события и месяцы жизни режут или возвращают её (см. лист 04).',
    ]:
        r += 1
        mput(ws, f'B{r}:N{r}', text, kind='cell')
        ws.row_dimensions[r].height = 30

    r += 2
    mput(ws, f'B{r}:N{r}', 'Ⅹ · LAWMAN · BACKUP: ВЫЗОВ ПОДКРЕПЛЕНИЯ  ·  CP:R СТР. 158–159', kind='h1')
    r += 1
    for idx, head in enumerate(['РАНГ BACKUP', 'БОЕВОЙ №', 'SP', 'HP', 'MOVE / BODY', 'КТО ПРИЕДЕТ']):
        put(ws, f'{get_column_letter(2 + idx)}{r}', head, kind='head')
    for rank, cn, sp, hp, mb, who in [
        ('1–2', '8', '7', '20', '4 / 4', 'Корпоративная охрана: 4 прокат-копа, пешком. Heavy Pistols, Kevlar.'),
        ('3–4', '10', '7', '25', '5 / 5', 'Патрульные: 4 копа на двух Compact Groundcar. Heavy Pistols, Kevlar.'),
        ('5–7', '14', '13', '35', '4 / 4', 'Департамент шерифа: 2 «маунти» на High Performance Groundcar. Heavy Pistols + Assault Rifles, Heavy Armorjack.'),
        ('8', '16', '15', '50', '6 / 6', 'Маршал зоны восстановления: один, на Superbike. Very Heavy Pistol, Assault Rifle, Grenade Launcher, Flak.'),
        ('9', '15', '18', '35', '4 / 4', 'C-SWAT: 2 бойца Psycho Squad с AV-4. Assault Rifles + Rocket Launchers, Metalgear.'),
        ('10', '14', '11', '35', '6 / 6', 'Национальные силы / Интерпол / Netwatch: 2 агента с AV-4. Very Heavy Pistols + Assault Rifles, Light Armorjack.'),
    ]:
        r += 1
        for idx, value in enumerate([rank, cn, sp, hp, mb]):
            put(ws, f'{get_column_letter(2 + idx)}{r}', value, kind='cellc' if idx else 'cell')
        mput(ws, f'G{r}:N{r}', who, kind='cell')
        ws.row_dimensions[r].height = 26
    r += 2
    for text in [
        'ВЫЗОВ: Действие → бросок 1d10, успех при результате ≤ ранга Backup. Дальше 1d6 — через сколько раундов подкрепление на месте. Выпало «6» — приезжает тир на уровень выше (на 10-м ранге — сразу две группы). Никто не ответил — пробуй в следующем ходу.',
        'ЗЛОУПОТРЕБЛЕНИЕ: если звать Backup по каждому чиху, начальство штрафует или разжаловает (решает GM). Отставной коп зовёт только тех, с кем сохранил отношения, — это и есть цена ухода со службы.',
        'В БОЮ: Backup атакует и защищается боевым номером (стат + навык) и НЕ уклоняется от пуль. Их ходы ведёт GM; они приезжают на своей технике.',
        'РАНГ 10, ОСОБОЕ: 2 агента остаются до закрытия дела и могут считать по боевому номеру навыки Criminology, Deduction, Interrogation, Paramedic, Perception, Stealth, Tracking и другие «следственные».',
        'ОБЯЗАТЕЛЬНЫЕ НАВЫКИ LAWMAN (минимум 2 каждому): Autofire (×2 — 2 очка за уровень), Criminology, Deduction, Handgun, Interrogation, Shoulder Arms, Tracking.',
        'ЛАЙФПАТ LAWMAN (1d6 по каждому): должность в подразделении, юрисдикция, коррумпированность подразделения, кто охотится на подразделение, главная цель подразделения. Запись — на листе 01 ДОСЬЕ, блок Ⅱ.',
    ]:
        r += 1
        mput(ws, f'B{r}:N{r}', '▪ ' + text, kind='cell')
        ws.row_dimensions[r].height = 34

    r += 2
    mput(ws, f'B{r}:N{r}', 'Ⅺ · СНАРЯЖЕНИЕ И БОЙ: ЧАСТЫЕ ВОПРОСЫ', kind='h1')
    r += 1
    for q, a in [
        ('Можно ли надеть броню на голову и тело отдельно?', 'Да. SP головы и SP тела считаются отдельно, лучший SP в локации работает, второй слой не складывается.'),
        ('Что делать, если урон меньше SP?', 'Урон не проходит, и броня НЕ аблейтится: правило абляции работает только когда урон прошёл (CP:R стр. 186).'),
        ('Как складываются штрафы брони?', 'Берётся только самый строгий штраф — он применяется один раз ко всем REF, DEX и MOVE.'),
        ('Крит-травма «не проходит» через SP?', 'Нет. Крит-травма наносит +5 урона напрямую в HP и не гасится броней, даже если SP остановил весь обычный урон.'),
        ('Сколько крит-травм может быть у персонажа?', 'Сколько угодно, но повторные травмы того же вида перебрасываются. Лечение — Quick Fix (эффект) или полноценное лечение (DV по таблице на листе 06).'),
        ('Как лечится серьёзное ранение?', 'Естественно — 1 HP в день отдыха при стабилизации; Stim снимает штраф на час, Speedheal лечит BODY+WILL HP. Оба — не чаще раза в день.'),
    ]:
        r += 1
        put(ws, f'B{r}', q, kind='cell')
        mput(ws, f'C{r}:N{r}', a, kind='cell')
        ws.row_dimensions[r].height = 26

    # Ⅻ · таблицы крит-травм для стола (на них ссылается трекер листа 06)
    global CRIT_BODY_FIRST, CRIT_HEAD_FIRST
    r += 2
    mput(ws, f'B{r}:N{r}', 'Ⅻ · КРИТИЧЕСКИЕ ТРАВМЫ  ·  2D6  ·  CP:R СТР. 187–188', kind='h1')
    r += 1
    CRIT_BODY_FIRST = r + 1
    put(ws, f'B{r}', '2D6', kind='head')
    put(ws, f'C{r}', 'ТРАВМА ТЕЛА', kind='head')
    mput(ws, f'D{r}:H{r}', 'ЭФФЕКТ', kind='head')
    mput(ws, f'I{r}:K{r}', 'БЫСТРЫЙ ФИКС', kind='head')
    mput(ws, f'L{r}:N{r}', 'ЛЕЧЕНИЕ', kind='head')
    for idx, row in enumerate(RULES.CRIT_BODY):
        rr = CRIT_BODY_FIRST + idx
        put(ws, f'B{rr}', row[0], kind='cellc')
        put(ws, f'C{rr}', row[1], kind='cell')
        mput(ws, f'D{rr}:H{rr}', row[2], kind='cell')
        mput(ws, f'I{rr}:K{rr}', row[3], kind='cellc')
        mput(ws, f'L{rr}:N{rr}', row[4], kind='cellc')
        ws.row_dimensions[rr].height = 30
    r = CRIT_BODY_FIRST + len(RULES.CRIT_BODY)
    mput(ws, f'B{r}:N{r}', 'Крит-травма даёт +5 урона напрямую в HP (SP не гасит). Без прицельного выстрела в голову — таблица тела. '
                           'Повторную травму того же вида перебрасывай. Quick Fix лечит эффект, но не саму травму.', kind='note')
    ws.row_dimensions[r].height = 26

    r += 2
    mput(ws, f'B{r}:N{r}', 'ⅩⅢ · КРИТИЧЕСКИЕ ТРАВМЫ ГОЛОВЫ  ·  ТОЛЬКО ПРИЦЕЛЬНЫЙ ВЫСТРЕЛ (−8, УРОН ×2)', kind='h1')
    r += 1
    CRIT_HEAD_FIRST = r + 1
    put(ws, f'B{r}', '2D6', kind='head')
    put(ws, f'C{r}', 'ТРАВМА ГОЛОВЫ', kind='head')
    mput(ws, f'D{r}:H{r}', 'ЭФФЕКТ', kind='head')
    mput(ws, f'I{r}:K{r}', 'БЫСТРЫЙ ФИКС', kind='head')
    mput(ws, f'L{r}:N{r}', 'ЛЕЧЕНИЕ', kind='head')
    for idx, row in enumerate(RULES.CRIT_HEAD):
        rr = CRIT_HEAD_FIRST + idx
        put(ws, f'B{rr}', row[0], kind='cellc')
        put(ws, f'C{rr}', row[1], kind='cell')
        mput(ws, f'D{rr}:H{rr}', row[2], kind='cell')
        mput(ws, f'I{rr}:K{rr}', row[3], kind='cellc')
        mput(ws, f'L{rr}:N{rr}', row[4], kind='cellc')
        ws.row_dimensions[rr].height = 30
    r = CRIT_HEAD_FIRST + len(RULES.CRIT_HEAD)
    mput(ws, f'B{r}:N{r}', 'В голову попадают только прицельным выстрелом (−8 к атаке). Урон ×2 (при треснувшем черепе ×3). '
                           'Трекер травм персонажа — на листе 06.', kind='note')
    ws.row_dimensions[r].height = 26
    return ws


# ================================================================ ПРАВИЛА ===
def build_rules(wb):
    """ПРАВИЛА — короткая инструкция: цвета, шаги создания, Lawman в 2070-х, где что лежит."""
    ws = wb.create_sheet(NAMES['rul'])
    widths(ws, {'A': 2, 'B': 30, 'C': 130, 'D': 2})
    sheet_setup(ws, BAND, landscape=True)
    mput(ws, 'B1:C1', 'КАК ПОЛЬЗОВАТЬСЯ ЭТИМ ЛИСТОМ  ▚  NC//NET · НАЙТ-СИТИ 2070  ▚  HUD-ОФОРМЛЕНИЕ', kind='banner')
    heights(ws, {1: 32})
    r = 3
    blocks = [
        ('Ⅰ · ЦВЕТА И ЛОГИКА', [
            ('Янтарные поля', 'Сюда пишешь ты: имена, отыгрыш, уровни навыков, оружие, патроны, даты.'),
            ('Тёмные поля', 'Считается само. Можно перебить своим значением — формула заменится цифрой.'),
            ('Красный и «⚠»', 'Проверки и опасность: перерасход бюджета, лишние очки, киберпсихоз, превышение ранга роли.'),
            ('Шрифты', 'Заголовки — Oswald, текст — Roboto, цифры и метки — Roboto Mono. Все три есть в Google Таблицах; '
                       'в Excel без них подставится системный шрифт.'),
            ('Альбомная ориентация', 'Все листы свёрстаны под альбом и печать по ширине страницы (Файл → Печать → '
                                     '«Вписать по ширине»).'),
        ]),
        ('Ⅱ · ГДЕ ЧТО ЛЕЖИТ', [
            ('01 ДОСЬЕ', 'Кто персонаж: личность, служба, прошлое, связи и служебная сводка с игровых листов. Две колонки, '
                         'фото — в правом верхнем углу. Это то, что читает GM.'),
            ('02 ОСНОВА', 'Характеристики (62 очка), производные (HP, Humanity, инициатива, MOVE), Backup (Lawman), '
                           'оружие в руках, броня и памятка бойца.'),
            ('03 НАВЫКИ', '66 навыков + 6 свободных строк. Пишешь только уровень; база (уровень + стата со штрафом брони) '
                          'считается сама. Справа — панель проверок: 86 очков, максимум 6, 13 обязательных и пакет Lawman.'),
            ('04 ХРОМ', 'Импланты: HL по среднему, срез максимума Humanity, клиника, слоты. Ниже — Humanity, терапия и '
                        'таблица «что режет Humanity» (хром, события, жизнь).'),
            ('05 СНАРЯЖЕНИЕ', 'Бюджеты 2550 €$ и 800 €$ на стиль, оружие, броня, инвентарь и касса кампании. Броня и хром '
                              'считаются каждый в своём блоке — в инвентарь их дублировать не надо.'),
            ('06 СОСТОЯНИЕ', 'Трекер крит-травм (выбери локацию и 2d6 — травма подтянется из СПРАВКИ), зависимости, '
                             'IP и лог дел.'),
            ('КАТАЛОГ / СПРАВКА / ПРАВИЛА', 'Каталог 1092 позиций из Data Pool, справочник DV/укрытий/крит-травм/IP и эта '
                                             'инструкция. Служебные листы не правь — на них ссылаются формулы.'),
        ]),
        ('Ⅲ · ШАГИ СОЗДАНИЯ ПЕРСОНАЖА (ГАЙД SPES DESPERATA)', [
            ('1. Роль', 'Lawman (коп в отставке) — ролевая способность Backup. На старте ранг роли 4. Обязательный пакет '
                        'роли — 7 навыков минимум по 2 (лист 03, панель справа).'),
            ('2. Lifepath', 'Общий (CP:R стр. 45) + ролевой: Lawman — стр. 36 (должность, юрисдикция, коррумпированность, '
                            'враг, цель). Результаты — на лист 01 ДОСЬЕ.'),
            ('3. Характеристики', '62 очка на 10 стат, каждая от 2 до 8. Рабочий приём: по 6 везде, потом 2 лишних по вкусу.'),
            ('4. Производные', 'HP = 10 + 5 × ⌈(BODY+WILL)/2⌉, порог серьёзного ранения — половина HP вверх, спасбросок = BODY, '
                               'Humanity = EMP × 10. Всё считается на листе 02.'),
            ('5. Навыки', '86 очков: 26 в 13 обязательных (по 2) + 60 свободных, максимум 6. Родной язык — 4 уровня бесплатно. '
                          'Навыки с ×2 стоят 2 очка за уровень.'),
            ('6. Закупка', '2550 €$ на оружие, броню, снаряжение и хром + 800 €$ на Fashion и Fashionware. Neuroport при '
                           'создании бесплатен (0 €$, 0 HL). Остаток бюджета снаряжения забираешь наличными, остаток модного '
                           'бюджета сгорает (CP:R стр. 104).'),
            ('7. Lifestyle', 'Жильё 1 000 €$ + Kibble Lifestyle 100 €$/мес = 1 100 €$ к 1-му числу, первый месяц покрыт '
                             '(CP:R стр. 105, 377). Дальше платишь сам — см. СПРАВКУ.'),
        ]),
        ('Ⅳ · LAWMAN В 2070-Х: КОП ВНЕ СИСТЕМЫ', [
            ('Backup — твой козырь', 'Ранг роли = шанс дозвониться. Действие, 1d10 ≤ ранга, приезд через 1d6 раундов; «6» на d6 — '
                                     'тир выше. Таблица тиров — на листах 02 и СПРАВКА.'),
            ('Цена отставки', 'Отставной коп зовёт только тех, с кем сохранил отношения, и только когда действительно надо: '
                              'частые вызовы = штраф или разжалование. Взамен — свобода работать вне приказов и доступ к старым базам данных.'),
            ('Навыки копа', 'Criminology, Deduction, Interrogation, Tracking — расследование; Autofire (×2), Handgun, Shoulder Arms — '
                            'стволы; плюс социальные (Conversation, Human Perception, Persuasion, Bribery), чтобы говорить с улицей и управлением.'),
            ('Роль в команде', 'Ты — тот, кто читает место преступления, держит допрос и приводит подкрепление, когда всё пошло не так. '
                               'Броня и ствол у тебя как у «стены», но решать дело ты можешь и языком.'),
        ]),
        ('Ⅴ · ЕСЛИ ЧТО-ТО СЛОМАЛОСЬ', [
            ('Вещь не из каталога', 'Впиши название вручную, а цену — в столбец «ЦЕНА СВОЯ»: сумма и бюджет посчитаются по ней.'),
            ('Добавляешь строки', 'Вставляй строки ВНУТРИ таблиц (не вместо заголовков) — формулы и суммы подтянутся.'),
            ('Не переименовывай листы', 'Формулы ссылаются на «02 ОСНОВА», «04 ХРОМ» и остальные листы по именам.'),
            ('Хочешь больше автоподстановки', 'Расширь КАТАЛОГ: добавь строку с тем же порядком столбцов — подстановка заработает.'),
        ]),
        ('Ⅵ · ИСТОЧНИКИ', [
            ('Cyberpunk RED Corebook', 'Создание персонажа (стр. 73–89), навыки (стр. 86–90), броня и оружие (стр. 340–351), '
                                       'бой (стр. 170–190), терапия (стр. 229), крит-травмы (стр. 187–188), IP (стр. 408), Lifestyle (стр. 377).'),
            ('Cyberpunk: Edgerunners Mission Kit', 'Правила 2070-х: Neuroport (стр. 26, 35), твики ролей, расширенная доступность, '
                                                   'ментальная травма (стр. 28–30).'),
            ('Гайд «Spes Desperata»', 'Порядок создания, 62/86, must-have навыки по ролям, закупка, Lifestyle — используется в кампании.'),
            ('Дисклеймер', 'Это домашний лист для вашей кампании. Если у стола свои дом-правила — правь смело: формулы простые, '
                           'все правила лежат рядом.'),
        ]),
    ]
    for title, rows in blocks:
        r += 1
        mput(ws, f'B{r}:C{r}', title, kind='h1')
        for label, text in rows:
            r += 1
            put(ws, f'B{r}', label, kind='kv_label')
            put(ws, f'C{r}', text, kind='text')
            ws.row_dimensions[r].height = max(28, 15 * (len(text) // 100 + 1))
        r += 1
    return ws

# ================================================================= MAIN ====
def make_photo_placeholder(path, width=640, height=380):
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (width, height), (10, 10, 12))
    draw = ImageDraw.Draw(img)
    for x in range(0, width, 18):
        draw.line([(x, 0), (x + height, height)], fill=(26, 26, 32), width=5)
    draw.rectangle([6, 6, width - 7, height - 7], outline=(255, 0, 60), width=4)
    draw.text((26, 26), 'NCPD  ·  FILE PHOTO', fill=(255, 177, 0))
    draw.text((26, height - 62), 'ФОТО ОБЪЕКТА', fill=(255, 255, 255))
    draw.text((26, height - 40), 'вставь сюда портрет своего персонажа', fill=(166, 171, 178))
    draw.line([(26, height - 74), (width - 26, height - 74)], fill=(255, 0, 60), width=2)
    img.save(path)
    return path


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'NC-NET_CharSheet_2070.xlsx')
    with open(os.path.join(ROOT, 'app', 'data', 'items.json'), encoding='utf-8') as fh:
        data = json.load(fh)
    rows = catalog_rows(data)
    global CAT_LAST
    CAT_LAST = CAT_FIRST_ROW + len(rows) - 1
    set_ranges()

    wb = Workbook()
    wb.remove(wb.active)
    use_theme('hud')           # единое оформление: HUD Night City (чёрный / красный / янтарный)
    global CRIT_BODY_FIRST, CRIT_HEAD_FIRST
    build_catalog(wb, rows)
    build_reference(wb, data)  # считает адреса таблиц крит-травм, на них ссылается лист 06
    build_dossier(wb)
    build_base(wb)
    build_skills(wb)
    build_chrome(wb)
    build_gear(wb)
    build_state(wb)
    build_rules(wb)
    # вкладки — в игровом порядке: досье, механика, служебные листы
    order = [NAMES['doc'], NAMES['base'], NAMES['skl'], NAMES['chr'], NAMES['gear'],
             NAMES['sta'], NAMES['cat'], NAMES['ref'], NAMES['rul']]
    wb._sheets = [wb[name] for name in order]

    ws = wb[NAMES['doc']]
    tmpdir = tempfile.mkdtemp(prefix='ncnet-sheet-')
    try:
        from openpyxl.drawing.image import Image as XLImage
        photo = make_photo_placeholder(os.path.join(tmpdir, 'photo.png'))
        img = XLImage(photo)
        img.width, img.height = 460, 250
        ws.add_image(img, 'F4')
    except Exception as exc:  # noqa: BLE001
        print('фото-заглушка не добавлена:', exc)

    wb.save(out)
    shutil.rmtree(tmpdir, ignore_errors=True)
    print(f'готово: {out} ({os.path.getsize(out) / 1024:.0f} КБ) · листов: {len(wb.sheetnames)} · позиций каталога: {len(rows)}')


if __name__ == '__main__':
    main()

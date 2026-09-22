#!/usr/bin/env python3
"""Build Street-File.xlsx — ledger, contacts, role tabs, play-screen REF."""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chartsheet import Chartsheet  # noqa: F401
from openpyxl.drawing.image import Image as XLImage
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import (
    Alignment, Border, Font, PatternFill, Protection, Side,
)
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.page import PageMargins
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.comments import Comment
from openpyxl.workbook.properties import CalcProperties

ROOT = Path(__file__).resolve().parent
PRINT = ROOT / "assets" / "print"

# palette
INK = "1A1A1A"
GOLD = "C4A35A"
CRIMSON = "9B1B2E"
PAPER = "F7F1E6"
CREAM = "FFF8EC"
SLATE = "2C3338"
ROW_ALT = "F3EDE0"
WHITE = "FFFFFF"

thin = Border(
    left=Side(style="thin", color="B9A989"),
    right=Side(style="thin", color="B9A989"),
    top=Side(style="thin", color="B9A989"),
    bottom=Side(style="thin", color="B9A989"),
)
thick_bottom = Border(bottom=Side(style="medium", color=INK))

font_title = Font(name="Calibri", size=18, bold=True, color=GOLD)
font_h = Font(name="Calibri", size=11, bold=True, color=WHITE)
font_label = Font(name="Calibri", size=9, bold=True, color=INK)
font_cell = Font(name="Calibri", size=10, color=INK)
font_small = Font(name="Calibri", size=8, italic=True, color="5C5346")
font_gold = Font(name="Calibri", size=10, bold=True, color=GOLD)

fill_ink = PatternFill("solid", fgColor=INK)
fill_red = PatternFill("solid", fgColor=CRIMSON)
fill_gold = PatternFill("solid", fgColor=GOLD)
fill_paper = PatternFill("solid", fgColor=PAPER)
fill_cream = PatternFill("solid", fgColor=CREAM)
fill_white = PatternFill("solid", fgColor=WHITE)
fill_slate = PatternFill("solid", fgColor=SLATE)

center = Alignment(horizontal="center", vertical="center", wrap_text=True)
left = Alignment(horizontal="left", vertical="center", wrap_text=True)
top_left = Alignment(horizontal="left", vertical="top", wrap_text=True)


def _page(ws, landscape=False, fit=True):
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.orientation = "landscape" if landscape else "portrait"
    ws.page_setup.fitToPage = fit
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.page_setup.horizontalCentered = True
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins = PageMargins(left=0.4, right=0.4, top=0.5, bottom=0.5, header=0.2, footer=0.2)
    ws.sheet_view.showGridLines = False
    ws.sheet_view.view = "pageLayout"
    ws.print_options.horizontalCentered = True
    ws.oddFooter.left.text = "NC//NET STREET FILE  ·  unofficial table aid"
    ws.oddFooter.right.text = "&A  ·  &P/&N"


def _header_row(ws, row, headers, fill=fill_ink, font=font_h):
    for i, h in enumerate(headers, 1):
        cell = ws.cell(row, i, h)
        cell.font = font
        cell.fill = fill
        cell.alignment = center
        cell.border = thin


def _input(cell, value=""):
    cell.value = value
    cell.font = font_cell
    cell.fill = fill_white
    cell.border = thin
    cell.alignment = left
    return cell


def _label(cell, text):
    cell.value = text
    cell.font = font_label
    cell.fill = fill_paper
    cell.alignment = left
    return cell


def _banner(ws, text, cols, fill=fill_ink):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=cols)
    c = ws.cell(1, 1, text)
    c.font = font_title
    c.fill = fill
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 28
    for i in range(1, cols + 1):
        ws.cell(1, i).fill = fill


def _note(ws, row, cols, text):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=cols)
    c = ws.cell(row, 1, text)
    c.font = font_small
    c.alignment = left
    return c


def _widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _dv(ws, formula, sqref, name):
    dv = DataValidation(type="list", formula1=formula, allow_blank=True)
    dv.error = "Pick from the list"
    dv.errorTitle = name
    dv.prompt = name
    dv.showErrorMessage = False
    dv.showInputMessage = False
    ws.add_data_validation(dv)
    dv.add(sqref)
    return dv


def sheet_meta(wb):
    ws = wb.active
    ws.title = "META"
    _page(ws, landscape=False)
    _banner(ws, "  STREET FILE   ·   META", 8)
    _widths(ws, [22, 22, 18, 16, 16, 16, 18, 22])

    # identity
    rows = [
        (3, "Handle", "B3", "Case No.", "D3"),
        (4, "Real Name", "B4", "Player", "D4"),
        (5, "Role / Rank", "B5", "Role 2 / Rank 2", "D5"),
        (6, "Crew", "B6", "In-world date", "D6"),
        (7, "Era (2045 / 2070)", "B7", "House rules", "D7"),
    ]
    for r, l1, _, l2, _ in rows:
        _label(ws.cell(r, 1), l1)
        _input(ws.cell(r, 2))
        _label(ws.cell(r, 3), l2)
        _input(ws.cell(r, 4))
        ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=6)
        ws.row_dimensions[r].height = 18

    ws["B7"] = "2070"
    ws["D7"] = "Point buy 62/86 · HUM −2/non-fashion chrome · −4 Borgware (campaign)"
    ws["B3"].comment = Comment("Must match Handle on Street-File.pdf", "NC//NET")

    # running totals — truth for money/IP/heat lives HERE
    ws.merge_cells("A9:F9")
    h = ws["A9"]
    h.value = "RUNNING TOTALS  ·  source of truth (copy Cash / IP / Heat onto PDF page 2 after each session)"
    h.font = font_h
    h.fill = fill_red
    h.alignment = left
    for col in range(1, 7):
        ws.cell(9, col).fill = fill_red

    labels = [
        (10, "Starting Cash (eb)", "B10"),
        (11, "Cash now (eb)", "B11"),
        (12, "IP current", "B12"),
        (13, "IP earned (all-time)", "B13"),
        (14, "IP spent", "B14"),
        (15, "Heat now", "B15"),
        (16, "Reputation (number)", "B16"),
    ]
    for r, lab, _ in labels:
        _label(ws.cell(r, 1), lab)
        _input(ws.cell(r, 2), 0 if r != 15 else "")
        ws.row_dimensions[r].height = 18

    ws["B10"] = 0
    # Cash now = starting + sum of ledger €$ (A1 refs: LibreOffice-friendly)
    ws["B11"] = "=B10+SUM(LEDGER!F4:F43)"
    ws["B11"].number_format = '#,##0'
    ws["B11"].font = Font(name="Calibri", size=12, bold=True, color=CRIMSON)
    ws["B12"] = "=B13-B14"
    ws["B13"] = "=SUM(LEDGER!G4:G43)"
    ws["B15"] = '=IFERROR(LOOKUP(2,1/(LEDGER!A4:A43<>""),LEDGER!H4:H43),"")'

    _label(ws.cell(10, 4), "Trauma Team / subs")
    _input(ws.cell(10, 5))
    ws.merge_cells("E10:F10")
    _label(ws.cell(11, 4), "Ripper / flatline contact")
    _input(ws.cell(11, 5))
    ws.merge_cells("E11:F11")
    _label(ws.cell(12, 4), "Agent #")
    _input(ws.cell(12, 5))
    ws.merge_cells("E12:F12")
    _label(ws.cell(13, 4), "ID / SIN")
    _input(ws.cell(13, 5))
    ws.merge_cells("E13:F13")

    _note(ws, 18, 8,
          "Sync rule: PDF is truth for stats, skills, chrome, dossier. This book is truth for €$, IP, heat, people, jobs. "
          "After a session: add a LEDGER row, then copy B11 / B12 / B15 onto PDF page 2.")
    _note(ws, 19, 8,
          "Photos: Insert → Pictures into the boxes on the right (booking + known photograph). Acrobat does the same on PDF page 0.")
    ws.row_dimensions[18].height = 32
    ws.row_dimensions[19].height = 20

    ws.merge_cells("A21:C21")
    ws["A21"] = "BOOKING PHOTO"
    ws["A21"].font = font_label
    ws.merge_cells("E21:G21")
    ws["E21"] = "KNOWN PHOTOGRAPH"
    ws["E21"].font = font_label
    ws.merge_cells("A22:C30")
    ws.merge_cells("E22:G30")
    for addr in ("A22", "E22"):
        ws[addr].fill = fill_cream
        ws[addr].border = Border(
            left=Side(style="medium", color=INK),
            right=Side(style="medium", color=INK),
            top=Side(style="medium", color=INK),
            bottom=Side(style="medium", color=INK),
        )
        ws[addr].alignment = center
        ws[addr].font = font_small
    ws["A22"] = "Insert booking photo"
    ws["E22"] = "Insert street / known photo"
    ws.row_dimensions[22].height = 22
    for r in range(23, 31):
        ws.row_dimensions[r].height = 18

    # logos
    ncpd = PRINT / "ncpd-seal.png"
    op = PRINT / "operator-mark.png"
    if ncpd.exists():
        img = XLImage(str(ncpd))
        img.width = 88
        img.height = 88
        ws.add_image(img, "H3")
    if op.exists():
        img = XLImage(str(op))
        img.width = 88
        img.height = 88
        ws.add_image(img, "H9")

    ws.freeze_panes = "A3"
    ws.sheet_properties.tabColor = CRIMSON
    return ws


def sheet_ledger(wb):
    ws = wb.create_sheet("LEDGER")
    _page(ws, landscape=True)
    _banner(ws, "  INCIDENT LOG   ·   OPERATOR LEDGER", 11, fill_red)
    _widths(ws, [14, 22, 16, 20, 14, 12, 8, 16, 10, 28, 14])
    headers = [
        "Date", "Job / incident", "Client", "Related persons",
        "Outcome", "eb", "IP", "Heat", "Therapy HL", "Notes", "Crew present",
    ]
    _header_row(ws, 3, headers, fill=fill_red)
    ws.auto_filter.ref = "A3:K43"
    ws.freeze_panes = "A4"
    outcomes = '"extracted,paid,burned,unfinished,KIA,fled,other"'
    _dv(ws, outcomes, "E4:E43", "Outcome")

    for r in range(4, 44):
        for c in range(1, 12):
            cell = ws.cell(r, c, None)
            cell.border = thin
            cell.font = font_cell
            cell.fill = fill_white if r % 2 == 0 else PatternFill("solid", fgColor="FBF6EC")
            cell.alignment = left
        ws.cell(r, 6).number_format = '#,##0'
        ws.cell(r, 7).number_format = '0'
        ws.row_dimensions[r].height = 18

    # Excel table so META SUMIF(LEDGER[eb]) works
    tab = Table(displayName="LEDGER", ref="A3:K43")
    tab.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    ws.add_table(tab)

    ws.merge_cells("A45:B45")
    _label(ws["A45"], "Session €$ (this sheet)")
    ws["C45"] = "=SUM(F4:F43)"
    ws["C45"].font = Font(name="Calibri", size=12, bold=True, color=CRIMSON)
    ws["C45"].number_format = '#,##0" eb"'
    _label(ws["E45"], "Session IP")
    ws["F45"] = "=SUM(G4:G43)"
    ws["F45"].font = Font(name="Calibri", size=12, bold=True)
    _note(ws, 47, 11, "In-world date, not real-world. Related persons should match CONTACTS handles. Heat = NCPD / corp / gang and a short note.")
    ws.sheet_properties.tabColor = CRIMSON
    return ws


def sheet_contacts(wb):
    ws = wb.create_sheet("CONTACTS")
    _page(ws, landscape=True)
    _banner(ws, "  KNOWN ASSOCIATES   ·   CREW FILE", 10)
    _widths(ws, [18, 18, 14, 14, 28, 22, 10, 18, 18, 28])
    headers = [
        "Handle", "Real name", "Role", "Relation", "Hook (one line)",
        "Useful for", "Trust 1–5", "Owed / owing", "Reach (Agent / hangout)", "Notes",
    ]
    _header_row(ws, 3, headers)
    _dv(ws, '"crew,client,rival,romance,contact,debt,fan,backup,family,corp,other"', "D4:D23", "Relation")
    for r in range(4, 24):
        for c in range(1, 11):
            cell = ws.cell(r, c)
            cell.border = thin
            cell.font = font_cell
            cell.fill = fill_white if r % 2 == 0 else PatternFill("solid", fgColor="FBF6EC")
            cell.alignment = left
        ws.row_dimensions[r].height = 20
    tab = Table(displayName="CONTACTS", ref="A3:J23")
    tab.tableStyleInfo = TableStyleInfo(name="TableStyleMedium1", showRowStripes=True)
    ws.add_table(tab)
    _note(ws, 25, 10, "Other PCs at the table + recurring NPCs. Dossier page 0 only keeps name-lists; this sheet is the actual cards. Trust 1 = will burn you, 5 = choomba.")
    ws.freeze_panes = "A4"
    ws.sheet_properties.tabColor = GOLD
    return ws


def sheet_net(wb):
    ws = wb.create_sheet("NET")
    _page(ws, landscape=False)
    _banner(ws, "  NET   ·   INTERFACE / QUICKHACKS", 6)
    _widths(ws, [26, 16, 14, 14, 18, 28])
    _label(ws["A3"], "Cyberdeck")
    _input(ws["B3"])
    ws.merge_cells("B3:C3")
    _label(ws["D3"], "Interface Rank")
    _input(ws["E3"])
    _label(ws["A4"], "NET Actions / turn")
    ws["B4"] = '=IF(E3="","",IF(E3<=3,2,IF(E3<=6,3,IF(E3<=9,4,5))))'
    ws["B4"].font = Font(name="Calibri", size=12, bold=True, color=CRIMSON)
    ws["B4"].border = thin
    _label(ws["D4"], "Self-ICE / Passwalls")
    _input(ws["E4"])
    _label(ws["A5"], "Neuroport deck port?")
    _input(ws["B5"], "Y")
    _label(ws["D5"], "Ex-Disks")
    _input(ws["E5"])

    ws.merge_cells("A7:F7")
    ws["A7"] = "PROGRAMS  /  HARDWARE"
    ws["A7"].font = font_h
    ws["A7"].fill = fill_slate
    for i in range(1, 7):
        ws.cell(7, i).fill = fill_slate
    _header_row(ws, 8, ["Name", "Type (Program/HW)", "ATK", "DEF", "Slots / notes", "Installed?"], fill=fill_slate)
    for r in range(9, 21):
        for c in range(1, 7):
            _input(ws.cell(r, c))
        ws.row_dimensions[r].height = 18

    ws.merge_cells("A22:F22")
    ws["A22"] = "QUICKHACKS  ·  CEMK 2070s  ·  Interface + 1d10 vs DV   (CPR p.197 / CEMK RB p.16–18, 39)"
    ws["A22"].font = font_h
    ws["A22"].fill = fill_red
    for i in range(1, 7):
        ws.cell(22, i).fill = fill_red
    _header_row(ws, 23, ["Quickhack", "DV", "Class", "Effect (short)", "", ""], fill=fill_ink)
    hacks = [
        ("Impair Movement", 6, "Simple", "MOVE −1 for 60s; 0 MOVE = no Move Action"),
        ("Sonic Shock", 6, "Simple", "Damaged Ear crit (no bonus dmg) 60s"),
        ("Overheat", 8, "Standard", "On fire: 4 HP at end of their Turn, bypass SP"),
        ("Short Circuit", 8, "Standard", "GM picks 3 chrome pieces offline 60s"),
        ("Cyberware Malfunction", 10, "Difficult", "You pick 1 chrome offline 60s (not Neuroport)"),
        ("Lure", 10, "Difficult", "Force their next Move; only if unaware"),
        ("Slow", 10, "Difficult", "MOVE −1d6 for 60s"),
        ("Synapse Burnout", 10, "Difficult", "3d6 HP, bypass armor, no ablation"),
        ("Puppet", 12, "Advanced", "You spend their next Action + Move"),
        ("Shard Ejection", 12, "Advanced", "Eject 1 chipware into adjacent square"),
        ("System Reset", 12, "Advanced", "Unconscious 60s or until damaged; Prone"),
    ]
    for i, (n, dv, cl, fx) in enumerate(hacks):
        r = 24 + i
        ws.cell(r, 1, n).font = font_cell
        ws.cell(r, 2, dv).alignment = center
        ws.cell(r, 3, cl)
        ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=6)
        ws.cell(r, 4, fx)
        for c in range(1, 7):
            ws.cell(r, c).border = thin
            ws.cell(r, c).fill = fill_white if i % 2 == 0 else fill_cream
    _note(ws, 36, 6, "Jack In: Interface + 1d10 vs target WILL + 1d10, 50 m, target must have a Neuroport. Failure still jacks in but they know. Eject: WILL + Concentration + 1d10 vs Interface + 1d10.")
    ws.row_dimensions[36].height = 32
    ws.sheet_properties.tabColor = "3D7A9A"
    return ws


def sheet_garage(wb):
    ws = wb.create_sheet("GARAGE")
    _page(ws, landscape=True)
    _banner(ws, "  GARAGE   ·   MOTO / FAMILY MOTORPOOL", 10)
    _widths(ws, [22, 16, 10, 10, 10, 10, 12, 14, 28, 14])
    _label(ws["A3"], "Moto Rank")
    _input(ws["B3"])
    _label(ws["C3"], "Pack / Family")
    _input(ws["D3"])
    ws.merge_cells("D3:F3")
    _note(ws, 4, 10, "Moto Rank adds to Drive/Pilot and Vehicle Tech checks. Only one Family Vehicle out at a time (all of them at Rank 10). CPR p.161–164.")
    headers = ["Vehicle", "Type", "MOVE", "SDP", "SP", "Seats", "Out now?", "Moto rank req.", "Upgrades", "Notes"]
    _header_row(ws, 6, headers)
    for r in range(7, 17):
        for c in range(1, 11):
            _input(ws.cell(r, c))
        ws.row_dimensions[r].height = 20
    tab = Table(displayName="GARAGE", ref="A6:J16")
    tab.tableStyleInfo = TableStyleInfo(name="TableStyleMedium4", showRowStripes=True)
    ws.add_table(tab)
    ws.freeze_panes = "A7"
    ws.sheet_properties.tabColor = "6B5A3A"
    return ws


def sheet_workshop(wb):
    ws = wb.create_sheet("WORKSHOP")
    _page(ws, landscape=False)
    _banner(ws, "  WORKSHOP   ·   MAKER", 6)
    _widths(ws, [26, 14, 14, 16, 16, 30])
    for i, lab in enumerate(["Field Expertise", "Upgrade Expertise", "Fabrication Expertise", "Invention Expertise"], 3):
        _label(ws.cell(i, 1), lab)
        _input(ws.cell(i, 2), 0)
        ws.cell(i, 3, "Rank")
        ws.cell(i, 3).font = font_small
    _label(ws["A7"], "Maker Rank (Role)")
    _input(ws["B7"])
    _note(ws, 8, 6, "Each Maker Rank: +1 to two different specialties. Field Expertise also jury-rigs as an Action. CPR p.147–149.")
    ws.merge_cells("A10:F10")
    ws["A10"] = "JOBS  ·  repairs, upgrades, inventions"
    ws["A10"].font = font_h
    ws["A10"].fill = fill_slate
    for i in range(1, 7):
        ws.cell(10, i).fill = fill_slate
    _header_row(ws, 11, ["Item / invention", "Specialty", "Price cat.", "DV", "Time", "Notes"], fill=fill_slate)
    for r in range(12, 24):
        for c in range(1, 7):
            _input(ws.cell(r, c))
    _note(ws, 25, 6, "Upgrade/Fabricate/Invent DV by price: Cheap 9 / 1h · Costly 13 / 6h · Premium 17 / 1d · Expensive 21 / 1w · V.Exp 24 / 2w · Luxury 29 / 1mo · Super Luxury 29 / 1mo per 10,000eb.")
    ws.row_dimensions[25].height = 32
    ws.sheet_properties.tabColor = "4A6B4A"
    return ws


def sheet_clinic(wb):
    ws = wb.create_sheet("CLINIC")
    _page(ws, landscape=False)
    _banner(ws, "  CLINIC   ·   MEDICINE", 6, fill_red)
    _widths(ws, [24, 14, 16, 16, 16, 30])
    for i, lab in enumerate(["Surgery (skill = 2× pts)", "Medical Tech — Pharma", "Medical Tech — Cryo"], 3):
        _label(ws.cell(i, 1), lab)
        _input(ws.cell(i, 2), 0)
    _label(ws["A6"], "Medicine Rank (Role)")
    _input(ws["B6"])
    _note(ws, 7, 6, "Each Medicine Rank: +1 to one specialty. Surgery Skill = 2 per point (max 10). Installation, harvesting, bodysculpt, therapy: CPR p.149, 226.")
    ws.merge_cells("A9:F9")
    ws["A9"] = "PATIENTS  /  THERAPY  /  PHARMA"
    ws["A9"].font = font_h
    ws["A9"].fill = fill_red
    for i in range(1, 7):
        ws.cell(9, i).fill = fill_red
    _header_row(ws, 10, ["Who / what", "Procedure", "HL recovered", "eb", "Date", "Notes"], fill=fill_ink)
    for r in range(11, 23):
        for c in range(1, 7):
            _input(ws.cell(r, c))
    ws.sheet_properties.tabColor = CRIMSON
    return ws


def sheet_team(wb):
    ws = wb.create_sheet("TEAM")
    _page(ws, landscape=True)
    _banner(ws, "  TEAM   ·   EXEC TEAMWORK", 12)
    _widths(ws, [16, 16, 16, 8, 8, 8, 8, 8, 8, 10, 22, 18])
    _label(ws["A3"], "Teamwork Rank")
    _input(ws["B3"])
    _label(ws["C3"], "Corp / cover")
    _input(ws["D3"])
    ws.merge_cells("D3:F3")
    _note(ws, 4, 12, "Exec team members are mechanical NPCs, not just CONTACTS. Use cover job / true job. CPR p.153–157 for who you get at each Rank.")
    headers = ["Handle", "Cover job", "True job", "HP", "SP", "INT", "REF", "DEX", "COOL", "MOVE", "Gear / chrome", "Notes"]
    _header_row(ws, 6, headers)
    for r in range(7, 13):
        for c in range(1, 13):
            _input(ws.cell(r, c))
        ws.row_dimensions[r].height = 20
    tab = Table(displayName="TEAM", ref="A6:L12")
    tab.tableStyleInfo = TableStyleInfo(name="TableStyleMedium7", showRowStripes=True)
    ws.add_table(tab)
    ws.sheet_properties.tabColor = "2F4A6E"
    return ws


def sheet_wishlist(wb):
    ws = wb.create_sheet("WISHLIST")
    _page(ws, landscape=False)
    _banner(ws, "  WISHLIST   ·   NIGHT MARKET", 6, fill_slate)
    _widths(ws, [28, 16, 12, 14, 14, 30])
    _header_row(ws, 3, ["Item", "Category", "Price cat.", "eb", "Source / Fixer", "Notes"], fill=fill_slate)
    _dv(ws, '"Cheap,Everyday,Costly,Premium,Expensive,Very Expensive,Luxury,Super Luxury"', "C4:C23", "Price")
    for r in range(4, 24):
        for c in range(1, 7):
            _input(ws.cell(r, c))
        ws.cell(r, 4).number_format = '#,##0'
    _note(ws, 25, 6, "Price categories (CPR p.385): Cheap 10 · Everyday 20 · Costly 50 · Premium 100 · Expensive 500 · Very Expensive 1,000 · Luxury 5,000 · Super Luxury 10,000+.")
    ws.sheet_properties.tabColor = SLATE
    return ws


def sheet_ref_combat(wb):
    ws = wb.create_sheet("REF_COMBAT")
    _page(ws, landscape=False)
    _banner(ws, "  REF  ·  COMBAT  ·  CPR p.127–176, 186", 4)
    _widths(ws, [28, 52, 18, 18])
    ws.merge_cells("A3:D3")
    ws["A3"] = "Turn = 1 Move Action + 1 other Action. Round ≈ 3 seconds. Initiative = REF + 1d10. Move = MOVE × 2 m (or MOVE squares, diagonals OK)."
    ws["A3"].font = font_small
    ws["A3"].alignment = left
    ws.row_dimensions[3].height = 28

    _header_row(ws, 4, ["Action", "What it does", "Notes", "CPR"], fill=fill_ink)
    actions = [
        ("Move Action", "MOVE × 2 m / MOVE squares", "Every round, free", "127"),
        ("Attack", "Melee or ranged attack", "ROF 2 can split around Move", "170"),
        ("Aimed Shot", "−8, ROF 1. Head: leftover ×2. Leg: Broken Leg. Held item: drop", "Not Autofire / shells", "169"),
        ("Reload", "Full mag, one ammo type", "Action", "171"),
        ("Get Up", "Leave Prone", "Can't move until you do", "127"),
        ("Grab / Choke / Throw / Human Shield", "Grapple suite", "See melee", "175"),
        ("Hold Action", "Delay; name trigger + action + target", "", "127"),
        ("Run", "Extra Move Action", "Only if you already Moved", "128"),
        ("Stabilize", "Start natural heal / pull out of Mortally Wounded", "Action", "222"),
        ("Use a Skill / Object", "3-second task", "Longer = spend Actions", "128"),
        ("Use NET Actions", "Netrunner: NET instead of meat Action", "Interface rank", "197"),
        ("Start / Get in Vehicle / Maneuver", "Vehicle combat", "", "189"),
        ("Equip/Drop Shield", "Shield = Action to don or drop", "", "127"),
    ]
    for i, (a, b, n, p) in enumerate(actions):
        r = 5 + i
        ws.cell(r, 1, a).font = Font(name="Calibri", size=9, bold=True)
        ws.cell(r, 2, b).font = font_cell
        ws.cell(r, 3, n).font = font_small
        ws.cell(r, 4, p).alignment = center
        for c in range(1, 5):
            ws.cell(r, c).border = thin
            ws.cell(r, c).fill = fill_white if i % 2 == 0 else fill_cream
            ws.cell(r, c).alignment = left
        ws.row_dimensions[r].height = 28

    r0 = 19
    ws.merge_cells(start_row=r0, start_column=1, end_row=r0, end_column=4)
    ws.cell(r0, 1, "WOUNDS  ·  ARMOR  ·  BRAWLING").font = font_h
    ws.cell(r0, 1).fill = fill_red
    for c in range(1, 5):
        ws.cell(r0, c).fill = fill_red

    blocks = [
        "Seriously Wounded: HP ≤ ⌈HP max / 2⌉. −2 to all Actions. Death Save = BODY. Mortally Wounded: HP 0. At start of your Turn roll 1d10 ≤ BODY or die. Each time you take damage while Mortal: Critical Injury +1 Death Save Penalty.",
        "Armor: if damage > SP, HP loss = damage − SP, then ablate SP by 1 (unless the attack says otherwise). Melee weapons ignore half SP (round up). Brawling does NOT. Ablate Head and Body separately.",
        "Brawling DMG by BODY: ≤4 → 1d6 · 5–6 (or ≤4 with Cyberarm) → 2d6 · 7–10 → 3d6 · 11+ → 4d6. Cyberarm brawl is at least 2d6.",
        "Facedown: both roll COOL + 1d10. Loser backs down or takes −2 on Checks against the winner until they beat them once. Cover: if they can see you, you are not in cover (bulletproof glass excepted).",
        "LUCK: spend 1:1 on a Check, resets each session. Extra Time: ×4 duration = +1 once. Complementary Skill: +1 once, no stack. Crit success: natural 10, add extra 1d10. Crit fail: natural 1, subtract extra 1d10.",
    ]
    for i, t in enumerate(blocks):
        r = r0 + 1 + i
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
        ws.cell(r, 1, t).font = font_cell
        ws.cell(r, 1).alignment = top_left
        ws.row_dimensions[r].height = 48
        ws.cell(r, 1).fill = fill_white if i % 2 == 0 else fill_cream
        ws.cell(r, 1).border = thin
    ws.sheet_properties.tabColor = INK
    return ws


def sheet_ref_range(wb):
    ws = wb.create_sheet("REF_RANGE")
    _page(ws, landscape=True)
    _banner(ws, "  REF  ·  RANGE TABLES  ·  CPR p.173–174", 9)
    _widths(ws, [22, 10, 10, 10, 10, 12, 12, 12, 12])
    ws.merge_cells("A3:I3")
    ws["A3"] = "Ranged: REF + weapon Skill + 1d10 vs DV by range (or vs DEX + Evasion + 1d10 if defender REF ≥ 8). Tie: defender wins. CPR p.173."
    ws["A3"].font = font_small

    ws.merge_cells("A4:I4")
    ws["A4"] = "SINGLE SHOT DV"
    ws["A4"].font = font_h
    ws["A4"].fill = fill_ink
    for c in range(1, 10):
        ws.cell(4, c).fill = fill_ink
    headers = ["Weapon", "0–6 m", "7–12", "13–25", "26–50", "51–100", "101–200", "201–400", "401–800"]
    _header_row(ws, 5, headers)
    rows = [
        ("Pistol", 13, 15, 20, 25, 30, 30, "—", "—"),
        ("SMG", 15, 13, 15, 20, 25, 25, 30, "—"),
        ("Shotgun (Slug)", 13, 15, 20, 25, 30, 35, "—", "—"),
        ("Assault Rifle", 17, 16, 15, 13, 15, 20, 25, 30),
        ("Sniper Rifle", 30, 25, 25, 20, 15, 16, 17, 20),
        ("Bow / Crossbow", 15, 13, 15, 17, 20, 22, "—", "—"),
        ("Grenade Launcher", 16, 15, 15, 17, 20, 22, 25, "—"),
        ("Rocket Launcher", 17, 16, 15, 15, 20, 20, 25, 30),
    ]
    for i, row in enumerate(rows):
        r = 6 + i
        for c, v in enumerate(row, 1):
            cell = ws.cell(r, c, v)
            cell.border = thin
            cell.alignment = center if c > 1 else left
            cell.font = Font(name="Calibri", size=10, bold=(c == 1))
            cell.fill = fill_white if i % 2 == 0 else fill_cream
        ws.row_dimensions[r].height = 18

    ws.merge_cells("A15:I15")
    ws["A15"] = "AUTOFIRE DV   ·   costs 10 bullets  ·   Autofire Skill  ·   damage 2d6 × amount you beat DV, cap = weapon Autofire (SMG 3 / AR 4)  ·  no Aimed Shot"
    ws["A15"].font = font_h
    ws["A15"].fill = fill_red
    for c in range(1, 10):
        ws.cell(15, c).fill = fill_red
        ws.cell(15, c).font = font_h
    _header_row(ws, 16, ["Weapon", "0–6 m", "7–12", "13–25", "26–50", "51–100", "", "", ""])
    af = [("SMG", 20, 17, 20, 25, 30), ("Assault Rifle", 22, 20, 17, 20, 25)]
    for i, row in enumerate(af):
        r = 17 + i
        for c, v in enumerate(row, 1):
            cell = ws.cell(r, c, v)
            cell.border = thin
            cell.alignment = center if c > 1 else left
            cell.fill = fill_white if i % 2 == 0 else fill_cream

    notes = [
        "Shotgun shell: 1 attack vs DV13; every target you can see in 6 m cone takes 3d6 (roll once). No Aimed Shot.",
        "Suppressive Fire: Action + 10 bullets. Everyone on foot, out of cover, in LOS, ≤25 m: WILL + Concentration + 1d10 vs your REF + Autofire + 1d10 or they must Move into cover.",
        "Thrown weapons: ROF 1, REF + Athletics vs thrown range DV. Melee thrown does not halve SP. Grenades deal explosive damage in 10×10 m.",
        "Arrows: loading is part of the attack (no Reload Action). Basic arrows can be retrieved.",
    ]
    for i, t in enumerate(notes):
        r = 20 + i
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=9)
        ws.cell(r, 1, t).font = font_cell
        ws.cell(r, 1).alignment = left
        ws.row_dimensions[r].height = 22
    ws.sheet_properties.tabColor = INK
    return ws


def sheet_ref_dv(wb):
    ws = wb.create_sheet("REF_DV")
    _page(ws, landscape=False)
    _banner(ws, "  REF  ·  DIFFICULTY  ·  IP  ·  PRICES  ·  CPR p.129–130, 385, 411", 4)
    _widths(ws, [18, 12, 42, 22])
    ws.merge_cells("A3:D3")
    ws["A3"] = "STAT + Skill + 1d10 vs DV  (or vs defender STAT + Skill + 1d10). Tie: defender wins. No Skill: STAT + 1d10 only."
    ws["A3"].font = font_small

    _header_row(ws, 5, ["Difficulty", "DV", "On the street", "CPR"])
    dvs = [
        ("Simple", 9, "Most people, no thinking — hard for a child", "130"),
        ("Everyday", 13, "Most people, no special training", "130"),
        ("Difficult", 15, "Needs training or talent", "130"),
        ("Professional", 17, "Actual training; you are a pro", "130"),
        ("Heroic", 21, "Sports-star / best of the best", "130"),
        ("Incredible", 24, "Olympian, top of the class", "130"),
        ("Legendary", 29, "People write stories about this", "130"),
    ]
    for i, (n, dv, desc, p) in enumerate(dvs):
        r = 6 + i
        ws.cell(r, 1, n).font = Font(name="Calibri", size=10, bold=True)
        ws.cell(r, 2, dv).alignment = center
        ws.cell(r, 2).font = Font(name="Calibri", size=12, bold=True, color=CRIMSON)
        ws.cell(r, 3, desc)
        ws.cell(r, 4, p).alignment = center
        for c in range(1, 5):
            ws.cell(r, c).border = thin
            ws.cell(r, c).fill = fill_white if i % 2 == 0 else fill_cream

    ws.merge_cells("A14:D14")
    ws["A14"] = "IMPROVEMENT POINTS  (spend between sessions)"
    ws["A14"].font = font_h
    ws["A14"].fill = fill_red
    for c in range(1, 5):
        ws.cell(14, c).fill = fill_red
    ip_rows = [
        ("Raise a Skill", "10 × new level", "0→1 costs 10; 5→6 costs 60. x2 skills cost double.", "411"),
        ("Raise Role Ability", "20 × new rank", "3→4 costs 80", "411"),
        ("Playstyle IP", "GM table 10–80", "Group vs Warrior / Socializer / Explorer / Roleplayer", "410"),
    ]
    _header_row(ws, 15, ["What", "Cost", "Note", "CPR"])
    for i, row in enumerate(ip_rows):
        r = 16 + i
        for c, v in enumerate(row, 1):
            ws.cell(r, c, v).border = thin
            ws.cell(r, c).fill = fill_cream
            ws.cell(r, c).font = font_cell

    ws.merge_cells("A20:D20")
    ws["A20"] = "PRICE CATEGORIES  ·  without a Fixer you buy up to Premium only"
    ws["A20"].font = font_h
    ws["A20"].fill = fill_ink
    for c in range(1, 5):
        ws.cell(20, c).fill = fill_ink
    _header_row(ws, 21, ["Category", "eb", "Note", "CPR"])
    prices = [
        ("Cheap", 10, "", "385"),
        ("Everyday", 20, "", "385"),
        ("Costly", 50, "", "385"),
        ("Premium", 100, "Street ceiling without a Fixer", "385"),
        ("Expensive", 500, "Needs Fixer / Night Market", "385"),
        ("Very Expensive", 1000, "", "385"),
        ("Luxury", 5000, "", "385"),
        ("Super Luxury", "10000+", "", "385"),
    ]
    for i, row in enumerate(prices):
        r = 22 + i
        for c, v in enumerate(row, 1):
            cell = ws.cell(r, c, v)
            cell.border = thin
            cell.fill = fill_white if i % 2 == 0 else fill_cream
            cell.font = font_cell
            if c == 2:
                cell.alignment = center

    ws.merge_cells("A31:D31")
    ws["A31"] = "Modifiers (subtract from your roll, they stack): night −1 · never done this −1 · complex −2 · no tools −2 · bad sleep −2 · extreme stress −2 · exhausted −4 · drunk/sedated −4 · secretly −4 · smoke/dark −4. Extra Time ×4 = +1. Complementary Skill = +1 once."
    ws["A31"].font = font_small
    ws["A31"].alignment = top_left
    ws.row_dimensions[31].height = 48
    ws.sheet_properties.tabColor = INK
    return ws


def build_xlsx(path: Path):
    wb = Workbook()
    wb.calculation = CalcProperties(fullCalcOnLoad=True)
    sheet_meta(wb)
    sheet_ledger(wb)
    sheet_contacts(wb)
    sheet_net(wb)
    sheet_garage(wb)
    sheet_workshop(wb)
    sheet_clinic(wb)
    sheet_team(wb)
    sheet_wishlist(wb)
    sheet_ref_combat(wb)
    sheet_ref_range(wb)
    sheet_ref_dv(wb)
    wb.properties.title = "NC//NET Street File"
    wb.properties.creator = "NC//NET"
    wb.properties.description = "Offline character ledger + play screen for Cyberpunk RED. Unofficial table aid."
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    print("wrote", path, "sheets:", wb.sheetnames)
    return path

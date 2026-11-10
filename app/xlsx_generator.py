import os
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

POLISH_COLLATE_MAP = {
    'a': 'a0', 'ą': 'a1', 'b': 'b0', 'c': 'c0', 'ć': 'c1', 'd': 'd0',
    'e': 'e0', 'ę': 'e1', 'f': 'f0', 'g': 'g0', 'h': 'h0', 'i': 'i0',
    'j': 'j0', 'k': 'k0', 'l': 'l0', 'ł': 'l1', 'm': 'm0', 'n': 'n0',
    'ń': 'n1', 'o': 'o0', 'ó': 'o1', 'p': 'p0', 'r': 'r0', 's': 's0',
    'ś': 's1', 't': 't0', 'u': 'u0', 'w': 'w0', 'y': 'y0', 'z': 'z0',
    'ź': 'z1', 'ż': 'z2'
}

def polish_sort_key(text: str) -> str:
    """Klucz sortowania alfabetycznego uwzględniający polskie znaki diakrytyczne."""
    return "".join(POLISH_COLLATE_MAP.get(ch, ch) for ch in (text or "").lower())

CANONICAL_CATEGORIES = [
    "Pieczywo",
    "Zboża/pseudozboża i produkty",
    "Nabiał i produkty nabiałowe oraz roślinne",
    "Mięso",
    "Wędliny i wyroby",
    "Ryby",
    "Owoce morza",
    "Owoce",
    "Warzywa",
    "Inne produkty roślinne",
    "Nasiona i orzechy",
    "Napoje",
    "Przyprawy",
    "Inne",
    "Dodatki do żywności"
]

STATUS_DISPLAY = {
    "zalecane": "Zalecane",
    "dozwolone": "Dozwolone",
    "ograniczone": "Ograniczone",
    "zakazane": "Zakazane"
}

STATUS_FILLS = {
    "zalecane": PatternFill(start_color="ECFDF5", end_color="ECFDF5", fill_type="solid"),
    "dozwolone": PatternFill(start_color="F0F9FF", end_color="F0F9FF", fill_type="solid"),
    "ograniczone": PatternFill(start_color="FFFBEB", end_color="FFFBEB", fill_type="solid"),
    "zakazane": PatternFill(start_color="FEF2F2", end_color="FEF2F2", fill_type="solid")
}

STATUS_FONTS = {
    "zalecane": Font(name="Calibri", size=10, bold=True, color="047857"),
    "dozwolone": Font(name="Calibri", size=10, bold=True, color="0284C7"),
    "ograniczone": Font(name="Calibri", size=10, bold=True, color="B45309"),
    "zakazane": Font(name="Calibri", size=10, bold=True, color="B91C1C")
}

BORDER_THIN = Border(
    left=Side(style="thin", color="CBD5E1"),
    right=Side(style="thin", color="CBD5E1"),
    top=Side(style="thin", color="CBD5E1"),
    bottom=Side(style="thin", color="CBD5E1")
)

BORDER_CHECKBOX = Border(
    left=Side(style="medium", color="64748B"),
    right=Side(style="medium", color="64748B"),
    top=Side(style="thin", color="CBD5E1"),
    bottom=Side(style="thin", color="CBD5E1")
)


def generate_restrictions_xlsx(
    email: str | None,
    selected_ailments: list[str],
    merged_products: dict,
    output_filepath: str
) -> str:
    """
    Generuje elegancki arkusz kalkulacyjny Excel (.xlsx) z ograniczeniami żywieniowymi:
    - Podział na oryginalne podsekcje żywieniowe (np. Pieczywo, Nabiał, Warzywa...),
    - Sortowanie alfabetyczne wewnątrz każdej podkategorii (A-Z),
    - Kolorystyczne oznaczenia statusów TDP,
    - Dodatkowa interaktywna kolumna 'Dostępne?' do wstawiania 'x' przez pacjenta,
    - Zablokowany nagłówek (Freeze Panes) oraz włączone autofiltry.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Ograniczenia Żywieniowe"
    ws.views.sheetView[0].showGridLines = True

    # 1. Nagłówek raportu
    ws.merge_cells("A1:G1")
    ws["A1"] = "Diet-Med • Test Doboru Produktów dla Zdrowia (TDP)"
    ws["A1"].font = Font(name="Calibri", size=14, bold=True, color="1E3A8A")
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")

    ws.merge_cells("A2:G2")
    pacjent_txt = f"Pacjent: {email} | " if email else ""
    ailments_txt = ", ".join(selected_ailments) if selected_ailments else "Ogólne wytyczne"
    date_txt = datetime.now().strftime("%d.%m.%Y %H:%M")
    ws["A2"] = f"{pacjent_txt}Data: {date_txt} | Zbadane dolegliwości: {ailments_txt}"
    ws["A2"].font = Font(name="Calibri", size=10, italic=True, color="475569")
    ws["A2"].alignment = Alignment(horizontal="left", vertical="center")

    # Wiersz 3: Nagłówki tabeli
    headers = [
        "Kategoria",
        "Produkt",
        "Status TDP",
        "Ilość / Porcja",
        "Jednostka",
        "Uwagi kliniczne",
        "Dostępne? (wstaw 'x')"
    ]
    ws.append(headers)
    ws.row_dimensions[3].height = 26

    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    for col_idx in range(1, 8):
        cell = ws.cell(row=3, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER_THIN

    # 3. Pogrupowanie produktów wg kategorii
    category_buckets: dict[str, list] = {}
    for item in merged_products.values():
        cat = item.get("kategoria") or "Inne"
        cat_clean = cat.strip().capitalize()
        category_buckets.setdefault(cat_clean, []).append(item)

    # Ustalenie kolejności kategorii: najpierw kanoniczne, potem pozostałe
    known_order_map = {cat.lower(): idx for idx, cat in enumerate(CANONICAL_CATEGORIES)}
    sorted_categories = sorted(
        category_buckets.keys(),
        key=lambda c: (known_order_map.get(c.lower(), 99), polish_sort_key(c))
    )

    current_row = 4
    cat_banner_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    cat_banner_font = Font(name="Calibri", size=11, bold=True, color="0F172A")
    cat_banner_border = Border(
        top=Side(style="medium", color="94A3B8"),
        bottom=Side(style="medium", color="94A3B8"),
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1")
    )

    for cat_name in sorted_categories:
        items = category_buckets[cat_name]
        # Sortowanie alfabetyczne produktów wewnątrz podkategorii
        items.sort(key=lambda x: polish_sort_key(x["rodzaj"]))

        # Wiersz nagłówka sekcji/kategorii
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=7)
        banner_cell = ws.cell(row=current_row, column=1)
        banner_cell.value = f"PODSEKCJA: {cat_name.upper()} ({len(items)} produktów)"
        banner_cell.font = cat_banner_font
        banner_cell.fill = cat_banner_fill
        banner_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        for c_idx in range(1, 8):
            ws.cell(row=current_row, column=c_idx).border = cat_banner_border
        ws.row_dimensions[current_row].height = 22
        current_row += 1

        # Wiersze produktów
        for prod in items:
            raw_status = prod.get("status", "dozwolone").lower()
            status_text = STATUS_DISPLAY.get(raw_status, raw_status.capitalize())
            qty = prod.get("ilosc")
            qty_val = float(qty) if qty is not None else None
            unit = prod.get("jednostka") or ""
            comments = " / ".join(prod.get("komentarze", [])) if prod.get("komentarze") else ""

            row_data = [
                cat_name,
                prod["rodzaj"],
                status_text,
                qty_val,
                unit,
                comments,
                ""  # Pusta kolumna 'Dostępne?'
            ]
            ws.append(row_data)
            ws.row_dimensions[current_row].height = 19

            # Stylizacja komórek produktu
            c_cat = ws.cell(row=current_row, column=1)
            c_prod = ws.cell(row=current_row, column=2)
            c_stat = ws.cell(row=current_row, column=3)
            c_qty = ws.cell(row=current_row, column=4)
            c_unit = ws.cell(row=current_row, column=5)
            c_comm = ws.cell(row=current_row, column=6)
            c_avail = ws.cell(row=current_row, column=7)

            for c in (c_cat, c_prod, c_stat, c_qty, c_unit, c_comm):
                c.border = BORDER_THIN
                c.font = Font(name="Calibri", size=9.5, color="1E293B")

            c_cat.alignment = Alignment(horizontal="left", vertical="center")
            c_prod.alignment = Alignment(horizontal="left", vertical="center")
            c_qty.alignment = Alignment(horizontal="right", vertical="center")
            c_unit.alignment = Alignment(horizontal="center", vertical="center")
            c_comm.alignment = Alignment(horizontal="left", vertical="center")

            # Kolorowanie statusu
            if raw_status in STATUS_FILLS:
                c_stat.fill = STATUS_FILLS[raw_status]
                c_stat.font = STATUS_FONTS[raw_status]
            c_stat.alignment = Alignment(horizontal="center", vertical="center")

            # Specjalna stylizacja kolumny 'Dostępne?' do zaznaczania 'x'
            c_avail.border = BORDER_CHECKBOX
            c_avail.alignment = Alignment(horizontal="center", vertical="center")
            c_avail.font = Font(name="Calibri", size=11, bold=True, color="0F172A")
            c_avail.fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

            current_row += 1

    # 4. Włączenie autofiltrów i zamrożenie nagłówków
    last_row = current_row - 1
    ws.auto_filter.ref = f"A3:G{last_row}"
    ws.freeze_panes = "A4"

    # 5. Automatyczne dopasowanie szerokości kolumn
    base_widths = {
        1: 22,  # Kategoria
        2: 36,  # Produkt
        3: 16,  # Status TDP
        4: 14,  # Ilość / Porcja
        5: 12,  # Jednostka
        6: 42,  # Uwagi kliniczne
        7: 20   # Dostępne? (wstaw 'x')
    }
    for col_idx, width in base_widths.items():
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = width

    os.makedirs(os.path.dirname(os.path.abspath(output_filepath)), exist_ok=True)
    wb.save(output_filepath)
    return output_filepath

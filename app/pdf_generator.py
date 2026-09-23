import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# Rejestracja czcionek z polskimi znakami
FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
REGULAR_FONT_PATH = os.path.join(FONTS_DIR, "DejaVuSans.ttf")
BOLD_FONT_PATH = os.path.join(FONTS_DIR, "DejaVuSans-Bold.ttf")

if os.path.exists(REGULAR_FONT_PATH):
    pdfmetrics.registerFont(TTFont("DejaVuSans", REGULAR_FONT_PATH))
    FONT_NORMAL = "DejaVuSans"
else:
    FONT_NORMAL = "Helvetica"

if os.path.exists(BOLD_FONT_PATH):
    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", BOLD_FONT_PATH))
    FONT_BOLD = "DejaVuSans-Bold"
else:
    FONT_BOLD = "Helvetica-Bold"


def resolve_product_conflicts(products_by_ailment: list[dict]) -> dict:
    """
    Logika łączenia produktów z wielu dolegliwości:
    - Priorytet: 'zakazane' > 'umiarkowane' > 'dozwolone'
    - Gdy 'umiarkowane':
      - ilosc i jednostka razem bez spacji (np. 135g)
      - jeśli dolegliwości mają 'umiarkowane' -> bierzemy mniejszą ilość
    - ZAWSZE łączymy unikalne komentarze ze wszystkich wybranych dolegliwości
    """
    merged = {}
    STATUS_PRIORITY = {"dozwolone": 1, "umiarkowane": 2, "zakazane": 3}

    for item in products_by_ailment:
        key = item["rodzaj"].strip().lower()
        curr_status = item.get("status", "dozwolone")

        if key not in merged:
            merged[key] = {
                "rodzaj": item["rodzaj"].strip(),
                "status": curr_status,
                "ilosc": item.get("ilosc") if curr_status == "umiarkowane" else None,
                "jednostka": item.get("jednostka") if curr_status == "umiarkowane" else None,
                "komentarze": [item.get("komentarz")] if item.get("komentarz") else []
            }
        else:
            existing = merged[key]
            existing_score = STATUS_PRIORITY.get(existing["status"], 0)
            new_score = STATUS_PRIORITY.get(curr_status, 0)

            # Wyższy priorytet zastępuje niższy w kwestii statusu
            if new_score > existing_score:
                existing["status"] = curr_status
                if curr_status == "umiarkowane":
                    existing["ilosc"] = item.get("ilosc")
                    existing["jednostka"] = item.get("jednostka")
                elif curr_status == "zakazane":
                    existing["ilosc"] = None
                    existing["jednostka"] = None
            elif new_score == existing_score and curr_status == "umiarkowane":
                # Konflikt dwóch ograniczeń: wybieramy mniejszą ilość
                new_qty = item.get("ilosc")
                old_qty = existing.get("ilosc")
                if new_qty is not None and old_qty is not None:
                    if float(new_qty) < float(old_qty):
                        existing["ilosc"] = new_qty
                        existing["jednostka"] = item.get("jednostka") or existing.get("jednostka")
                elif new_qty is not None and old_qty is None:
                    existing["ilosc"] = new_qty
                    existing["jednostka"] = item.get("jednostka")

            # ZAWSZE dołączamy unikalne komentarze ze wszystkich wybranych dolegliwości
            new_comm = item.get("komentarz")
            if new_comm:
                norm_existing = [c.strip().lower() for c in existing["komentarze"]]
                if new_comm.strip().lower() not in norm_existing:
                    existing["komentarze"].append(new_comm.strip())

    return merged


PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN_LEFT = 36.0
MARGIN_RIGHT = 36.0
TOP_MARGIN = 36.0
BOTTOM_MARGIN = 36.0
USABLE_WIDTH = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT  # 523.2755 pt


def compute_umiarkowane_layout(items: list[dict], usable_width: float = USABLE_WIDTH) -> dict:
    """
    Dynamicznie oblicza optymalne szerokości kolumn i typografię tabeli produktów ograniczonych.
    Elastycznie dostosowuje się do długości komentarzy, braku komentarzy lub nietypowych nazw produktów.
    """
    has_comments = any(bool(p.get("komentarze")) for p in items)

    # 1. Zmierz zapotrzebowanie kolumny 'Porcja'
    port_strings = []
    for p in items:
        if p.get("ilosc") is not None:
            qty_str = f"{float(p['ilosc']):g}"
            unit_str = p.get("jednostka") or ""
            port_strings.append(f"{qty_str}{unit_str}")
        else:
            port_strings.append("w niewielkich ilościach")

    header_port_w = pdfmetrics.stringWidth("Dopuszczalna porcja", FONT_BOLD, 9)
    max_val_port_w = max([pdfmetrics.stringWidth(s, FONT_NORMAL, 9) for s in port_strings]) if port_strings else 0
    # Margines komórki (4pt lewy + 4pt prawy = 8pt) + 3pt margines bezpieczeństwa
    needed_port_w = max(header_port_w, max_val_port_w) + 11.0

    # Gdy w tabeli nie ma ŻADNYCH komentarzy, redukujemy do 2 kolumn i oddajemy miejsce produktom
    if not has_comments:
        col_port = min(needed_port_w, usable_width * 0.35)
        col_prod = usable_width - col_port
        return {
            "has_comments": False,
            "col_widths": [col_prod, col_port],
            "font_size": 9.0,
            "leading": 12.0
        }

    # 2. Zmierz długości produktów i komentarzy
    prod_widths = [pdfmetrics.stringWidth(p["rodzaj"], FONT_BOLD, 9) for p in items]
    sorted_pw = sorted(prod_widths)
    p85_prod_w = sorted_pw[int(len(sorted_pw) * 0.85)] if sorted_pw else 100.0

    comm_strings = [" / ".join(p["komentarze"]) for p in items if p.get("komentarze")]
    max_comm_w = max([pdfmetrics.stringWidth(c, FONT_NORMAL, 9) for c in comm_strings]) if comm_strings else 0

    # Skalowanie typografii w przypadku bardzo obszernych uwag/komentarzy
    font_size = 9.0
    leading = 12.0
    if max_comm_w > 450.0:
        font_size = 8.5
        leading = 11.0
    if max_comm_w > 700.0:
        font_size = 8.0
        leading = 10.5

    # Bezpieczne granice szerokości porcji
    col_port = max(105.0, min(needed_port_w, 125.0))

    # Dynamiczne dopasowanie kolumny produktu
    # Jeśli w danym zestawie pojawiają się bardzo długie komentarze (> 250 pt),
    # pozwalamy kolumnie produktu być bardziej zwięzłą (135 - 155 pt), aby komentarze otrzymały maksimum miejsca.
    if max_comm_w > 250.0:
        col_prod = max(135.0, min(p85_prod_w + 10.0, 155.0))
    else:
        col_prod = max(145.0, min(p85_prod_w + 10.0, 170.0))

    # Kolumna komentarzy otrzymuje 100% pozostałej przestrzeni roboczej strony A4!
    col_comm = usable_width - col_prod - col_port

    return {
        "has_comments": True,
        "col_widths": [col_prod, col_port, col_comm],
        "font_size": font_size,
        "leading": leading
    }


def compute_dozwolone_layout(items: list[dict], usable_width: float = USABLE_WIDTH) -> tuple[int, list[float]]:
    """
    Dynamicznie ustala optymalną liczbę kolumn (3, 2 lub 1) i ich szerokości dla sekcji Dozwolone.
    """
    widths = []
    for p in items:
        raw_text = f"✓ {p['rodzaj']}"
        if p.get("komentarze"):
            raw_text += f" ({', '.join(p['komentarze'])})"
        widths.append(pdfmetrics.stringWidth(raw_text, FONT_NORMAL, 9))

    if not widths:
        return 3, [usable_width / 3.0] * 3

    max_w = max(widths)
    sorted_w = sorted(widths)
    p85_w = sorted_w[int(len(sorted_w) * 0.85)]

    # 3 kolumny dają ~174.4 pt (po odliczeniu paddingu ~164 pt na tekst).
    # Jeśli 85% pozycji mieści się w 160 pt, a max <= 240 pt, 3 kolumny prezentują się estetycznie i oszczędzają miejsce.
    if p85_w <= 160.0 and max_w <= 240.0:
        cols_count = 3
    elif max_w <= 450.0:
        cols_count = 2
    else:
        cols_count = 1

    col_w = usable_width / float(cols_count)
    return cols_count, [col_w] * cols_count


def compute_zakazane_layout(items: list[dict], usable_width: float = USABLE_WIDTH) -> tuple[int, list[float]]:
    """
    Dynamicznie ustala liczbę kolumn i ich szerokości dla sekcji Zakazane.
    """
    widths = []
    for p in items:
        raw_text = f"• {p['rodzaj']}"
        if p.get("komentarze"):
            raw_text += f" ({', '.join(p['komentarze'])})"
        widths.append(pdfmetrics.stringWidth(raw_text, FONT_NORMAL, 9))

    if not widths:
        return 2, [usable_width / 2.0] * 2

    max_w = max(widths)
    sorted_w = sorted(widths)
    p90_w = sorted_w[int(len(sorted_w) * 0.90)]

    if max_w <= 160.0:
        cols_count = 3
    elif p90_w <= 250.0 or max_w <= 480.0:
        cols_count = 2
    else:
        cols_count = 1

    col_w = usable_width / float(cols_count)
    return cols_count, [col_w] * cols_count


class NumberedCanvas(canvas.Canvas):
    """
    Dwuprzebiegowy canvas ReportLab do dynamicznego nanoszenia numeracji stron ('Strona X z Y')
    oraz powtarzalnych nagłówków i stopek na każdej stronie raportu.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont(FONT_NORMAL, 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # 1. Bieżący dyskretny nagłówek na kolejnych stronach (strona 2+)
        if self._pageNumber > 1:
            self.drawString(MARGIN_LEFT, PAGE_HEIGHT - 24, "Diet-Med • TDP — Spersonalizowany Raport Ograniczeń Żywieniowych")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(MARGIN_LEFT, PAGE_HEIGHT - 28, PAGE_WIDTH - MARGIN_RIGHT, PAGE_HEIGHT - 28)

        # 2. Bieżąca stopka na każdej stronie
        page_str = f"Strona {self._pageNumber} z {page_count}"
        self.drawRightString(PAGE_WIDTH - MARGIN_RIGHT, 16, page_str)
        self.drawString(MARGIN_LEFT, 16, "Diet-Med (TDP) • Zalecenia pomocnicze. W razie wątpliwości skonsultuj się ze specjalistą.")

        # Linia nad stopką
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(MARGIN_LEFT, 26, PAGE_WIDTH - MARGIN_RIGHT, 26)

        self.restoreState()


def generate_restrictions_pdf(
    email: str | None,
    selected_ailments: list[str],
    merged_products: dict,
    output_filepath: str
) -> str:
    """
    Generuje elegancki, w pełni dynamiczny plik PDF z ograniczeniami żywieniowymi: 'ograniczenia zywieniowe.pdf'
    """
    doc = SimpleDocTemplate(
        output_filepath,
        pagesize=A4,
        leftMargin=MARGIN_LEFT,
        rightMargin=MARGIN_RIGHT,
        topMargin=TOP_MARGIN,
        bottomMargin=BOTTOM_MARGIN
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1e3a8a"),
        alignment=0,
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName=FONT_NORMAL,
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#475569"),
        spaceAfter=15
    )

    h2_zakazane = ParagraphStyle(
        "H2Zakazane",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#991b1b"),
        spaceBefore=14,
        spaceAfter=6
    )

    h2_umiarkowane = ParagraphStyle(
        "H2Umiarkowane",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#b45309"),
        spaceBefore=14,
        spaceAfter=6
    )

    h2_dozwolone = ParagraphStyle(
        "H2Dozwolone",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#065f46"),
        spaceBefore=14,
        spaceAfter=6
    )

    cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName=FONT_NORMAL,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1e293b")
    )

    cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1e293b")
    )

    story = []

    # Nagłówek dokumentu
    pacjent_info = f"<b>Pacjent:</b> {email} &nbsp;|&nbsp; " if email else ""
    story.append(Paragraph("Diet-Med • Test Doboru Produktów dla Zdrowia (TDP)", subtitle_style))
    story.append(Paragraph("Ograniczenia Żywieniowe", title_style))
    story.append(Paragraph(
        f"{pacjent_info}"
        f"<b>Data generowania:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}<br/>"
        f"<b>Wskazane dolegliwości:</b> {', '.join(selected_ailments) if selected_ailments else 'Ogólne wytyczne'}",
        subtitle_style
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=14))

    # Podział produktów wg kategorii
    zakazane = []
    umiarkowane = []
    dozwolone = []

    for item in sorted(merged_products.values(), key=lambda x: x["rodzaj"]):
        st = item["status"]
        if st == "zakazane":
            zakazane.append(item)
        elif st == "umiarkowane":
            umiarkowane.append(item)
        elif st == "dozwolone":
            dozwolone.append(item)

    # 1. SEKCJA: PRODUKTY DOZWOLONE
    if dozwolone:
        story.append(Paragraph("✅ Produkty Dozwolone (Bezpieczne)", h2_dozwolone))
        story.append(Paragraph(
            "Produkty w pełni rekomendowane w diecie:",
            subtitle_style
        ))

        cols_count, col_widths = compute_dozwolone_layout(dozwolone, USABLE_WIDTH)
        table_data = []
        row = []
        for p in dozwolone:
            text_p = f"✓ {p['rodzaj']}"
            if p.get("komentarze"):
                comm_joined = ", ".join(p["komentarze"])
                text_p += f' <font color="#047857"><i>({comm_joined})</i></font>'
            row.append(Paragraph(text_p, cell_style))
            if len(row) == cols_count:
                table_data.append(row)
                row = []
        if row:
            while len(row) < cols_count:
                row.append(Paragraph("", cell_style))
            table_data.append(row)

        t_dozwolone = Table(table_data, colWidths=col_widths)
        t_dozwolone.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f0fdf4"), colors.white]),
        ]))
        story.append(t_dozwolone)
        story.append(Spacer(1, 14))

    # 2. SEKCJA: PRODUKTY OGRANICZONE (UMIARKOWANE)
    if umiarkowane:
        if dozwolone:
            story.append(PageBreak())
        story.append(Paragraph("⚠️ Produkty Ograniczone (Dopuszczalne w wyznaczonych porcjach)", h2_umiarkowane))
        story.append(Paragraph(
            "Poniższe produkty można spożywać wyłącznie z uwzględnieniem wskazanej gramatury/ilości oraz uwag dodatkowych:",
            subtitle_style
        ))

        um_layout = compute_umiarkowane_layout(umiarkowane, USABLE_WIDTH)
        has_comm = um_layout["has_comments"]
        col_widths = um_layout["col_widths"]

        # Dynamiczne style z zachowaniem odpowiedniego rozmiaru fontu
        um_cell_style = ParagraphStyle(
            "UmTableCell",
            parent=cell_style,
            fontSize=um_layout["font_size"],
            leading=um_layout["leading"]
        )
        um_cell_bold = ParagraphStyle(
            "UmTableCellBold",
            parent=cell_bold,
            fontSize=um_layout["font_size"],
            leading=um_layout["leading"]
        )

        if has_comm:
            table_data = [[
                Paragraph("<b>Produkt / Rodzaj</b>", um_cell_bold),
                Paragraph("<b>Dopuszczalna porcja</b>", um_cell_bold),
                Paragraph("<b>Uwagi i komentarz</b>", um_cell_bold)
            ]]
        else:
            table_data = [[
                Paragraph("<b>Produkt / Rodzaj</b>", um_cell_bold),
                Paragraph("<b>Dopuszczalna porcja</b>", um_cell_bold)
            ]]

        for p in umiarkowane:
            if p["ilosc"] is not None:
                qty_str = f"{float(p['ilosc']):g}"
                unit_str = p.get("jednostka") or ""
                porcja_str = f"{qty_str}{unit_str}"
            else:
                porcja_str = "w niewielkich ilościach"

            if has_comm:
                comm_str = " / ".join(p["komentarze"]) if p["komentarze"] else "—"
                table_data.append([
                    Paragraph(p["rodzaj"], um_cell_bold),
                    Paragraph(porcja_str, um_cell_style),
                    Paragraph(comm_str, um_cell_style)
                ])
            else:
                table_data.append([
                    Paragraph(p["rodzaj"], um_cell_bold),
                    Paragraph(porcja_str, um_cell_style)
                ])

        t_umiarkowane = Table(table_data, colWidths=col_widths, repeatRows=1)
        t_umiarkowane.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fef3c7")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#92400e")),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#fde68a")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fffbeb")]),
        ]))
        story.append(t_umiarkowane)
        story.append(Spacer(1, 14))

    # 3. SEKCJA: PRODUKTY ZAKAZANE
    if zakazane:
        if dozwolone or umiarkowane:
            story.append(PageBreak())
        story.append(Paragraph("⛔ Produkty Przeciwwskazane (Zakazane)", h2_zakazane))
        story.append(Paragraph(
            "Tych produktów należy bezwzględnie unikać przy wskazanych dolegliwościach:",
            subtitle_style
        ))

        cols_count, col_widths = compute_zakazane_layout(zakazane, USABLE_WIDTH)
        table_data = []
        row = []
        for p in zakazane:
            text_p = f"• {p['rodzaj']}"
            if p.get("komentarze"):
                comm_joined = ", ".join(p["komentarze"])
                text_p += f' <font color="#991b1b"><i>({comm_joined})</i></font>'
            row.append(Paragraph(text_p, cell_style))
            if len(row) == cols_count:
                table_data.append(row)
                row = []
        if row:
            while len(row) < cols_count:
                row.append(Paragraph("", cell_style))
            table_data.append(row)

        t_zakazane = Table(table_data, colWidths=col_widths)
        t_zakazane.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#fef2f2"), colors.white]),
        ]))
        story.append(t_zakazane)
        story.append(Spacer(1, 14))

    # Stopka
    story.append(Spacer(1, 15))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#94a3b8"), spaceAfter=10))
    footer_style = ParagraphStyle(
        "DocFooter",
        parent=styles["Normal"],
        fontName=FONT_NORMAL,
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#64748b"),
        alignment=1
    )
    story.append(Paragraph(
        "Dokument wygenerowany automatycznie w ramach systemu Diet-Med (TDP). "
        "Przedstawione zalecenia mają charakter pomocniczy. "
        "W razie wątpliwości skonsultuj się ze specjalistą dietetykiem lub lekarzem prowadzącym.",
        footer_style
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    return output_filepath


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


def merge_comments(existing_comments: list[str], new_comment: str | None) -> list[str]:
    if not new_comment:
        return existing_comments
    new_c = new_comment.strip()
    if not new_c:
        return existing_comments
    
    new_lower = new_c.lower()
    for idx, ext in enumerate(existing_comments):
        ext_lower = ext.lower()
        if new_lower == ext_lower or new_lower in ext_lower:
            return existing_comments
        if ext_lower in new_lower:
            existing_comments[idx] = new_c
            return existing_comments
            
    existing_comments.append(new_c)
    return existing_comments


def resolve_product_conflicts(products_by_ailment: list[dict]) -> dict:
    """
    Logika łączenia produktów z wielu dolegliwości:
    - Priorytet: 'zakazane' > 'umiarkowane' > 'dozwolone'
    - Gdy 'umiarkowane':
      - ilosc i jednostka razem bez spacji (np. 135g)
      - jeśli dolegliwości mają 'umiarkowane' -> bierzemy mniejszą ilość
    - ZAWSZE łączymy unikalne komentarze ze wszystkich wybranych dolegliwości (bez powtórzeń)
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
                "komentarze": [item.get("komentarz").strip()] if item.get("komentarz") and item.get("komentarz").strip() else []
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

            # ZAWSZE dołączamy unikalne komentarze ze wszystkich wybranych dolegliwości bez duplikatów
            existing["komentarze"] = merge_comments(existing["komentarze"], item.get("komentarz"))

    return merged


PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN_LEFT = 36.0
MARGIN_RIGHT = 36.0
TOP_MARGIN = 36.0
BOTTOM_MARGIN = 36.0
USABLE_WIDTH = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT  # 523.2755 pt



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
            self.drawString(MARGIN_LEFT, PAGE_HEIGHT - 24, "Diet-Med | TDP — Spersonalizowany Raport Ograniczeń Żywieniowych")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(MARGIN_LEFT, PAGE_HEIGHT - 28, PAGE_WIDTH - MARGIN_RIGHT, PAGE_HEIGHT - 28)

        # 2. Bieżąca stopka na każdej stronie
        page_str = f"Strona {self._pageNumber} z {page_count}"
        self.drawRightString(PAGE_WIDTH - MARGIN_RIGHT, 16, page_str)
        self.drawString(MARGIN_LEFT, 16, "Diet-Med (TDP) — Zalecenia pomocnicze. W razie wątpliwości skonsultuj się ze specjalistą.")

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
    story.append(Paragraph("Diet-Med — Test Doboru Produktów dla Zdrowia (TDP)", subtitle_style))
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

        cols_count = 3
        col_widths = [173, 173, 174]
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

        # Ścisłe, zweryfikowane szerokości kolumn (łącznie 523 pt robocze A4):
        # Produkt: 151 pt, Dopuszczalna porcja: 112 pt, Uwagi i komentarz: 260 pt
        col_widths = [151, 112, 260]

        umiark_header_style = ParagraphStyle(
            "UmiarkowaneHeader",
            parent=styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#92400e")
        )
        umiark_prod_style = ParagraphStyle(
            "UmiarkowaneProd",
            parent=styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=8.5,
            leading=11.5,
            textColor=colors.HexColor("#1e293b")
        )
        umiark_portion_style = ParagraphStyle(
            "UmiarkowanePortion",
            parent=styles["Normal"],
            fontName=FONT_NORMAL,
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#1e293b")
        )
        umiark_comm_style = ParagraphStyle(
            "UmiarkowaneComm",
            parent=styles["Normal"],
            fontName=FONT_NORMAL,
            fontSize=8.0,
            leading=10.5,
            textColor=colors.HexColor("#1e293b")
        )

        table_data = [[
            Paragraph("Produkt / Rodzaj", umiark_header_style),
            Paragraph("Dopuszczalna porcja", umiark_header_style),
            Paragraph("Uwagi i komentarz", umiark_header_style)
        ]]

        for p in umiarkowane:
            if p["ilosc"] is not None:
                qty_str = f"{float(p['ilosc']):g}"
                unit_str = p.get("jednostka") or ""
                porcja_str = f"{qty_str}{unit_str}"
            else:
                porcja_str = "w niewielkich ilościach"

            comm_str = " / ".join(p["komentarze"]) if p["komentarze"] else "—"
            table_data.append([
                Paragraph(p["rodzaj"], umiark_prod_style),
                Paragraph(porcja_str, umiark_portion_style),
                Paragraph(comm_str, umiark_comm_style)
            ])

        t_umiarkowane = Table(table_data, colWidths=col_widths, repeatRows=1)
        t_umiarkowane.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fef3c7")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#92400e")),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
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

        cols_count = 2
        col_widths = [261, 262]
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


import os
import re
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
    - Priorytet klasyfikacji: 'zakazane' (4) > 'ograniczone' (3) > 'dozwolone' (2) > 'zalecane' (1)
    - Gdy następuje zmiana klasyfikacji (new_score > existing_score):
      - poprzednie gramatury i komentarze są całkowicie wyczyszczone,
      - produkt przyjmuje wyłącznie gramaturę i komentarz ze statusu nadrzędnego.
    - Gdy nowy rekord ma niższy priorytet (new_score < existing_score):
      - jest całkowicie ignorowany (brak wycieku cech z niższego statusu do wyższego).
    - Gdy produkt zachowuje tę samą klasyfikację (new_score == existing_score):
      - gramatura: wybierana jest mniejsza ilość min(ilość_1, ilość_2)
      - komentarze: unikalne uwagi ze wszystkich dolegliwości o tym samym statusie są łączone bez powtórzeń.
    """
    merged = {}
    STATUS_PRIORITY = {
        "zalecane": 1,
        "dozwolone": 2,
        "ograniczone": 3,
        "zakazane": 4
    }

    for item in products_by_ailment:
        raw_name = item["rodzaj"].strip()
        clean_name = re.sub(r'^[•✓✔\*\-\.\s]+', '', raw_name).strip() or raw_name
        key = clean_name.lower()
        curr_status = item.get("status", "zalecane")

        qty = item.get("ilosc")
        unit = item.get("jednostka")
        raw_comm = item.get("komentarz")
        comm = raw_comm.strip() if (isinstance(raw_comm, str) and raw_comm.strip()) else None

        if key not in merged:
            merged[key] = {
                "rodzaj": clean_name,
                "status": curr_status,
                "ilosc": qty if curr_status != "zakazane" else None,
                "jednostka": unit if curr_status != "zakazane" else None,
                "komentarze": [comm] if comm else []
            }
        else:
            existing = merged[key]
            existing_score = STATUS_PRIORITY.get(existing["status"], 0)
            new_score = STATUS_PRIORITY.get(curr_status, 0)

            # 1. Wyższy priorytet zastępuje niższy -> zmiana klasyfikacji czyści stare cechy
            if new_score > existing_score:
                existing["status"] = curr_status
                existing["ilosc"] = qty if curr_status != "zakazane" else None
                existing["jednostka"] = unit if curr_status != "zakazane" else None
                existing["komentarze"] = [comm] if comm else []

            # 2. Ten sam status -> brak zmiany klasyfikacji, łączenie cech w ramach tej samej grupy
            elif new_score == existing_score:
                if curr_status != "zakazane":
                    old_qty = existing.get("ilosc")
                    if qty is not None and old_qty is not None:
                        try:
                            if float(qty) < float(old_qty):
                                existing["ilosc"] = qty
                                existing["jednostka"] = unit or existing.get("jednostka")
                        except (ValueError, TypeError):
                            pass
                    elif qty is not None and old_qty is None:
                        existing["ilosc"] = qty
                        existing["jednostka"] = unit

                if comm:
                    existing["komentarze"] = merge_comments(existing["komentarze"], comm)

            # 3. Niższy priorytet niż istniejący -> ignorujemy dane z niższego statusu
            else:
                pass

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
        self.drawString(MARGIN_LEFT, 16, "Diet-Med (TDP) — W razie wątpliwości skonsultuj się pod adresem poczta@diet-med.pl lub numerem telefonu +48 602 742 411.")

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

    h2_zalecane = ParagraphStyle(
        "H2Zalecane",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#065f46"),
        spaceBefore=14,
        spaceAfter=6
    )

    h2_dozwolone = ParagraphStyle(
        "H2Dozwolone",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0284c7"),
        spaceBefore=14,
        spaceAfter=6
    )

    h2_ograniczone = ParagraphStyle(
        "H2Ograniczone",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#b45309"),
        spaceBefore=14,
        spaceAfter=6
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

    cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName=FONT_NORMAL,
        fontSize=8.5,
        leading=11.5,
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
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=12))

    # Sekcja: Kategorie Produktów (objaśnienie 4 kategorii TDP)
    h2_legend_title = ParagraphStyle(
        "LegendTitle",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#1e3a8a"),
        spaceAfter=3
    )
    legend_desc_intro = ParagraphStyle(
        "LegendDescIntro",
        parent=styles["Normal"],
        fontName=FONT_NORMAL,
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#475569"),
        spaceAfter=6
    )
    legend_badge_zalecane = ParagraphStyle(
        "LegendBadgeZalecane",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#065f46")
    )
    legend_badge_dozwolone = ParagraphStyle(
        "LegendBadgeDozwolone",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0284c7")
    )
    legend_badge_ograniczone = ParagraphStyle(
        "LegendBadgeOgraniczone",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#b45309")
    )
    legend_badge_zakazane = ParagraphStyle(
        "LegendBadgeZakazane",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#991b1b")
    )
    legend_item_desc = ParagraphStyle(
        "LegendItemDesc",
        parent=styles["Normal"],
        fontName=FONT_NORMAL,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1e293b")
    )

    story.append(Paragraph("Kategorie Produktów", h2_legend_title))
    story.append(Paragraph(
        "Każdy produkt w systemie TDP klasyfikowany jest do jednej z 4 kategorii wg aktualnych zaleceń klinicznych:",
        legend_desc_intro
    ))

    legend_data = [
        [
            Paragraph("★ Zalecane", legend_badge_zalecane),
            Paragraph("Szczególnie rekomendowane składniki o udowodnionym korzystnym wpływie", legend_item_desc)
        ],
        [
            Paragraph("✓ Dozwolone", legend_badge_dozwolone),
            Paragraph("Bezpieczne składniki w codziennej diecie", legend_item_desc)
        ],
        [
            Paragraph("⚠️ Ograniczone", legend_badge_ograniczone),
            Paragraph("Dopuszczalne w wyznaczonych porcjach gramaturowych", legend_item_desc)
        ],
        [
            Paragraph("✕ Zakazane", legend_badge_zakazane),
            Paragraph("Produkty przeciwwskazane, do bezwzględnego wyeliminowania", legend_item_desc)
        ]
    ]
    t_legend = Table(legend_data, colWidths=[105, 418])
    t_legend.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ecfdf5")),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f0f9ff")),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#fffbeb")),
        ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#fef2f2")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
    ]))
    story.append(t_legend)
    story.append(Spacer(1, 14))

    # Podział produktów wg 4 kategorii w wymaganej kolejności: zalecane, dozwolone, ograniczone, zakazane
    zalecane = []
    dozwolone = []
    ograniczone = []
    zakazane = []

    for item in sorted(merged_products.values(), key=lambda x: x["rodzaj"].lower()):
        st = item["status"]
        if st == "zalecane":
            zalecane.append(item)
        elif st == "dozwolone":
            dozwolone.append(item)
        elif st == "ograniczone":
            ograniczone.append(item)
        elif st == "zakazane":
            zakazane.append(item)

    # 1. SEKCJA: PRODUKTY ZALECANE
    if zalecane:
        story.append(Paragraph("★ Produkty Zalecane (Szczególnie Rekomendowane)", h2_zalecane))
        story.append(Paragraph(
            "Produkty o udowodnionym korzystnym wpływie przy wskazanych dolegliwościach (najwyższa rekomendacja):",
            subtitle_style
        ))

        cols_count = 3
        col_widths = [173, 173, 174]
        table_data = []
        row = []
        for p in zalecane:
            text_p = p['rodzaj']
            details = []
            if p.get("ilosc") is not None:
                qty_s = f"{float(p['ilosc']):g}"
                u_s = p.get('jednostka') or ''
                details.append(f"{qty_s}{u_s}")
            if p.get("komentarze"):
                details.append(", ".join(p["komentarze"]))
            if details:
                text_p += f' <font color="#047857"><i>({" - ".join(details)})</i></font>'
            row.append(Paragraph(text_p, cell_style))
            if len(row) == cols_count:
                table_data.append(row)
                row = []
        if row:
            while len(row) < cols_count:
                row.append(Paragraph("", cell_style))
            table_data.append(row)

        t_zalecane = Table(table_data, colWidths=col_widths)
        t_zalecane.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#ecfdf5"), colors.white]),
        ]))
        story.append(t_zalecane)
        story.append(Spacer(1, 14))

    # 2. SEKCJA: PRODUKTY DOZWOLONE
    if dozwolone:
        if zalecane:
            story.append(PageBreak())
        story.append(Paragraph("✓ Produkty Dozwolone (Bezpieczne)", h2_dozwolone))
        story.append(Paragraph(
            "Produkty bezpieczne w codziennej diecie, niepowodujące zaostrzenia objawów:",
            subtitle_style
        ))

        cols_count = 3
        col_widths = [173, 173, 174]
        table_data = []
        row = []
        for p in dozwolone:
            text_p = p['rodzaj']
            details = []
            if p.get("ilosc") is not None:
                qty_s = f"{float(p['ilosc']):g}"
                u_s = p.get('jednostka') or ''
                details.append(f"{qty_s}{u_s}")
            if p.get("komentarze"):
                details.append(", ".join(p["komentarze"]))
            if details:
                text_p += f' <font color="#0284c7"><i>({" - ".join(details)})</i></font>'
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
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f0f9ff"), colors.white]),
        ]))
        story.append(t_dozwolone)
        story.append(Spacer(1, 14))

    # 3. SEKCJA: PRODUKTY OGRANICZONE
    if ograniczone:
        if zalecane or dozwolone:
            story.append(PageBreak())
        story.append(Paragraph("⚠️ Produkty Ograniczone (Dopuszczalne w wyznaczonych porcjach)", h2_ograniczone))
        story.append(Paragraph(
            "Poniższe produkty można spożywać wyłącznie z uwzględnieniem wskazanej gramatury/ilości oraz uwag dodatkowych:",
            subtitle_style
        ))

        cols_count = 3
        col_widths = [173, 173, 174]
        table_data = []
        row = []
        for p in ograniczone:
            text_p = p['rodzaj']
            details = []
            if p.get("ilosc") is not None:
                qty_s = f"{float(p['ilosc']):g}"
                u_s = p.get('jednostka') or ''
                details.append(f"{qty_s}{u_s}")
            if p.get("komentarze"):
                details.append(", ".join(p["komentarze"]))
            if details:
                text_p += f' <font color="#b45309"><i>({" - ".join(details)})</i></font>'
            row.append(Paragraph(text_p, cell_style))
            if len(row) == cols_count:
                table_data.append(row)
                row = []
        if row:
            while len(row) < cols_count:
                row.append(Paragraph("", cell_style))
            table_data.append(row)

        t_ograniczone = Table(table_data, colWidths=col_widths)
        t_ograniczone.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#fffbeb"), colors.white]),
        ]))
        story.append(t_ograniczone)
        story.append(Spacer(1, 14))

    # 4. SEKCJA: PRODUKTY ZAKAZANE
    if zakazane:
        if zalecane or dozwolone or ograniczone:
            story.append(PageBreak())
        story.append(Paragraph("✕ Produkty Przeciwwskazane (Zakazane)", h2_zakazane))
        story.append(Paragraph(
            "Tych produktów należy bezwzględnie unikać przy wskazanych dolegliwościach:",
            subtitle_style
        ))

        cols_count = 3
        col_widths = [173, 173, 174]
        table_data = []
        row = []
        for p in zakazane:
            text_p = p['rodzaj']
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
        "W razie wątpliwości skonsultuj się pod adresem poczta@diet-med.pl lub numerem telefonu +48 602 742 411.",
        footer_style
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    return output_filepath


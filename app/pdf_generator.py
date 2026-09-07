import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

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
      - komentarz odrobinę oddzielony
      - jeśli obie dolegliwości mają 'umiarkowane' -> bierzemy mniejszą ilość
      - jeśli komentarze takie same -> jeden, jeśli różne -> oba dołączone
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
                "ilosc": item.get("ilosc"),
                "jednostka": item.get("jednostka"),
                "komentarze": [item.get("komentarz")] if item.get("komentarz") else []
            }
        else:
            existing = merged[key]
            existing_score = STATUS_PRIORITY.get(existing["status"], 0)
            new_score = STATUS_PRIORITY.get(curr_status, 0)

            # Wyższy priorytet zastępuje niższy
            if new_score > existing_score:
                existing["status"] = curr_status
                existing["ilosc"] = item.get("ilosc")
                existing["jednostka"] = item.get("jednostka")
                existing["komentarze"] = [item.get("komentarz")] if item.get("komentarz") else []
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

                # Łączenie komentarzy
                new_comm = item.get("komentarz")
                if new_comm:
                    # Sprawdzamy czy taki komentarz już istnieje
                    norm_existing = [c.strip().lower() for c in existing["komentarze"]]
                    if new_comm.strip().lower() not in norm_existing:
                        existing["komentarze"].append(new_comm.strip())

    return merged


def generate_restrictions_pdf(
    email: str,
    selected_ailments: list[str],
    merged_products: dict,
    output_filepath: str
) -> str:
    """
    Generuje elegancki plik PDF z ograniczeniami żywieniowymi: 'ograniczenia zywieniowe.pdf'
    """
    doc = SimpleDocTemplate(
        output_filepath,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
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
    story.append(Paragraph("Diet-Med • Test Doboru Produktów dla Zdrowia", subtitle_style))
    story.append(Paragraph("Ograniczenia Żywieniowe", title_style))
    story.append(Paragraph(
        f"<b>Raport indywidualny dla:</b> {email} &nbsp;|&nbsp; "
        f"<b>Data:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}<br/>"
        f"<b>Wskazane dolegliwości:</b> {', '.join(selected_ailments) if selected_ailments else 'Brak'}",
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

    # 1. SEK CJA: PRODUKTY OGRANICZONE (UMIARKOWANE)
    if umiarkowane:
        story.append(Paragraph("⚠️ Produkty Ograniczone (Dopuszczalne w wyznaczonych porcjach)", h2_umiarkowane))
        story.append(Paragraph(
            "Poniższe produkty można spożywać wyłącznie z uwzględnieniem wskazanej gramatury/ilości oraz uwag dodatkowych:",
            subtitle_style
        ))
        
        table_data = [[
            Paragraph("<b>Produkt / Rodzaj</b>", cell_bold),
            Paragraph("<b>Dopuszczalna porcja</b>", cell_bold),
            Paragraph("<b>Uwagi i komentarz</b>", cell_bold)
        ]]

        for p in umiarkowane:
            # Ilość i jednostki razem bez spacji, np. 135g, 2plasterki
            if p["ilosc"] is not None:
                # Usunięcie zbędnego .0 w liczbach całkowitych
                qty_str = f"{float(p['ilosc']):g}"
                unit_str = p.get("jednostka") or ""
                porcja_str = f"{qty_str}{unit_str}"
            else:
                porcja_str = "w niewielkich ilościach"

            comm_str = " / ".join(p["komentarze"]) if p["komentarze"] else "—"

            table_data.append([
                Paragraph(p["rodzaj"], cell_bold),
                Paragraph(porcja_str, cell_style),
                Paragraph(comm_str, cell_style)
            ])

        t_umiarkowane = Table(table_data, colWidths=[200, 110, 210])
        t_umiarkowane.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fef3c7")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#92400e")),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#fde68a")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fffbeb")]),
        ]))
        story.append(t_umiarkowane)
        story.append(Spacer(1, 14))

    # 2. SEKCJA: PRODUKTY ZAKAZANE
    if zakazane:
        story.append(Paragraph("⛔ Produkty Przeciwwskazane (Zakazane)", h2_zakazane))
        story.append(Paragraph(
            "Tych produktów należy bezwzględnie unikać przy wskazanych dolegliwościach:",
            subtitle_style
        ))
        
        # Prezentacja w dwóch kolumnach dla oszczędności miejsca i czytelności
        cols_count = 2
        table_data = []
        row = []
        for p in zakazane:
            row.append(Paragraph(f"• {p['rodzaj']}", cell_style))
            if len(row) == cols_count:
                table_data.append(row)
                row = []
        if row:
            while len(row) < cols_count:
                row.append(Paragraph("", cell_style))
            table_data.append(row)

        t_zakazane = Table(table_data, colWidths=[260, 260])
        t_zakazane.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#fef2f2"), colors.white]),
        ]))
        story.append(t_zakazane)
        story.append(Spacer(1, 14))

    # 3. SEKCJA: PRODUKTY DOZWOLONE
    if dozwolone:
        story.append(Paragraph("✅ Produkty Dozwolone (Bezpieczne)", h2_dozwolone))
        story.append(Paragraph(
            "Produkty w pełni rekomendowane w diecie:",
            subtitle_style
        ))
        
        cols_count = 3
        table_data = []
        row = []
        for p in dozwolone:
            row.append(Paragraph(f"✓ {p['rodzaj']}", cell_style))
            if len(row) == cols_count:
                table_data.append(row)
                row = []
        if row:
            while len(row) < cols_count:
                row.append(Paragraph("", cell_style))
            table_data.append(row)

        t_dozwolone = Table(table_data, colWidths=[173, 173, 174])
        t_dozwolone.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f0fdf4"), colors.white]),
        ]))
        story.append(t_dozwolone)
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

    doc.build(story)
    return output_filepath

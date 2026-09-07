import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from app.config import settings

logger = logging.getLogger("diet_med.email")

EMAIL_BODY_TEMPLATE = """Szanowni Państwo,

Dziękujemy za wypełnienie Testu Doboru Produktów dla Zdrowia (TDP).

W oparciu o wskazane przez Państwa problemy zdrowotne przygotowaliśmy spersonalizowaną listę ograniczeń żywieniowych, uwzględniającą zasady doboru produktów oraz wzajemne wykluczenia.

W załączniku do niniejszej wiadomości przesyłamy Państwa indywidualne podsumowanie w formacie PDF: „ograniczenia zywieniowe.pdf”.

W razie jakichkolwiek pytań lub potrzeby dalszych konsultacji dietetycznych, serdecznie zapraszamy do kontaktu.

Życzymy dużo zdrowia i pomyślności!

Z poważaniem,
Zespół Diet-Med
"""

def send_email_with_pdf(to_email: str, pdf_path: str, filename: str = "ograniczenia zywieniowe.pdf") -> bool:
    """
    Wysyła wiadomość e-mail z załącznikiem PDF na podany adres e-mail.
    Jeśli dane SMTP nie są skonfigurowane, loguje informację i zapisuje plik lokalnie.
    """
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        logger.info(
            f"[DEV MODE] Serwer SMTP nie jest skonfigurowany. "
            f"Symulacja wysyłki maila do {to_email} z załącznikiem {pdf_path}. "
            f"Plik PDF jest dostępny lokalnie."
        )
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to_email
        msg["Subject"] = "Twoje indywidualne ograniczenia żywieniowe • Diet-Med TDP"

        msg.attach(MIMEText(EMAIL_BODY_TEMPLATE, "plain", "utf-8"))

        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                pdf_attachment = MIMEApplication(f.read(), _subtype="pdf")
                pdf_attachment.add_header(
                    "Content-Disposition",
                    f'attachment; filename="{filename}"'
                )
                msg.attach(pdf_attachment)
        else:
            logger.error(f"Plik PDF {pdf_path} nie istnieje!")
            return False

        # Nawiązanie połączenia SMTP
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
        if settings.SMTP_USE_TLS:
            server.starttls()
        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            
        server.send_message(msg)
        server.quit()
        logger.info(f"Pomyślnie wysłano e-mail z PDF do: {to_email}")
        return True

    except Exception as e:
        logger.error(f"Błąd podczas wysyłania wiadomości e-mail do {to_email}: {e}")
        return False

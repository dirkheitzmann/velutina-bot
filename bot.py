import os
import time
import smtplib
from email.message import EmailMessage
from datetime import datetime
import requests
from fastapi import FastAPI, Request, Response
from dotenv import load_dotenv
from pathlib import Path
import traceback

# .env-Datei zuverlässig aus dem gleichen Ordner wie bot.py laden
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)
#load_dotenv()

app = FastAPI()

# Basis-URL sicher zusammensetzen
GRAPH_BASE = "https://graph.facebook.com/v21.0"

# Konfiguration laden
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY")
ROBOFLOW_MODEL_URL = os.getenv("ROBOFLOW_MODEL_URL")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO")

IMAGE_DIR = os.path.expanduser("~/velutina-bot/bilder")
os.makedirs(IMAGE_DIR, exist_ok=True)

# Zwischenspeicher für laufende Meldungen (Telefonnummer -> letzter Fund)
active_reports = {}

@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == VERIFY_TOKEN:
        return Response(content=params.get("hub.challenge"), media_type="text/plain")
    return Response(status_code=403)

@app.post("/webhook")
async def handle_webhook(request: Request):
    data = await request.json()
    try:
        value = data["entry"][0]["changes"][0]["value"]
        if "messages" not in value:
            return {"status": "no_message"}

        message = value["messages"][0]
        sender = message["from"]
        msg_type = message["type"]

        # FALL 1: Ein Foto wurde gesendet
        if msg_type == "image":
            media_id = message["image"]["id"]
            caption = message["image"].get("caption", "")
            image_bytes = download_whatsapp_media(media_id)

            # Bild lokal sichern
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(IMAGE_DIR, f"{timestamp}_{sender}.jpg")
            with open(filepath, "wb") as f:
                f.write(image_bytes)

            # KI-Prüfung durchführen
            predictions = check_veludetect(image_bytes)
            is_velutina, detected_class, confidence = analyze_hits(predictions)

            # Meldung im Speicher ablegen, um auf Standort-Pin zu warten
            active_reports[sender] = {
                "timestamp": time.time(),
                "filepath": filepath,
                "is_velutina": is_velutina,
                "detected_class": detected_class,
                "confidence": confidence,
                "caption": caption,
                "alert_sent": False
            }

            if is_velutina:
                send_whatsapp_text(
                    sender,
                    f"⚠️ *Verdacht auf Asiatische Hornisse* ({confidence} % Sicherheit).\n\n"
                    "Bitte senden Sie uns jetzt noch Ihren *Standort* (unten auf das Plus/Büroklammer-Symbol tippen -> *Standort* -> *Aktuellen Standort senden*) "
                    "und schreiben Sie kurz, ob Sie ein einzelnes Tier oder ein Nest gesehen haben."
                )
            else:
                send_whatsapp_text(
                    sender,
                    f"Vielen Dank für Ihr Foto! Unsere erste KI-Prüfung stuft das Tier als *{detected_class}* ({confidence} % Sicherheit) ein.\n\n"
                    "Falls Sie dennoch unsicher sind, senden Sie uns gerne noch Ihren Standort, damit ein Fachberater drüberschauen kann."
                )
                # Bei Nicht-Velutina direkt leise dokumentieren/weiterleiten
                notify_experts(sender, active_reports[sender], location=None)
                active_reports[sender]["alert_sent"] = True

        # FALL 2: Ein Standort-Pin wurde gesendet
        elif msg_type == "location":
            loc = message["location"]
            lat = loc["latitude"]
            lon = loc["longitude"]
            address = loc.get("address", "")
            maps_link = f"https://google.com{lat},{lon}"

            report = active_reports.get(sender)
            # Prüfen, ob in den letzten 30 Minuten ein Bild von dieser Nummer kam
            if report and (time.time() - report["timestamp"] < 1800):
                send_whatsapp_text(
                    sender,
                    "✅ Vielen Dank! Wir haben Ihren Standort zusammen mit dem Foto an unsere Fachberater weitergeleitet. "
                    "Bei Rückfragen melden wir uns unter dieser Nummer bei Ihnen."
                )
                notify_experts(sender, report, location={"lat": lat, "lon": lon, "address": address, "url": maps_link})
                report["alert_sent"] = True
            else:
                send_whatsapp_text(
                    sender,
                    "Vielen Dank für den Standort! Bitte senden Sie uns jetzt noch ein möglichst scharfes Foto des Insekts oder Nests dazu."
                )

        # FALL 3: Zusätzlicher Text (z. B. "Nest im Apfelbaum")
        elif msg_type == "text":
            text_body = message["text"]["body"]
            report = active_reports.get(sender)
            if report and (time.time() - report["timestamp"] < 1800):
                report["caption"] += f" | Zusatzinfo: {text_body}"
                send_whatsapp_text(sender, "Danke für die Zusatzinfo! Wir haben den Hinweis Ihrer Meldung hinzugefügt.")
                # Falls der Alarm wegen fehlendem Standort noch nicht rausging, jetzt senden
                if not report["alert_sent"]:
                    notify_experts(sender, report, location=None)
                    report["alert_sent"] = True
            else:
                send_whatsapp_text(
                    sender,
                    "Willkommen bei der Hornissen-Meldestelle des Imkervereins! 🐝\n"
                    "Bitte senden Sie uns ein *Foto* des Tieres oder Nests sowie anschließend Ihren *Standort*."
                )

    except Exception as e:
        traceback.print_exc()
        print(f"Webhook-Fehler: {e}")

    return {"status": "ok"}

def download_whatsapp_media(media_id: str) -> bytes:
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    info_url = f"{GRAPH_BASE}/{media_id}"
    print(f"[LOG] Rufe Media-Info URL auf: {info_url}", flush=True)

    res_info = requests.get(info_url, headers=headers, timeout=15).json()
    if "url" not in res_info:
        print(f"[FEHLER] Keine Media-URL von Meta erhalten: {res_info}", flush=True)
        raise ValueError("Media-URL fehlt in Meta-Antwort")

    media_url = res_info["url"]
    print(f"[LOG] Lade Bild herunter von: {media_url}", flush=True)
    res_media = requests.get(media_url, headers=headers, timeout=20)
    return res_media.content

def check_veludetect(image_bytes: bytes) -> list:
    print(f"[LOG] Sende Bild an Roboflow-Modell: {ROBOFLOW_MODEL_URL}", flush=True)
    response = requests.post(
        ROBOFLOW_MODEL_URL,
        params={"api_key": ROBOFLOW_API_KEY, "confidence": 40},
        files={"file": ("hornisse.jpg", image_bytes, "image/jpeg")},
        timeout=20
    )
    if response.status_code >= 400:
        print(f"[FEHLER] Roboflow ({response.status_code}): {response.text}", flush=True)
        return []
    return response.json().get("predictions", [])

def analyze_hits(predictions: list):
    if not predictions:
        return False, "Unbekannt / Kein Insekt erkannt", 0
    top_hit = max(predictions, key=lambda x: x["confidence"])
    detected_class = top_hit["class"]
    confidence = round(top_hit["confidence"] * 100)
    is_velutina = "velutina" in detected_class.lower()
    return is_velutina, detected_class, confidence

def send_whatsapp_text(to_phone: str, text: str):
    url = f"{GRAPH_BASE}/{PHONE_NUMBER_ID}/messages"
    print(f"[LOG] Sende WhatsApp-Nachricht an URL: {url}", flush=True)

    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": text}
    }
    res = requests.post(url, headers=headers, json=payload, timeout=15)
    print(f"[LOG] Meta-Antwort ({res.status_code}): {res.text}", flush=True)

def notify_experts(sender: str, report: dict, location: dict | None):
    status_emoji = "🚨 VELUTINA-VERDACHT" if report["is_velutina"] else "ℹ️ Sichtung (Entwarnung/Prüfung)"
    loc_text = f"{location['url']} ({location['address']})" if location else "Noch kein Standort-Pin gesendet"
    
    summary = (
        f"{status_emoji}\n"
        f"Melder: +{sender}\n"
        f"KI-Ergebnis: {report['detected_class']} ({report['confidence']} %)\n"
        f"Text/Info: {report['caption'] or 'Keine'}\n"
        f"Standort: {loc_text}"
    )

    # 1. Telegram senden (falls konfiguriert)
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            tg_url = f"https://telegram.org{TELEGRAM_BOT_TOKEN}/sendPhoto"
            with open(report["filepath"], "rb") as img:
                requests.post(
                    tg_url,
                    data={"chat_id": TELEGRAM_CHAT_ID, "caption": summary},
                    files={"photo": img}
                )
        except Exception as e:
            print(f"Telegram-Fehler: {e}")

    # 2. E-Mail senden (falls konfiguriert)
    if SMTP_SERVER and ALERT_EMAIL_TO:
        try:
            msg = EmailMessage()
            msg["Subject"] = f"[{status_emoji}] Hornissenmeldung +{sender}"
            msg["From"] = SMTP_USER
            msg["To"] = ALERT_EMAIL_TO
            msg.set_content(summary)

            with open(report["filepath"], "rb") as img:
                msg.add_attachment(img.read(), maintype="image", subtype="jpeg", filename=os.path.basename(report["filepath"]))

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
        except Exception as e:
            print(f"E-Mail-Fehler: {e}")


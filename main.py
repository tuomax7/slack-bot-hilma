import requests
from datetime import datetime, timezone
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv
import ssl
import certifi

ssl_context = ssl.create_default_context(cafile=certifi.where())

# Load API keys and config from environment variables (no dotenv here)
API_KEY = os.getenv("HANKINTA_API_KEY")
SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")

client = WebClient(token=SLACK_TOKEN)

SEARCH_TERMS = [
    "sovellus", "web-sovellus", "mobiilisovellus", "digipalvelu",
    "ohjelmisto", "software", "application", "web application",
    "mobile app", "digital service"
]

API_URL = "https://api.hankintailmoitukset.fi/avp/eformnotices/docs/search"

HEADERS = {
    "Content-Type": "application/json",
    "Cache-Control": "no-cache",
    "Ocp-Apim-Subscription-Key": API_KEY
}


def fetch_procurements():
    search_query = " OR ".join(SEARCH_TERMS)
    body = {
        "search": search_query,
        "top": "1000",
        "count": "true",
        "searchMode": "any",
        "orderby": "datePublished desc"
    }

    try:
        response = requests.post(API_URL, json=body, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"API request failed: {e}")
        return None


def filter_fields(data):
    filtered = []
    skipped = 0

    for item in data.get("value", []):
        if (
            item.get("mainType") == "ContractAwardNotices"
            or item.get("procurementTypeCode") != "services"
        ):
            skipped += 1
            continue

        title = item.get("titleFi")
        org = item.get("organisationNameFi")
        desc = item.get("descriptionFi")
        procedure_id = item.get("procedureId")
        notice_id = item.get("noticeId")

        if title and org and desc and procedure_id and notice_id:
            filtered.append({
                "datePublished": item.get("datePublished"),
                "titleFi": title,
                "organisationNameFi": org,
                "descriptionFi": desc,
                "deadline": item.get("deadline"),
                "procedureId": procedure_id,
                "noticeId": notice_id,
                "estimatedValue": item.get("estimatedValue")  # new field
            })
        else:
            skipped += 1

    print(f"Filtered {len(filtered)} valid service offers, skipped {skipped}.")
    return filtered


def format_date_fi(date_str):
    if not date_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y")
    except Exception:
        return date_str[:10]  # fallback


def format_message(offers):
    if not offers:
        return "_Ei löydetty uusia tarjouksia._"

    message_lines = []
    for i, offer in enumerate(offers[:5], start=1):
        link = f"https://www.hankintailmoitukset.fi/fi/public/procedure/{offer['procedureId']}/enotice/{offer['noticeId']}/"
        est_val_str = f"*Arvioitu arvo:* {offer['estimatedValue']:,.2f} €\n" if offer.get("estimatedValue") else ""
        
        message_lines.append(
            f"*{i}. <{link}|{offer['titleFi']}>*\n"
            f"> *Organisaatio:* {offer['organisationNameFi']}\n"
            f"> *Julkaistu:* {format_date_fi(offer['datePublished'])}\n"
            f"> *Deadline:* {format_date_fi(offer['deadline'])}\n"
            f"> {est_val_str}"
        )
        desc_preview = offer['descriptionFi'][:300] + ("..." if len(offer['descriptionFi']) > 300 else "")
        message_lines.append(desc_preview)

        # Add divider after each offer except the last one
        if i < len(offers[:5]):
            message_lines.append("──────────")  # Unicode heavy line as divider

    return "\n\n".join(message_lines)


def send_to_slack(message):
    try:
        response = client.chat_postMessage(
            channel=CHANNEL_ID,
            text=f":mag: *Eilisen tarjouskatsaus ({datetime.now(timezone.utc).strftime('%d.%m.%Y')})*\n\n{message}"
        )
        print(f"Message sent: {response['ts']}")
    except SlackApiError as e:
        print(f"Slack API error: {e.response['error']}")


def job():
    data = fetch_procurements()
    if data is None:
        message = "Hilma-tarjousten hakeminen epäonnistui."
    else:
        filtered_data = filter_fields(data)

        if len(filtered_data) >= 3:
            message = format_message(filtered_data[:5])
        elif filtered_data:
            message = format_message(filtered_data)
        else:
            message = "_Alle 3 kelvollista palvelutarjousilmoitusta tänään._"

    send_to_slack(message)


# Cloud Function entry point
def run_daily_procurements(event, context):
    job()

import requests
from datetime import datetime, timezone, timedelta
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import ssl
import certifi

# Load dotenv only if run locally
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

ssl_context = ssl.create_default_context(cafile=certifi.where())

# Load API keys and configs
API_KEY = os.getenv("PRIMARY_API_KEY")
SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")

client = WebClient(token=SLACK_TOKEN)
API_URL = "https://api.hankintailmoitukset.fi/avp/eformnotices/docs/search"

HEADERS = {
    "Content-Type": "application/json",
    "Cache-Control": "no-cache",
    "Ocp-Apim-Subscription-Key": API_KEY
}

today = datetime.now(timezone.utc).date()
yesterday = today - timedelta(days=1)

# User configurable configs

MESSAGE_NOTICE_LIMIT = 5

SEARCH_TERMS = [
    "sovelluskehitys", "ohjelmistokehitys", "web-sovellus", "mobiilisovellus",
    "digipalvelu", "verkkopalvelu", "järjestelmäkehitys", "palvelumuotoilu",
    "käytettävyystutkimus", "UX", "UI", "käyttöliittymäsuunnittelu", 
    "käyttäjäkokemussuunnittelu", "design sprint", "strateginen muotoilu", "pilvipalvelu", "pilviarkkitehtuuri", "DevOps",
    "Google Cloud", "AWS", "Azure", "tekoäly", "koneoppiminen", 
    "AI", "machine learning", "TensorFlow", "React", "React Native",
]

# TODO: add configs for CPV codes, region filters, notice mainTypes and description text cutoff length

def fetch_procurements():
    
    search_query =  "(" + " OR ".join(SEARCH_TERMS) + ")" + "cpvCodes:(48* OR 72*)"

    date_from = f"{yesterday.isoformat()}T00:00:00.000Z"
    date_to = f"{yesterday.isoformat()}T23:59:00.000Z"
    expiration_date = f"{today.isoformat()}T23:59:00.000Z"

    date_filter = f'datePublished ge {date_from} and datePublished lt {date_to} and expirationDate ge {expiration_date}'
    
    notice_type_filter = "search.in(mainType, 'ContractNotices|NationalNotices|PriorInformationNotices', '|')"

    body = {
        "search": search_query,
        "filter": notice_type_filter + " and " + date_filter,
        "count": "true",
        "searchMode": "any",
    }

    try:
        response = requests.post(API_URL, json=body, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"API request failed: {e}")
        return None


def filter_fields(data):
    valid_notices = []

    for item in data.get("value", []):

        valid_notices.append({
        	"datePublished": item.get("datePublished"),
        	"title": item.get("titleFi") or item.get("titleEn") or item.get("titleSv"),
        	"organisationName": item.get("organisationNameFi") or item.get("organisationNameEn") or item.get("organisationNameSv"),
        	"description": item.get("descriptionFi") or item.get("descriptionEn") or item.get("descriptionSv"),
        	"deadline": item.get("deadline"),
        	"procedureId": item.get("procedureId"),
        	"noticeId": item.get("noticeId"),
        	"estimatedValue": item.get("estimatedValue"),
        	"searchScore": item.get("@search.score")
        })


    print(f"LOG: Found {len(valid_notices)} valid procurement notices.")
    return valid_notices


def format_date_fi(date_str):
    if not date_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y")
    except Exception:
        return date_str[:10]


def format_message(offers):

    message_lines = []
    for i, offer in enumerate(offers[:MESSAGE_NOTICE_LIMIT], start=1):
        link = f"https://www.hankintailmoitukset.fi/fi/public/procedure/{offer['procedureId']}/enotice/{offer['noticeId']}/"
        
        est_val_str = f"*Arvo:* {offer['estimatedValue']:,.2f} €\n" if offer.get("estimatedValue") else ""
        
        message_lines.append(
            f"*{i}. <{link}|{offer['title']}>*\n"
            f"> *Sopivuuspisteet:* {round(offer['searchScore'])}\n"
            f"> *Organisaatio:* {offer['organisationName']}\n"
            f"> *Julkaistu:* {format_date_fi(offer['datePublished'])}\n"
            f"> *Deadline:* {format_date_fi(offer['deadline'])}\n"
            f"> {est_val_str}"
        )
        
        desc_preview = offer['description'][:300] + ("..." if len(offer['description']) > 300 else "")
        message_lines.append(desc_preview + "\n\n")

    message_lines.append("──────────────────\n\n")

    return "\n".join(message_lines)


def send_to_slack(message):
    try:
        response = client.chat_postMessage(
            channel=CHANNEL_ID,
            text=f":mag: *Eilisen hankintailmoituskatsaus ({yesterday.strftime('%d.%m.%Y')})*\n\n{message}"
        )
        print("LOG: Message sent succesfully!")
    except SlackApiError as e:
        print(f"Slack API error: {e.response['error']}")


def job():
    data = fetch_procurements()
    if data is None:
        message = "Hilma-hankintailmoitusten hakeminen epäonnistui."
    else:
        filtered_data = filter_fields(data)
        sorted_data = sorted(filtered_data, key=lambda x: x["searchScore"], reverse=True)

        if len(filtered_data) >= 1:
            message = format_message(sorted_data[:MESSAGE_NOTICE_LIMIT])
        else:
            message = "_0 eilen julkaistua hankintailmoitusta löydetty._"

    send_to_slack(message)


def run_daily_procurements(event, context):
    job()


if __name__ == "__main__":
    job()

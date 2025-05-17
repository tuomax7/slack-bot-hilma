# Hilma Procurement Slack Bot

This Slack bot function fetches procurement and project notices related to digital services from the [Hilma AVP API](https://hns-hilma-prod-apim.developer.azure-api.net/) (Finnish procurement system for the public sector) and posts a concise summary of posted relevant procurement notices to a Slack channel.

## Configuration and search options

`main.py` defines all of the procurement API search logic. The following search configuration values can be set to define what type of procurement notices are searched for.

- `SEARCH_TERMS`: an array that includes all search strings, such as: 'software', 'application', etc.
- `COUNT`: maximum number of procurement notices sent to user
- `PROCUREMENT_TYPE_CODE`: what type of procurement notices are looked for, e.g. 'services'

---

## How to create your own Slack Procurement Bot

### 1. Create your Slack Bot

1. Follow the instructions at [Create an app (from scratch)](https://api.slack.com/) to create a Slack bot.
2. Add the bot to your workspace and give the bot `chat:write` permissions
3. Navigate to settings under **OAuth & Permission** and store the `Bot User OAuth Token` securely for later use
4. At this point you can also choose which Slack channel you want to add the bot to and view **Channel details** in Slack to copy the `Channel ID` for later use

### 2. Sign up for the Hilma API

1. Sign up for the [Hilma API](https://hns-hilma-prod-apim.developer.azure-api.net/) for free.
2. Create subscription for the **Search** API product at [avp-read API product page](https://hns-hilma-prod-apim.developer.azure-api.net/product#product=avp-read)
3. Save the API primary key you received securely

### 3. Clone the repo

```bash
git clone https://github.com/tuomax7/slack-bot-hilma.git
cd slack-bot-hilma
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Create a .env file (for manual testing)

Create a `.env` file in the project root with the following contents for running the bot locally:

```bash
PRIMARY_API_KEY=your_hilma_api_primary_key
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
SLACK_CHANNEL_ID=your-slack-channel-id
```

### 6. Test running the bot locally

Simply run the Python file and check the Slack channel to see a message from the Slack bot.

```bash
python main.py
```

## Deployment (Cloud Function)

This bot is designed to be deployed as a scheduled cloud function (e.g., Google Cloud Functions or AWS Lambda).

Here is an example of how to deploy to a Google Cloud Run Function using the `gcloud` CLI.

### 1. Deploy the cloud function

```bash
gcloud functions deploy run_daily_procurements \
--runtime python312 \
--trigger-topic procurements-topic \
--entry-point run_daily_procurements \
--timeout 540 \
--set-env-vars
PRIMARY_API_KEY="XXX",SLACK_BOT_TOKEN="YYY",SLACK_CHANNEL_ID="ZZZ"
```

### 2. Create a Cloud PubSub-topic

```bash
gcloud pubsub topics create procurements-topic
```

### 3. Create a Cloud Scheduler job

Set the `--schedule` option to the specify how often should the bot run and send a Slack message. Use [unix-cron-formatting](https://www.ibm.com/docs/en/db2/11.5.x?topic=task-unix-cron-format). The example below runs at 06:00 UTC time every day Mon - Sun.

```bash
gcloud scheduler jobs create pubsub procurements-job \
  --schedule="0 6 * * *" \
  --topic=procurements-topic \
  --message-body="run" \
  --location="us-central1"
```

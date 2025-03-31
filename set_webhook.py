# set_webhook.py
from telegram import Bot

TOKEN = "7730083251:AAHBcvHlFU-vvYFDsuwBALK3iNtMA9Il0Hc"
WEBHOOK_URL = "https://your-cloud-run-url/webhook"

bot = Bot(token=TOKEN)
bot.set_webhook(url=WEBHOOK_URL)

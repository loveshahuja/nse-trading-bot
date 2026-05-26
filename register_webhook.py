# Run this ONCE after Render deployment to register webhook with Telegram
import requests
import os

BOT_TOKEN = os.environ.get('TELEGRAM_TOKEN')
RENDER_URL = os.environ.get('RENDER_URL')  # e.g. https://lovesh-trading-bot.onrender.com

webhook_url = f"{RENDER_URL}/webhook"
api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"

r = requests.post(api_url, json={"url": webhook_url})
print(f"Status: {r.status_code}")
print(f"Response: {r.json()}")

# Verify
r2 = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo")
print(f"\nWebhook info: {r2.json()}")

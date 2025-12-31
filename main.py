import os
import requests
from datetime import datetime
import pytz

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise RuntimeError("Secrets missing")

IST = pytz.timezone("Asia/Kolkata")
now = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
r = requests.post(url, json={
    "chat_id": CHAT_ID,
    "text": f"✅ GitHub Actions test message\n{now} IST"
})

print(r.text)

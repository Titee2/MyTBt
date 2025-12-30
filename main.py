# ==========================================================
# AI TREND NAVIGATOR — TELEGRAM ALERT BOT
# CLOUD / HEROKU READY
# ==========================================================

import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime
import os

# =========================
# TELEGRAM CONFIG
# =========================
BOT_TOKEN = "PUT_YOUR_BOT_TOKEN_HERE"
CHAT_ID = "PUT_YOUR_CHAT_ID_HERE"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg}
    requests.post(url, json=payload, timeout=10)

# =========================
# STRATEGY CONFIG
# =========================
TIMEFRAME = "1h"
PRICE_LEN = 5
TARGET_LEN = 5
NUM_CLOSEST = 3
SCAN_INTERVAL = 60

CSV_FILE = "ai_trend_navigator_log.csv"
BINANCE = "https://api.binance.com"

# =========================
# CSV INIT
# =========================
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w") as f:
        f.write("Time,Symbol,Signal,knnMA\n")

# =========================
# DATA
# =========================
def top_25():
    data = requests.get(f"{BINANCE}/api/v3/ticker/24hr").json()
    usdt = [x for x in data if x["symbol"].endswith("USDT")]
    usdt.sort(key=lambda x: float(x["quoteVolume"]), reverse=True)
    return [x["symbol"] for x in usdt[:25]]

def klines(symbol):
    r = requests.get(f"{BINANCE}/api/v3/klines", params={
        "symbol": symbol,
        "interval": TIMEFRAME,
        "limit": 200
    }).json()

    df = pd.DataFrame(r, columns=[
        "ot","o","h","l","c","v",
        "ct","q","n","tbb","tbq","ig"
    ])
    df[["h","l","c"]] = df[["h","l","c"]].astype(float)
    return df

# =========================
# INDICATOR CORE
# =========================
def mean_of_k_closest(value, target, k):
    window = max(k, 30)
    out = np.full(len(value), np.nan)

    for i in range(window, len(value)):
        distances = np.abs(value[i-window:i] - target[i])
        idx = np.argsort(distances)[:k]
        out[i] = value[i-window:i][idx].mean()

    return out

def wma(series, length):
    w = np.arange(1, length + 1)
    return series.rolling(length).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)

# =========================
# MAIN LOOP
# =========================
last_state = {}

send_telegram("✅ AI Trend Navigator bot started")

while True:
    try:
        for sym in top_25():
            df = klines(sym)

            hl2 = (df["h"] + df["l"]) / 2
            value_in = hl2.rolling(PRICE_LEN).mean()
            target = df["c"].rolling(TARGET_LEN).mean()

            knnMA = mean_of_k_closest(value_in.values, target.values, NUM_CLOSEST)
            knnMA = pd.Series(knnMA)
            knnMA_ = wma(knnMA, 5)

            a, b, c = knnMA_.iloc[-3], knnMA_.iloc[-2], knnMA_.iloc[-1]
            if np.isnan([a,b,c]).any():
                continue

            switch_up = b < c and b <= a
            switch_dn = b > c and b >= a

            prev = last_state.get(sym)

            if switch_up and prev != "GREEN":
                msg = f"🟢 BUY\n{sym}\nknnMA: {round(c,6)}\nTF: 1H\n{datetime.utcnow()}"
                send_telegram(msg)
                last_state[sym] = "GREEN"

            elif switch_dn and prev != "RED":
                msg = f"🔴 SELL\n{sym}\nknnMA: {round(c,6)}\nTF: 1H\n{datetime.utcnow()}"
                send_telegram(msg)
                last_state[sym] = "RED"

        time.sleep(SCAN_INTERVAL)

    except Exception as e:
        send_telegram(f"⚠️ ERROR: {str(e)}")
        time.sleep(60)

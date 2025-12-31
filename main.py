# ==========================================================
# AI TREND NAVIGATOR — TELEGRAM ALERT BOT
# REPLIT / CLOUD READY (NO REPAINT)
# IST TIME + SL / TP ADDED
# ==========================================================

import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime, timezone, timedelta
import os

# =========================
# TELEGRAM CONFIG (ENV VARS)
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise RuntimeError("❌ BOT_TOKEN or CHAT_ID not set in environment variables")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg}
    requests.post(url, json=payload, timeout=10)

# =========================
# IST TIMEZONE
# =========================
IST = timezone(timedelta(hours=5, minutes=30))

def now_ist():
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")

# =========================
# STRATEGY CONFIG
# =========================
TIMEFRAME = "1h"
PRICE_LEN = 5
TARGET_LEN = 5
NUM_CLOSEST = 3
SCAN_INTERVAL = 60  # seconds

CSV_FILE = "ai_trend_navigator_log.csv"
BINANCE = "https://api.binance.com"

# =========================
# CSV INIT
# =========================
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w") as f:
        f.write("Time,Symbol,Signal,Entry,SL,TP,knnMA\n")

# =========================
# DATA FETCH
# =========================
def top_25():
    data = requests.get(f"{BINANCE}/api/v3/ticker/24hr", timeout=10).json()
    usdt = [x for x in data if x["symbol"].endswith("USDT")]
    usdt.sort(key=lambda x: float(x["quoteVolume"]), reverse=True)
    return [x["symbol"] for x in usdt[:25]]

def klines(symbol):
    r = requests.get(
        f"{BINANCE}/api/v3/klines",
        params={"symbol": symbol, "interval": TIMEFRAME, "limit": 200},
        timeout=10
    ).json()

    df = pd.DataFrame(r, columns=[
        "ot","o","h","l","c","v",
        "ct","q","n","tbb","tbq","ig"
    ])
    df[["h","l","c"]] = df[["h","l","c"]].astype(float)
    return df

# =========================
# INDICATOR CORE (KNN)
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
    weights = np.arange(1, length + 1)
    return series.rolling(length).apply(
        lambda x: np.dot(x, weights) / weights.sum(), raw=True
    )

# =========================
# MAIN LOOP (CONFIRMED ONLY)
# =========================
last_state = {}

send_telegram(f"✅ AI Trend Navigator bot started (CONFIRMED candles only)\n{now_ist()}")

while True:
    try:
        symbols = top_25()

        for sym in symbols:
            df = klines(sym)

            # ❗ USE LAST CLOSED CANDLE (barstate.isconfirmed)
            df = df.iloc[:-1]

            hl2 = (df["h"] + df["l"]) / 2
            value_in = hl2.rolling(PRICE_LEN).mean()
            target = df["c"].rolling(TARGET_LEN).mean()

            knnMA = mean_of_k_closest(value_in.values, target.values, NUM_CLOSEST)
            knnMA = pd.Series(knnMA, index=df.index)
            knnMA_ = wma(knnMA, 5)

            a = knnMA_.iloc[-3]
            b = knnMA_.iloc[-2]
            c = knnMA_.iloc[-1]

            if np.isnan([a, b, c]).any():
                continue

            # 🔁 COLOR SWITCH LOGIC (EXACT PINE PORT)
            switch_up = b < c and b <= a
            switch_dn = b > c and b >= a

            prev = last_state.get(sym)

            entry = df["c"].iloc[-1]
            swing_low = df["l"].iloc[-10:].min()
            swing_high = df["h"].iloc[-10:].max()

            now = now_ist()

            # ===== BUY =====
            if switch_up and prev != "GREEN":
                sl = swing_low
                tp = entry + 2 * (entry - sl)

                msg = (
                    f"🟢 BUY SIGNAL\n"
                    f"{sym}\n"
                    f"Entry: {entry:.6f}\n"
                    f"SL: {sl:.6f}\n"
                    f"TP: {tp:.6f}\n"
                    f"KNN: {round(c,6)}\n"
                    f"TF: 1H\n"
                    f"{now}"
                )
                send_telegram(msg)
                last_state[sym] = "GREEN"

                with open(CSV_FILE, "a") as f:
                    f.write(f"{now},{sym},BUY,{entry},{sl},{tp},{c}\n")

            # ===== SELL =====
            elif switch_dn and prev != "RED":
                sl = swing_high
                tp = entry - 2 * (sl - entry)

                msg = (
                    f"🔴 SELL SIGNAL\n"
                    f"{sym}\n"
                    f"Entry: {entry:.6f}\n"
                    f"SL: {sl:.6f}\n"
                    f"TP: {tp:.6f}\n"
                    f"KNN: {round(c,6)}\n"
                    f"TF: 1H\n"
                    f"{now}"
                )
                send_telegram(msg)
                last_state[sym] = "RED"

                with open(CSV_FILE, "a") as f:
                    f.write(f"{now},{sym},SELL,{entry},{sl},{tp},{c}\n")

        time.sleep(SCAN_INTERVAL)

    except Exception as e:
        send_telegram(f"⚠️ BOT ERROR:\n{str(e)}\n{now_ist()}")
        time.sleep(60)

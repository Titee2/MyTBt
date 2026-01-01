# ==========================================================
# AI TREND NAVIGATOR — GITHUB ACTIONS VERSION (FIXED)
# 5M CONFIRMED CANDLE CLOSE + TELEGRAM ALERTS
# ==========================================================

import requests
import pandas as pd
import numpy as np
import time
import os
from datetime import datetime

# =========================
# WAIT FOR CANDLE CONFIRMATION
# =========================
time.sleep(35)

# =========================
# CONFIG
# =========================
TIMEFRAME = "5m"
PRICE_LEN = 5
TARGET_LEN = 5
NUM_CLOSEST = 3
SMOOTHING = 5

BINANCE = "https://api.binance.com"

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# =========================
# TELEGRAM
# =========================
def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID:
        return

    r = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": msg},
        timeout=10
    )

    if r.status_code != 200:
        print("Telegram error:", r.text)

# =========================
# SAFE BINANCE REQUEST
# =========================
def binance_get(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()

        # Binance error response is a dict, not list
        if isinstance(data, dict):
            print("Binance API error:", data)
            return None

        return data

    except Exception as e:
        print("Binance request failed:", e)
        return None

# =========================
# SYMBOL SELECTION
# =========================
def top_25():
    data = binance_get(f"{BINANCE}/api/v3/ticker/24hr")
    if not data:
        return []

    usdt = [x for x in data if x.get("symbol", "").endswith("USDT")]
    usdt.sort(key=lambda x: float(x.get("quoteVolume", 0)), reverse=True)
    return [x["symbol"] for x in usdt[:25]]

# =========================
# KLINES
# =========================
def klines(symbol):
    data = binance_get(
        f"{BINANCE}/api/v3/klines",
        params={
            "symbol": symbol,
            "interval": TIMEFRAME,
            "limit": 200
        }
    )

    if not data:
        return None

    df = pd.DataFrame(data, columns=[
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
        d = np.abs(value[i-window:i] - target[i])
        idx = np.argsort(d)[:k]
        out[i] = value[i-window:i][idx].mean()

    return out

def wma(series, length):
    w = np.arange(1, length + 1)
    return series.rolling(length).apply(
        lambda x: np.dot(x, w) / w.sum(),
        raw=True
    )

# =========================
# SCAN ONCE (CONFIRMED CANDLE)
# =========================
def scan_once():
    symbols = top_25()
    if not symbols:
        print("No symbols fetched, exiting run.")
        return

    for sym in symbols:
        df = klines(sym)
        if df is None or len(df) < 50:
            continue

        hl2 = (df["h"] + df["l"]) / 2
        value_in = hl2.rolling(PRICE_LEN).mean()
        target = df["c"].rolling(TARGET_LEN).mean()

        knn = mean_of_k_closest(
            value_in.values,
            target.values,
            NUM_CLOSEST
        )

        knn = wma(pd.Series(knn), SMOOTHING)

        if len(knn) < 3:
            continue

        a = knn.iloc[-3]
        b = knn.iloc[-2]
        c = knn.iloc[-1]

        if np.isnan([a, b, c]).any():
            continue

        buy = b < c and b <= a
        sell = b > c and b >= a

        if buy or sell:
            side = "BUY" if buy else "SELL"
            strength = round(abs(c - b) / abs(b) * 100, 2)

            msg = (
                f"{side} SIGNAL\n"
                f"Symbol: {sym}\n"
                f"Timeframe: 5m\n"
                f"Strength: {strength}\n"
                f"Confirmed candle close\n"
                f"UTC: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            send_telegram(msg)

# =========================
# RUN
# =========================
if __name__ == "__main__":
    scan_once()

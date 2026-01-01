# ==========================================================
# AI TREND NAVIGATOR — OKX CONTINUOUS BOT
# TOP 100 BY MARKET CAP (EXCLUDING STABLECOINS)
# 30M TIMEFRAME — ATR TP / SL
# ==========================================================

import requests
import pandas as pd
import numpy as np
import time
import os
from datetime import datetime, timedelta, timezone

# =========================
# CONFIG
# =========================
TIMEFRAME = "30m"

PRICE_LEN = 5
TARGET_LEN = 5
NUM_CLOSEST = 3
SMOOTHING = 5

ATR_LEN = 14
ATR_SL_MULT = 1.0
ATR_TP_MULT = 2.0

OKX = "https://www.okx.com"
COINGECKO = "https://api.coingecko.com/api/v3"

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

IST = timezone(timedelta(hours=5, minutes=30))

# =========================
# STABLECOIN FILTER
# =========================
STABLECOINS = {
    "USDT","USDC","BUSD","DAI","TUSD","USDP","FDUSD",
    "FRAX","LUSD","USDD","GUSD","PYUSD","EURT"
}

# =========================
# TELEGRAM
# =========================
def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID:
        return

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": msg},
        timeout=10
    )

# =========================
# WAIT FOR NEXT 30M CLOSE
# =========================
def wait_for_next_30m():
    now = time.time()
    next_close = ((now // 1800) + 1) * 1800
    time.sleep(max(0, next_close - now + 40))

# =========================
# TOP 100 (MARKET CAP) — NO STABLES
# =========================
def top_100_marketcap():
    r = requests.get(
        f"{COINGECKO}/coins/markets",
        params={
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 120,  # fetch extra to offset removed stables
            "page": 1
        },
        timeout=15
    ).json()

    symbols = []
    for coin in r:
        sym = coin["symbol"].upper()
        if sym in STABLECOINS:
            continue

        symbols.append(f"{sym}-USDT")

        if len(symbols) == 100:
            break

    return symbols

# =========================
# OKX CANDLES
# =========================
def klines(symbol):
    r = requests.get(
        f"{OKX}/api/v5/market/candles",
        params={
            "instId": symbol,
            "bar": TIMEFRAME,
            "limit": 200
        },
        timeout=10
    ).json()

    data = r.get("data")
    if not data:
        return None

    data.reverse()

    df = pd.DataFrame(
        data,
        columns=["ts","o","h","l","c","v","volCcy","volCcyQuote","confirm"]
    )

    df[["h","l","c"]] = df[["h","l","c"]].astype(float)
    return df

# =========================
# INDICATORS
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

def atr(df, length):
    high = df["h"]
    low = df["l"]
    close = df["c"].shift(1)

    tr = pd.concat([
        high - low,
        (high - close).abs(),
        (low - close).abs()
    ], axis=1).max(axis=1)

    return tr.rolling(length).mean()

# =========================
# STATE (NO DUPLICATES)
# =========================
last_state = {}

# =========================
# SCAN
# =========================
def scan():
    symbols = top_100_marketcap()

    for sym in symbols:
        df = klines(sym)
        if df is None or len(df) < 60:
            continue

        hl2 = (df["h"] + df["l"]) / 2
        value_in = hl2.rolling(PRICE_LEN).mean()
        target = df["c"].rolling(TARGET_LEN).mean()

        knn = mean_of_k_closest(value_in.values, target.values, NUM_CLOSEST)
        knn = wma(pd.Series(knn), SMOOTHING)

        if len(knn) < 3:
            continue

        a, b, c = knn.iloc[-3], knn.iloc[-2], knn.iloc[-1]
        if np.isnan([a, b, c]).any():
            continue

        buy = b < c and b <= a
        sell = b > c and b >= a

        state = "GREEN" if buy else "RED" if sell else None
        if not state or last_state.get(sym) == state:
            continue

        last_state[sym] = state

        entry = round(df["c"].iloc[-2], 6)
        atr_val = atr(df, ATR_LEN).iloc[-2]
        if np.isnan(atr_val):
            continue

        if state == "GREEN":
            side = "🟢 BUY"
            sl = round(entry - ATR_SL_MULT * atr_val, 6)
            tp = round(entry + ATR_TP_MULT * atr_val, 6)
        else:
            side = "🔴 SELL"
            sl = round(entry + ATR_SL_MULT * atr_val, 6)
            tp = round(entry - ATR_TP_MULT * atr_val, 6)

        ist_time = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

        msg = (
            f"{side} SIGNAL (OKX)\n"
            f"Symbol: {sym}\n"
            f"Timeframe: 30m\n"
            f"Entry: {entry}\n"
            f"ATR({ATR_LEN}): {round(atr_val,6)}\n"
            f"TP: {tp}\n"
            f"SL: {sl}\n"
            f"IST: {ist_time}"
        )

        send_telegram(msg)

# =========================
# MAIN LOOP
# =========================
if __name__ == "__main__":
    send_telegram(
        "🚀 Bot Started (OKX)\n"
        "Universe: Top 100 by Market Cap (No Stablecoins)\n"
        "Timeframe: 30m\n"
        "TP/SL: ATR-based\n"
        "Mode: Confirmed candle close only"
    )

    while True:
        wait_for_next_30m()
        scan()

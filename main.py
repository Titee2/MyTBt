# ==========================================================
# AI TREND NAVIGATOR — CONFIRMED 5M COLOR CHANGE ALERTS
# PineScript 1:1 Logic | Closed Candles Only | Headless Safe
# ==========================================================

import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime
import os

# =========================
# CONFIG
# =========================
TIMEFRAME = "5m"
PRICE_LEN = 5
TARGET_LEN = 5
NUM_CLOSEST = 3
SMOOTHING = 50          # SAME as Pine (do NOT scale)
SCAN_INTERVAL = 60      # seconds
BINANCE = "https://api.binance.com"

CSV_FILE = "signals.csv"

# =========================
# CSV INIT
# =========================
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w") as f:
        f.write("Time,Symbol,Signal,knnMA\n")

# =========================
# SYMBOL SELECTION
# =========================
def top_25():
    data = requests.get(f"{BINANCE}/api/v3/ticker/24hr", timeout=10).json()
    usdt = [x for x in data if x["symbol"].endswith("USDT")]
    usdt.sort(key=lambda x: float(x["quoteVolume"]), reverse=True)
    return [x["symbol"] for x in usdt[:25]]

# =========================
# KLINES
# =========================
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
# INDICATOR CORE (PINE MATCH)
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
        lambda x: np.dot(x, weights) / weights.sum(),
        raw=True
    )

# =========================
# ALERT HANDLER
# =========================
def send_signal(symbol, side, value):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts},{symbol},{side},{round(value,6)}"

    print("SIGNAL:", line)

    with open(CSV_FILE, "a") as f:
        f.write(line + "\n")

# =========================
# SCANNER (CONFIRMED ONLY)
# =========================
last_state = {}

def scan():
    print("Bot started (5M, CONFIRMED candle close only)")

    while True:
        try:
            symbols = top_25()

            for sym in symbols:
                df = klines(sym)

                # PRICE + TARGET
                hl2 = (df["h"] + df["l"]) / 2
                value_in = hl2.rolling(PRICE_LEN).mean()
                target = df["c"].rolling(TARGET_LEN).mean()

                # KNN MA
                knn = mean_of_k_closest(
                    value_in.values,
                    target.values,
                    NUM_CLOSEST
                )
                knn = pd.Series(knn)
                knnMA = wma(knn, 5)

                if len(knnMA) < 6:
                    continue

                # =========================
                # CONFIRMED CANDLE LOGIC
                # a = candle -4
                # b = candle -3
                # c = candle -2  <-- last CLOSED candle
                # =========================
                a = knnMA.iloc[-4]
                b = knnMA.iloc[-3]
                c = knnMA.iloc[-2]

                if np.isnan([a, b, c]).any():
                    continue

                # EXACT PINE LOGIC
                switch_up = b < c and b <= a
                switch_dn = b > c and b >= a

                prev = last_state.get(sym)

                if switch_up and prev != "GREEN":
                    send_signal(sym, "BUY", c)
                    last_state[sym] = "GREEN"

                elif switch_dn and prev != "RED":
                    send_signal(sym, "SELL", c)
                    last_state[sym] = "RED"

        except Exception as e:
            print("⚠️ BOT ERROR:", str(e))

        time.sleep(SCAN_INTERVAL)

# =========================
# START
# =========================
if __name__ == "__main__":
    scan()

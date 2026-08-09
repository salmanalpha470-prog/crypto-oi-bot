import requests
import time
import pandas as pd
from threading import Thread
from flask import Flask
import os

# ================= CONFIGURATION =================
TELEGRAM_BOT_TOKEN = '8035884889:AAECyVzikK_ZlutJo4r_vPy7R2K9hhr6TvE'
TELEGRAM_CHAT_ID = '8282135014'
TIMEFRAMES = ['5m', '15m', '1h']
LOOKBACK_CANDLES = 40
POLL_INTERVAL = 60

# Binance Futures Public API endpoints
BASE_URL = 'https://fapi.binance.com'

# --- DUMMY WEB SERVER FOR RENDER FREE TIER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "🚀 OI Divergence Bot is Running 24/7!"

def run_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
# ---------------------------------------------

def send_telegram_alert(symbol, timeframe, price, prev_high, current_oi, prev_oi):
    message = (
        f"🚨 **OI DIVERGENCE BREAKOUT ALERT** 🚨\n\n"
        f"🪙 **Coin:** #{symbol}\n"
        f"⏰ **Timeframe:** {timeframe}\n"
        f"📈 **Current Close Price:** {price}\n"
        f"📌 **Previous High Price:** {prev_high}\n"
        f"📊 **Current Open Interest:** {current_oi:,.0f}\n"
        f"📉 **Previous High OI:** {prev_oi:,.0f}\n\n"
        f"⚠️ *Price broke previous high, but Open Interest is lower/ranging!*"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending Telegram alert: {e}")

def get_futures_symbols():
    url = f"{BASE_URL}/fapi/v1/exchangeInfo"
    try:
        res = requests.get(url, timeout=10).json()
        if 'symbols' not in res:
            return []
        symbols = [
            s['symbol'] for s in res['symbols'] 
            if s['quoteAsset'] == 'USDT' and s['status'] == 'TRADING' and s['contractType'] == 'PERPETUAL'
        ]
        return symbols
    except Exception as e:
        print("Error fetching symbols:", e)
        return []

def get_klines_and_oi(symbol, tf):
    try:
        kline_url = f"{BASE_URL}/fapi/v1/klines?symbol={symbol}&interval={tf}&limit={LOOKBACK_CANDLES}"
        klines = requests.get(kline_url, timeout=10).json()
        
        oi_url = f"{BASE_URL}/futures/data/openInterestHist?symbol={symbol}&period={tf}&limit={LOOKBACK_CANDLES}"
        oi_data = requests.get(oi_url, timeout=10).json()
        
        if not klines or not oi_data or len(klines) < LOOKBACK_CANDLES or len(oi_data) < LOOKBACK_CANDLES:
            return None

        df_price = pd.DataFrame(klines, columns=['time', 'open', 'high', 'low', 'close', 'volume', '_', '_', '_', '_', '_', '_'])
        df_price['high'] = df_price['high'].astype(float)
        df_price['close'] = df_price['close'].astype(float)
        
        df_oi = pd.DataFrame(oi_data)
        df_oi['sumOpenInterest'] = df_oi['sumOpenInterest'].astype(float)
        
        return df_price, df_oi
    except Exception:
        return None

def scan_markets():
    symbols = get_futures_symbols()
    if not symbols:
        return
        
    print(f"Scanning {len(symbols)} USDT Futures symbols for timeframes: {TIMEFRAMES}...")
    
    for symbol in symbols:
        for tf in TIMEFRAMES:
            data = get_klines_and_oi(symbol, tf)
            if data is None:
                continue
                
            df_price, df_oi = data
            current_close = df_price['close'].iloc[-1]
            current_oi = df_oi['sumOpenInterest'].iloc[-1]
            
            hist_price = df_price.iloc[:-1]
            hist_oi = df_oi.iloc[:-1]
            
            max_price_idx = hist_price['high'].idxmax()
            prev_high_price = hist_price['high'].loc[max_price_idx]
            prev_high_oi = hist_oi['sumOpenInterest'].max()
            
            if current_close > prev_high_price and current_oi < prev_high_oi:
                print(f"✅ MATCH FOUND: {symbol} on {tf} timeframe!")
                send_telegram_alert(symbol, tf, current_close, prev_high_price, current_oi, prev_high_oi)
                
            time.sleep(0.1) 

def run_bot():
    print("🚀 OI Divergence Bot Started!")
    while True:
        scan_markets()
        print(f"✅ Scan complete. Waiting {POLL_INTERVAL} seconds...\n")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    # 1. Web server ko alag background thread mein start karein
    server_thread = Thread(target=run_server)
    server_thread.start()
    
    # 2. Asal Bot ka kaam shuru karein
    run_bot()
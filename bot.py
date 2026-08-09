import requests
import time
import pandas as pd

# ================= CONFIGURATION =================
TELEGRAM_BOT_TOKEN = '8035884889:AAECyVzikK_ZlutJo4r_vPy7R2K9hhr6TvE'
TELEGRAM_CHAT_ID = '8282135014'
TIMEFRAMES = ['5m', '15m', '1h']   # Multi-timeframe setup
LOOKBACK_CANDLES = 40              # Pichli 40 candles ko check karega
POLL_INTERVAL = 60                 # Har 60 seconds baad market dobara scan hogi

# Binance Futures Public API endpoints
BASE_URL = 'https://fapi.binance.com'

def send_telegram_alert(symbol, timeframe, price, prev_high, current_oi, prev_oi):
    message = (
        f"🚨 **OI DIVERGENCE BREAKOUT ALERT** 🚨\n\n"
        f"🪙 **Coin:** #{symbol}\n"
        f"⏰ **Timeframe:** {timeframe}\n"
        f"📈 **Current Close Price:** {price}\n"
        f"📌 **Previous High Price:** {prev_high}\n"
        f"📊 **Current Open Interest:** {current_oi:,.0f}\n"
        f"📉 **Previous High OI:** {prev_oi:,.0f}\n\n"
        f"⚠️ *Price ne previous High break kar diya hai, lekin OI nechy hai ya range mein hai (Possible Reversal / Liquidity Sweep)!*"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending Telegram alert: {e}")

def get_futures_symbols():
    """Binance Futures ke tamam Active USDT Pairs fetch karta hai"""
    url = f"{BASE_URL}/fapi/v1/exchangeInfo"
    try:
        res = requests.get(url).json()
        symbols = [
            s['symbol'] for s in res['symbols'] 
            if s['quoteAsset'] == 'USDT' and s['status'] == 'TRADING' and s['contractType'] == 'PERPETUAL'
        ]
        return symbols
    except Exception as e:
        print("Error fetching symbols:", e)
        return []

def get_klines_and_oi(symbol, tf):
    """Specific timeframe ke liye Klines aur Open Interest fetch karta hai"""
    try:
        # Fetch Price Klines
        kline_url = f"{BASE_URL}/fapi/v1/klines?symbol={symbol}&interval={tf}&limit={LOOKBACK_CANDLES}"
        klines = requests.get(kline_url, timeout=5).json()
        
        # Fetch OI History
        oi_url = f"{BASE_URL}/futures/data/openInterestHist?symbol={symbol}&period={tf}&limit={LOOKBACK_CANDLES}"
        oi_data = requests.get(oi_url, timeout=5).json()
        
        if not klines or not oi_data or len(klines) < LOOKBACK_CANDLES or len(oi_data) < LOOKBACK_CANDLES:
            return None

        df_price = pd.DataFrame(klines, columns=['time', 'open', 'high', 'low', 'close', 'volume', '_', '_', '_', '_', '_', '_'])
        df_price['high'] = df_price['high'].astype(float)
        df_price['close'] = df_price['close'].astype(float)
        
        df_oi = pd.DataFrame(oi_data)
        df_oi['sumOpenInterest'] = df_oi['sumOpenInterest'].astype(float)
        
        return df_price, df_oi
    except Exception as e:
        return None

def scan_markets():
    symbols = get_futures_symbols()
    print(f"Scanning {len(symbols)} USDT Futures symbols for timeframes: {TIMEFRAMES}...")
    
    for symbol in symbols:
        for tf in TIMEFRAMES:
            data = get_klines_and_oi(symbol, tf)
            if data is None:
                continue
                
            df_price, df_oi = data
            
            # Current (latest closed) candle
            current_close = df_price['close'].iloc[-1]
            current_oi = df_oi['sumOpenInterest'].iloc[-1]
            
            # Lookback window (excluding the current candle)
            hist_price = df_price.iloc[:-1]
            hist_oi = df_oi.iloc[:-1]
            
            # Find Previous Price High and corresponding Index
            max_price_idx = hist_price['high'].idxmax()
            prev_high_price = hist_price['high'].loc[max_price_idx]
            
            # Get max OI around the previous high (Peak OI of lookback period)
            prev_high_oi = hist_oi['sumOpenInterest'].max()
            
            # CONDITIONS:
            # 1. Price pichle high se upar close hui ho
            # 2. Lekin OI pichle peak OI se kam ho
            if current_close > prev_high_price and current_oi < prev_high_oi:
                print(f"✅ MATCH FOUND: {symbol} on {tf} timeframe!")
                send_telegram_alert(symbol, tf, current_close, prev_high_price, current_oi, prev_high_oi)
                
            # API ko block hone se bachane ke liye chota sa delay
            time.sleep(0.1) 

if __name__ == "__main__":
    print("🚀 OI Divergence Bot Started Successfully!")
    while True:
        scan_markets()
        print(f"✅ Scan complete. Waiting {POLL_INTERVAL} seconds for the next cycle...\n")
        time.sleep(POLL_INTERVAL)
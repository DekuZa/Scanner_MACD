import ccxt
import pandas as pd
import pandas_ta as ta
import requests
import time
import os
from datetime import datetime
import pytz

# --- KONFIGURASI DARI GITHUB SECRETS ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# --- PENGATURAN SCANNER ---
TIMEFRAMES = ['1d', '1w']
TOP_N = 100
EXCHANGE_ID = 'gate'

# Inisialisasi Exchange
exchange = getattr(ccxt, EXCHANGE_ID)()

def send_telegram(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ Error: Secrets belum diatur!")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Gagal kirim Telegram: {e}")

def get_tv_link(symbol):
    clean_symbol = symbol.replace("/", "")
    return f"https://www.tradingview.com/chart/?symbol={EXCHANGE_ID.upper()}:{clean_symbol}"

def get_top_volume_symbols(limit=100):
    tickers = exchange.fetch_tickers()
    leverage_filters = ['3L', '3S', '5L', '5S', 'BEAR', 'BULL']
    
    usdt_pairs = []
    for s, t in tickers.items():
        if '/USDT' in s and t['quoteVolume'] is not None:
            symbol_base = s.split('/')[0]
            is_leverage = any(f in symbol_base for f in leverage_filters)
            if not is_leverage:
                usdt_pairs.append({'symbol': s, 'vol': t['quoteVolume']})
    
    sorted_pairs = sorted(usdt_pairs, key=lambda x: x['vol'], reverse=True)
    return [p['symbol'] for p in sorted_pairs[:limit]]

def fetch_and_analyze(symbol, tf):
    # Ambil data candle
    bars = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=100)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

    # --- INDIKATOR MACD (12, 26, 9) ---
    # pandas_ta menghasilkan kolom: MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9
    macd_df = ta.macd(df['close'], fast=12, slow=26, signal=9)
    df = pd.concat([df, macd_df], axis=1)

    # Nama kolom hasil pandas_ta
    macd_col = 'MACD_12_26_9'
    signal_col = 'MACDs_12_26_9'

    # Ambil nilai saat ini dan sebelumnya
    macd_now = df[macd_col].iloc[-1]
    signal_now = df[signal_col].iloc[-1]
    macd_prev = df[macd_col].iloc[-2]
    signal_prev = df[signal_col].iloc[-2]

    # Logika Golden Cross: MACD memotong ke atas Signal Line
    is_golden_cross = macd_prev <= signal_prev and macd_now > signal_now
    
    # Tambahan: Hanya anggap sinyal kuat jika terjadi di bawah garis nol (Oversold/Recovery)
    signal_type = None
    if is_golden_cross:
        if macd_now < 0:
            signal_type = "🚀 *MACD GOLDEN CROSS (Bullish Reversal)*"
        else:
            signal_type = "📈 *MACD CROSS (Bullish Momentum)*"
            
    return signal_type, macd_now, signal_now

def run_scanner():
    tz_jkt = pytz.timezone('Asia/Jakarta')
    waktu_sekarang = datetime.now(tz_jkt).strftime('%d/%m/%Y %H:%M:%S')
    
    send_telegram(f"🔍 *MACD Scanner Aktif*\nWaktu: `{waktu_sekarang} WIB`\nStatus: Memindai Golden Cross (Tanpa Leverage)")

    try:
        symbols = get_top_volume_symbols(TOP_N)
    except Exception as e:
        send_telegram(f"❌ Error API: {e}")
        return

    for tf in TIMEFRAMES:
        total_signals = 0
        for symbol in symbols:
            try:
                time.sleep(0.1) 
                signal, m_val, s_val = fetch_and_analyze(symbol, tf)

                if signal:
                    total_signals += 1
                    tv_url = get_tv_link(symbol)
                    msg = (
                        f"{signal}\n"
                        f"*Pair*: `{symbol}`\n"
                        f"*TF*: `{tf}`\n"
                        f"*MACD*: {m_val:.4f}\n"
                        f"*Signal*: {s_val:.4f}\n"
                        f"📈 [Lihat Chart]({tv_url})"
                    )
                    send_telegram(msg)
            except:
                continue
        
        send_telegram(f"📊 *Scan {tf} Selesai*\nDitemukan {total_signals} sinyal MACD.")

if __name__ == "__main__":
    run_scanner()

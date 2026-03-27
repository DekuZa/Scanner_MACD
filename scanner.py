import ccxt
import pandas as pd
import pandas_ta as ta
import requests
import os
import time
from datetime import datetime

# === KONFIGURASI ===
# Masukkan Token & Chat ID di GitHub Secrets dengan nama berikut:
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False  # Biar link TradingView bisa diklik dengan rapi
        }
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Gagal mengirim pesan Telegram: {e}")

def get_top_volume_coins(exchange, limit=100):
    try:
        # Mengambil data ticker dari Bitget
        tickers = exchange.fetch_tickers()
        # Filter hanya pasangan USDT (Spot)
        usdt_pairs = [t for t in tickers.values() if '/USDT' in t['symbol'] and 'quoteVolume' in t]
        # Sortir berdasarkan volume transaksi 24 jam (tertinggi ke terendah)
        sorted_tickers = sorted(usdt_pairs, key=lambda x: x['quoteVolume'], reverse=True)
        return [t['symbol'] for t in sorted_tickers][:limit]
    except Exception as e:
        print(f"Error saat mengambil data volume: {e}")
        return []

def check_signals():
    # Inisialisasi koneksi ke Bitget
    exchange = ccxt.bitget()
    
    # 1. Notifikasi Bot Mulai Berjalan
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    status_msg = f"🤖 *Bot Scanner Bitget Aktif*\n"
    status_msg += f"⏰ Waktu: `{now}`\n"
    status_msg += f"🔎 Memindai 100 koin top volume (Timeframe: 1 Day)"
    send_telegram(status_msg)

    symbols = get_top_volume_coins(exchange)
    found_signals = []

    # 2. Loop Pemindaian Indikator
    for symbol in symbols:
        try:
            # Ambil data OHLCV (100 bar terakhir untuk akurasi indikator)
            bars = exchange.fetch_ohlcv(symbol, timeframe='1d', limit=100)
            if len(bars) < 35: continue # Lewati koin baru yang datanya belum cukup
            
            df = pd.DataFrame(bars, columns=['time', 'open', 'high', 'low', 'close', 'vol'])
            
            # Hitung MACD (12, 26, 9) menggunakan pandas_ta
            macd_df = df.ta.macd(fast=12, slow=26, signal=9)
            
            # Ambil nilai DIFF (MACD_12_26_9) dan DEA (MACDs_12_26_9)
            curr_diff = macd_df['MACD_12_26_9'].iloc[-1]
            curr_dea = macd_df['MACDs_12_26_9'].iloc[-1]
            prev_diff = macd_df['MACD_12_26_9'].iloc[-2]
            prev_dea = macd_df['MACDs_12_26_9'].iloc[-2]
            
            last_price = df['close'].iloc[-1]

            # Logika Sinyal: 
            # - Golden Cross: DIFF memotong ke atas DEA
            # - Posisi: Persilangan terjadi di area negatif (di bawah angka 0)
            if prev_diff < prev_dea and curr_diff > curr_dea and curr_diff < 0:
                # Siapkan Link TradingView khusus bursa Bitget
                tv_symbol = symbol.replace("/", "")
                tv_link = f"https://www.tradingview.com/chart/?symbol=BITGET:{tv_symbol}"
                
                found_signals.append({
                    'symbol': symbol,
                    'price': last_price,
                    'link': tv_link
                })
            
            # Jeda singkat agar tidak terkena ban/limit API dari Bitget
            time.sleep(0.15)
            
        except Exception as e:
            print(f"Skip {symbol} karena error: {e}")
            continue

    # 3. Kirim Laporan Akhir Sinyal
    if found_signals:
        report_msg = "🚀 *SINYAL BUY MACD DITEMUKAN*\n"
        report_msg += "_Kriteria: Golden Cross di bawah Garis Nol (1D)_\n\n"
        
        for item in found_signals:
            report_msg += f"✅ *{item['symbol']}*\n"
            report_msg += f"💰 Price: `{item['price']}`\n"
            report_msg += f"📊 [Lihat di TradingView]({item['link']})\n\n"
        
        send_telegram(report_msg)
    else:
        send_telegram("ℹ️ Pemindaian selesai. Tidak ada koin yang memenuhi kriteria sinyal buy saat ini.")

if __name__ == "__main__":
    check_signals()

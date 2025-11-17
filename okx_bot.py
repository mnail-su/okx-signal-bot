import requests
import time
import pandas as pd
import numpy as np
from datetime import datetime

# Telegram Bot Ayarları
TELEGRAM_BOT_TOKEN = "8041647887:AAHpL1aYGCH0lgFO_ZhbgtFMkwYhNHVA-ZA"
TELEGRAM_CHAT_ID = "176031945"

# Bot Ayarları
CONFIG = {
    "timeframe": "1H",
    "leverage": "10x",
    "check_interval": 300,
    "top_coins": 100
}

class OKXAnalyzer:
    def __init__(self):
        self.base_url = "https://www.okx.com/api/v5"
        self.headers = {"Content-Type": "application/json"}
    
    def get_top_coins(self, limit=100):
        try:
            url = f"{self.base_url}/market/tickers?instType=SPOT"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == "0":
                    tickers = data.get("data", [])
                    usdt_pairs = []
                    for ticker in tickers:
                        inst_id = ticker.get("instId", "")
                        if "-USDT" in inst_id and "-USDT-" not in inst_id:
                            try:
                                vol = float(ticker.get("volCcy24h", 0))
                                usdt_pairs.append({
                                    "symbol": inst_id,
                                    "volume": vol,
                                    "price": float(ticker.get("last", 0))
                                })
                            except:
                                continue
                    usdt_pairs.sort(key=lambda x: x["volume"], reverse=True)
                    return usdt_pairs[:limit]
            return []
        except Exception as e:
            print(f"Coin listesi hatası: {e}")
            return []
    
    def get_klines(self, symbol, timeframe="1H", limit=100):
        try:
            tf_map = {"15m": "15m", "1H": "1H", "4H": "4H"}
            bar = tf_map.get(timeframe, "1H")
            
            url = f"{self.base_url}/market/candles"
            params = {"instId": symbol, "bar": bar, "limit": str(limit)}
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == "0":
                    candles = data.get("data", [])
                    df = pd.DataFrame(candles, columns=[
                        'timestamp', 'open', 'high', 'low', 'close', 'volume', 'volCcy', 'volCcyQuote', 'confirm'
                    ])
                    for col in ['open', 'high', 'low', 'close', 'volume']:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                    df = df.sort_values('timestamp')
                    return df
            return None
        except Exception as e:
            print(f"{symbol} veri hatası: {e}")
            return None
    
    def calculate_rsi(self, df, period=14):
        try:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi
        except:
            return pd.Series([50] * len(df))
    
    def detect_support_resistance(self, df, window=20):
        try:
            highs = df['high'].rolling(window=window, center=True).max()
            lows = df['low'].rolling(window=window, center=True).min()
            return lows.iloc[-1], highs.iloc[-1]
        except:
            return None, None
    
    def analyze_pattern(self, df):
        try:
            if len(df) < 20:
                return None
            
            df['rsi'] = self.calculate_rsi(df)
            support, resistance = self.detect_support_resistance(df)
            
            current_price = df['close'].iloc[-1]
            prev_price = df['close'].iloc[-2]
            rsi = df['rsi'].iloc[-1]
            
            signal = None
            
            if rsi < 35 and current_price > prev_price and support:
                if current_price > support * 1.001:
                    signal = {
                        "direction": "Long",
                        "formation": "Destek Bölgesinde Tutunma + RSI Aşırı Satım",
                        "entry": current_price,
                        "stop": support * 0.98,
                        "targets": [
                            current_price * 1.02,
                            current_price * 1.04,
                            current_price * 1.07,
                            current_price * 1.10
                        ],
                        "rsi": rsi
                    }
            elif rsi > 65 and current_price < prev_price and resistance:
                if current_price < resistance * 0.999:
                    signal = {
                        "direction": "Short",
                        "formation": "Direnç Bölgesinde Ret + RSI Aşırı Alım",
                        "entry": current_price,
                        "stop": resistance * 1.02,
                        "targets": [
                            current_price * 0.98,
                            current_price * 0.96,
                            current_price * 0.93,
                            current_price * 0.90
                        ],
                        "rsi": rsi
                    }
            elif resistance and current_price > resistance * 1.005:
                signal = {
                    "direction": "Long",
                    "formation": "Direnç Kırılımı + Yükseliş Momentumu",
                    "entry": current_price,
                    "stop": resistance * 0.99,
                    "targets": [
                        current_price * 1.03,
                        current_price * 1.05,
                        current_price * 1.08,
                        current_price * 1.12
                    ],
                    "rsi": rsi
                }
            return signal
        except Exception as e:
            print(f"Analiz hatası: {e}")
            return None

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Telegram hatası: {e}")
        return False

def format_signal(coin, signal):
    emoji = "📈" if signal["direction"] == "Long" else "📉"
    return f"""
{emoji} <b>#{coin.replace('-USDT', '')} {signal['direction']}</b>
⏰ Zaman Dilimi: {CONFIG['timeframe']}
⚙️ Kaldıraç: {CONFIG['leverage']}
📊 Formasyon: {signal['formation']}

🟩 Giriş: {signal['entry']:.4f}
❌ Stop: {signal['stop']:.4f}

🎯 Hedefler:
1️⃣ {signal['targets'][0]:.4f}
2️⃣ {signal['targets'][1]:.4f}
3️⃣ {signal['targets'][2]:.4f}
4️⃣ {signal['targets'][3]:.4f}

📊 RSI: {signal['rsi']:.1f}
🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}
    """.strip()

def main():
    analyzer = OKXAnalyzer()
    print("🚀 OKX Sinyal Botu Başladı!")
    send_telegram("🤖 <b>Bot Aktif!</b>\n\nOKX Sinyal Botu çalışmaya başladı.")
    
    signal_count = 0
    check_count = 0
    
    while True:
        try:
            check_count += 1
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔍 Analiz #{check_count}")
            
            top_coins = analyzer.get_top_coins(CONFIG['top_coins'])
            if not top_coins:
                print("❌ Coin listesi alınamadı")
                time.sleep(30)
                continue
            
            print(f"✅ {len(top_coins)} coin analiz ediliyor...")
            
            analyzed = 0
            for coin_data in top_coins:
                symbol = coin_data['symbol']
                df = analyzer.get_klines(symbol, CONFIG['timeframe'])
                
                if df is None or len(df) < 20:
                    continue
                
                analyzed += 1
                signal = analyzer.analyze_pattern(df)
                
                if signal:
                    signal_count += 1
                    print(f"\n🎯 SİNYAL: {symbol} - {signal['direction']}")
                    message = format_signal(symbol, signal)
                    if send_telegram(message):
                        print("✅ Telegram'a gönderildi!")
                
                time.sleep(0.5)
            
            print(f"\n✅ {analyzed} coin kontrol edildi | Toplam sinyal: {signal_count}")
            print(f"⏰ Sonraki kontrol: {CONFIG['check_interval']}s sonra")
            time.sleep(CONFIG['check_interval'])
            
        except KeyboardInterrupt:
            print("\n🛑 Bot durduruldu!")
            send_telegram("🛑 <b>Bot Durduruldu</b>")
            break
        except Exception as e:
            print(f"\n❌ Hata: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
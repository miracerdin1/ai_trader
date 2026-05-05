"""Hızlı fonksiyonel test - veri kaynaklarının çalıştığını doğrular."""

import sys

print("=" * 50)
print("AI TRADER - Hizli Test")
print("=" * 50)

# Test 1: TradingView-TA
print("\n[1/4] TradingView-TA testi...")
try:
    from tradingview_ta import TA_Handler, Interval
    handler = TA_Handler(
        symbol="BTCUSDT",
        screener="crypto",
        exchange="BINANCE",
        interval=Interval.INTERVAL_1_HOUR,
    )
    analysis = handler.get_analysis()
    rec = analysis.summary["RECOMMENDATION"]
    close = analysis.indicators.get("close", "N/A")
    rsi = analysis.indicators.get("RSI", "N/A")
    print(f"   OK - BTC/USDT 1h: {rec}, Fiyat: ${close:,.2f}, RSI: {rsi:.1f}")
except Exception as e:
    print(f"   HATA: {e}")

# Test 2: ccxt (public)
print("\n[2/4] ccxt Public OHLCV testi...")
try:
    import ccxt
    exchange = ccxt.binance({"enableRateLimit": True})
    ohlcv = exchange.fetch_ohlcv("BTC/USDT", timeframe="1h", limit=5)
    print(f"   OK - {len(ohlcv)} mum verisi cekildi. Son kapani: ${ohlcv[-1][4]:,.2f}")
except Exception as e:
    print(f"   HATA: {e}")

# Test 3: Fear & Greed Index
print("\n[3/4] Fear & Greed Index testi...")
try:
    import requests
    resp = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
    data = resp.json()["data"][0]
    print(f"   OK - Deger: {data['value']} ({data['value_classification']})")
except Exception as e:
    print(f"   HATA: {e}")

# Test 4: pandas_ta
print("\n[4/4] pandas_ta testi...")
try:
    import pandas as pd
    import pandas_ta as ta
    df = pd.DataFrame({"close": [100, 102, 101, 103, 104, 105, 103, 102, 106, 108]})
    rsi = ta.rsi(df["close"], length=5)
    print(f"   OK - RSI hesaplandi: {rsi.iloc[-1]:.2f}")
except Exception as e:
    print(f"   HATA: {e}")

print("\n" + "=" * 50)
print("Testler tamamlandi!")
print("=" * 50)

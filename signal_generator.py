"""
Sinyal üretici modülü
- Teknik analiz + Duygu analizi verilerini birleştirip nihai sinyal oluşturur
- Güven skoru hesaplar
- Mesaj formatlar
"""

from datetime import datetime, timezone
from loguru import logger

import config
from data_fetcher import get_tradingview_analysis, get_current_price
from technical_analysis import evaluate_tradingview_signals, analyze_with_pandas_ta
from sentiment_analysis import get_combined_sentiment


def calculate_levels(price: float, atr: float, direction: str) -> dict:
    """
    ATR tabanlı Stop-Loss ve Take-Profit seviyelerini hesaplar.
    """
    if direction == "LONG":
        sl = price - (atr * config.SL_ATR_MULTIPLIER)
        tp1 = price + (atr * config.TP1_ATR_MULTIPLIER)
        tp2 = price + (atr * config.TP2_ATR_MULTIPLIER)
        tp3 = price + (atr * config.TP3_ATR_MULTIPLIER)
    else:  # SHORT
        sl = price + (atr * config.SL_ATR_MULTIPLIER)
        tp1 = price - (atr * config.TP1_ATR_MULTIPLIER)
        tp2 = price - (atr * config.TP2_ATR_MULTIPLIER)
        tp3 = price - (atr * config.TP3_ATR_MULTIPLIER)

    return {
        "stop_loss": round(sl, 2),
        "tp1": round(tp1, 2),
        "tp2": round(tp2, 2),
        "tp3": round(tp3, 2),
    }


def generate_signal() -> dict | None:
    """
    Tüm veri kaynaklarını bir araya getirip sinyal üretir.

    Returns:
        Sinyal dict'i veya None (sinyal yoksa)
    """
    logger.info("═" * 60)
    logger.info("🔍 Tarama başlatıldı...")
    logger.info("═" * 60)

    # ─── 1. TradingView-TA Analizi ──────────────────────────────────────
    tv_data = get_tradingview_analysis()
    tv_result = evaluate_tradingview_signals(tv_data)

    # ─── 2. Yedek: pandas_ta analizi (TradingView başarısızsa) ──────────
    fallback_used = False
    if tv_result["direction"] is None:
        logger.info("[Fallback] TradingView sinyali belirsiz, pandas_ta deneniyor...")
        pta_1h = analyze_with_pandas_ta("1h")
        pta_4h = analyze_with_pandas_ta("4h")

        if pta_1h and pta_4h:
            # pandas_ta'dan yön belirleme
            if pta_1h["ema_signal"] == "LONG" and pta_4h["ema_signal"] == "LONG":
                tv_result["direction"] = "LONG"
                tv_result["score"] = 3.5
                tv_result["reasons"].append("📊 pandas_ta: 1h+4h EMA LONG konfirmasyonu")
                fallback_used = True
            elif pta_1h["ema_signal"] == "SHORT" and pta_4h["ema_signal"] == "SHORT":
                tv_result["direction"] = "SHORT"
                tv_result["score"] = 3.5
                tv_result["reasons"].append("📊 pandas_ta: 1h+4h EMA SHORT konfirmasyonu")
                fallback_used = True

            # RSI ek puan
            if pta_1h.get("rsi_signal") == "OVERSOLD":
                tv_result["score"] += 1.0
                tv_result["reasons"].append(
                    f"💚 pandas_ta RSI: {pta_1h['rsi']} (Aşırı Satım)"
                )
            elif pta_1h.get("rsi_signal") == "OVERBOUGHT":
                tv_result["score"] += 1.0
                tv_result["reasons"].append(
                    f"💔 pandas_ta RSI: {pta_1h['rsi']} (Aşırı Alım)"
                )

            # Verileri güncelle
            if pta_1h.get("close"):
                tv_result["close"] = pta_1h["close"]
            if pta_1h.get("atr"):
                tv_result["atr"] = pta_1h["atr"]
            if pta_1h.get("rsi"):
                tv_result["rsi"] = pta_1h["rsi"]

    # ─── 3. Hâlâ yön yoksa → sinyal yok ────────────────────────────────
    if tv_result["direction"] is None:
        logger.info("⏸️  Belirgin sinyal yok. Bir sonraki taramayı bekliyorum...")
        return None

    # ─── 4. Duygu Analizi ───────────────────────────────────────────────
    sentiment = get_combined_sentiment()

    # Duygu puanını teknik puana ekle (max 10)
    total_score = min(tv_result["score"] + sentiment["total_sentiment_score"], 10.0)
    total_score = round(total_score, 1)

    # Duygu analizi neden listesine ekle
    if sentiment.get("summary"):
        tv_result["reasons"].append(f"🧠 {sentiment['summary']}")

    # ─── 5. Minimum güven kontrolü ──────────────────────────────────────
    if total_score < config.MIN_CONFIDENCE_SCORE:
        logger.info(
            f"⚠️  Güven skoru düşük: {total_score}/10 "
            f"(minimum: {config.MIN_CONFIDENCE_SCORE}). Sinyal göndermiyorum."
        )
        return None

    # ─── 6. Fiyat ve seviyeleri hesapla ─────────────────────────────────
    current_price = get_current_price()
    if current_price is None:
        current_price = tv_result.get("close", 0)

    # ATR her zaman ccxt + pandas_ta'dan hesaplanır (TradingView-TA ATR sağlamaz)
    atr = tv_result.get("atr")
    if atr is None or atr == 0:
        logger.info("ATR TradingView'da yok, ccxt+pandas_ta ile hesaplanıyor...")
        pta_atr = analyze_with_pandas_ta("1h")
        if pta_atr and pta_atr.get("atr"):
            atr = pta_atr["atr"]
            logger.info(f"ATR (pandas_ta 1h): {atr}")
            # RSI bilgisini de al
            if pta_atr.get("rsi") and tv_result.get("rsi") is None:
                tv_result["rsi"] = pta_atr["rsi"]
        else:
            logger.warning("ATR hesaplanamadi, sinyal gondermiyorum.")
            return None

    levels = calculate_levels(current_price, atr, tv_result["direction"])

    # ─── 7. Sinyal nesnesini oluştur ────────────────────────────────────
    signal = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "symbol": config.SYMBOL,
        "direction": tv_result["direction"],
        "entry_price": current_price,
        "stop_loss": levels["stop_loss"],
        "tp1": levels["tp1"],
        "tp2": levels["tp2"],
        "tp3": levels["tp3"],
        "confidence_score": total_score,
        "reasons": tv_result["reasons"],
        "fear_greed_value": (
            sentiment["fear_greed"]["value"]
            if sentiment.get("fear_greed")
            else None
        ),
        "fear_greed_label": (
            sentiment["fear_greed"]["label"]
            if sentiment.get("fear_greed")
            else "N/A"
        ),
        "news_sentiment": sentiment["news"]["overall"],
        "rsi": tv_result.get("rsi"),
        "atr": atr,
        "fallback_used": fallback_used,
    }

    logger.success(
        f"✅ SİNYAL: {signal['direction']} @ ${signal['entry_price']:,.2f} "
        f"| Güven: {signal['confidence_score']}/10"
    )

    return signal


def format_telegram_message(signal: dict) -> str:
    """
    Sinyali profesyonel Telegram mesaj formatına dönüştürür.
    """
    direction_emoji = "🟢" if signal["direction"] == "LONG" else "🔴"
    direction_text = "LONG (AL)" if signal["direction"] == "LONG" else "SHORT (SAT)"

    reasons_text = "\n".join(f"   • {r}" for r in signal["reasons"])

    # Risk/Ödül oranı
    risk = abs(signal["entry_price"] - signal["stop_loss"])
    reward = abs(signal["tp2"] - signal["entry_price"])
    rr_ratio = round(reward / risk, 2) if risk > 0 else 0

    message = f"""
{'━' * 35}
{direction_emoji} *AI TRADER SİNYALİ* {direction_emoji}
{'━' * 35}

🪙 *Çift:* `{signal['symbol']}`
⏰ *Zaman:* `{signal['timestamp']}`

🚀 *YÖN:* `{direction_text}`
📍 *GİRİŞ:* `${signal['entry_price']:,.2f}`
🛑 *STOP-LOSS:* `${signal['stop_loss']:,.2f}`

🎯 *HEDEFLER:*
   TP1: `${signal['tp1']:,.2f}`
   TP2: `${signal['tp2']:,.2f}`
   TP3: `${signal['tp3']:,.2f}`

📊 *GÜVEN SKORU:* `{signal['confidence_score']}/10` {'⭐' * int(signal['confidence_score'] // 2)}
📐 *Risk/Ödül:* `1:{rr_ratio}`

🧠 *DUYARLILIK:*
   😨 Fear & Greed: `{signal.get('fear_greed_value', 'N/A')} ({signal.get('fear_greed_label', 'N/A')})`
   📰 Haberler: `{signal.get('news_sentiment', 'N/A')}`
   📈 RSI: `{signal.get('rsi', 'N/A')}`

💡 *NEDEN:*
{reasons_text}

{'━' * 35}
⚠️ _Bu bir yatırım tavsiyesi değildir._
_Risk yönetiminizi yapın ve kendi araştırmanızı uygulayın._
{'━' * 35}
"""
    return message.strip()

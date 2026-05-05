"""
Duygu Analizi (Sentiment) modülü
- Alternative.me Fear & Greed Index (API key gerektirmez)
- CryptoPanic RSS haberleri ile piyasa duyarlılığı
"""

import re
import requests
import xml.etree.ElementTree as ET
from loguru import logger

import config


def get_fear_greed_index() -> dict | None:
    """
    Alternative.me Fear & Greed Index API'sinden veri çeker.
    API Key gerektirmez.

    Returns:
        {
            "value": int (0-100),
            "label": str ("Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"),
            "sentiment_score": float (puan katkısı, 0-3 arası),
            "description": str,
        }
    """
    try:
        response = requests.get(config.FEAR_GREED_API, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "data" not in data or len(data["data"]) == 0:
            logger.warning("[Sentiment] Fear & Greed API boş yanıt döndü.")
            return None

        entry = data["data"][0]
        value = int(entry["value"])
        label = entry["value_classification"]

        # Sentiment puan katkısı hesaplama
        # Aşırı Korku → LONG'a +puan, Aşırı Açgözlülük → SHORT'a +puan
        if value <= 20:
            sentiment_score = 3.0
            description = f"🟢 Aşırı Korku ({value}/100) → Tepki alımı beklentisi yüksek"
        elif value <= 35:
            sentiment_score = 2.0
            description = f"🟡 Korku ({value}/100) → Alım fırsatı olabilir"
        elif value <= 55:
            sentiment_score = 0.5
            description = f"⚪ Nötr ({value}/100) → Piyasa kararsız"
        elif value <= 75:
            sentiment_score = 1.5
            description = f"🟠 Açgözlülük ({value}/100) → Dikkatli olunmalı"
        else:
            sentiment_score = 2.5
            description = f"🔴 Aşırı Açgözlülük ({value}/100) → Düzeltme riski var"

        result = {
            "value": value,
            "label": label,
            "sentiment_score": sentiment_score,
            "description": description,
            "bias": "LONG" if value <= 35 else ("SHORT" if value >= 65 else "NEUTRAL"),
        }

        logger.info(f"[Sentiment] Fear & Greed: {value} ({label})")
        return result

    except Exception as e:
        logger.error(f"[Sentiment] Fear & Greed API hatası: {e}")
        return None


def get_crypto_news_sentiment() -> dict:
    """
    CryptoPanic RSS beslemesinden haber başlıklarını çekip
    basit anahtar kelime analizi ile duyarlılık belirler.

    Returns:
        {
            "positive_count": int,
            "negative_count": int,
            "neutral_count": int,
            "overall": "Pozitif" | "Negatif" | "Nötr",
            "headlines": [str],  # son 10 haber başlığı
            "news_score": float (0-1 arası ek puan),
        }
    """
    # Pozitif ve negatif anahtar kelimeler
    positive_keywords = [
        "bull", "surge", "rally", "pump", "breakout", "soar", "gain",
        "recovery", "adoption", "approval", "etf approved", "all-time high",
        "ath", "moon", "buy", "upgrade", "positive", "growth", "rising",
        "support", "accumulation", "institutional", "yükseliş", "rekor",
    ]

    negative_keywords = [
        "bear", "crash", "dump", "plunge", "hack", "ban", "regulation",
        "sell-off", "selloff", "fear", "risk", "decline", "drop", "fall",
        "scam", "fraud", "bankruptcy", "liquidation", "warning", "concern",
        "crisis", "bubble", "correction", "düşüş", "yasak", "çöküş",
    ]

    try:
        response = requests.get(config.CRYPTOPANIC_RSS, timeout=10)
        response.raise_for_status()

        # XML parse - bozuk HTML durumunda regex fallback
        try:
            root = ET.fromstring(response.content)
            items = root.findall(".//item")
            titles_raw = []
            for item in items[:15]:
                title_elem = item.find("title")
                if title_elem is not None and title_elem.text:
                    titles_raw.append(title_elem.text)
        except ET.ParseError:
            # Bozuk XML - regex ile title'ları çek
            text = response.text
            titles_raw = re.findall(r"<title>(?:<![CDATA[)?(.*?)(?:]]>)?</title>", text)
            titles_raw = [t.strip() for t in titles_raw[:15] if t.strip()]

        positive_count = 0
        negative_count = 0
        neutral_count = 0
        headlines = []

        for raw_title in titles_raw:
            title = raw_title.lower()
            headlines.append(raw_title)

            is_positive = any(kw in title for kw in positive_keywords)
            is_negative = any(kw in title for kw in negative_keywords)

            if is_positive and not is_negative:
                positive_count += 1
            elif is_negative and not is_positive:
                negative_count += 1
            else:
                neutral_count += 1

        # Genel duyarlılık
        if positive_count > negative_count:
            overall = "Pozitif"
            news_score = 0.5
        elif negative_count > positive_count:
            overall = "Negatif"
            news_score = 0.5  # Negatif haberler de sinyal gücüne katkı sağlar
        else:
            overall = "Nötr"
            news_score = 0.0

        result = {
            "positive_count": positive_count,
            "negative_count": negative_count,
            "neutral_count": neutral_count,
            "overall": overall,
            "headlines": headlines[:10],
            "news_score": news_score,
        }

        logger.info(
            f"[Sentiment] Haberler: +{positive_count} / -{negative_count} → {overall}"
        )
        return result

    except Exception as e:
        logger.warning(f"[Sentiment] Haber çekme hatası (devam ediliyor): {e}")
        return {
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "overall": "Nötr",
            "headlines": [],
            "news_score": 0.0,
        }


def get_combined_sentiment() -> dict:
    """
    Fear & Greed + Haber duyarlılığını birleştirir.

    Returns:
        {
            "fear_greed": dict | None,
            "news": dict,
            "total_sentiment_score": float (0-3 arası),
            "sentiment_bias": "LONG" | "SHORT" | "NEUTRAL",
            "summary": str,
        }
    """
    fg = get_fear_greed_index()
    news = get_crypto_news_sentiment()

    # Toplam duyarlılık puanı
    total_score = 0.0
    bias = "NEUTRAL"
    summary_parts = []

    if fg:
        total_score += fg["sentiment_score"]
        summary_parts.append(fg["description"])
        bias = fg["bias"]

    total_score += news["news_score"]
    if news["overall"] != "Nötr":
        summary_parts.append(f"📰 Haberler: {news['overall']}")

    # Haber duyarlılığı Fear & Greed ile uyumluysa bias'ı güçlendir
    if fg and fg["bias"] == "LONG" and news["overall"] == "Negatif":
        # Korku + negatif haberler → güçlü LONG sinyali (kontrarian)
        total_score += 0.5
        summary_parts.append("⚡ Kontrarian sinyal: Korku + negatif haberler")
    elif fg and fg["bias"] == "SHORT" and news["overall"] == "Pozitif":
        # Açgözlülük + pozitif haberler → güçlü SHORT sinyali (kontrarian)
        total_score += 0.5
        summary_parts.append("⚡ Kontrarian sinyal: Açgözlülük + pozitif haberler")

    return {
        "fear_greed": fg,
        "news": news,
        "total_sentiment_score": round(min(total_score, 3.0), 1),
        "sentiment_bias": bias,
        "summary": " | ".join(summary_parts) if summary_parts else "Duyarlılık verisi yok",
    }

"""Market Dashboard - Flask backend using FREE APIs (no Yahoo Finance)."""

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from datetime import datetime, timedelta
import logging
import requests
import random
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Simple in-memory cache
_cache = {}
CACHE_TTL_SECONDS = 300  # 5 minutes

# ============================================================================
# FREE API CONFIGURATION
# ============================================================================
# This dashboard uses simulated realistic market data by default.
# For REAL data, sign up for free API keys:
#
# 1. Twelve Data - https://twelvedata.com (800 calls/day free)
# 2. Alpha Vantage - https://alphavantage.co (25 calls/day free)
# 3. Financial Modeling Prep - https://financialmodelingprep.com
#
# Set environment variables:
#   TWELVE_DATA_API_KEY=your_key
#   FMP_API_KEY=your_key
# ============================================================================

TWELVE_DATA_API_KEY = os.environ.get("TWELVE_DATA_API_KEY", "")
FMP_API_KEY = os.environ.get("FMP_API_KEY", "")

# Instrument definitions with realistic base prices and volatility
INSTRUMENTS = {
    "Dollar Index": {"symbol": "DXY", "base_price": 104.50, "volatility": 0.003, "currency": "$"},
    "Gold": {"symbol": "XAU/USD", "base_price": 2050.00, "volatility": 0.008, "currency": "$"},
    "Silver": {"symbol": "XAG/USD", "base_price": 23.50, "volatility": 0.015, "currency": "$"},
    "Copper": {"symbol": "HG", "base_price": 3.85, "volatility": 0.012, "currency": "$"},
    "Aluminium": {"symbol": "ALI", "base_price": 2280.00, "volatility": 0.010, "currency": "$"},
    "Crude Oil": {"symbol": "CL", "base_price": 78.50, "volatility": 0.020, "currency": "$"},
    "Nifty 50": {"symbol": "NSEI", "base_price": 22150.00, "volatility": 0.012, "currency": "₹"},
    "Dow Jones": {"symbol": "DJI", "base_price": 38950.00, "volatility": 0.008, "currency": "$"},
    "Nasdaq": {"symbol": "IXIC", "base_price": 16200.00, "volatility": 0.012, "currency": "$"},
    "Nikkei 225": {"symbol": "N225", "base_price": 39800.00, "volatility": 0.010, "currency": "¥"},
    "Nifty Smallcap 250": {"symbol": "NSEMDCP", "base_price": 15800.00, "volatility": 0.015, "currency": "₹"},
    "Hang Seng": {"symbol": "HSI", "base_price": 16750.00, "volatility": 0.014, "currency": "HK$"},
}

# Indian stocks for golden cross scanner
INDIAN_STOCKS = {
    "Reliance": {"symbol": "RELIANCE", "base_price": 2450.00, "volatility": 0.018},
    "TCS": {"symbol": "TCS", "base_price": 3850.00, "volatility": 0.012},
    "HDFC Bank": {"symbol": "HDFCBANK", "base_price": 1680.00, "volatility": 0.015},
    "Infosys": {"symbol": "INFY", "base_price": 1520.00, "volatility": 0.014},
    "ICICI Bank": {"symbol": "ICICIBANK", "base_price": 1050.00, "volatility": 0.016},
    "Bharti Airtel": {"symbol": "BHARTIARTL", "base_price": 1180.00, "volatility": 0.013},
    "SBI": {"symbol": "SBIN", "base_price": 780.00, "volatility": 0.018},
    "ITC": {"symbol": "ITC", "base_price": 435.00, "volatility": 0.010},
    "Kotak Bank": {"symbol": "KOTAKBANK", "base_price": 1780.00, "volatility": 0.014},
    "L&T": {"symbol": "LT", "base_price": 3450.00, "volatility": 0.015},
    "HUL": {"symbol": "HINDUNILVR", "base_price": 2580.00, "volatility": 0.008},
    "Axis Bank": {"symbol": "AXISBANK", "base_price": 1120.00, "volatility": 0.017},
    "Bajaj Finance": {"symbol": "BAJFINANCE", "base_price": 6850.00, "volatility": 0.020},
    "Maruti": {"symbol": "MARUTI", "base_price": 10500.00, "volatility": 0.014},
    "Asian Paints": {"symbol": "ASIANPAINT", "base_price": 2850.00, "volatility": 0.012},
    "Titan": {"symbol": "TITAN", "base_price": 3250.00, "volatility": 0.015},
    "Sun Pharma": {"symbol": "SUNPHARMA", "base_price": 1180.00, "volatility": 0.014},
    "Wipro": {"symbol": "WIPRO", "base_price": 480.00, "volatility": 0.013},
    "HCL Tech": {"symbol": "HCLTECH", "base_price": 1450.00, "volatility": 0.013},
    "M&M": {"symbol": "MM", "base_price": 1850.00, "volatility": 0.016},
    "NTPC": {"symbol": "NTPC", "base_price": 350.00, "volatility": 0.012},
    "Power Grid": {"symbol": "POWERGRID", "base_price": 285.00, "volatility": 0.011},
    "Tata Steel": {"symbol": "TATASTEEL", "base_price": 145.00, "volatility": 0.022},
    "JSW Steel": {"symbol": "JSWSTEEL", "base_price": 880.00, "volatility": 0.020},
    "Adani Ports": {"symbol": "ADANIPORTS", "base_price": 1280.00, "volatility": 0.025},
    "Tech Mahindra": {"symbol": "TECHM", "base_price": 1320.00, "volatility": 0.016},
    "IndusInd Bank": {"symbol": "INDUSINDBK", "base_price": 1480.00, "volatility": 0.020},
    "Tata Motors": {"symbol": "TATAMOTORS", "base_price": 780.00, "volatility": 0.022},
    "Coal India": {"symbol": "COALINDIA", "base_price": 420.00, "volatility": 0.015},
    "ONGC": {"symbol": "ONGC", "base_price": 265.00, "volatility": 0.018},
    "Nifty 50 Index": {"symbol": "NIFTY", "base_price": 22150.00, "volatility": 0.012},
    "Nifty Bank": {"symbol": "BANKNIFTY", "base_price": 47500.00, "volatility": 0.014},
    "Nifty IT": {"symbol": "NIFTYIT", "base_price": 35800.00, "volatility": 0.013},
}


def generate_realistic_history(base_price: float, volatility: float, days: int = 90, seed: int = None):
    """Generate realistic price history using random walk with drift."""
    if seed is not None:
        random.seed(seed)
    
    prices = []
    price = base_price * (1 + random.uniform(-0.08, 0.08))
    drift = 0.0002  # Slight upward drift
    
    for i in range(days):
        # Add some mean reversion
        mean_reversion = (base_price - price) / base_price * 0.01
        change = random.gauss(drift + mean_reversion, volatility)
        price = max(price * (1 + change), base_price * 0.5)  # Floor at 50% of base
        prices.append(round(price, 2))
    
    return prices


def try_fetch_real_data(symbol: str, api_type: str = "twelve") -> dict | None:
    """Try to fetch real data from free APIs."""
    
    # Try Twelve Data
    if api_type == "twelve" and TWELVE_DATA_API_KEY:
        try:
            url = "https://api.twelvedata.com/time_series"
            params = {
                "symbol": symbol,
                "interval": "1day",
                "outputsize": 30,
                "apikey": TWELVE_DATA_API_KEY
            }
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if "values" in data:
                    logger.info(f"Got real data for {symbol} from Twelve Data")
                    return data
        except Exception as e:
            logger.warning(f"Twelve Data error: {e}")
    
    # Try Financial Modeling Prep
    if FMP_API_KEY:
        try:
            url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol}"
            params = {"apikey": FMP_API_KEY, "timeseries": 30}
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if "historical" in data:
                    logger.info(f"Got real data for {symbol} from FMP")
                    return data
        except Exception as e:
            logger.warning(f"FMP error: {e}")
    
    return None


def generate_market_data(instruments: dict):
    """Generate market data for all instruments."""
    results = []
    base_date = datetime.now()
    
    for name, config in instruments.items():
        # Use date-based seed for consistent data within same day
        seed = hash(name + base_date.strftime("%Y-%m-%d"))
        
        # Try to fetch real data first
        real_data = try_fetch_real_data(config["symbol"])
        
        if real_data and "values" in real_data:
            # Parse Twelve Data format
            values = real_data["values"]
            sparkline = [float(v["close"]) for v in reversed(values[:30])]
            dates = [v["datetime"] for v in reversed(values[:30])]
            current_price = sparkline[-1]
            prev_price = sparkline[-2] if len(sparkline) > 1 else current_price
            data_source = "live"
        else:
            # Generate simulated data
            history = generate_realistic_history(
                config["base_price"],
                config["volatility"],
                days=90,
                seed=seed
            )
            sparkline = history[-30:]
            dates = [(base_date - timedelta(days=30-i)).strftime("%Y-%m-%d") for i in range(30)]
            current_price = sparkline[-1]
            prev_price = sparkline[-2]
            data_source = "simulated"
        
        change = current_price - prev_price
        change_pct = (change / prev_price) * 100 if prev_price else 0
        
        results.append({
            "name": name,
            "symbol": config["symbol"],
            "currency": config.get("currency", "$"),
            "price": round(current_price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "sparkline": sparkline,
            "dates": dates,
            "high_52w": round(max(sparkline) * 1.08, 2),
            "low_52w": round(min(sparkline) * 0.92, 2),
            "last_updated": base_date.strftime("%Y-%m-%d %H:%M"),
            "data_source": data_source,
        })
    
    return results


def calculate_sma(prices: list, period: int) -> list:
    """Calculate Simple Moving Average."""
    sma = []
    for i in range(len(prices)):
        if i < period - 1:
            sma.append(None)
        else:
            sma.append(sum(prices[i-period+1:i+1]) / period)
    return sma


def calculate_dma_crossovers(stocks: dict):
    """Calculate 20/200 DMA crossovers for stocks."""
    results = {
        "golden_crosses": [],
        "death_crosses": [],
        "bullish_trend": [],
        "bearish_trend": [],
        "errors": [],
    }
    
    base_date = datetime.now()
    
    for name, config in stocks.items():
        try:
            seed = hash(name + base_date.strftime("%Y-%m-%d"))
            history = generate_realistic_history(
                config["base_price"],
                config["volatility"],
                days=250,
                seed=seed
            )
            
            if len(history) < 200:
                continue
            
            dma_20 = calculate_sma(history, 20)
            dma_200 = calculate_sma(history, 200)
            
            # Filter out None values
            valid_idx = [i for i in range(len(dma_200)) if dma_200[i] is not None]
            if len(valid_idx) < 6:
                continue
            
            current_price = history[-1]
            curr_20 = dma_20[-1]
            curr_200 = dma_200[-1]
            
            item = {
                "name": name,
                "symbol": config["symbol"],
                "current_price": round(current_price, 2),
                "dma_20": round(curr_20, 2),
                "dma_200": round(curr_200, 2),
            }
            
            # Check for crossover in last 5 days
            cross_found = False
            for i in range(-5, 0):
                if dma_20[i-1] is None or dma_200[i-1] is None:
                    continue
                    
                prev_20 = dma_20[i-1]
                prev_200 = dma_200[i-1]
                curr_20_i = dma_20[i]
                curr_200_i = dma_200[i]
                
                if prev_20 < prev_200 and curr_20_i > curr_200_i:
                    item["cross_type"] = "golden"
                    item["cross_date"] = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
                    item["days_ago"] = abs(i)
                    results["golden_crosses"].append(item)
                    cross_found = True
                    break
                elif prev_20 > prev_200 and curr_20_i < curr_200_i:
                    item["cross_type"] = "death"
                    item["cross_date"] = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
                    item["days_ago"] = abs(i)
                    results["death_crosses"].append(item)
                    cross_found = True
                    break
            
            if not cross_found:
                if curr_20 > curr_200:
                    item["status"] = "above"
                    results["bullish_trend"].append(item)
                else:
                    item["status"] = "below"
                    results["bearish_trend"].append(item)
                    
        except Exception as e:
            logger.warning(f"Error calculating DMA for {name}: {e}")
            results["errors"].append({"name": name, "error": str(e)})
    
    results["golden_crosses"].sort(key=lambda x: x.get("days_ago", 999))
    results["death_crosses"].sort(key=lambda x: x.get("days_ago", 999))
    
    return results


# ============================================================================
# ROUTES
# ============================================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/prices")
def get_prices():
    cache_key = "prices"
    
    if cache_key in _cache:
        cached_data, cache_time = _cache[cache_key]
        if (datetime.now() - cache_time).total_seconds() < CACHE_TTL_SECONDS:
            return jsonify(cached_data)
    
    results = generate_market_data(INSTRUMENTS)
    has_live = any(r.get("data_source") == "live" for r in results)
    
    response_data = {
        "instruments": results,
        "fetched_at": datetime.now().isoformat(),
        "data_source": "live" if has_live else "simulated",
        "api_configured": bool(TWELVE_DATA_API_KEY or FMP_API_KEY),
    }
    
    _cache[cache_key] = (response_data, datetime.now())
    return jsonify(response_data)


@app.route("/api/golden-crosses")
def get_golden_crosses():
    cache_key = "golden_crosses"
    
    if cache_key in _cache:
        cached_data, cache_time = _cache[cache_key]
        if (datetime.now() - cache_time).total_seconds() < CACHE_TTL_SECONDS:
            return jsonify(cached_data)
    
    results = calculate_dma_crossovers(INDIAN_STOCKS)
    
    response_data = {
        **results,
        "fetched_at": datetime.now().isoformat(),
        "total_scanned": len(INDIAN_STOCKS),
        "data_source": "simulated",
    }
    
    _cache[cache_key] = (response_data, datetime.now())
    return jsonify(response_data)


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "apis_configured": {
            "twelve_data": bool(TWELVE_DATA_API_KEY),
            "fmp": bool(FMP_API_KEY),
        }
    })


@app.route("/api/clear-cache")
def clear_cache():
    _cache.clear()
    return jsonify({"status": "cache cleared"})


def calculate_fear_greed_index():
    """
    Calculate a Fear & Greed Index (0-100) based on multiple market factors.
    This is a simplified version inspired by CNN's Fear & Greed Index.
    
    Factors considered:
    1. Market Momentum (Nifty vs 125-day MA)
    2. Market Volatility (simulated VIX-like measure)
    3. Safe Haven Demand (Gold strength)
    4. Stock Price Breadth (advancing vs declining)
    5. Put/Call Ratio (simulated)
    """
    base_date = datetime.now()
    seed = hash("fear_greed" + base_date.strftime("%Y-%m-%d"))
    random.seed(seed)
    
    # Factor 1: Market Momentum (0-100)
    # Compare current index level to 125-day moving average
    nifty_history = generate_realistic_history(22150, 0.012, days=150, seed=hash("nifty_fg" + base_date.strftime("%Y-%m-%d")))
    current_nifty = nifty_history[-1]
    ma_125 = sum(nifty_history[-125:]) / 125
    momentum_ratio = current_nifty / ma_125
    momentum_score = min(100, max(0, (momentum_ratio - 0.9) / 0.2 * 100))
    
    # Factor 2: Volatility (inverse - low volatility = greed)
    # Simulated VIX-like measure (typically 12-35 range)
    vix = 15 + random.gauss(0, 5)
    vix = max(10, min(40, vix))
    volatility_score = max(0, min(100, (35 - vix) / 25 * 100))
    
    # Factor 3: Safe Haven Demand (Gold weakness = greed)
    gold_history = generate_realistic_history(2050, 0.008, days=30, seed=hash("gold_fg" + base_date.strftime("%Y-%m-%d")))
    gold_change = (gold_history[-1] - gold_history[0]) / gold_history[0]
    safe_haven_score = max(0, min(100, 50 - gold_change * 500))
    
    # Factor 4: Market Breadth (% of stocks above 50-day MA)
    breadth_pct = 45 + random.gauss(10, 15)
    breadth_pct = max(20, min(80, breadth_pct))
    breadth_score = breadth_pct
    
    # Factor 5: Put/Call Ratio (low ratio = greed)
    put_call_ratio = 0.8 + random.gauss(0, 0.2)
    put_call_ratio = max(0.5, min(1.3, put_call_ratio))
    put_call_score = max(0, min(100, (1.2 - put_call_ratio) / 0.7 * 100))
    
    # Weighted average
    weights = {
        "momentum": 0.25,
        "volatility": 0.25,
        "safe_haven": 0.15,
        "breadth": 0.20,
        "put_call": 0.15,
    }
    
    overall_score = (
        momentum_score * weights["momentum"] +
        volatility_score * weights["volatility"] +
        safe_haven_score * weights["safe_haven"] +
        breadth_score * weights["breadth"] +
        put_call_score * weights["put_call"]
    )
    
    # Determine sentiment label
    if overall_score <= 25:
        sentiment = "Extreme Fear"
        color = "#dc2626"
    elif overall_score <= 45:
        sentiment = "Fear"
        color = "#f97316"
    elif overall_score <= 55:
        sentiment = "Neutral"
        color = "#eab308"
    elif overall_score <= 75:
        sentiment = "Greed"
        color = "#84cc16"
    else:
        sentiment = "Extreme Greed"
        color = "#22c55e"
    
    # Generate historical scores for the chart
    historical = []
    for days_ago in range(30, 0, -1):
        past_seed = hash("fear_greed" + (base_date - timedelta(days=days_ago)).strftime("%Y-%m-%d"))
        random.seed(past_seed)
        past_score = 50 + random.gauss(0, 15)
        past_score = max(5, min(95, past_score))
        historical.append({
            "date": (base_date - timedelta(days=days_ago)).strftime("%Y-%m-%d"),
            "score": round(past_score, 1)
        })
    
    # Add today's score
    historical.append({
        "date": base_date.strftime("%Y-%m-%d"),
        "score": round(overall_score, 1)
    })
    
    return {
        "score": round(overall_score, 1),
        "sentiment": sentiment,
        "color": color,
        "factors": {
            "momentum": {"score": round(momentum_score, 1), "label": "Market Momentum", "description": f"Nifty vs 125-day MA"},
            "volatility": {"score": round(volatility_score, 1), "label": "Volatility", "description": f"VIX at {vix:.1f}"},
            "safe_haven": {"score": round(safe_haven_score, 1), "label": "Safe Haven Demand", "description": "Gold demand"},
            "breadth": {"score": round(breadth_score, 1), "label": "Market Breadth", "description": f"{breadth_pct:.0f}% above 50-day MA"},
            "put_call": {"score": round(put_call_score, 1), "label": "Put/Call Ratio", "description": f"Ratio: {put_call_ratio:.2f}"},
        },
        "historical": historical,
        "last_updated": base_date.strftime("%Y-%m-%d %H:%M"),
    }


@app.route("/api/fear-greed")
def get_fear_greed():
    """Return the Fear & Greed Index."""
    cache_key = "fear_greed"
    
    if cache_key in _cache:
        cached_data, cache_time = _cache[cache_key]
        if (datetime.now() - cache_time).total_seconds() < CACHE_TTL_SECONDS:
            return jsonify(cached_data)
    
    result = calculate_fear_greed_index()
    result["fetched_at"] = datetime.now().isoformat()
    
    _cache[cache_key] = (result, datetime.now())
    return jsonify(result)


def calculate_india_fear_greed_index():
    """
    Calculate India-specific Fear & Greed Index (0-100).
    Uses Indian market indicators.
    
    Factors:
    1. Nifty 50 Momentum (vs 125-day MA)
    2. India VIX (volatility)
    3. FII/DII Flow sentiment
    4. Nifty PCR (Put-Call Ratio)
    5. Advance-Decline Ratio (NSE breadth)
    6. Nifty Bank strength
    """
    base_date = datetime.now()
    seed = hash("india_fg" + base_date.strftime("%Y-%m-%d"))
    random.seed(seed)
    
    # Factor 1: Nifty 50 Momentum
    nifty_history = generate_realistic_history(22150, 0.012, days=150, seed=hash("nifty50_ind" + base_date.strftime("%Y-%m-%d")))
    current_nifty = nifty_history[-1]
    ma_125 = sum(nifty_history[-125:]) / 125
    momentum_ratio = current_nifty / ma_125
    momentum_score = min(100, max(0, (momentum_ratio - 0.9) / 0.2 * 100))
    
    # Factor 2: India VIX (typically 10-30 range)
    india_vix = 13 + random.gauss(0, 4)
    india_vix = max(9, min(35, india_vix))
    vix_score = max(0, min(100, (30 - india_vix) / 20 * 100))
    
    # Factor 3: FII/DII Flow (net buying = greed)
    fii_flow = random.gauss(500, 2000)  # in crores
    dii_flow = random.gauss(800, 1500)
    net_flow = fii_flow + dii_flow
    fii_score = max(0, min(100, 50 + net_flow / 100))
    
    # Factor 4: Nifty PCR (0.7-1.3 typical range)
    nifty_pcr = 0.85 + random.gauss(0, 0.15)
    nifty_pcr = max(0.5, min(1.5, nifty_pcr))
    # PCR > 1 = more puts = fear, PCR < 1 = more calls = greed
    pcr_score = max(0, min(100, (1.3 - nifty_pcr) / 0.8 * 100))
    
    # Factor 5: Advance-Decline Ratio (NSE)
    advances = 800 + random.gauss(200, 300)
    declines = 1000 - advances + random.gauss(0, 100)
    ad_ratio = advances / max(declines, 1)
    ad_score = max(0, min(100, ad_ratio * 50))
    
    # Factor 6: Nifty Bank vs Nifty 50 (sector rotation)
    bank_nifty = generate_realistic_history(47500, 0.014, days=30, seed=hash("banknifty_ind" + base_date.strftime("%Y-%m-%d")))
    bank_change = (bank_nifty[-1] - bank_nifty[0]) / bank_nifty[0]
    nifty_change = (nifty_history[-1] - nifty_history[-30]) / nifty_history[-30]
    relative_strength = bank_change - nifty_change
    bank_score = max(0, min(100, 50 + relative_strength * 500))
    
    # Weighted average (India-specific weights)
    weights = {
        "momentum": 0.20,
        "vix": 0.20,
        "fii_dii": 0.20,
        "pcr": 0.15,
        "breadth": 0.15,
        "bank": 0.10,
    }
    
    overall_score = (
        momentum_score * weights["momentum"] +
        vix_score * weights["vix"] +
        fii_score * weights["fii_dii"] +
        pcr_score * weights["pcr"] +
        ad_score * weights["breadth"] +
        bank_score * weights["bank"]
    )
    
    # Determine sentiment
    if overall_score <= 25:
        sentiment = "Extreme Fear"
        color = "#dc2626"
        emoji = "😱"
    elif overall_score <= 45:
        sentiment = "Fear"
        color = "#f97316"
        emoji = "😨"
    elif overall_score <= 55:
        sentiment = "Neutral"
        color = "#eab308"
        emoji = "😐"
    elif overall_score <= 75:
        sentiment = "Greed"
        color = "#84cc16"
        emoji = "😊"
    else:
        sentiment = "Extreme Greed"
        color = "#22c55e"
        emoji = "🤑"
    
    # Historical data
    historical = []
    for days_ago in range(30, 0, -1):
        past_seed = hash("india_fg" + (base_date - timedelta(days=days_ago)).strftime("%Y-%m-%d"))
        random.seed(past_seed)
        past_score = 50 + random.gauss(0, 18)
        past_score = max(5, min(95, past_score))
        historical.append({
            "date": (base_date - timedelta(days=days_ago)).strftime("%Y-%m-%d"),
            "score": round(past_score, 1)
        })
    historical.append({"date": base_date.strftime("%Y-%m-%d"), "score": round(overall_score, 1)})
    
    return {
        "score": round(overall_score, 1),
        "sentiment": sentiment,
        "color": color,
        "emoji": emoji,
        "market": "India",
        "factors": {
            "momentum": {"score": round(momentum_score, 1), "label": "Nifty Momentum", "description": f"Nifty vs 125-day MA"},
            "vix": {"score": round(vix_score, 1), "label": "India VIX", "description": f"VIX: {india_vix:.1f}"},
            "fii_dii": {"score": round(fii_score, 1), "label": "FII/DII Flow", "description": f"Net: ₹{net_flow:.0f}Cr"},
            "pcr": {"score": round(pcr_score, 1), "label": "Nifty PCR", "description": f"PCR: {nifty_pcr:.2f}"},
            "breadth": {"score": round(ad_score, 1), "label": "Advance/Decline", "description": f"{advances:.0f}/{declines:.0f}"},
            "bank": {"score": round(bank_score, 1), "label": "Bank Nifty Strength", "description": f"vs Nifty"},
        },
        "historical": historical,
        "last_updated": base_date.strftime("%Y-%m-%d %H:%M"),
    }


@app.route("/api/fear-greed-india")
def get_fear_greed_india():
    """Return India-specific Fear & Greed Index."""
    cache_key = "fear_greed_india"
    
    if cache_key in _cache:
        cached_data, cache_time = _cache[cache_key]
        if (datetime.now() - cache_time).total_seconds() < CACHE_TTL_SECONDS:
            return jsonify(cached_data)
    
    result = calculate_india_fear_greed_index()
    result["fetched_at"] = datetime.now().isoformat()
    
    _cache[cache_key] = (result, datetime.now())
    return jsonify(result)


def detect_railroad_tracks(stocks: dict):
    """
    Detect stocks where 20 SMA and 40 SMA are running parallel like railroad tracks.
    This indicates a strong, sustained trend.
    
    Railroad tracks criteria:
    1. 20 SMA and 40 SMA are close together (within 2-4% of price)
    2. Both SMAs have similar slope (same direction)
    3. Consistent gap maintained over last 10+ days
    """
    base_date = datetime.now()
    
    results = {
        "bullish_tracks": [],  # Both SMAs rising, 20 > 40
        "bearish_tracks": [],  # Both SMAs falling, 20 < 40
        "converging": [],      # SMAs getting closer (potential crossover)
        "diverging": [],       # SMAs getting further apart
    }
    
    for name, config in stocks.items():
        try:
            seed = hash(name + base_date.strftime("%Y-%m-%d"))
            history = generate_realistic_history(
                config["base_price"],
                config["volatility"],
                days=60,
                seed=seed
            )
            
            if len(history) < 45:
                continue
            
            # Calculate SMAs
            def calc_sma(data, period, end_idx):
                start = max(0, end_idx - period + 1)
                return sum(data[start:end_idx+1]) / (end_idx - start + 1)
            
            # Current SMAs
            sma_20 = calc_sma(history, 20, len(history)-1)
            sma_40 = calc_sma(history, 40, len(history)-1)
            
            # SMAs from 5 days ago (to calculate slope)
            sma_20_prev = calc_sma(history, 20, len(history)-6)
            sma_40_prev = calc_sma(history, 40, len(history)-6)
            
            # SMAs from 10 days ago
            sma_20_10d = calc_sma(history, 20, len(history)-11)
            sma_40_10d = calc_sma(history, 40, len(history)-11)
            
            current_price = history[-1]
            
            # Calculate metrics
            gap_pct = abs(sma_20 - sma_40) / current_price * 100
            gap_pct_prev = abs(sma_20_prev - sma_40_prev) / history[-6] * 100
            gap_pct_10d = abs(sma_20_10d - sma_40_10d) / history[-11] * 100
            
            sma_20_slope = (sma_20 - sma_20_prev) / sma_20_prev * 100
            sma_40_slope = (sma_40 - sma_40_prev) / sma_40_prev * 100
            
            # Check if slopes are similar (both moving same direction)
            slopes_aligned = (sma_20_slope > 0 and sma_40_slope > 0) or (sma_20_slope < 0 and sma_40_slope < 0)
            
            # Railroad track criteria: gap between 1-4%, consistent over 10 days
            is_railroad = (1.0 <= gap_pct <= 4.0) and slopes_aligned and abs(gap_pct - gap_pct_10d) < 1.0
            
            item = {
                "name": name,
                "symbol": config["symbol"],
                "price": round(current_price, 2),
                "sma_20": round(sma_20, 2),
                "sma_40": round(sma_40, 2),
                "gap_pct": round(gap_pct, 2),
                "sma_20_slope": round(sma_20_slope, 3),
                "sma_40_slope": round(sma_40_slope, 3),
                "trend_strength": round(abs(sma_20_slope + sma_40_slope) / 2, 3),
            }
            
            if is_railroad:
                if sma_20 > sma_40 and sma_20_slope > 0:
                    item["signal"] = "Bullish Railroad"
                    item["description"] = "Strong uptrend - SMAs rising in parallel"
                    results["bullish_tracks"].append(item)
                elif sma_20 < sma_40 and sma_20_slope < 0:
                    item["signal"] = "Bearish Railroad"
                    item["description"] = "Strong downtrend - SMAs falling in parallel"
                    results["bearish_tracks"].append(item)
            else:
                # Check for converging/diverging
                gap_change = gap_pct - gap_pct_prev
                if abs(gap_change) > 0.3:
                    if gap_change < 0:
                        item["signal"] = "Converging"
                        item["description"] = "SMAs getting closer - watch for crossover"
                        results["converging"].append(item)
                    else:
                        item["signal"] = "Diverging"
                        item["description"] = "SMAs spreading apart - trend strengthening"
                        results["diverging"].append(item)
                        
        except Exception as e:
            logger.warning(f"Error detecting railroad for {name}: {e}")
    
    # Sort by trend strength
    for key in results:
        results[key].sort(key=lambda x: x.get("trend_strength", 0), reverse=True)
    
    return results


@app.route("/api/railroad-tracks")
def get_railroad_tracks():
    """Return stocks with railroad track pattern (parallel 20/40 SMA)."""
    cache_key = "railroad_tracks"
    
    if cache_key in _cache:
        cached_data, cache_time = _cache[cache_key]
        if (datetime.now() - cache_time).total_seconds() < CACHE_TTL_SECONDS:
            return jsonify(cached_data)
    
    results = detect_railroad_tracks(INDIAN_STOCKS)
    
    response_data = {
        **results,
        "fetched_at": datetime.now().isoformat(),
        "total_scanned": len(INDIAN_STOCKS),
    }
    
    _cache[cache_key] = (response_data, datetime.now())
    return jsonify(response_data)


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                       MARKET DASHBOARD                               ║
╠══════════════════════════════════════════════════════════════════════╣
║  🌐 Dashboard URL: http://127.0.0.1:5050                             ║
║                                                                      ║
║  📊 Data Mode: """ + ("LIVE (API keys configured)" if (TWELVE_DATA_API_KEY or FMP_API_KEY) else "SIMULATED (no API keys)") + """
║                                                                      ║
║  🔑 For LIVE data, set environment variables:                        ║
║     • TWELVE_DATA_API_KEY - Free: https://twelvedata.com             ║
║     • FMP_API_KEY - Free: https://financialmodelingprep.com          ║
╚══════════════════════════════════════════════════════════════════════╝
    """)
    app.run(debug=True, port=5050, host="0.0.0.0")

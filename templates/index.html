"""Market Dashboard - Flask backend using FREE APIs (no Yahoo Finance)."""

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from datetime import datetime, timedelta
import logging
import requests
import random
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Simple in-memory cache
_cache = {}


# ============================================================================
# CONFIGURATION LOADER
# ============================================================================
def load_config():
    """
    Load configuration from multiple sources with priority:
    1. Environment variables (highest priority)
    2. config.properties file in the app directory
    3. Default values (lowest priority)
    """
    config = {
        "TWELVE_DATA_API_KEY": "",
        "FMP_API_KEY": "",
        "CACHE_TTL_SECONDS": 300,
    }
    
    # Try to load from config.properties file
    config_file = Path(__file__).parent / "config.properties"
    if config_file.exists():
        logger.info(f"Loading configuration from {config_file}")
        try:
            with open(config_file, "r") as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip()
                        # Only use non-placeholder values
                        if key in config and value and not value.startswith("your_"):
                            if key == "CACHE_TTL_SECONDS":
                                config[key] = int(value)
                            else:
                                config[key] = value
                            logger.info(f"Loaded {key} from config.properties")
        except Exception as e:
            logger.warning(f"Error reading config.properties: {e}")
    else:
        logger.info(f"No config.properties found at {config_file}, using defaults")
    
    # Environment variables override config file
    for key in config:
        env_value = os.environ.get(key)
        if env_value:
            if key == "CACHE_TTL_SECONDS":
                config[key] = int(env_value)
            else:
                config[key] = env_value
            logger.info(f"Loaded {key} from environment variable")
    
    return config


# Load configuration
_config = load_config()
TWELVE_DATA_API_KEY = _config["TWELVE_DATA_API_KEY"]
FMP_API_KEY = _config["FMP_API_KEY"]
CACHE_TTL_SECONDS = _config["CACHE_TTL_SECONDS"]

# Log configuration status
if TWELVE_DATA_API_KEY:
    logger.info("Twelve Data API key configured")
else:
    logger.info("Twelve Data API key NOT configured - will use simulated data")
    
if FMP_API_KEY:
    logger.info("FMP API key configured")
else:
    logger.info("FMP API key NOT configured")


# ============================================================================
# FREE API CONFIGURATION
# ============================================================================
# This dashboard uses simulated realistic market data by default.
# For REAL data, configure API keys in one of these ways:
#
# Option 1: Edit config.properties file in the app directory
# Option 2: Set environment variables:
#   TWELVE_DATA_API_KEY=your_key
#   FMP_API_KEY=your_key
#
# Get free API keys from:
# 1. Twelve Data - https://twelvedata.com (800 calls/day free)
# 2. Financial Modeling Prep - https://financialmodelingprep.com
# ============================================================================

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
    
    logger.info(f"🔍 Attempting to fetch real data for {symbol}...")
    
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
            logger.info(f"📡 Calling Twelve Data API for {symbol}...")
            resp = requests.get(url, params=params, timeout=10)
            logger.info(f"📡 Twelve Data response status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                if "values" in data:
                    logger.info(f"✅ Got real data for {symbol} from Twelve Data")
                    return data
                elif "code" in data or "message" in data:
                    logger.warning(f"⚠️ Twelve Data API error for {symbol}: {data.get('message', data)}")
            else:
                logger.warning(f"⚠️ Twelve Data HTTP {resp.status_code} for {symbol}")
        except requests.exceptions.Timeout:
            logger.warning(f"⏱️ Twelve Data TIMEOUT for {symbol} - likely blocked by firewall")
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"🔌 Twelve Data CONNECTION ERROR for {symbol}: {e}")
        except Exception as e:
            logger.warning(f"❌ Twelve Data error for {symbol}: {e}")
    
    # Try Financial Modeling Prep
    if FMP_API_KEY:
        try:
            url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol}"
            params = {"apikey": FMP_API_KEY, "timeseries": 30}
            logger.info(f"📡 Calling FMP API for {symbol}...")
            resp = requests.get(url, params=params, timeout=10)
            logger.info(f"📡 FMP response status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                if "historical" in data:
                    logger.info(f"✅ Got real data for {symbol} from FMP")
                    return data
                else:
                    logger.warning(f"⚠️ FMP no historical data for {symbol}: {data}")
            else:
                logger.warning(f"⚠️ FMP HTTP {resp.status_code} for {symbol}")
        except requests.exceptions.Timeout:
            logger.warning(f"⏱️ FMP TIMEOUT for {symbol} - likely blocked by firewall")
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"🔌 FMP CONNECTION ERROR for {symbol}: {e}")
        except Exception as e:
            logger.warning(f"❌ FMP error for {symbol}: {e}")
    
    logger.info(f"📊 Using simulated data for {symbol}")
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


def calculate_relative_strength(stocks: dict):
    """
    Calculate Relative Strength of stocks vs their parent index.
    Shows stocks outperforming/underperforming Nifty 50.
    
    RS = (Stock Performance / Index Performance) over different periods.
    """
    base_date = datetime.now()
    
    # Get Nifty 50 data as benchmark
    nifty_seed = hash("Nifty 50 Index" + base_date.strftime("%Y-%m-%d"))
    nifty_history = generate_realistic_history(22150, 0.012, days=90, seed=nifty_seed)
    
    # Calculate Nifty returns over different periods
    nifty_returns = {
        "1w": (nifty_history[-1] - nifty_history[-6]) / nifty_history[-6] * 100 if len(nifty_history) > 6 else 0,
        "1m": (nifty_history[-1] - nifty_history[-22]) / nifty_history[-22] * 100 if len(nifty_history) > 22 else 0,
        "3m": (nifty_history[-1] - nifty_history[0]) / nifty_history[0] * 100,
    }
    
    results = {
        "outperformers": [],
        "underperformers": [],
        "benchmark": {
            "name": "Nifty 50",
            "returns": nifty_returns,
        }
    }
    
    # Exclude indices from stock analysis
    exclude_symbols = ["NIFTY", "BANKNIFTY", "NIFTYIT"]
    
    for name, config in stocks.items():
        if config["symbol"] in exclude_symbols:
            continue
            
        try:
            seed = hash(name + base_date.strftime("%Y-%m-%d"))
            history = generate_realistic_history(
                config["base_price"],
                config["volatility"],
                days=90,
                seed=seed
            )
            
            if len(history) < 22:
                continue
            
            current_price = history[-1]
            
            # Calculate stock returns
            stock_returns = {
                "1w": (history[-1] - history[-6]) / history[-6] * 100 if len(history) > 6 else 0,
                "1m": (history[-1] - history[-22]) / history[-22] * 100 if len(history) > 22 else 0,
                "3m": (history[-1] - history[0]) / history[0] * 100,
            }
            
            # Calculate Relative Strength (RS) vs Nifty
            rs_values = {
                "1w": stock_returns["1w"] - nifty_returns["1w"],
                "1m": stock_returns["1m"] - nifty_returns["1m"],
                "3m": stock_returns["3m"] - nifty_returns["3m"],
            }
            
            # Overall RS score (weighted average)
            rs_score = rs_values["1w"] * 0.2 + rs_values["1m"] * 0.3 + rs_values["3m"] * 0.5
            
            # RS momentum (is RS improving?)
            # Calculate RS line slope
            rs_line = []
            for i in range(20, 0, -1):
                if len(history) > i and len(nifty_history) > i:
                    stock_ret = (history[-1] - history[-i]) / history[-i]
                    nifty_ret = (nifty_history[-1] - nifty_history[-i]) / nifty_history[-i]
                    rs_line.append(stock_ret / max(nifty_ret, 0.001) if nifty_ret != 0 else 1)
            
            rs_momentum = "rising" if len(rs_line) > 5 and rs_line[-1] > rs_line[-5] else "falling"
            
            item = {
                "name": name,
                "symbol": config["symbol"],
                "price": round(current_price, 2),
                "stock_returns": {k: round(v, 2) for k, v in stock_returns.items()},
                "rs_vs_nifty": {k: round(v, 2) for k, v in rs_values.items()},
                "rs_score": round(rs_score, 2),
                "rs_momentum": rs_momentum,
                "outperforming": rs_score > 0,
            }
            
            if rs_score > 0:
                results["outperformers"].append(item)
            else:
                results["underperformers"].append(item)
                
        except Exception as e:
            logger.warning(f"Error calculating RS for {name}: {e}")
    
    # Sort by RS score
    results["outperformers"].sort(key=lambda x: x["rs_score"], reverse=True)
    results["underperformers"].sort(key=lambda x: x["rs_score"])
    
    return results


@app.route("/api/relative-strength")
def get_relative_strength():
    """Return stocks ranked by relative strength vs Nifty 50."""
    cache_key = "relative_strength"
    
    if cache_key in _cache:
        cached_data, cache_time = _cache[cache_key]
        if (datetime.now() - cache_time).total_seconds() < CACHE_TTL_SECONDS:
            return jsonify(cached_data)
    
    results = calculate_relative_strength(INDIAN_STOCKS)
    
    response_data = {
        **results,
        "fetched_at": datetime.now().isoformat(),
        "total_scanned": len(INDIAN_STOCKS) - 3,  # Exclude indices
    }
    
    _cache[cache_key] = (response_data, datetime.now())
    return jsonify(response_data)


# Sector definitions with constituent stocks
INDIAN_SECTORS = {
    "Banking": {
        "stocks": ["HDFC Bank", "ICICI Bank", "SBI", "Kotak Bank", "Axis Bank", "IndusInd Bank"],
        "index": "Nifty Bank",
        "color": "#3b82f6"
    },
    "IT": {
        "stocks": ["TCS", "Infosys", "Wipro", "HCL Tech", "Tech Mahindra"],
        "index": "Nifty IT",
        "color": "#8b5cf6"
    },
    "Energy": {
        "stocks": ["Reliance", "ONGC", "Coal India", "NTPC", "Power Grid"],
        "index": "Nifty 50 Index",
        "color": "#f59e0b"
    },
    "Metals": {
        "stocks": ["Tata Steel", "JSW Steel"],
        "index": "Nifty 50 Index",
        "color": "#6b7280"
    },
    "Auto": {
        "stocks": ["Maruti", "M&M", "Tata Motors"],
        "index": "Nifty 50 Index",
        "color": "#ef4444"
    },
    "Pharma": {
        "stocks": ["Sun Pharma"],
        "index": "Nifty 50 Index",
        "color": "#10b981"
    },
    "FMCG": {
        "stocks": ["HUL", "ITC", "Asian Paints", "Titan"],
        "index": "Nifty 50 Index",
        "color": "#ec4899"
    },
    "Infra": {
        "stocks": ["L&T", "Adani Ports"],
        "index": "Nifty 50 Index",
        "color": "#14b8a6"
    },
    "Telecom": {
        "stocks": ["Bharti Airtel"],
        "index": "Nifty 50 Index",
        "color": "#06b6d4"
    },
    "Finance": {
        "stocks": ["Bajaj Finance"],
        "index": "Nifty 50 Index",
        "color": "#84cc16"
    },
}


def analyze_sectors():
    """
    Analyze sector performance and identify:
    1. Top performing sectors
    2. Bottomed out sectors (showing reversal signs)
    3. Underperforming sectors
    
    Also provides top 2 stocks in each category.
    """
    base_date = datetime.now()
    
    sector_results = []
    
    for sector_name, sector_config in INDIAN_SECTORS.items():
        stock_performances = []
        
        for stock_name in sector_config["stocks"]:
            if stock_name not in INDIAN_STOCKS:
                continue
                
            config = INDIAN_STOCKS[stock_name]
            seed = hash(stock_name + base_date.strftime("%Y-%m-%d"))
            history = generate_realistic_history(
                config["base_price"],
                config["volatility"],
                days=90,
                seed=seed
            )
            
            if len(history) < 30:
                continue
            
            current_price = history[-1]
            
            # Calculate returns
            returns_1w = (history[-1] - history[-6]) / history[-6] * 100 if len(history) > 6 else 0
            returns_1m = (history[-1] - history[-22]) / history[-22] * 100 if len(history) > 22 else 0
            returns_3m = (history[-1] - history[0]) / history[0] * 100
            
            # Check for reversal signs (price bouncing from recent lows)
            min_30d = min(history[-30:])
            max_30d = max(history[-30:])
            min_idx = history[-30:].index(min_30d)
            bounce_from_low = (current_price - min_30d) / min_30d * 100
            is_near_bottom = min_idx < 10 and bounce_from_low > 3  # Low was recent and bounced
            
            # RSI-like momentum indicator
            gains = sum(max(0, history[i] - history[i-1]) for i in range(-14, 0))
            losses = sum(max(0, history[i-1] - history[i]) for i in range(-14, 0))
            rsi = 100 - (100 / (1 + gains / max(losses, 0.01)))
            
            stock_performances.append({
                "name": stock_name,
                "symbol": config["symbol"],
                "price": round(current_price, 2),
                "returns_1w": round(returns_1w, 2),
                "returns_1m": round(returns_1m, 2),
                "returns_3m": round(returns_3m, 2),
                "bounce_from_low": round(bounce_from_low, 2),
                "is_near_bottom": is_near_bottom,
                "rsi": round(rsi, 1),
            })
        
        if not stock_performances:
            continue
        
        # Calculate sector averages
        avg_returns_1w = sum(s["returns_1w"] for s in stock_performances) / len(stock_performances)
        avg_returns_1m = sum(s["returns_1m"] for s in stock_performances) / len(stock_performances)
        avg_returns_3m = sum(s["returns_3m"] for s in stock_performances) / len(stock_performances)
        avg_bounce = sum(s["bounce_from_low"] for s in stock_performances) / len(stock_performances)
        bottomed_stocks = sum(1 for s in stock_performances if s["is_near_bottom"])
        
        # Sector score (weighted)
        sector_score = avg_returns_1w * 0.3 + avg_returns_1m * 0.4 + avg_returns_3m * 0.3
        
        # Is sector showing reversal? (bottomed out)
        is_bottomed = avg_returns_3m < -5 and avg_bounce > 5 and bottomed_stocks >= len(stock_performances) * 0.5
        
        sector_results.append({
            "sector": sector_name,
            "color": sector_config["color"],
            "stocks_count": len(stock_performances),
            "avg_returns": {
                "1w": round(avg_returns_1w, 2),
                "1m": round(avg_returns_1m, 2),
                "3m": round(avg_returns_3m, 2),
            },
            "sector_score": round(sector_score, 2),
            "avg_bounce": round(avg_bounce, 2),
            "is_bottomed": is_bottomed,
            "stocks": stock_performances,
        })
    
    # Sort and categorize
    sector_results.sort(key=lambda x: x["sector_score"], reverse=True)
    
    # Top performing (top 3 by score)
    top_performing = [s for s in sector_results if s["sector_score"] > 2][:3]
    
    # Bottomed out (showing reversal signs)
    bottomed_out = [s for s in sector_results if s["is_bottomed"]]
    
    # Underperforming (bottom 3 by score, excluding bottomed)
    underperforming = [s for s in sector_results if s["sector_score"] < -2 and not s["is_bottomed"]][:3]
    
    # Get top 2 stocks for each category
    def get_top_stocks(sectors, sort_key="returns_1m", reverse=True, limit=2):
        all_stocks = []
        for sector in sectors:
            for stock in sector["stocks"]:
                stock["sector"] = sector["sector"]
                stock["sector_color"] = sector["color"]
                all_stocks.append(stock)
        all_stocks.sort(key=lambda x: x.get(sort_key, 0), reverse=reverse)
        return all_stocks[:limit]
    
    return {
        "top_performing": {
            "sectors": top_performing,
            "top_stocks": get_top_stocks(top_performing, "returns_1m", True, 2),
        },
        "bottomed_out": {
            "sectors": bottomed_out,
            "top_stocks": get_top_stocks(bottomed_out, "bounce_from_low", True, 2),
        },
        "underperforming": {
            "sectors": underperforming,
            "top_stocks": get_top_stocks(underperforming, "returns_1m", False, 2),
        },
        "all_sectors": sector_results,
    }


@app.route("/api/sector-analysis")
def get_sector_analysis():
    """Return sector performance analysis."""
    cache_key = "sector_analysis"
    
    if cache_key in _cache:
        cached_data, cache_time = _cache[cache_key]
        if (datetime.now() - cache_time).total_seconds() < CACHE_TTL_SECONDS:
            return jsonify(cached_data)
    
    results = analyze_sectors()
    
    response_data = {
        **results,
        "fetched_at": datetime.now().isoformat(),
        "total_sectors": len(INDIAN_SECTORS),
    }
    
    _cache[cache_key] = (response_data, datetime.now())
    return jsonify(response_data)


def detect_rounding_bottom(stocks: dict):
    """
    Detect stocks showing a rounding bottom pattern.
    
    Rounding bottom (saucer bottom) characteristics:
    1. Price declined over a period
    2. Price stabilized and formed a rounded base
    3. Price is now recovering from the base
    4. Volume typically increases on the right side
    
    We look for:
    - 3M return negative (was in decline)
    - Recent price above the 30-day low
    - Gradual recovery (bounce from low > 5%)
    - Price forming a "U" shape pattern
    """
    base_date = datetime.now()
    results = []
    
    # Exclude indices
    exclude_symbols = ["NIFTY", "BANKNIFTY", "NIFTYIT"]
    
    for name, config in stocks.items():
        if config["symbol"] in exclude_symbols:
            continue
            
        try:
            seed = hash(name + base_date.strftime("%Y-%m-%d"))
            history = generate_realistic_history(
                config["base_price"],
                config["volatility"],
                days=90,
                seed=seed
            )
            
            if len(history) < 60:
                continue
            
            current_price = history[-1]
            
            # Calculate metrics
            # 3M return (was in decline?)
            returns_3m = (history[-1] - history[0]) / history[0] * 100
            
            # Find the bottom (minimum price) and when it occurred
            min_price = min(history)
            min_idx = history.index(min_price)
            days_since_bottom = len(history) - min_idx - 1
            
            # Bounce from bottom
            bounce_pct = (current_price - min_price) / min_price * 100
            
            # Check if bottom was in the middle portion (rounding pattern)
            # Bottom should be roughly in the middle third of the period
            is_middle_bottom = 20 < min_idx < 70
            
            # Calculate the "roundness" - price should gradually decline then gradually rise
            # Compare first third, middle third, last third averages
            first_third = sum(history[:30]) / 30
            middle_third = sum(history[30:60]) / 30
            last_third = sum(history[60:]) / 30
            
            # Rounding bottom: first > middle, last > middle (U shape)
            is_u_shape = first_third > middle_third and last_third > middle_third
            
            # Recovery strength (last 10 days momentum)
            recent_momentum = (history[-1] - history[-10]) / history[-10] * 100 if len(history) > 10 else 0
            
            # Rounding bottom criteria
            is_rounding_bottom = (
                returns_3m < 5 and  # Was not strongly trending up
                bounce_pct > 5 and  # Meaningful bounce from low
                bounce_pct < 25 and  # Not already recovered too much
                is_middle_bottom and  # Bottom in middle
                is_u_shape and  # U-shaped pattern
                days_since_bottom > 5 and  # Some time since bottom
                recent_momentum > 0  # Currently recovering
            )
            
            if is_rounding_bottom:
                # Calculate pattern strength score
                pattern_score = (
                    min(bounce_pct / 15 * 30, 30) +  # Bounce contribution (max 30)
                    min(recent_momentum * 5, 25) +  # Recent momentum (max 25)
                    (25 if 30 < min_idx < 50 else 15) +  # How centered the bottom is (max 25)
                    min((first_third - middle_third) / middle_third * 100, 20)  # U-shape depth (max 20)
                )
                
                results.append({
                    "name": name,
                    "symbol": config["symbol"],
                    "price": round(current_price, 2),
                    "min_price": round(min_price, 2),
                    "bounce_pct": round(bounce_pct, 2),
                    "days_since_bottom": days_since_bottom,
                    "returns_3m": round(returns_3m, 2),
                    "recent_momentum": round(recent_momentum, 2),
                    "pattern_score": round(pattern_score, 1),
                    "stage": "Early Recovery" if bounce_pct < 10 else "Mid Recovery" if bounce_pct < 18 else "Late Recovery",
                })
                
        except Exception as e:
            logger.warning(f"Error detecting rounding bottom for {name}: {e}")
    
    # Sort by pattern score
    results.sort(key=lambda x: x["pattern_score"], reverse=True)
    
    return results


@app.route("/api/rounding-bottom")
def get_rounding_bottom():
    """Return stocks showing rounding bottom pattern."""
    cache_key = "rounding_bottom"
    
    if cache_key in _cache:
        cached_data, cache_time = _cache[cache_key]
        if (datetime.now() - cache_time).total_seconds() < CACHE_TTL_SECONDS:
            return jsonify(cached_data)
    
    results = detect_rounding_bottom(INDIAN_STOCKS)
    
    response_data = {
        "stocks": results,
        "fetched_at": datetime.now().isoformat(),
        "total_found": len(results),
        "total_scanned": len(INDIAN_STOCKS) - 3,
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

"""Market Dashboard - Flask backend using FREE APIs (no Yahoo Finance)."""

from flask import Flask, jsonify, render_template, request, abort
from flask_cors import CORS
from datetime import datetime, timedelta
from functools import wraps
from threading import Lock
from collections import OrderedDict
import logging
import requests
import random
import os
import re
import html
from pathlib import Path

# Configure logging with secure format (avoid log injection)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Security: Configure CORS with specific origins in production
# For development, allow all origins; in production, specify allowed origins
CORS(app, resources={
    r"/api/*": {
        "origins": "*",  # In production, replace with specific domains
        "methods": ["GET"],
        "allow_headers": ["Content-Type"]
    }
})


# ============================================================================
# GLOBAL ERROR HANDLERS
# ============================================================================
@app.errorhandler(Exception)
def handle_exception(e):
    """Handle all uncaught exceptions."""
    logger.error(f"Unhandled exception: {e}", exc_info=True)
    return jsonify({
        "error": "An internal error occurred",
        "status": "error"
    }), 500


@app.errorhandler(404)
def handle_not_found(e):
    """Handle 404 errors."""
    return jsonify({
        "error": "Resource not found",
        "status": "not_found"
    }), 404


@app.errorhandler(405)
def handle_method_not_allowed(e):
    """Handle 405 errors."""
    return jsonify({
        "error": "Method not allowed",
        "status": "method_not_allowed"
    }), 405


@app.errorhandler(500)
def handle_internal_error(e):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {e}", exc_info=True)
    return jsonify({
        "error": "Internal server error",
        "status": "error"
    }), 500


# Security: Set secure headers
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses."""
    try:
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        # Content Security Policy for API responses
        if request.path.startswith('/api/'):
            response.headers['Content-Type'] = 'application/json'
    except Exception as e:
        logger.warning(f"Error adding security headers: {e}")
    return response


# ============================================================================
# SECURE CACHE IMPLEMENTATION
# ============================================================================
class SecureCache:
    """
    Thread-safe cache with TTL, max size limit, and automatic cleanup.
    Prevents memory leaks by limiting cache size and removing expired entries.
    """
    
    def __init__(self, max_size: int = 100, default_ttl: int = 300):
        self._cache: OrderedDict = OrderedDict()
        self._lock = Lock()
        self._max_size = max_size
        self._default_ttl = default_ttl
    
    def get(self, key: str) -> tuple:
        """Get cached item if not expired. Returns (data, is_valid)."""
        with self._lock:
            if key not in self._cache:
                return None, False
            
            data, expiry_time = self._cache[key]
            if datetime.now() > expiry_time:
                # Remove expired entry
                del self._cache[key]
                return None, False
            
            # Move to end (LRU behavior)
            self._cache.move_to_end(key)
            return data, True
    
    def set(self, key: str, data: any, ttl: int = None) -> None:
        """Set cache item with TTL."""
        if ttl is None:
            ttl = self._default_ttl
        
        expiry_time = datetime.now() + timedelta(seconds=ttl)
        
        with self._lock:
            # Remove oldest items if cache is full
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            
            self._cache[key] = (data, expiry_time)
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count of removed items."""
        removed = 0
        now = datetime.now()
        
        with self._lock:
            expired_keys = [
                key for key, (_, expiry) in self._cache.items()
                if now > expiry
            ]
            for key in expired_keys:
                del self._cache[key]
                removed += 1
        
        return removed
    
    def stats(self) -> dict:
        """Return cache statistics."""
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "keys": list(self._cache.keys())
            }


# Initialize secure cache
_cache = SecureCache(max_size=50, default_ttl=300)


# ============================================================================
# RATE LIMITING (Simple in-memory rate limiter)
# ============================================================================
class RateLimiter:
    """Simple rate limiter to prevent API abuse."""
    
    def __init__(self, requests_per_minute: int = 60):
        self._requests: dict = {}
        self._lock = Lock()
        self._limit = requests_per_minute
    
    def is_allowed(self, client_ip: str) -> bool:
        """Check if request is allowed for this client."""
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        
        with self._lock:
            # Cleanup old entries
            self._requests = {
                ip: times for ip, times in self._requests.items()
                if times and times[-1] > minute_ago
            }
            
            if client_ip not in self._requests:
                self._requests[client_ip] = []
            
            # Remove requests older than 1 minute
            self._requests[client_ip] = [
                t for t in self._requests[client_ip] if t > minute_ago
            ]
            
            if len(self._requests[client_ip]) >= self._limit:
                return False
            
            self._requests[client_ip].append(now)
            return True


_rate_limiter = RateLimiter(requests_per_minute=120)


def rate_limit(f):
    """Decorator to apply rate limiting to routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.remote_addr or 'unknown'
        if not _rate_limiter.is_allowed(client_ip):
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return jsonify({"error": "Rate limit exceeded. Please try again later."}), 429
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# INPUT VALIDATION HELPERS
# ============================================================================
def sanitize_string(value: str, max_length: int = 100) -> str:
    """Sanitize string input to prevent injection attacks."""
    try:
        if not isinstance(value, str):
            return ""
        # Remove any HTML/script tags and limit length
        value = html.escape(value[:max_length])
        # Remove any potentially dangerous characters
        value = re.sub(r'[<>"\';(){}\[\]]', '', value)
        return value.strip()
    except Exception:
        return ""


def validate_symbol(symbol: str) -> bool:
    """Validate that a symbol contains only allowed characters."""
    try:
        if not symbol or not isinstance(symbol, str):
            return False
        # Symbols should only contain alphanumeric, dots, slashes, and hyphens
        return bool(re.match(r'^[A-Za-z0-9./\-_]{1,20}$', symbol))
    except Exception:
        return False


# ============================================================================
# SAFE MATH HELPERS (Division-by-zero proof)
# ============================================================================
def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default if denominator is zero or invalid."""
    try:
        if denominator is None or denominator == 0:
            return default
        result = numerator / denominator
        # Check for infinity or NaN
        if result != result or abs(result) == float('inf'):  # NaN check
            return default
        return result
    except (TypeError, ValueError, ZeroDivisionError):
        return default


def safe_percentage(part: float, whole: float, default: float = 0.0) -> float:
    """Calculate percentage safely."""
    return safe_divide(part * 100, whole, default)


def safe_float(value, default: float = 0.0) -> float:
    """Safely convert value to float."""
    try:
        if value is None:
            return default
        result = float(value)
        if result != result:  # NaN check
            return default
        return result
    except (TypeError, ValueError):
        return default


def safe_int(value, default: int = 0) -> int:
    """Safely convert value to int."""
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_round(value: float, decimals: int = 2, default: float = 0.0) -> float:
    """Safely round a value."""
    try:
        if value is None or value != value:  # None or NaN check
            return default
        return round(float(value), decimals)
    except (TypeError, ValueError):
        return default


def safe_max(values: list, default: float = 0.0) -> float:
    """Safely get max from a list."""
    try:
        if not values:
            return default
        filtered = [v for v in values if v is not None and v == v]  # Filter None and NaN
        return max(filtered) if filtered else default
    except (TypeError, ValueError):
        return default


def safe_min(values: list, default: float = 0.0) -> float:
    """Safely get min from a list."""
    try:
        if not values:
            return default
        filtered = [v for v in values if v is not None and v == v]  # Filter None and NaN
        return min(filtered) if filtered else default
    except (TypeError, ValueError):
        return default


def safe_sum(values: list, default: float = 0.0) -> float:
    """Safely sum a list of values."""
    try:
        if not values:
            return default
        filtered = [safe_float(v) for v in values if v is not None]
        return sum(filtered)
    except (TypeError, ValueError):
        return default


def safe_avg(values: list, default: float = 0.0) -> float:
    """Safely calculate average of a list."""
    try:
        if not values:
            return default
        filtered = [safe_float(v) for v in values if v is not None]
        if not filtered:
            return default
        return safe_divide(sum(filtered), len(filtered), default)
    except (TypeError, ValueError):
        return default


def safe_get(dictionary: dict, key: str, default=None):
    """Safely get value from dictionary."""
    try:
        if not isinstance(dictionary, dict):
            return default
        return dictionary.get(key, default)
    except Exception:
        return default


def safe_list_get(lst: list, index: int, default=None):
    """Safely get value from list by index."""
    try:
        if not isinstance(lst, list) or not lst:
            return default
        if index < 0:
            index = len(lst) + index
        if 0 <= index < len(lst):
            return lst[index]
        return default
    except Exception:
        return default


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


def generate_realistic_history(base_price: float, volatility: float, days: int = 90, seed: int = None) -> list:
    """
    Generate realistic price history using random walk with drift.
    
    Args:
        base_price: Starting price (must be positive)
        volatility: Daily volatility factor (typically 0.01-0.03)
        days: Number of days to generate
        seed: Random seed for reproducibility
        
    Returns:
        List of prices, or empty list if error
    """
    try:
        # Validate inputs
        base_price = safe_float(base_price, 100.0)
        volatility = safe_float(volatility, 0.01)
        days = safe_int(days, 90)
        
        # Sanity checks
        if base_price <= 0:
            base_price = 100.0
        if volatility <= 0 or volatility > 1:
            volatility = 0.01
        if days <= 0 or days > 1000:
            days = 90
            
        if seed is not None:
            random.seed(seed)
        
        prices = []
        price = base_price * (1 + random.uniform(-0.08, 0.08))
        drift = 0.0002  # Slight upward drift
        
        for i in range(days):
            try:
                # Add some mean reversion
                mean_reversion = safe_divide(base_price - price, base_price, 0) * 0.01
                change = random.gauss(drift + mean_reversion, volatility)
                price = max(price * (1 + change), base_price * 0.5)  # Floor at 50% of base
                prices.append(safe_round(price, 2))
            except Exception:
                prices.append(safe_round(base_price, 2))
        
        return prices if prices else [base_price]
    except Exception as e:
        logger.error(f"Error generating price history: {e}")
        return [safe_float(base_price, 100.0)]


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


def generate_market_data(instruments: dict) -> list:
    """
    Generate market data for all instruments.
    
    Args:
        instruments: Dictionary of instrument configurations
        
    Returns:
        List of market data dictionaries, never empty
    """
    results = []
    base_date = datetime.now()
    
    if not instruments or not isinstance(instruments, dict):
        logger.warning("generate_market_data called with invalid instruments")
        return []
    
    for name, config in instruments.items():
        try:
            # Validate config
            if not isinstance(config, dict):
                logger.warning(f"Invalid config for {name}, skipping")
                continue
                
            # Use date-based seed for consistent data within same day
            seed = hash(name + base_date.strftime("%Y-%m-%d"))
            
            # Try to fetch real data first
            symbol = safe_get(config, "symbol", name)
            real_data = try_fetch_real_data(symbol)
            
            if real_data and "values" in real_data:
                try:
                    # Parse Twelve Data format
                    values = real_data.get("values", [])
                    if values and len(values) > 0:
                        sparkline = [safe_float(v.get("close", 0)) for v in reversed(values[:30])]
                        dates = [v.get("datetime", "") for v in reversed(values[:30])]
                        current_price = safe_list_get(sparkline, -1, 0)
                        prev_price = safe_list_get(sparkline, -2, current_price)
                        data_source = "live"
                    else:
                        raise ValueError("Empty values list")
                except Exception as e:
                    logger.warning(f"Error parsing real data for {name}: {e}")
                    real_data = None
            
            if not real_data or "values" not in real_data:
                # Generate simulated data
                base_price = safe_float(safe_get(config, "base_price", 100), 100)
                volatility = safe_float(safe_get(config, "volatility", 0.01), 0.01)
                
                history = generate_realistic_history(
                    base_price,
                    volatility,
                    days=90,
                    seed=seed
                )
                sparkline = history[-30:] if len(history) >= 30 else history
                dates = [(base_date - timedelta(days=len(sparkline)-1-i)).strftime("%Y-%m-%d") for i in range(len(sparkline))]
                current_price = safe_list_get(sparkline, -1, base_price)
                prev_price = safe_list_get(sparkline, -2, current_price)
                data_source = "simulated"
            
            # Calculate changes safely
            change = current_price - prev_price
            change_pct = safe_percentage(change, prev_price, 0)
            
            results.append({
                "name": name,
                "symbol": symbol,
                "currency": safe_get(config, "currency", "$"),
                "price": safe_round(current_price, 2),
                "change": safe_round(change, 2),
                "change_pct": safe_round(change_pct, 2),
                "sparkline": sparkline,
                "dates": dates,
                "high_52w": safe_round(safe_max(sparkline, current_price) * 1.08, 2),
                "low_52w": safe_round(safe_min(sparkline, current_price) * 0.92, 2),
                "last_updated": base_date.strftime("%Y-%m-%d %H:%M"),
                "data_source": data_source,
            })
        except Exception as e:
            logger.error(f"Error generating market data for {name}: {e}")
            # Add fallback data
            results.append({
                "name": name,
                "symbol": safe_get(config, "symbol", name) if isinstance(config, dict) else name,
                "currency": "$",
                "price": 0.0,
                "change": 0.0,
                "change_pct": 0.0,
                "sparkline": [],
                "dates": [],
                "high_52w": 0.0,
                "low_52w": 0.0,
                "last_updated": base_date.strftime("%Y-%m-%d %H:%M"),
                "data_source": "error",
                "error": str(e)
            })
    
    return results


def calculate_sma(prices: list, period: int) -> list:
    """
    Calculate Simple Moving Average.
    
    Args:
        prices: List of prices
        period: SMA period
        
    Returns:
        List of SMA values (None for insufficient data points)
    """
    try:
        if not prices or not isinstance(prices, list):
            return []
        
        period = safe_int(period, 20)
        if period <= 0:
            period = 20
            
        sma = []
        for i in range(len(prices)):
            if i < period - 1:
                sma.append(None)
            else:
                window = prices[i-period+1:i+1]
                sma.append(safe_avg(window))
        return sma
    except Exception as e:
        logger.warning(f"Error calculating SMA: {e}")
        return [None] * len(prices) if prices else []


def calculate_dma_crossovers(stocks: dict) -> dict:
    """
    Calculate 20/200 DMA crossovers for stocks.
    
    Args:
        stocks: Dictionary of stock configurations
        
    Returns:
        Dictionary with golden_crosses, death_crosses, bullish_trend, bearish_trend, errors
    """
    results = {
        "golden_crosses": [],
        "death_crosses": [],
        "bullish_trend": [],
        "bearish_trend": [],
        "errors": [],
    }
    
    if not stocks or not isinstance(stocks, dict):
        logger.warning("calculate_dma_crossovers called with invalid stocks")
        return results
    
    base_date = datetime.now()
    
    for name, config in stocks.items():
        try:
            # Validate config
            if not isinstance(config, dict):
                results["errors"].append({"name": name, "error": "Invalid config"})
                continue
                
            seed = hash(name + base_date.strftime("%Y-%m-%d"))
            
            base_price = safe_float(safe_get(config, "base_price", 100), 100)
            volatility = safe_float(safe_get(config, "volatility", 0.01), 0.01)
            
            history = generate_realistic_history(
                base_price,
                volatility,
                days=250,
                seed=seed
            )
            
            if len(history) < 200:
                continue
            
            dma_20 = calculate_sma(history, 20)
            dma_200 = calculate_sma(history, 200)
            
            # Validate SMA calculations
            if not dma_20 or not dma_200 or len(dma_20) != len(dma_200):
                results["errors"].append({"name": name, "error": "SMA calculation failed"})
                continue
            
            # Filter out None values
            valid_idx = [i for i in range(len(dma_200)) if dma_200[i] is not None]
            if len(valid_idx) < 6:
                continue
            
            current_price = safe_list_get(history, -1, 0)
            curr_20 = safe_list_get(dma_20, -1, 0)
            curr_200 = safe_list_get(dma_200, -1, 0)
            
            if curr_20 is None or curr_200 is None:
                continue
            
            item = {
                "name": name,
                "symbol": safe_get(config, "symbol", name),
                "current_price": safe_round(current_price, 2),
                "dma_20": safe_round(curr_20, 2),
                "dma_200": safe_round(curr_200, 2),
            }
            
            # Check for crossover in last 5 days
            cross_found = False
            for i in range(-5, 0):
                try:
                    prev_20 = safe_list_get(dma_20, i-1)
                    prev_200 = safe_list_get(dma_200, i-1)
                    curr_20_i = safe_list_get(dma_20, i)
                    curr_200_i = safe_list_get(dma_200, i)
                    
                    if None in (prev_20, prev_200, curr_20_i, curr_200_i):
                        continue
                        
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
                except Exception:
                    continue
            
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
    
    # Sort safely
    try:
        results["golden_crosses"].sort(key=lambda x: x.get("days_ago", 999))
        results["death_crosses"].sort(key=lambda x: x.get("days_ago", 999))
    except Exception as e:
        logger.warning(f"Error sorting crossovers: {e}")
    
    return results


# ============================================================================
# ROUTES
# ============================================================================

@app.route("/")
def index():
    """Serve the main dashboard page."""
    try:
        return render_template("index.html")
    except Exception as e:
        logger.error(f"Error rendering index.html: {e}")
        return "<h1>Error loading dashboard</h1><p>Please check server logs.</p>", 500


@app.route("/api/prices")
@rate_limit
def get_prices():
    """Get current market prices for all instruments."""
    cache_key = "prices"
    
    cached_data, is_valid = _cache.get(cache_key)
    if is_valid:
        return jsonify(cached_data)
    
    try:
        results = generate_market_data(INSTRUMENTS)
        has_live = any(r.get("data_source") == "live" for r in results)
        
        response_data = {
            "instruments": results,
            "fetched_at": datetime.now().isoformat(),
            "data_source": "live" if has_live else "simulated",
            "api_configured": bool(TWELVE_DATA_API_KEY or FMP_API_KEY),
        }
        
        _cache.set(cache_key, response_data, CACHE_TTL_SECONDS)
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error in get_prices: {e}")
        return jsonify({"error": "Failed to fetch prices"}), 500


@app.route("/api/golden-crosses")
@rate_limit
def get_golden_crosses():
    """Get DMA crossover signals for Indian stocks."""
    cache_key = "golden_crosses"
    
    cached_data, is_valid = _cache.get(cache_key)
    if is_valid:
        return jsonify(cached_data)
    
    try:
        results = calculate_dma_crossovers(INDIAN_STOCKS)
        
        response_data = {
            **results,
            "fetched_at": datetime.now().isoformat(),
            "total_scanned": len(INDIAN_STOCKS),
            "data_source": "simulated",
        }
        
        _cache.set(cache_key, response_data, CACHE_TTL_SECONDS)
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error in get_golden_crosses: {e}")
        return jsonify({"error": "Failed to fetch golden crosses data"}), 500


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
@rate_limit
def clear_cache():
    """Clear the application cache."""
    stats_before = _cache.stats()
    _cache.clear()
    logger.info(f"Cache cleared. Items removed: {stats_before['size']}")
    return jsonify({
        "status": "cache cleared",
        "items_removed": stats_before['size']
    })


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
@rate_limit
def get_fear_greed():
    """Return the Fear & Greed Index."""
    cache_key = "fear_greed"
    
    cached_data, is_valid = _cache.get(cache_key)
    if is_valid:
        return jsonify(cached_data)
    
    try:
        result = calculate_fear_greed_index()
        result["fetched_at"] = datetime.now().isoformat()
        
        _cache.set(cache_key, result, CACHE_TTL_SECONDS)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_fear_greed: {e}")
        return jsonify({"error": "Failed to calculate Fear & Greed Index"}), 500


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
@rate_limit
def get_fear_greed_india():
    """Return India-specific Fear & Greed Index."""
    cache_key = "fear_greed_india"
    
    cached_data, is_valid = _cache.get(cache_key)
    if is_valid:
        return jsonify(cached_data)
    
    try:
        result = calculate_india_fear_greed_index()
        result["fetched_at"] = datetime.now().isoformat()
        
        _cache.set(cache_key, result, CACHE_TTL_SECONDS)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_fear_greed_india: {e}")
        return jsonify({"error": "Failed to calculate India Fear & Greed Index"}), 500


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
@rate_limit
def get_railroad_tracks():
    """Return stocks with railroad track pattern (parallel 20/40 SMA)."""
    cache_key = "railroad_tracks"
    
    cached_data, is_valid = _cache.get(cache_key)
    if is_valid:
        return jsonify(cached_data)
    
    try:
        results = detect_railroad_tracks(INDIAN_STOCKS)
        
        response_data = {
            **results,
            "fetched_at": datetime.now().isoformat(),
            "total_scanned": len(INDIAN_STOCKS),
        }
        
        _cache.set(cache_key, response_data, CACHE_TTL_SECONDS)
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error in get_railroad_tracks: {e}")
        return jsonify({"error": "Failed to detect railroad track patterns"}), 500


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
@rate_limit
def get_relative_strength():
    """Return stocks ranked by relative strength vs Nifty 50."""
    cache_key = "relative_strength"
    
    cached_data, is_valid = _cache.get(cache_key)
    if is_valid:
        return jsonify(cached_data)
    
    try:
        results = calculate_relative_strength(INDIAN_STOCKS)
        
        response_data = {
            **results,
            "fetched_at": datetime.now().isoformat(),
            "total_scanned": len(INDIAN_STOCKS) - 3,  # Exclude indices
        }
        
        _cache.set(cache_key, response_data, CACHE_TTL_SECONDS)
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error in get_relative_strength: {e}")
        return jsonify({"error": "Failed to calculate relative strength"}), 500


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
@rate_limit
def get_sector_analysis():
    """Return sector performance analysis."""
    cache_key = "sector_analysis"
    
    cached_data, is_valid = _cache.get(cache_key)
    if is_valid:
        return jsonify(cached_data)
    
    try:
        results = analyze_sectors()
        
        response_data = {
            **results,
            "fetched_at": datetime.now().isoformat(),
            "total_sectors": len(INDIAN_SECTORS),
        }
        
        _cache.set(cache_key, response_data, CACHE_TTL_SECONDS)
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error in get_sector_analysis: {e}")
        return jsonify({"error": "Failed to analyze sectors"}), 500


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
@rate_limit
def get_rounding_bottom():
    """Return stocks showing rounding bottom pattern."""
    cache_key = "rounding_bottom"
    
    cached_data, is_valid = _cache.get(cache_key)
    if is_valid:
        return jsonify(cached_data)
    
    try:
        results = detect_rounding_bottom(INDIAN_STOCKS)
        
        response_data = {
            "stocks": results,
            "fetched_at": datetime.now().isoformat(),
            "total_found": len(results),
            "total_scanned": len(INDIAN_STOCKS) - 3,
        }
        
        _cache.set(cache_key, response_data, CACHE_TTL_SECONDS)
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error in get_rounding_bottom: {e}")
        return jsonify({"error": "Failed to detect rounding bottom patterns"}), 500


# ============================================================================
# CANDLESTICK PATTERN DETECTION
# ============================================================================

def generate_ohlc_data(base_price: float, volatility: float, days: int = 30, seed: int = None) -> list:
    """
    Generate realistic OHLC (Open, High, Low, Close) data.
    
    Returns list of dicts with: date, open, high, low, close, volume
    """
    try:
        if seed is not None:
            random.seed(seed)
        
        base_price = safe_float(base_price, 100)
        volatility = safe_float(volatility, 0.015)
        days = safe_int(days, 30)
        
        ohlc_data = []
        price = base_price * (1 + random.uniform(-0.05, 0.05))
        base_date = datetime.now()
        
        for i in range(days):
            try:
                # Daily range based on volatility
                daily_range = price * volatility * random.uniform(0.5, 2.0)
                
                # Open is previous close (or initial price)
                open_price = price
                
                # Determine if bullish or bearish day
                is_bullish = random.random() > 0.48  # Slight bullish bias
                
                if is_bullish:
                    # Bullish: close > open
                    close_price = open_price + daily_range * random.uniform(0.2, 1.0)
                    high_price = close_price + daily_range * random.uniform(0, 0.3)
                    low_price = open_price - daily_range * random.uniform(0, 0.3)
                else:
                    # Bearish: close < open
                    close_price = open_price - daily_range * random.uniform(0.2, 1.0)
                    high_price = open_price + daily_range * random.uniform(0, 0.3)
                    low_price = close_price - daily_range * random.uniform(0, 0.3)
                
                # Ensure high >= max(open, close) and low <= min(open, close)
                high_price = max(high_price, open_price, close_price)
                low_price = min(low_price, open_price, close_price)
                
                # Volume (simulated)
                avg_volume = 1000000 + random.randint(-500000, 500000)
                volume = int(avg_volume * random.uniform(0.5, 2.0))
                
                ohlc_data.append({
                    "date": (base_date - timedelta(days=days-i-1)).strftime("%Y-%m-%d"),
                    "open": safe_round(open_price, 2),
                    "high": safe_round(high_price, 2),
                    "low": safe_round(low_price, 2),
                    "close": safe_round(close_price, 2),
                    "volume": volume
                })
                
                # Next day opens near this close
                price = close_price * (1 + random.uniform(-0.01, 0.01))
                
            except Exception as e:
                logger.warning(f"Error generating OHLC for day {i}: {e}")
                continue
        
        return ohlc_data
    except Exception as e:
        logger.error(f"Error in generate_ohlc_data: {e}")
        return []


def detect_candlestick_patterns(ohlc_data: list) -> dict:
    """
    Detect candlestick patterns from OHLC data.
    
    Returns detected patterns with signal (bullish/bearish/neutral) and probability.
    """
    if not ohlc_data or len(ohlc_data) < 5:
        return {"patterns": [], "signal": "neutral", "probability": 50}
    
    patterns = []
    
    try:
        # Get last few candles for pattern detection
        candles = ohlc_data[-5:]  # Last 5 candles
        
        def body_size(candle):
            return abs(candle["close"] - candle["open"])
        
        def upper_shadow(candle):
            return candle["high"] - max(candle["open"], candle["close"])
        
        def lower_shadow(candle):
            return min(candle["open"], candle["close"]) - candle["low"]
        
        def is_bullish(candle):
            return candle["close"] > candle["open"]
        
        def is_bearish(candle):
            return candle["close"] < candle["open"]
        
        def candle_range(candle):
            return candle["high"] - candle["low"]
        
        # Current candle (most recent)
        c0 = candles[-1]
        c1 = candles[-2] if len(candles) >= 2 else None
        c2 = candles[-3] if len(candles) >= 3 else None
        c3 = candles[-4] if len(candles) >= 4 else None
        
        avg_body = safe_avg([body_size(c) for c in candles])
        avg_range = safe_avg([candle_range(c) for c in candles])
        
        # ===== SINGLE CANDLE PATTERNS =====
        
        # 1. Doji - small body, indicates indecision
        if body_size(c0) < avg_body * 0.1 and candle_range(c0) > avg_range * 0.5:
            patterns.append({
                "name": "Doji",
                "type": "single",
                "signal": "neutral",
                "description": "Indecision pattern - market is undecided",
                "reliability": 50,
                "icon": "⚖️"
            })
        
        # 2. Hammer (bullish) - small body at top, long lower shadow
        if (lower_shadow(c0) > body_size(c0) * 2 and 
            upper_shadow(c0) < body_size(c0) * 0.5 and
            body_size(c0) > 0):
            patterns.append({
                "name": "Hammer",
                "type": "single",
                "signal": "bullish",
                "description": "Potential bullish reversal - buyers stepped in",
                "reliability": 65,
                "icon": "🔨"
            })
        
        # 3. Inverted Hammer (bullish) - small body at bottom, long upper shadow
        if (upper_shadow(c0) > body_size(c0) * 2 and 
            lower_shadow(c0) < body_size(c0) * 0.5 and
            body_size(c0) > 0):
            patterns.append({
                "name": "Inverted Hammer",
                "type": "single",
                "signal": "bullish",
                "description": "Potential bullish reversal after downtrend",
                "reliability": 60,
                "icon": "🔨"
            })
        
        # 4. Hanging Man (bearish) - same as hammer but in uptrend
        if (lower_shadow(c0) > body_size(c0) * 2 and 
            upper_shadow(c0) < body_size(c0) * 0.5 and
            is_bearish(c0) and
            c1 and is_bullish(c1)):
            patterns.append({
                "name": "Hanging Man",
                "type": "single",
                "signal": "bearish",
                "description": "Potential bearish reversal - sellers emerging",
                "reliability": 60,
                "icon": "☠️"
            })
        
        # 5. Shooting Star (bearish) - small body at bottom, long upper shadow
        if (upper_shadow(c0) > body_size(c0) * 2 and 
            lower_shadow(c0) < body_size(c0) * 0.5 and
            is_bearish(c0)):
            patterns.append({
                "name": "Shooting Star",
                "type": "single",
                "signal": "bearish",
                "description": "Bearish reversal signal - rejection at highs",
                "reliability": 65,
                "icon": "💫"
            })
        
        # 6. Marubozu (strong trend) - no shadows
        if (upper_shadow(c0) < body_size(c0) * 0.05 and 
            lower_shadow(c0) < body_size(c0) * 0.05 and
            body_size(c0) > avg_body * 1.5):
            signal = "bullish" if is_bullish(c0) else "bearish"
            patterns.append({
                "name": f"{'Bullish' if is_bullish(c0) else 'Bearish'} Marubozu",
                "type": "single",
                "signal": signal,
                "description": f"Strong {signal} momentum - no rejection",
                "reliability": 70,
                "icon": "💪" if is_bullish(c0) else "📉"
            })
        
        # 7. Spinning Top - small body, long shadows on both sides
        if (body_size(c0) < avg_body * 0.5 and
            upper_shadow(c0) > body_size(c0) and
            lower_shadow(c0) > body_size(c0)):
            patterns.append({
                "name": "Spinning Top",
                "type": "single",
                "signal": "neutral",
                "description": "Indecision - neither bulls nor bears in control",
                "reliability": 45,
                "icon": "🔄"
            })
        
        # ===== TWO CANDLE PATTERNS =====
        if c1:
            # 8. Bullish Engulfing
            if (is_bearish(c1) and is_bullish(c0) and
                c0["open"] < c1["close"] and c0["close"] > c1["open"] and
                body_size(c0) > body_size(c1)):
                patterns.append({
                    "name": "Bullish Engulfing",
                    "type": "double",
                    "signal": "bullish",
                    "description": "Strong bullish reversal - buyers overwhelmed sellers",
                    "reliability": 75,
                    "icon": "🐂"
                })
            
            # 9. Bearish Engulfing
            if (is_bullish(c1) and is_bearish(c0) and
                c0["open"] > c1["close"] and c0["close"] < c1["open"] and
                body_size(c0) > body_size(c1)):
                patterns.append({
                    "name": "Bearish Engulfing",
                    "type": "double",
                    "signal": "bearish",
                    "description": "Strong bearish reversal - sellers overwhelmed buyers",
                    "reliability": 75,
                    "icon": "🐻"
                })
            
            # 10. Piercing Line (bullish)
            if (is_bearish(c1) and is_bullish(c0) and
                c0["open"] < c1["low"] and
                c0["close"] > (c1["open"] + c1["close"]) / 2 and
                c0["close"] < c1["open"]):
                patterns.append({
                    "name": "Piercing Line",
                    "type": "double",
                    "signal": "bullish",
                    "description": "Bullish reversal - strong recovery from lows",
                    "reliability": 65,
                    "icon": "📈"
                })
            
            # 11. Dark Cloud Cover (bearish)
            if (is_bullish(c1) and is_bearish(c0) and
                c0["open"] > c1["high"] and
                c0["close"] < (c1["open"] + c1["close"]) / 2 and
                c0["close"] > c1["open"]):
                patterns.append({
                    "name": "Dark Cloud Cover",
                    "type": "double",
                    "signal": "bearish",
                    "description": "Bearish reversal - selling pressure from highs",
                    "reliability": 65,
                    "icon": "🌧️"
                })
            
            # 12. Tweezer Top (bearish)
            if (abs(c0["high"] - c1["high"]) < avg_range * 0.05 and
                is_bullish(c1) and is_bearish(c0)):
                patterns.append({
                    "name": "Tweezer Top",
                    "type": "double",
                    "signal": "bearish",
                    "description": "Bearish reversal - resistance at same level",
                    "reliability": 60,
                    "icon": "🔝"
                })
            
            # 13. Tweezer Bottom (bullish)
            if (abs(c0["low"] - c1["low"]) < avg_range * 0.05 and
                is_bearish(c1) and is_bullish(c0)):
                patterns.append({
                    "name": "Tweezer Bottom",
                    "type": "double",
                    "signal": "bullish",
                    "description": "Bullish reversal - support at same level",
                    "reliability": 60,
                    "icon": "🔻"
                })
        
        # ===== THREE CANDLE PATTERNS =====
        if c1 and c2:
            # 14. Morning Star (bullish)
            if (is_bearish(c2) and body_size(c2) > avg_body and
                body_size(c1) < avg_body * 0.5 and
                is_bullish(c0) and body_size(c0) > avg_body and
                c0["close"] > (c2["open"] + c2["close"]) / 2):
                patterns.append({
                    "name": "Morning Star",
                    "type": "triple",
                    "signal": "bullish",
                    "description": "Strong bullish reversal pattern",
                    "reliability": 80,
                    "icon": "🌟"
                })
            
            # 15. Evening Star (bearish)
            if (is_bullish(c2) and body_size(c2) > avg_body and
                body_size(c1) < avg_body * 0.5 and
                is_bearish(c0) and body_size(c0) > avg_body and
                c0["close"] < (c2["open"] + c2["close"]) / 2):
                patterns.append({
                    "name": "Evening Star",
                    "type": "triple",
                    "signal": "bearish",
                    "description": "Strong bearish reversal pattern",
                    "reliability": 80,
                    "icon": "🌙"
                })
            
            # 16. Three White Soldiers (bullish)
            if (is_bullish(c2) and is_bullish(c1) and is_bullish(c0) and
                c1["close"] > c2["close"] and c0["close"] > c1["close"] and
                body_size(c0) > avg_body * 0.7 and body_size(c1) > avg_body * 0.7):
                patterns.append({
                    "name": "Three White Soldiers",
                    "type": "triple",
                    "signal": "bullish",
                    "description": "Strong bullish continuation - sustained buying",
                    "reliability": 75,
                    "icon": "⬆️⬆️⬆️"
                })
            
            # 17. Three Black Crows (bearish)
            if (is_bearish(c2) and is_bearish(c1) and is_bearish(c0) and
                c1["close"] < c2["close"] and c0["close"] < c1["close"] and
                body_size(c0) > avg_body * 0.7 and body_size(c1) > avg_body * 0.7):
                patterns.append({
                    "name": "Three Black Crows",
                    "type": "triple",
                    "signal": "bearish",
                    "description": "Strong bearish continuation - sustained selling",
                    "reliability": 75,
                    "icon": "⬇️⬇️⬇️"
                })
        
        # Calculate overall signal and probability
        if not patterns:
            # No pattern detected - use basic trend
            if is_bullish(c0):
                return {
                    "patterns": [{
                        "name": "Bullish Candle",
                        "type": "single",
                        "signal": "bullish",
                        "description": "Simple bullish candle - close above open",
                        "reliability": 50,
                        "icon": "📈"
                    }],
                    "signal": "bullish",
                    "probability": 52,
                    "confidence": "low"
                }
            else:
                return {
                    "patterns": [{
                        "name": "Bearish Candle",
                        "type": "single",
                        "signal": "bearish",
                        "description": "Simple bearish candle - close below open",
                        "reliability": 50,
                        "icon": "📉"
                    }],
                    "signal": "bearish",
                    "probability": 52,
                    "confidence": "low"
                }
        
        # Calculate weighted signal from all patterns
        bullish_score = sum(p["reliability"] for p in patterns if p["signal"] == "bullish")
        bearish_score = sum(p["reliability"] for p in patterns if p["signal"] == "bearish")
        neutral_score = sum(p["reliability"] for p in patterns if p["signal"] == "neutral")
        total_score = bullish_score + bearish_score + neutral_score
        
        if total_score == 0:
            return {"patterns": patterns, "signal": "neutral", "probability": 50, "confidence": "low"}
        
        if bullish_score > bearish_score and bullish_score > neutral_score:
            signal = "bullish"
            probability = min(50 + (bullish_score - bearish_score) / 2, 85)
        elif bearish_score > bullish_score and bearish_score > neutral_score:
            signal = "bearish"
            probability = min(50 + (bearish_score - bullish_score) / 2, 85)
        else:
            signal = "neutral"
            probability = 50
        
        # Determine confidence
        max_reliability = max(p["reliability"] for p in patterns) if patterns else 50
        if max_reliability >= 75:
            confidence = "high"
        elif max_reliability >= 60:
            confidence = "medium"
        else:
            confidence = "low"
        
        return {
            "patterns": patterns,
            "signal": signal,
            "probability": safe_round(probability, 1),
            "confidence": confidence
        }
        
    except Exception as e:
        logger.error(f"Error detecting candlestick patterns: {e}")
        return {"patterns": [], "signal": "neutral", "probability": 50, "confidence": "low", "error": str(e)}


def analyze_instrument_candlestick(name: str) -> dict:
    """
    Analyze candlestick patterns for a given instrument/stock.
    
    Args:
        name: Name of the stock/instrument (e.g., "Reliance", "Nifty 50")
        
    Returns:
        Analysis result with patterns, signal, and probability
    """
    try:
        # Search in Indian stocks first
        config = None
        found_name = None
        
        # Check Indian stocks
        for stock_name, stock_config in INDIAN_STOCKS.items():
            if (name.lower() in stock_name.lower() or 
                name.upper() == stock_config.get("symbol", "").upper()):
                config = stock_config
                found_name = stock_name
                break
        
        # Check instruments if not found in stocks
        if not config:
            for inst_name, inst_config in INSTRUMENTS.items():
                if (name.lower() in inst_name.lower() or 
                    name.upper() == inst_config.get("symbol", "").upper()):
                    config = inst_config
                    found_name = inst_name
                    break
        
        if not config:
            return {
                "error": f"Instrument '{name}' not found",
                "suggestion": "Try searching for: " + ", ".join(list(INDIAN_STOCKS.keys())[:5]) + "...",
                "available_stocks": list(INDIAN_STOCKS.keys()),
                "available_instruments": list(INSTRUMENTS.keys())
            }
        
        # Generate OHLC data
        base_date = datetime.now()
        seed = hash(found_name + base_date.strftime("%Y-%m-%d"))
        
        base_price = safe_float(safe_get(config, "base_price", 100), 100)
        volatility = safe_float(safe_get(config, "volatility", 0.015), 0.015)
        
        ohlc_data = generate_ohlc_data(base_price, volatility, days=30, seed=seed)
        
        if not ohlc_data:
            return {"error": "Failed to generate price data"}
        
        # Detect patterns
        pattern_result = detect_candlestick_patterns(ohlc_data)
        
        # Get current price info
        latest = ohlc_data[-1] if ohlc_data else {}
        prev = ohlc_data[-2] if len(ohlc_data) >= 2 else latest
        
        change = safe_float(latest.get("close", 0)) - safe_float(prev.get("close", 0))
        change_pct = safe_percentage(change, safe_float(prev.get("close", 1), 1))
        
        return {
            "name": found_name,
            "symbol": safe_get(config, "symbol", ""),
            "current_price": safe_float(latest.get("close", 0)),
            "open": safe_float(latest.get("open", 0)),
            "high": safe_float(latest.get("high", 0)),
            "low": safe_float(latest.get("low", 0)),
            "close": safe_float(latest.get("close", 0)),
            "change": safe_round(change, 2),
            "change_pct": safe_round(change_pct, 2),
            "volume": latest.get("volume", 0),
            "patterns": pattern_result.get("patterns", []),
            "signal": pattern_result.get("signal", "neutral"),
            "probability": pattern_result.get("probability", 50),
            "confidence": pattern_result.get("confidence", "low"),
            "ohlc_data": ohlc_data[-10:],  # Last 10 days for chart
            "analysis_date": base_date.strftime("%Y-%m-%d %H:%M"),
            "data_source": "simulated"
        }
        
    except Exception as e:
        logger.error(f"Error analyzing candlestick for {name}: {e}")
        return {"error": f"Analysis failed: {str(e)}"}


@app.route("/api/candlestick/<instrument>")
@rate_limit
def get_candlestick_analysis(instrument: str):
    """
    Get candlestick pattern analysis for a specific instrument.
    
    Usage: /api/candlestick/Reliance
           /api/candlestick/TCS
           /api/candlestick/Nifty%2050
    """
    try:
        # Sanitize input
        instrument = sanitize_string(instrument, 50)
        
        if not instrument:
            return jsonify({"error": "Invalid instrument name"}), 400
        
        # Check cache
        cache_key = f"candlestick_{instrument.lower()}"
        cached_data, is_valid = _cache.get(cache_key)
        if is_valid:
            return jsonify(cached_data)
        
        # Analyze
        result = analyze_instrument_candlestick(instrument)
        
        if "error" in result and "not found" in result.get("error", "").lower():
            return jsonify(result), 404
        
        response_data = {
            **result,
            "fetched_at": datetime.now().isoformat()
        }
        
        _cache.set(cache_key, response_data, CACHE_TTL_SECONDS)
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error in get_candlestick_analysis: {e}")
        return jsonify({"error": "Failed to analyze candlestick patterns"}), 500


@app.route("/api/candlestick-scan")
@rate_limit
def scan_candlestick_patterns():
    """
    Scan all stocks for significant candlestick patterns.
    Returns stocks with high-confidence bullish or bearish signals.
    """
    cache_key = "candlestick_scan"
    
    cached_data, is_valid = _cache.get(cache_key)
    if is_valid:
        return jsonify(cached_data)
    
    try:
        bullish_signals = []
        bearish_signals = []
        neutral_signals = []
        
        for name in INDIAN_STOCKS.keys():
            try:
                result = analyze_instrument_candlestick(name)
                
                if "error" in result:
                    continue
                
                signal_info = {
                    "name": result.get("name"),
                    "symbol": result.get("symbol"),
                    "price": result.get("current_price"),
                    "change_pct": result.get("change_pct"),
                    "signal": result.get("signal"),
                    "probability": result.get("probability"),
                    "confidence": result.get("confidence"),
                    "patterns": [p["name"] for p in result.get("patterns", [])[:2]],
                    "top_pattern": result.get("patterns", [{}])[0] if result.get("patterns") else None
                }
                
                if result.get("signal") == "bullish" and result.get("probability", 0) >= 60:
                    bullish_signals.append(signal_info)
                elif result.get("signal") == "bearish" and result.get("probability", 0) >= 60:
                    bearish_signals.append(signal_info)
                else:
                    neutral_signals.append(signal_info)
                    
            except Exception as e:
                logger.warning(f"Error scanning {name}: {e}")
                continue
        
        # Sort by probability
        bullish_signals.sort(key=lambda x: x.get("probability", 0), reverse=True)
        bearish_signals.sort(key=lambda x: x.get("probability", 0), reverse=True)
        
        response_data = {
            "bullish": bullish_signals[:10],  # Top 10
            "bearish": bearish_signals[:10],
            "neutral_count": len(neutral_signals),
            "total_scanned": len(INDIAN_STOCKS),
            "fetched_at": datetime.now().isoformat(),
            "data_source": "simulated"
        }
        
        _cache.set(cache_key, response_data, CACHE_TTL_SECONDS)
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error in scan_candlestick_patterns: {e}")
        return jsonify({"error": "Failed to scan candlestick patterns"}), 500


# ============================================================================
# DCF VALUATION ANALYSIS
# ============================================================================

def perform_dcf_analysis(name: str, growth_rate: float = 15.0, 
                         discount_rate: float = 12.0, terminal_growth: float = 3.0) -> dict:
    """
    Perform Discounted Cash Flow (DCF) valuation analysis.
    
    Args:
        name: Stock name
        growth_rate: Expected annual growth rate (%)
        discount_rate: Weighted Average Cost of Capital (%)
        terminal_growth: Perpetual growth rate after projection period (%)
        
    Returns:
        DCF analysis with intrinsic value and recommendation
    """
    try:
        # Find stock config
        config = None
        found_name = None
        
        for stock_name, stock_config in INDIAN_STOCKS.items():
            if (name.lower() in stock_name.lower() or 
                name.upper() == stock_config.get("symbol", "").upper()):
                config = stock_config
                found_name = stock_name
                break
        
        if not config:
            return {
                "error": f"Stock '{name}' not found",
                "available_stocks": list(INDIAN_STOCKS.keys())[:10]
            }
        
        # Get current price from simulated data
        base_price = safe_float(config.get("base_price", 100), 100)
        symbol = config.get("symbol", "")
        
        # Generate realistic financial metrics based on stock type
        seed = hash(found_name + datetime.now().strftime("%Y-%m-%d"))
        random.seed(seed)
        
        # Current price with some variation
        current_price = base_price * (1 + random.uniform(-0.1, 0.1))
        
        # Generate company financials (simulated but realistic)
        market_cap = current_price * random.uniform(50000, 500000)  # In lakhs
        shares_outstanding = market_cap / current_price
        
        # Financial metrics
        eps = current_price / random.uniform(15, 35)  # P/E between 15-35
        pe_ratio = current_price / eps
        
        # Free Cash Flow (FCF) - typically 5-15% of market cap for good companies
        current_fcf = market_cap * random.uniform(0.03, 0.08) / 100  # In crores
        
        # Revenue and profitability metrics
        revenue = current_fcf * random.uniform(8, 15)  # FCF yield
        ebitda = revenue * random.uniform(0.15, 0.30)
        net_income = ebitda * random.uniform(0.4, 0.7)
        
        # Balance sheet items
        total_equity = market_cap * random.uniform(0.3, 0.6)
        total_debt = total_equity * random.uniform(0.1, 0.8)
        
        # Calculate metrics
        roe = (net_income / total_equity) * 100 if total_equity > 0 else 15
        roce = (net_income / (total_equity + total_debt)) * 100 if (total_equity + total_debt) > 0 else 12
        debt_equity = total_debt / total_equity if total_equity > 0 else 0.5
        ev = market_cap + total_debt
        ev_ebitda = ev / ebitda if ebitda > 0 else 15
        dividend_yield = random.uniform(0.5, 3.0)
        
        # DCF Calculation
        projection_years = 5
        cash_flows = []
        fcf = current_fcf
        
        # Project cash flows
        for year in range(1, projection_years + 1):
            # Growth tapers off over time
            year_growth = growth_rate * (1 - (year - 1) * 0.1)  # Slightly decreasing growth
            fcf = fcf * (1 + year_growth / 100)
            cash_flows.append(round(fcf, 2))
        
        # Calculate present value of projected cash flows
        pv_cash_flows = []
        for i, cf in enumerate(cash_flows):
            year = i + 1
            pv = cf / ((1 + discount_rate / 100) ** year)
            pv_cash_flows.append(pv)
        
        total_pv_fcf = sum(pv_cash_flows)
        
        # Terminal value calculation (Gordon Growth Model)
        terminal_fcf = cash_flows[-1] * (1 + terminal_growth / 100)
        terminal_value = terminal_fcf / ((discount_rate - terminal_growth) / 100)
        pv_terminal_value = terminal_value / ((1 + discount_rate / 100) ** projection_years)
        
        # Enterprise Value
        enterprise_value = total_pv_fcf + pv_terminal_value
        
        # Equity Value (EV - Net Debt)
        net_debt = total_debt - (total_equity * 0.1)  # Assume some cash
        equity_value = enterprise_value - max(0, net_debt)
        
        # Intrinsic value per share
        intrinsic_value = (equity_value * 100) / shares_outstanding  # Convert from crores
        
        # Margin of Safety
        margin_of_safety = ((intrinsic_value - current_price) / current_price) * 100
        
        # Generate recommendation
        if margin_of_safety > 30:
            recommendation = f"🟢 STRONG BUY: {found_name} appears significantly undervalued with a {margin_of_safety:.1f}% margin of safety. The DCF model suggests intrinsic value of ₹{intrinsic_value:,.2f} vs current price of ₹{current_price:,.2f}. Consider accumulating on dips."
        elif margin_of_safety > 15:
            recommendation = f"🟡 BUY: {found_name} appears moderately undervalued. With {margin_of_safety:.1f}% upside potential, it offers reasonable value at current levels. Good entry point for long-term investors."
        elif margin_of_safety > -10:
            recommendation = f"🟠 HOLD: {found_name} appears fairly valued based on DCF analysis. Current price is within ±10% of intrinsic value. Wait for better entry points or hold existing positions."
        elif margin_of_safety > -25:
            recommendation = f"🔴 REDUCE: {found_name} appears moderately overvalued by {abs(margin_of_safety):.1f}%. Consider booking partial profits or avoiding new positions at current levels."
        else:
            recommendation = f"⛔ SELL: {found_name} appears significantly overvalued by {abs(margin_of_safety):.1f}%. The stock is trading well above its intrinsic value. Consider reducing exposure."
        
        # Determine sector based on stock name patterns
        sector = "Diversified"
        name_lower = found_name.lower()
        if any(x in name_lower for x in ["bank", "hdfc", "icici", "axis", "kotak", "sbi", "indusind"]):
            sector = "Banking & Financial Services"
        elif any(x in name_lower for x in ["tcs", "infosys", "wipro", "hcl", "tech"]):
            sector = "Information Technology"
        elif any(x in name_lower for x in ["reliance", "ongc", "oil", "gas"]):
            sector = "Oil & Gas / Conglomerate"
        elif any(x in name_lower for x in ["pharma", "sun", "cipla"]):
            sector = "Pharmaceuticals"
        elif any(x in name_lower for x in ["steel", "tata steel", "jsw"]):
            sector = "Metals & Mining"
        elif any(x in name_lower for x in ["airtel", "bharti"]):
            sector = "Telecommunications"
        elif any(x in name_lower for x in ["maruti", "tata motors", "m&m"]):
            sector = "Automobiles"
        elif any(x in name_lower for x in ["itc", "hul", "asian", "titan"]):
            sector = "Consumer Goods"
        elif any(x in name_lower for x in ["power", "ntpc", "grid"]):
            sector = "Power & Utilities"
        elif any(x in name_lower for x in ["l&t", "adani"]):
            sector = "Infrastructure"
        elif any(x in name_lower for x in ["nifty", "index"]):
            sector = "Index"
        
        return {
            "name": found_name,
            "symbol": symbol,
            "sector": sector,
            "current_price": round(current_price, 2),
            "intrinsic_value": round(intrinsic_value, 2),
            "margin_of_safety": round(margin_of_safety, 2),
            "assumptions": {
                "growth_rate": growth_rate,
                "discount_rate": discount_rate,
                "terminal_growth": terminal_growth,
                "projection_years": projection_years
            },
            "cash_flows": cash_flows,
            "terminal_value": round(terminal_value, 2),
            "enterprise_value": round(enterprise_value, 2),
            "metrics": {
                "pe_ratio": round(pe_ratio, 2),
                "ev_ebitda": round(ev_ebitda, 2),
                "roe": round(roe, 2),
                "roce": round(roce, 2),
                "debt_equity": round(debt_equity, 2),
                "dividend_yield": round(dividend_yield, 2)
            },
            "recommendation": recommendation,
            "analyzed_at": datetime.now().isoformat(),
            "data_source": "simulated"
        }
        
    except Exception as e:
        logger.error(f"Error performing DCF analysis for {name}: {e}")
        return {"error": f"DCF analysis failed: {str(e)}"}


@app.route("/api/dcf-analysis/<stock_name>")
@rate_limit
def get_dcf_analysis(stock_name: str):
    """
    Get DCF valuation analysis for a stock.
    
    Query params:
        growth_rate: Expected growth rate (default: 15%)
        discount_rate: WACC (default: 12%)
        terminal_growth: Terminal growth rate (default: 3%)
    """
    try:
        # Sanitize input
        stock_name = sanitize_string(stock_name, 50)
        
        if not stock_name:
            return jsonify({"error": "Invalid stock name"}), 400
        
        # Get parameters
        growth_rate = safe_float(request.args.get('growth_rate', 15), 15)
        discount_rate = safe_float(request.args.get('discount_rate', 12), 12)
        terminal_growth = safe_float(request.args.get('terminal_growth', 3), 3)
        
        # Validate parameters
        growth_rate = max(0, min(50, growth_rate))
        discount_rate = max(5, min(25, discount_rate))
        terminal_growth = max(0, min(10, terminal_growth))
        
        # Ensure discount rate > terminal growth
        if terminal_growth >= discount_rate:
            terminal_growth = discount_rate - 1
        
        # Check cache
        cache_key = f"dcf_{stock_name.lower()}_{growth_rate}_{discount_rate}_{terminal_growth}"
        cached_data, is_valid = _cache.get(cache_key)
        if is_valid:
            return jsonify(cached_data)
        
        # Perform analysis
        result = perform_dcf_analysis(stock_name, growth_rate, discount_rate, terminal_growth)
        
        if "error" in result:
            return jsonify(result), 404 if "not found" in result.get("error", "").lower() else 400
        
        _cache.set(cache_key, result, CACHE_TTL_SECONDS)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in get_dcf_analysis: {e}")
        return jsonify({"error": "Failed to perform DCF analysis"}), 500


# ============================================================================
# TECHNICAL ANALYSIS INDICATORS
# ============================================================================

def calculate_rsi(prices: list, period: int = 14) -> float:
    """Calculate Relative Strength Index."""
    if len(prices) < period + 1:
        return 50.0
    
    gains = []
    losses = []
    
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    # Use last 'period' values
    recent_gains = gains[-period:]
    recent_losses = losses[-period:]
    
    avg_gain = sum(recent_gains) / period
    avg_loss = sum(recent_losses) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return round(rsi, 2)


def calculate_macd(prices: list) -> dict:
    """Calculate MACD (12, 26, 9)."""
    if len(prices) < 26:
        return {"macd": 0, "signal": 0, "histogram": 0}
    
    # Calculate EMAs
    def ema(data, period):
        multiplier = 2 / (period + 1)
        ema_values = [data[0]]
        for i in range(1, len(data)):
            ema_values.append((data[i] * multiplier) + (ema_values[-1] * (1 - multiplier)))
        return ema_values
    
    ema_12 = ema(prices, 12)
    ema_26 = ema(prices, 26)
    
    macd_line = [ema_12[i] - ema_26[i] for i in range(len(prices))]
    signal_line = ema(macd_line, 9)
    
    current_macd = macd_line[-1]
    current_signal = signal_line[-1]
    histogram = current_macd - current_signal
    
    # Check for crossover
    prev_macd = macd_line[-2]
    prev_signal = signal_line[-2]
    
    crossover = None
    if prev_macd <= prev_signal and current_macd > current_signal:
        crossover = "bullish"
    elif prev_macd >= prev_signal and current_macd < current_signal:
        crossover = "bearish"
    
    return {
        "macd": round(current_macd, 4),
        "signal": round(current_signal, 4),
        "histogram": round(histogram, 4),
        "crossover": crossover
    }


def calculate_bollinger_bands(prices: list, period: int = 20, std_dev: float = 2.0) -> dict:
    """Calculate Bollinger Bands."""
    if len(prices) < period:
        return {"upper": 0, "middle": 0, "lower": 0, "width": 0, "position": 0}
    
    recent_prices = prices[-period:]
    middle = sum(recent_prices) / period
    
    # Standard deviation
    variance = sum((p - middle) ** 2 for p in recent_prices) / period
    std = variance ** 0.5
    
    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)
    
    # Band width (% of middle)
    width = ((upper - lower) / middle) * 100
    
    # Current position within bands (0 = lower, 100 = upper)
    current_price = prices[-1]
    if upper != lower:
        position = ((current_price - lower) / (upper - lower)) * 100
    else:
        position = 50
    
    return {
        "upper": round(upper, 2),
        "middle": round(middle, 2),
        "lower": round(lower, 2),
        "width": round(width, 2),
        "position": round(position, 2),
        "squeeze": width < 5  # Tight squeeze when width < 5%
    }


def calculate_volume_analysis(base_price: float, volatility: float, seed: int) -> dict:
    """Generate simulated volume analysis."""
    random.seed(seed)
    
    # Generate 30 days of volume
    avg_volume = int(base_price * 10000 * (1 + volatility))
    volumes = []
    for _ in range(30):
        daily_vol = int(avg_volume * (0.5 + random.random()))
        volumes.append(daily_vol)
    
    current_volume = volumes[-1]
    avg_20_volume = sum(volumes[-20:]) / 20
    volume_ratio = current_volume / avg_20_volume if avg_20_volume > 0 else 1
    
    return {
        "current_volume": current_volume,
        "avg_volume": int(avg_20_volume),
        "volume_ratio": round(volume_ratio, 2),
        "unusual": volume_ratio > 1.5 or volume_ratio < 0.5,
        "signal": "High" if volume_ratio > 1.5 else "Low" if volume_ratio < 0.5 else "Normal"
    }


def generate_technical_analysis(stocks: dict) -> dict:
    """Generate technical analysis for all stocks."""
    base_date = datetime.now()
    
    rsi_results = {"overbought": [], "oversold": [], "neutral": []}
    macd_results = {"bullish_crossover": [], "bearish_crossover": [], "bullish_trend": [], "bearish_trend": []}
    bb_results = {"squeeze": [], "near_upper": [], "near_lower": []}
    volume_results = {"high_volume": [], "low_volume": []}
    
    exclude_symbols = ["NIFTY", "BANKNIFTY", "NIFTYIT"]
    
    for name, config in stocks.items():
        if config["symbol"] in exclude_symbols:
            continue
            
        try:
            seed = hash(name + base_date.strftime("%Y-%m-%d"))
            history = generate_realistic_history(
                config["base_price"],
                config["volatility"],
                days=60,
                seed=seed
            )
            
            current_price = history[-1]
            prev_price = history[-2]
            change_pct = ((current_price - prev_price) / prev_price) * 100
            
            # RSI Analysis
            rsi = calculate_rsi(history)
            rsi_data = {
                "name": name,
                "symbol": config["symbol"],
                "price": round(current_price, 2),
                "change_pct": round(change_pct, 2),
                "rsi": rsi
            }
            
            if rsi >= 70:
                rsi_results["overbought"].append(rsi_data)
            elif rsi <= 30:
                rsi_results["oversold"].append(rsi_data)
            else:
                rsi_results["neutral"].append(rsi_data)
            
            # MACD Analysis
            macd_data = calculate_macd(history)
            macd_entry = {
                "name": name,
                "symbol": config["symbol"],
                "price": round(current_price, 2),
                "change_pct": round(change_pct, 2),
                "macd": macd_data["macd"],
                "signal": macd_data["signal"],
                "histogram": macd_data["histogram"]
            }
            
            if macd_data["crossover"] == "bullish":
                macd_results["bullish_crossover"].append(macd_entry)
            elif macd_data["crossover"] == "bearish":
                macd_results["bearish_crossover"].append(macd_entry)
            elif macd_data["histogram"] > 0:
                macd_results["bullish_trend"].append(macd_entry)
            else:
                macd_results["bearish_trend"].append(macd_entry)
            
            # Bollinger Bands Analysis
            bb_data = calculate_bollinger_bands(history)
            bb_entry = {
                "name": name,
                "symbol": config["symbol"],
                "price": round(current_price, 2),
                "change_pct": round(change_pct, 2),
                "upper": bb_data["upper"],
                "lower": bb_data["lower"],
                "width": bb_data["width"],
                "position": bb_data["position"]
            }
            
            if bb_data["squeeze"]:
                bb_results["squeeze"].append(bb_entry)
            elif bb_data["position"] >= 80:
                bb_results["near_upper"].append(bb_entry)
            elif bb_data["position"] <= 20:
                bb_results["near_lower"].append(bb_entry)
            
            # Volume Analysis
            vol_data = calculate_volume_analysis(config["base_price"], config["volatility"], seed)
            vol_entry = {
                "name": name,
                "symbol": config["symbol"],
                "price": round(current_price, 2),
                "change_pct": round(change_pct, 2),
                "current_volume": vol_data["current_volume"],
                "avg_volume": vol_data["avg_volume"],
                "volume_ratio": vol_data["volume_ratio"]
            }
            
            if vol_data["signal"] == "High":
                volume_results["high_volume"].append(vol_entry)
            elif vol_data["signal"] == "Low":
                volume_results["low_volume"].append(vol_entry)
                
        except Exception as e:
            logger.warning(f"Error in technical analysis for {name}: {e}")
    
    # Sort results
    rsi_results["overbought"].sort(key=lambda x: x["rsi"], reverse=True)
    rsi_results["oversold"].sort(key=lambda x: x["rsi"])
    macd_results["bullish_crossover"].sort(key=lambda x: x["histogram"], reverse=True)
    bb_results["squeeze"].sort(key=lambda x: x["width"])
    volume_results["high_volume"].sort(key=lambda x: x["volume_ratio"], reverse=True)
    
    return {
        "rsi": rsi_results,
        "macd": macd_results,
        "bollinger": bb_results,
        "volume": volume_results
    }


# ============================================================================
# FUNDAMENTAL ANALYSIS INDICATORS
# ============================================================================

def generate_fundamental_analysis(stocks: dict) -> dict:
    """Generate fundamental analysis for all stocks."""
    base_date = datetime.now()
    
    pe_results = {"undervalued": [], "fairly_valued": [], "overvalued": []}
    dividend_results = {"high_yield": [], "moderate_yield": [], "low_yield": []}
    debt_results = {"low_debt": [], "moderate_debt": [], "high_debt": []}
    
    # Sector-wise PE benchmarks
    sector_pe = {
        "Banking": 15, "IT": 25, "FMCG": 40, "Auto": 20, "Pharma": 30,
        "Energy": 12, "Infra": 18, "Metals": 10, "Telecom": 15, "Default": 20
    }
    
    exclude_symbols = ["NIFTY", "BANKNIFTY", "NIFTYIT"]
    
    for name, config in stocks.items():
        if config["symbol"] in exclude_symbols:
            continue
            
        try:
            seed = hash(name + base_date.strftime("%Y-%m-%d") + "fundamental")
            random.seed(seed)
            
            # Get sector (approximate based on name)
            sector = "Default"
            if any(x in name for x in ["Bank", "HDFC", "ICICI", "Axis", "Kotak", "SBI"]):
                sector = "Banking"
            elif any(x in name for x in ["TCS", "Infosys", "Wipro", "HCL", "Tech"]):
                sector = "IT"
            elif any(x in name for x in ["HUL", "ITC", "Asian", "Titan"]):
                sector = "FMCG"
            elif any(x in name for x in ["Maruti", "M&M", "Bajaj"]):
                sector = "Auto"
            elif any(x in name for x in ["Sun Pharma", "Pharma"]):
                sector = "Pharma"
            elif any(x in name for x in ["Reliance", "NTPC", "Power"]):
                sector = "Energy"
            elif any(x in name for x in ["L&T", "Infra"]):
                sector = "Infra"
            elif any(x in name for x in ["Airtel", "Telecom"]):
                sector = "Telecom"
            
            current_price = config["base_price"] * (0.9 + random.random() * 0.2)
            
            # Generate PE Ratio (realistic range based on sector)
            benchmark_pe = sector_pe.get(sector, 20)
            pe_ratio = benchmark_pe * (0.5 + random.random() * 1.5)
            
            # Generate EPS
            eps = current_price / pe_ratio
            
            # Generate Dividend Yield (0.5% - 5%)
            dividend_yield = random.uniform(0.3, 4.5)
            
            # Generate Debt-to-Equity (0.1 - 2.5)
            debt_to_equity = random.uniform(0.1, 2.0)
            
            # Generate Market Cap (in Cr)
            market_cap = config["base_price"] * random.randint(500, 50000)
            
            # Generate Book Value
            book_value = current_price / (1 + random.random() * 3)
            pb_ratio = current_price / book_value
            
            # PE Classification
            pe_entry = {
                "name": name,
                "symbol": config["symbol"],
                "price": round(current_price, 2),
                "pe_ratio": round(pe_ratio, 2),
                "sector": sector,
                "sector_pe": benchmark_pe,
                "eps": round(eps, 2),
                "pb_ratio": round(pb_ratio, 2),
                "market_cap": f"{round(market_cap/10000, 2)}L Cr" if market_cap > 100000 else f"{round(market_cap, 0)} Cr"
            }
            
            if pe_ratio < benchmark_pe * 0.7:
                pe_results["undervalued"].append(pe_entry)
            elif pe_ratio > benchmark_pe * 1.3:
                pe_results["overvalued"].append(pe_entry)
            else:
                pe_results["fairly_valued"].append(pe_entry)
            
            # Dividend Classification
            div_entry = {
                "name": name,
                "symbol": config["symbol"],
                "price": round(current_price, 2),
                "dividend_yield": round(dividend_yield, 2),
                "sector": sector
            }
            
            if dividend_yield >= 3.0:
                dividend_results["high_yield"].append(div_entry)
            elif dividend_yield >= 1.5:
                dividend_results["moderate_yield"].append(div_entry)
            else:
                dividend_results["low_yield"].append(div_entry)
            
            # Debt Classification
            debt_entry = {
                "name": name,
                "symbol": config["symbol"],
                "price": round(current_price, 2),
                "debt_to_equity": round(debt_to_equity, 2),
                "sector": sector
            }
            
            if debt_to_equity <= 0.5:
                debt_results["low_debt"].append(debt_entry)
            elif debt_to_equity <= 1.0:
                debt_results["moderate_debt"].append(debt_entry)
            else:
                debt_results["high_debt"].append(debt_entry)
                
        except Exception as e:
            logger.warning(f"Error in fundamental analysis for {name}: {e}")
    
    # Sort results
    pe_results["undervalued"].sort(key=lambda x: x["pe_ratio"])
    pe_results["overvalued"].sort(key=lambda x: x["pe_ratio"], reverse=True)
    dividend_results["high_yield"].sort(key=lambda x: x["dividend_yield"], reverse=True)
    debt_results["low_debt"].sort(key=lambda x: x["debt_to_equity"])
    
    return {
        "pe_analysis": pe_results,
        "dividend": dividend_results,
        "debt": debt_results
    }


@app.route("/api/technical-analysis")
@rate_limit
def get_technical_analysis():
    """Return technical analysis indicators."""
    cache_key = "technical_analysis"
    
    cached_data, is_valid = _cache.get(cache_key)
    if is_valid:
        return jsonify(cached_data)
    
    try:
        results = generate_technical_analysis(INDIAN_STOCKS)
        
        response_data = {
            **results,
            "fetched_at": datetime.now().isoformat(),
            "total_scanned": len(INDIAN_STOCKS) - 3,
        }
        
        _cache.set(cache_key, response_data, CACHE_TTL_SECONDS)
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error in get_technical_analysis: {e}")
        return jsonify({"error": "Failed to generate technical analysis"}), 500


@app.route("/api/fundamental-analysis")
@rate_limit
def get_fundamental_analysis():
    """Return fundamental analysis indicators."""
    cache_key = "fundamental_analysis"
    
    cached_data, is_valid = _cache.get(cache_key)
    if is_valid:
        return jsonify(cached_data)
    
    try:
        results = generate_fundamental_analysis(INDIAN_STOCKS)
        
        response_data = {
            **results,
            "fetched_at": datetime.now().isoformat(),
            "total_scanned": len(INDIAN_STOCKS) - 3,
        }
        
        _cache.set(cache_key, response_data, CACHE_TTL_SECONDS)
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error in get_fundamental_analysis: {e}")
        return jsonify({"error": "Failed to generate fundamental analysis"}), 500


# ============================================================================
# MARKET NEWS
# ============================================================================

def generate_market_news() -> list:
    """Generate simulated market news for the day."""
    base_date = datetime.now()
    seed = hash(base_date.strftime("%Y-%m-%d"))
    random.seed(seed)
    
    # News templates with categories and sentiment
    news_templates = [
        # Global Markets
        {"category": "Global", "sentiment": "positive", "icon": "🌍",
         "headlines": [
             "Wall Street rallies as Fed signals pause on rate hikes",
             "US markets surge on strong jobs data and inflation cooling",
             "Global equities rise as US-China trade tensions ease",
             "S&P 500 hits new record high on tech earnings beat",
         ]},
        {"category": "Global", "sentiment": "negative", "icon": "🌍",
         "headlines": [
             "Markets tumble as recession fears grip Wall Street",
             "Global selloff intensifies amid banking sector concerns",
             "Dow drops 500 points on hawkish Fed commentary",
             "Trade war escalation sends shockwaves through markets",
         ]},
        # India Markets
        {"category": "India", "sentiment": "positive", "icon": "🇮🇳",
         "headlines": [
             "Nifty 50 hits all-time high as FIIs pump in ₹5,000 crore",
             "RBI keeps rates unchanged, markets cheer accommodative stance",
             "Sensex surges 800 points on strong Q3 earnings",
             "Indian markets outperform EM peers on robust GDP growth",
             "IT stocks rally as rupee weakens against dollar",
         ]},
        {"category": "India", "sentiment": "negative", "icon": "🇮🇳",
         "headlines": [
             "Nifty breaks below 22,000 as FIIs sell ₹3,500 crore",
             "Markets tank as RBI surprises with rate hike",
             "Banking stocks drag Sensex down 600 points",
             "Rupee hits record low, sparks market selloff",
         ]},
        # Sectors
        {"category": "Banking", "sentiment": "positive", "icon": "🏦",
         "headlines": [
             "Bank Nifty rallies 3% on strong credit growth data",
             "PSU banks surge as government announces recapitalization",
             "HDFC Bank Q3 results beat estimates, stock hits 52-week high",
         ]},
        {"category": "Banking", "sentiment": "negative", "icon": "🏦",
         "headlines": [
             "Banking stocks slide on rising NPA concerns",
             "Private banks fall as deposit growth slows",
         ]},
        {"category": "IT", "sentiment": "positive", "icon": "💻",
         "headlines": [
             "IT stocks jump as TCS announces record deal wins",
             "Infosys raises FY guidance, stock surges 5%",
             "Tech rally continues as AI demand boosts outlook",
         ]},
        {"category": "IT", "sentiment": "negative", "icon": "💻",
         "headlines": [
             "IT sector faces headwinds as US clients cut spending",
             "Wipro disappoints with weak Q3 guidance",
         ]},
        {"category": "Auto", "sentiment": "positive", "icon": "🚗",
         "headlines": [
             "Auto stocks rally on record monthly sales data",
             "EV demand surge lifts Tata Motors to new highs",
             "Maruti reports highest-ever quarterly profit",
         ]},
        {"category": "Pharma", "sentiment": "positive", "icon": "💊",
         "headlines": [
             "Pharma stocks surge on FDA approval for key drugs",
             "Sun Pharma gains 4% on positive clinical trial results",
         ]},
        {"category": "Commodities", "sentiment": "positive", "icon": "🛢️",
         "headlines": [
             "Crude oil jumps 3% on OPEC+ production cuts",
             "Gold hits record high amid geopolitical tensions",
             "Metal stocks rally as China stimulus boosts demand",
         ]},
        {"category": "Commodities", "sentiment": "negative", "icon": "🛢️",
         "headlines": [
             "Oil prices crash as demand concerns resurface",
             "Gold falls as dollar strengthens on Fed hawkishness",
         ]},
        {"category": "FII/DII", "sentiment": "positive", "icon": "💰",
         "headlines": [
             "FIIs turn net buyers after 5-day selling spree",
             "DIIs continue buying streak, absorb FII outflows",
             "Foreign investors bullish on India growth story",
         ]},
        {"category": "FII/DII", "sentiment": "negative", "icon": "💰",
         "headlines": [
             "FIIs pull out ₹10,000 crore in March, worst month this year",
             "Emerging market outflows hit India as dollar surges",
         ]},
        {"category": "Policy", "sentiment": "neutral", "icon": "📜",
         "headlines": [
             "Government announces new PLI scheme for electronics",
             "SEBI tightens rules for F&O trading",
             "Budget 2026: Key expectations from market participants",
             "RBI MPC meeting begins, rate decision on Friday",
         ]},
        {"category": "IPO", "sentiment": "positive", "icon": "🎯",
         "headlines": [
             "Mega IPO subscribed 50x on strong retail demand",
             "LIC shares surge 10% on bonus announcement",
             "Tech startup IPO lists at 40% premium",
         ]},
    ]
    
    # Select 8-12 random news items for today
    num_news = random.randint(8, 12)
    selected_news = []
    used_categories = set()
    
    # Ensure variety - pick from different categories
    shuffled_templates = news_templates.copy()
    random.shuffle(shuffled_templates)
    
    for template in shuffled_templates:
        if len(selected_news) >= num_news:
            break
        
        # Pick a random headline from this category
        headline = random.choice(template["headlines"])
        
        # Generate time (news throughout the day)
        hour = random.randint(6, 18)
        minute = random.randint(0, 59)
        time_str = f"{hour:02d}:{minute:02d}"
        
        # Generate impact score (-5 to +5)
        if template["sentiment"] == "positive":
            impact = random.uniform(1, 5)
        elif template["sentiment"] == "negative":
            impact = random.uniform(-5, -1)
        else:
            impact = random.uniform(-1, 1)
        
        selected_news.append({
            "headline": headline,
            "category": template["category"],
            "icon": template["icon"],
            "sentiment": template["sentiment"],
            "time": time_str,
            "impact": round(impact, 1),
            "source": random.choice(["ET Markets", "Moneycontrol", "CNBC-TV18", "Reuters", "Bloomberg", "Livemint", "Business Standard"])
        })
    
    # Sort by time (most recent first)
    selected_news.sort(key=lambda x: x["time"], reverse=True)
    
    return selected_news


@app.route("/api/market-news")
@rate_limit
def get_market_news():
    """Return today's market news."""
    cache_key = "market_news"
    
    cached_data, is_valid = _cache.get(cache_key)
    if is_valid:
        return jsonify(cached_data)
    
    try:
        news = generate_market_news()
        
        response_data = {
            "news": news,
            "fetched_at": datetime.now().isoformat(),
            "total": len(news),
            "date": datetime.now().strftime("%B %d, %Y")
        }
        
        _cache.set(cache_key, response_data, CACHE_TTL_SECONDS)
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error in get_market_news: {e}")
        return jsonify({"error": "Failed to fetch market news"}), 500


def generate_india_derivatives_data():
    """Generate simulated India F&O derivatives data."""
    import random
    
    # Nifty & Bank Nifty spot prices (simulated)
    nifty_spot = round(random.uniform(22000, 23500), 2)
    banknifty_spot = round(random.uniform(47000, 50000), 2)
    
    # Generate Call OI and Put OI (in lakhs)
    # Nifty OI
    nifty_call_oi = round(random.uniform(80, 150), 2)  # in lakhs
    nifty_put_oi = round(random.uniform(60, 180), 2)   # in lakhs
    nifty_pcr = round(nifty_put_oi / nifty_call_oi, 2)
    
    # BankNifty OI
    banknifty_call_oi = round(random.uniform(40, 90), 2)  # in lakhs
    banknifty_put_oi = round(random.uniform(30, 100), 2)  # in lakhs
    banknifty_pcr = round(banknifty_put_oi / banknifty_call_oi, 2)
    
    # OI Change from previous day
    nifty_call_oi_change = round(random.uniform(-15, 20), 1)
    nifty_put_oi_change = round(random.uniform(-15, 20), 1)
    banknifty_call_oi_change = round(random.uniform(-12, 18), 1)
    banknifty_put_oi_change = round(random.uniform(-12, 18), 1)
    
    # PCR interpretation
    def pcr_sentiment(pcr):
        if pcr > 1.2:
            return {"text": "Bullish", "color": "#22c55e"}
        elif pcr < 0.8:
            return {"text": "Bearish", "color": "#ef4444"}
        else:
            return {"text": "Neutral", "color": "#f59e0b"}
    
    # Max Pain - strike price where option buyers lose the most
    nifty_max_pain = round(nifty_spot / 50) * 50  # Round to nearest 50
    banknifty_max_pain = round(banknifty_spot / 100) * 100  # Round to nearest 100
    
    # India VIX (Volatility Index)
    india_vix = round(random.uniform(11, 22), 2)
    vix_change = round(random.uniform(-8, 8), 2)
    
    def vix_sentiment(vix):
        if vix < 13:
            return {"text": "Low Volatility", "color": "#22c55e"}
        elif vix > 18:
            return {"text": "High Volatility", "color": "#ef4444"}
        else:
            return {"text": "Normal", "color": "#f59e0b"}
    
    # Top F&O stocks by open interest change
    fo_stocks = [
        {"symbol": "RELIANCE", "oi_change": round(random.uniform(-15, 25), 1), "price": round(random.uniform(2400, 2700), 2)},
        {"symbol": "TCS", "oi_change": round(random.uniform(-12, 20), 1), "price": round(random.uniform(3800, 4200), 2)},
        {"symbol": "HDFCBANK", "oi_change": round(random.uniform(-18, 22), 1), "price": round(random.uniform(1500, 1700), 2)},
        {"symbol": "INFY", "oi_change": round(random.uniform(-10, 18), 1), "price": round(random.uniform(1400, 1600), 2)},
        {"symbol": "ICICIBANK", "oi_change": round(random.uniform(-14, 20), 1), "price": round(random.uniform(1000, 1150), 2)},
        {"symbol": "SBIN", "oi_change": round(random.uniform(-16, 24), 1), "price": round(random.uniform(750, 850), 2)},
        {"symbol": "TATAMOTORS", "oi_change": round(random.uniform(-20, 30), 1), "price": round(random.uniform(900, 1050), 2)},
        {"symbol": "AXISBANK", "oi_change": round(random.uniform(-12, 18), 1), "price": round(random.uniform(1050, 1200), 2)},
    ]
    # Sort by absolute OI change
    fo_stocks.sort(key=lambda x: abs(x["oi_change"]), reverse=True)
    top_fo_stocks = fo_stocks[:5]
    
    # FII/DII F&O data (in crores)
    fii_index_futures = round(random.uniform(-3000, 3000), 0)
    fii_index_options = round(random.uniform(-5000, 5000), 0)
    fii_stock_futures = round(random.uniform(-2000, 2000), 0)
    dii_index_futures = round(random.uniform(-1500, 1500), 0)
    
    # Expiry info
    from datetime import datetime, timedelta
    today = datetime.now()
    # Weekly expiry is Thursday
    days_until_thursday = (3 - today.weekday()) % 7
    if days_until_thursday == 0 and today.hour >= 15:
        days_until_thursday = 7
    next_expiry = today + timedelta(days=days_until_thursday)
    days_to_expiry = days_until_thursday if days_until_thursday > 0 else 7
    
    # Monthly expiry (last Thursday of month)
    import calendar
    last_day = calendar.monthrange(today.year, today.month)[1]
    last_thursday = last_day
    for d in range(last_day, 0, -1):
        if datetime(today.year, today.month, d).weekday() == 3:
            last_thursday = d
            break
    monthly_expiry_date = datetime(today.year, today.month, last_thursday)
    if monthly_expiry_date < today:
        # Move to next month
        next_month = today.month + 1 if today.month < 12 else 1
        next_year = today.year if today.month < 12 else today.year + 1
        last_day = calendar.monthrange(next_year, next_month)[1]
        for d in range(last_day, 0, -1):
            if datetime(next_year, next_month, d).weekday() == 3:
                monthly_expiry_date = datetime(next_year, next_month, d)
                break
    days_to_monthly = (monthly_expiry_date - today).days
    
    return {
        "nifty": {
            "spot": nifty_spot,
            "call_oi": nifty_call_oi,
            "put_oi": nifty_put_oi,
            "call_oi_change": nifty_call_oi_change,
            "put_oi_change": nifty_put_oi_change,
            "pcr": nifty_pcr,
            "pcr_sentiment": pcr_sentiment(nifty_pcr),
            "max_pain": nifty_max_pain,
            "lot_size": 25
        },
        "banknifty": {
            "spot": banknifty_spot,
            "call_oi": banknifty_call_oi,
            "put_oi": banknifty_put_oi,
            "call_oi_change": banknifty_call_oi_change,
            "put_oi_change": banknifty_put_oi_change,
            "pcr": banknifty_pcr,
            "pcr_sentiment": pcr_sentiment(banknifty_pcr),
            "max_pain": banknifty_max_pain,
            "lot_size": 15
        },
        "india_vix": {
            "value": india_vix,
            "change": vix_change,
            "sentiment": vix_sentiment(india_vix)
        },
        "top_fo_stocks": top_fo_stocks,
        "fii_dii": {
            "fii_index_futures": fii_index_futures,
            "fii_index_options": fii_index_options,
            "fii_stock_futures": fii_stock_futures,
            "dii_index_futures": dii_index_futures,
            "fii_net": fii_index_futures + fii_index_options + fii_stock_futures
        },
        "expiry": {
            "weekly": next_expiry.strftime("%d %b"),
            "days_to_weekly": days_to_expiry,
            "monthly": monthly_expiry_date.strftime("%d %b"),
            "days_to_monthly": max(0, days_to_monthly)
        }
    }


@app.route("/api/india-derivatives")
@rate_limit
def get_india_derivatives():
    """Return India F&O derivatives data."""
    cache_key = "india_derivatives"
    
    cached_data, is_valid = _cache.get(cache_key)
    if is_valid:
        return jsonify(cached_data)
    
    try:
        data = generate_india_derivatives_data()
        
        response_data = {
            **data,
            "fetched_at": datetime.now().isoformat(),
            "data_mode": "simulated"
        }
        
        _cache.set(cache_key, response_data, CACHE_TTL_SECONDS)
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error in get_india_derivatives: {e}")
        return jsonify({"error": "Failed to fetch derivatives data"}), 500


# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    # Security: Use environment variable to control debug mode
    DEBUG_MODE = os.environ.get("FLASK_DEBUG", "false").lower() in ("true", "1", "yes")
    
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
║                                                                      ║
║  🔐 Security Mode: """ + ("DEBUG (development)" if DEBUG_MODE else "PRODUCTION") + """
╚══════════════════════════════════════════════════════════════════════╝
    """)
    
    # Bind to localhost only for security (use reverse proxy in production)
    app.run(debug=DEBUG_MODE, port=5050, host="127.0.0.1")

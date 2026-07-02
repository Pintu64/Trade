"""
bitget_auth_client.py — Bitget authenticated REST API wrapper.

Supports account operations, position management, and order placement.
Requires API key, secret, and passphrase from Bitget account settings.

Design:
- HMAC-SHA256 signature authentication per Bitget API docs
- Supports both SPOT and USDT-FUTURES trading
- Thread-safe rate limiting shared across authenticated requests
- Smart retry logic with exponential backoff
- Proper request ordering (nonce + timestamp to prevent replay attacks)

Security Notes:
- Never log API keys or secrets
- Store credentials in .env file (never in code)
- Use IP whitelist on Bitget account for extra protection
- Rotate keys periodically
- This module is OPTIONAL — the bot works without it (signals-only mode)
"""

import time
import json
import logging
import threading
import hmac
import hashlib
from base64 import b64encode
from datetime import datetime
from typing import Optional, Dict, Any

import requests

from config import (
    BITGET_BASE_URL, PRODUCT_TYPE,
    REQUEST_TIMEOUT_SECONDS, HTTP_MAX_RETRIES,
    HTTP_RETRY_BACKOFF_SECONDS, MIN_SECONDS_BETWEEN_REQUESTS,
)

log = logging.getLogger("bitget_auth_client")

# ── Authentication credentials (load from environment) ────────────────────────
def _get_api_credentials() -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Retrieve API credentials from environment.
    Returns (api_key, api_secret, passphrase) or (None, None, None) if not configured.
    """
    import os
    api_key = os.environ.get("BITGET_API_KEY", "").strip()
    api_secret = os.environ.get("BITGET_API_SECRET", "").strip()
    passphrase = os.environ.get("BITGET_PASSPHRASE", "").strip()
    
    if api_key and api_secret and passphrase:
        return api_key, api_secret, passphrase
    return None, None, None


_api_key, _api_secret, _passphrase = _get_api_credentials()
_auth_available = bool(_api_key and _api_secret and _passphrase)

_session = requests.Session()
_session.headers.update({"User-Agent": "bitget-signal-bot/1.0"})

# ── Rate limiter (shared with public API) ─────────────────────────────────────
_rate_lock = threading.Lock()
_last_request_time = [0.0]


def _throttle():
    """Ensure minimum gap between HTTP requests."""
    with _rate_lock:
        elapsed = time.monotonic() - _last_request_time[0]
        gap = MIN_SECONDS_BETWEEN_REQUESTS - elapsed
        if gap > 0:
            time.sleep(gap)
        _last_request_time[0] = time.monotonic()


# ── Permanent API error codes ─────────────────────────────────────────────────
_PERMANENT_API_CODES = {
    "40009",   # missing / invalid parameter
    "40034",   # symbol does not exist
    "40308",   # invalid product type
    "40762",   # invalid granularity
    "40400",   # resource not found
    "40001",   # invalid API key
    "40002",   # invalid signature
    "40003",   # authentication failed
    "40005",   # order does not exist
    "40013",   # insufficient balance
    "40014",   # position does not exist
    "40020",   # margin call, reduce position
}


class BitgetAuthError(Exception):
    """Authentication/authorization API error."""
    def __init__(self, message, code=None, retryable=True):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class BitgetOrderError(Exception):
    """Order-specific error (insufficient funds, invalid params, etc)."""
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


# ── Signature generation ──────────────────────────────────────────────────────

def _generate_signature(
    method: str,
    request_path: str,
    body: str,
    timestamp: str,
    secret_key: str,
) -> str:
    """
    Generate HMAC-SHA256 signature for Bitget API authentication.
    
    Args:
        method: HTTP method (GET, POST, DELETE, etc.)
        request_path: API endpoint path (e.g., /api/v2/spot/wallet/transfer)
        body: Request body as JSON string (empty string for GET)
        timestamp: ISO 8601 timestamp
        secret_key: API secret key
    
    Returns:
        Base64-encoded HMAC-SHA256 signature
    """
    message = method + request_path + timestamp + body
    mac = hmac.new(
        bytes(secret_key, encoding="utf8"),
        bytes(message, encoding="utf8"),
        digestmod=hashlib.sha256,
    )
    return b64encode(mac.digest()).decode("utf-8")


def _request(
    method: str,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    body: Optional[Dict[str, Any]] = None,
    require_auth: bool = True,
) -> Any:
    """
    Core authenticated HTTP request with retry logic.
    
    Args:
        method: HTTP method (GET, POST, DELETE)
        path: API endpoint path
        params: Query parameters (for GET)
        body: Request body (for POST/DELETE)
        require_auth: If True, raises error if credentials not configured
    
    Returns:
        Response data field (dict or list)
    
    Raises:
        BitgetAuthError: On authentication failures or permanent API errors
        requests.RequestException: On network errors (after retries)
    """
    if require_auth and not _auth_available:
        raise BitgetAuthError(
            "Authentication not configured. Set BITGET_API_KEY, "
            "BITGET_API_SECRET, and BITGET_PASSPHRASE in .env",
            retryable=False,
        )
    
    url = f"{BITGET_BASE_URL}{path}"
    body_str = json.dumps(body) if body else ""
    timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "bitget-signal-bot/1.0",
    }
    
    # Add auth headers
    if require_auth and _auth_available:
        signature = _generate_signature(method, path, body_str, timestamp, _api_secret)
        headers.update({
            "ACCESS-KEY": _api_key,
            "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": _passphrase,
        })
    
    for attempt in range(1, HTTP_MAX_RETRIES + 1):
        _throttle()
        try:
            if method == "GET":
                resp = _session.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
            elif method == "POST":
                resp = _session.post(url, data=body_str, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
            elif method == "DELETE":
                resp = _session.delete(url, data=body_str, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Handle rate limit
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 10))
                log.warning("Rate limited on %s — waiting %ss (attempt %s)", path, wait, attempt)
                time.sleep(wait)
                continue
            
            # 4xx (except 429) are permanent client errors
            if 400 <= resp.status_code < 500:
                raise BitgetAuthError(
                    f"HTTP {resp.status_code} on {path} — permanent client error.",
                    retryable=False,
                )
            
            resp.raise_for_status()
            body_response = resp.json()
            api_code = str(body_response.get("code", ""))
            
            if api_code != "00000":
                msg = body_response.get("msg", "unknown error")
                permanent = api_code in _PERMANENT_API_CODES
                raise BitgetAuthError(
                    f"Bitget API {api_code}: {msg} [{path}]",
                    code=api_code,
                    retryable=not permanent,
                )
            
            return body_response.get("data")
        
        except BitgetAuthError as exc:
            if not exc.retryable:
                log.error("Permanent API error on %s: %s", path, exc)
                raise
            log.warning("Retryable API error attempt %s/%s on %s: %s",
                        attempt, HTTP_MAX_RETRIES, path, exc)
        
        except requests.RequestException as exc:
            log.warning("Network error attempt %s/%s on %s: %s",
                        attempt, HTTP_MAX_RETRIES, path, exc)
        
        if attempt < HTTP_MAX_RETRIES:
            sleep = HTTP_RETRY_BACKOFF_SECONDS * attempt
            log.debug("Backing off %.1fs before retry", sleep)
            time.sleep(sleep)
    
    raise BitgetAuthError(
        f"Gave up on {path} after {HTTP_MAX_RETRIES} attempts.",
        retryable=False,
    )


# ── Account Operations ────────────────────────────────────────────────────────

def get_account_info() -> dict:
    """
    Fetch authenticated account information.
    
    Returns:
        Account details: {
            'uid': user ID,
            'emailAddress': email,
            'memberLevel': account tier,
            ...
        }
    """
    return _request("GET", "/api/v2/account/info", require_auth=True)


def get_balance(coin: str = "USDT") -> dict | None:
    """
    Get wallet balance for a specific coin.
    
    Args:
        coin: Coin symbol (e.g., 'USDT', 'BTC')
    
    Returns:
        Balance info: {
            'coin': coin,
            'available': available balance,
            'hold': locked balance,
            'total': total balance,
        }
    """
    try:
        data = _request(
            "GET",
            "/api/v2/account/balance",
            params={"coin": coin},
            require_auth=True,
        )
        if isinstance(data, list):
            return data[0] if data else None
        return data
    except BitgetAuthError as e:
        log.warning("Failed to fetch balance for %s: %s", coin, e)
        return None


def get_balances() -> list:
    """
    Get all wallet balances (multiple coins).
    
    Returns:
        List of balance objects
    """
    try:
        data = _request("GET", "/api/v2/account/balance", require_auth=True)
        return data if isinstance(data, list) else []
    except BitgetAuthError as e:
        log.warning("Failed to fetch balances: %s", e)
        return []


# ── Position Management ───────────────────────────────────────────────────────

def get_open_positions(symbol: str = None) -> list:
    """
    Fetch all open futures positions (USDT-FUTURES only).
    
    Args:
        symbol: Optional symbol filter (e.g., 'BTCUSDT')
    
    Returns:
        List of position objects with fields:
        - symbol, contractSide, openPrice, qty, leverage, ...
    """
    if PRODUCT_TYPE != "USDT-FUTURES":
        log.error("get_open_positions only works with USDT-FUTURES")
        return []
    
    params = {"productType": PRODUCT_TYPE.lower()}
    if symbol:
        params["symbol"] = symbol
    
    try:
        data = _request(
            "GET",
            "/api/v2/mix/account/positions",
            params=params,
            require_auth=True,
        )
        return data if isinstance(data, list) else []
    except BitgetAuthError as e:
        log.error("Failed to fetch open positions: %s", e)
        return []


def get_position(symbol: str) -> dict | None:
    """
    Fetch a specific position for a symbol.
    
    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')
    
    Returns:
        Position object or None if not found
    """
    positions = get_open_positions(symbol)
    if positions:
        for pos in positions:
            if pos.get("symbol") == symbol:
                return pos
    return None


def close_position(
    symbol: str,
    close_percentage: float = 100.0,
) -> dict:
    """
    Close an open futures position (full or partial).
    
    Args:
        symbol: Trading pair
        close_percentage: % of position to close (0-100)
    
    Returns:
        Close order response
    
    Raises:
        BitgetOrderError: On failure
    """
    if PRODUCT_TYPE != "USDT-FUTURES":
        raise BitgetOrderError("close_position only works with USDT-FUTURES")
    
    body = {
        "symbol": symbol,
        "productType": PRODUCT_TYPE.lower(),
        "closePercent": str(close_percentage),
    }
    
    try:
        return _request(
            "POST",
            "/api/v2/mix/orders/close-position",
            body=body,
            require_auth=True,
        )
    except BitgetAuthError as e:
        raise BitgetOrderError(f"Failed to close position {symbol}: {e}", code=e.code)


# ── Order Operations ──────────────────────────────────────────────────────────

def place_order(
    symbol: str,
    side: str,          # "buy" or "sell"
    order_type: str,    # "limit" or "market"
    quantity: float,
    price: Optional[float] = None,
    client_oid: Optional[str] = None,
    reduce_only: bool = False,
) -> dict:
    """
    Place a new order (SPOT or FUTURES).
    
    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')
        side: 'buy' or 'sell'
        order_type: 'limit' or 'market'
        quantity: Order quantity
        price: Price (required for limit orders)
        client_oid: Optional custom order ID
        reduce_only: If True, only reduce positions (futures only)
    
    Returns:
        Order response with orderId, status, etc.
    
    Raises:
        BitgetOrderError: On order placement failure
    """
    if order_type == "limit" and price is None:
        raise BitgetOrderError("price required for limit orders")
    
    body = {
        "symbol": symbol,
        "side": side,
        "orderType": order_type,
        "quantity": str(quantity),
        "productType": PRODUCT_TYPE.lower(),
    }
    
    if order_type == "limit":
        body["price"] = str(price)
    
    if client_oid:
        body["clientOid"] = client_oid
    
    # Futures-specific
    if PRODUCT_TYPE == "USDT-FUTURES":
        body["reduceOnly"] = "yes" if reduce_only else "no"
    
    try:
        response = _request(
            "POST",
            "/api/v2/mix/orders/place" if PRODUCT_TYPE == "USDT-FUTURES" else "/api/v2/spot/orders/place",
            body=body,
            require_auth=True,
        )
        log.info(
            "Order placed: %s %s %s @ %s qty=%s",
            side, symbol, order_type, price or "market", quantity,
        )
        return response
    except BitgetAuthError as e:
        log.error("Order placement failed: %s", e)
        raise BitgetOrderError(f"Failed to place order: {e}", code=e.code)


def cancel_order(symbol: str, order_id: str) -> dict:
    """
    Cancel an open order.
    
    Args:
        symbol: Trading pair
        order_id: Order ID returned from place_order
    
    Returns:
        Cancellation response
    
    Raises:
        BitgetOrderError: If order doesn't exist or is already closed
    """
    body = {
        "symbol": symbol,
        "orderId": order_id,
        "productType": PRODUCT_TYPE.lower(),
    }
    
    try:
        return _request(
            "POST",
            "/api/v2/mix/orders/cancel" if PRODUCT_TYPE == "USDT-FUTURES" else "/api/v2/spot/orders/cancel",
            body=body,
            require_auth=True,
        )
    except BitgetAuthError as e:
        raise BitgetOrderError(f"Failed to cancel order {order_id}: {e}", code=e.code)


def get_order(symbol: str, order_id: str) -> dict | None:
    """
    Fetch order details.
    
    Args:
        symbol: Trading pair
        order_id: Order ID
    
    Returns:
        Order object or None if not found
    """
    try:
        return _request(
            "GET",
            "/api/v2/mix/orders/details" if PRODUCT_TYPE == "USDT-FUTURES" else "/api/v2/spot/orders/details",
            params={"symbol": symbol, "orderId": order_id, "productType": PRODUCT_TYPE.lower()},
            require_auth=True,
        )
    except BitgetAuthError as e:
        log.warning("Failed to fetch order %s: %s", order_id, e)
        return None


def get_open_orders(symbol: str = None) -> list:
    """
    Fetch all open orders.
    
    Args:
        symbol: Optional symbol filter
    
    Returns:
        List of open orders
    """
    params = {"productType": PRODUCT_TYPE.lower()}
    if symbol:
        params["symbol"] = symbol
    
    try:
        data = _request(
            "GET",
            "/api/v2/mix/orders/pending" if PRODUCT_TYPE == "USDT-FUTURES" else "/api/v2/spot/orders/pending",
            params=params,
            require_auth=True,
        )
        return data if isinstance(data, list) else []
    except BitgetAuthError as e:
        log.error("Failed to fetch open orders: %s", e)
        return []


def cancel_all_orders(symbol: str) -> list:
    """
    Cancel all open orders for a symbol.
    
    Args:
        symbol: Trading pair
    
    Returns:
        List of cancelled order IDs
    """
    body = {
        "symbol": symbol,
        "productType": PRODUCT_TYPE.lower(),
    }
    
    try:
        return _request(
            "POST",
            "/api/v2/mix/orders/cancel-all" if PRODUCT_TYPE == "USDT-FUTURES" else "/api/v2/spot/orders/cancel-all",
            body=body,
            require_auth=True,
        )
    except BitgetAuthError as e:
        log.error("Failed to cancel all orders for %s: %s", symbol, e)
        return []


# ── Leverage & Risk Management ────────────────────────────────────────────────

def set_leverage(symbol: str, leverage: int, side: str = None) -> dict:
    """
    Set leverage for a futures position (USDT-FUTURES only).
    
    Args:
        symbol: Trading pair
        leverage: Leverage multiplier (1-20)
        side: 'long' or 'short' (required for one-way mode)
    
    Returns:
        Leverage update response
    
    Raises:
        BitgetOrderError: If leverage setting fails
    """
    if PRODUCT_TYPE != "USDT-FUTURES":
        raise BitgetOrderError("set_leverage only works with USDT-FUTURES")
    
    if not (1 <= leverage <= 20):
        raise BitgetOrderError(f"leverage must be 1-20, got {leverage}")
    
    body = {
        "symbol": symbol,
        "leverage": str(leverage),
        "productType": PRODUCT_TYPE.lower(),
    }
    
    if side:
        body["side"] = side
    
    try:
        return _request(
            "POST",
            "/api/v2/mix/account/set-leverage",
            body=body,
            require_auth=True,
        )
    except BitgetAuthError as e:
        raise BitgetOrderError(f"Failed to set leverage: {e}", code=e.code)


def set_margin_mode(symbol: str, margin_mode: str) -> dict:
    """
    Set margin mode for a position (isolated or cross).
    
    Args:
        symbol: Trading pair
        margin_mode: 'isolated' or 'crossed'
    
    Returns:
        Mode update response
    """
    if margin_mode not in ("isolated", "crossed"):
        raise BitgetOrderError(f"Invalid margin mode: {margin_mode}")
    
    body = {
        "symbol": symbol,
        "marginMode": margin_mode,
        "productType": PRODUCT_TYPE.lower(),
    }
    
    try:
        return _request(
            "POST",
            "/api/v2/mix/account/set-margin-mode",
            body=body,
            require_auth=True,
        )
    except BitgetAuthError as e:
        log.error("Failed to set margin mode: %s", e)
        raise


# ── Convenience functions ─────────────────────────────────────────────────────

def is_authenticated() -> bool:
    """Check if API credentials are configured."""
    return _auth_available


def place_market_order(symbol: str, side: str, quantity: float) -> dict:
    """Shortcut for market order."""
    return place_order(symbol, side, "market", quantity)


def place_limit_order(symbol: str, side: str, quantity: float, price: float) -> dict:
    """Shortcut for limit order."""
    return place_order(symbol, side, "limit", quantity, price=price)


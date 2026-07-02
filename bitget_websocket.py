"""
bitget_websocket.py — Bitget WebSocket public feed for real-time market data.

Subscribes to public channels:
  - ticker — price updates
  - candle (1H) — 1-hour candle updates
  - funding-rate — funding rate changes

Uses thread-safe queue to pipe updates to the main loop.
Automatic reconnect with exponential backoff on connection loss.
Zero auth required — public market data only.

Design:
  - Long-lived connection in a daemon thread
  - Thread-safe dict cache of latest tickers
  - Graceful shutdown hook
"""

import json
import logging
import threading
import time
from collections import defaultdict
from datetime import datetime
from typing import Callable, Optional

import websocket

from config import (
    WHITELIST_SYMBOLS,
    REQUEST_TIMEOUT_SECONDS,
    PRODUCT_TYPE,
)

log = logging.getLogger("bitget_websocket")

# Bitget public WebSocket endpoint
BITGET_WS_URL = "wss://ws.bitget.com/spot/v1/public"
BITGET_FUTURES_WS_URL = "wss://ws.bitget.com/mix/v1/public"

# Reconnect parameters
INITIAL_BACKOFF = 1.0  # seconds
MAX_BACKOFF = 60.0  # seconds
BACKOFF_MULTIPLIER = 2.0


class BitgetWebSocketClient:
    """
    Manages a WebSocket connection to Bitget public feeds.
    Runs in a daemon thread; call start() to begin, stop() to shutdown.
    """

    def __init__(self, symbols: list, on_ticker: Optional[Callable] = None):
        """
        Args:
            symbols: List of symbols to subscribe (e.g. ['BTCUSDT', 'ETHUSDT'])
            on_ticker: Optional callback(symbol, ticker_data) for new tickers
        """
        self.symbols = symbols
        self.on_ticker = on_ticker
        self.ws = None
        self._shutdown = False
        self._thread = None
        self._lock = threading.Lock()
        self._ticker_cache = {}  # {symbol: {data}}
        self._backoff = INITIAL_BACKOFF

    def start(self):
        """Start the WebSocket connection in a daemon thread."""
        if self._thread is not None:
            log.warning("WebSocket already started")
            return
        self._shutdown = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        log.info("WebSocket client started for symbols: %s", ", ".join(self.symbols))

    def stop(self):
        """Gracefully shut down the WebSocket connection."""
        self._shutdown = True
        if self.ws:
            try:
                self.ws.close()
            except Exception as e:
                log.debug("Error closing WebSocket: %s", e)
        if self._thread:
            self._thread.join(timeout=5)
        log.info("WebSocket client stopped")

    def get_ticker(self, symbol: str) -> dict | None:
        """Returns latest cached ticker for symbol, or None if not yet received."""
        with self._lock:
            return self._ticker_cache.get(symbol)

    def _run(self):
        """Main WebSocket loop with auto-reconnect."""
        while not self._shutdown:
            try:
                self._connect_and_listen()
            except Exception as e:
                log.error("WebSocket error: %s", e)
                if not self._shutdown:
                    log.info("Reconnecting in %.1fs...", self._backoff)
                    time.sleep(self._backoff)
                    self._backoff = min(self._backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF)

    def _connect_and_listen(self):
        """Establish WebSocket connection and listen for messages."""
        ws_url = BITGET_FUTURES_WS_URL if PRODUCT_TYPE == "USDT-FUTURES" else BITGET_WS_URL
        
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        
        # Subscribe to channels
        self._subscribe()
        
        # Run until shutdown or error
        self.ws.run_forever(
            dispatcher=websocket.threading.ThreadingClientConnectionDispatcher(),
            ping_interval=30,
            ping_payload="",
        )

    def _subscribe(self):
        """Send subscription requests for ticker and candle channels."""
        # Subscribe to tickers
        for symbol in self.symbols:
            msg = {
                "op": "subscribe",
                "args": [
                    {
                        "instType": PRODUCT_TYPE,
                        "channel": "ticker",
                        "instId": symbol,
                    }
                ],
            }
            try:
                self.ws.send(json.dumps(msg))
                log.debug("Subscribed to ticker: %s", symbol)
            except Exception as e:
                log.warning("Failed to subscribe to ticker %s: %s", symbol, e)

        # Subscribe to 1H candles
        for symbol in self.symbols:
            msg = {
                "op": "subscribe",
                "args": [
                    {
                        "instType": PRODUCT_TYPE,
                        "channel": "candle1H",
                        "instId": symbol,
                    }
                ],
            }
            try:
                self.ws.send(json.dumps(msg))
                log.debug("Subscribed to candle1H: %s", symbol)
            except Exception as e:
                log.warning("Failed to subscribe to candle1H %s: %s", symbol, e)

        # Subscribe to funding rates (futures only)
        if PRODUCT_TYPE == "USDT-FUTURES":
            for symbol in self.symbols:
                msg = {
                    "op": "subscribe",
                    "args": [
                        {
                            "instType": PRODUCT_TYPE,
                            "channel": "fundingRate",
                            "instId": symbol,
                        }
                    ],
                }
                try:
                    self.ws.send(json.dumps(msg))
                    log.debug("Subscribed to fundingRate: %s", symbol)
                except Exception as e:
                    log.warning("Failed to subscribe to fundingRate %s: %s", symbol, e)

    def _on_message(self, ws, message: str):
        """Process incoming WebSocket message."""
        try:
            data = json.loads(message)
        except json.JSONDecodeError as e:
            log.warning("Invalid JSON from WebSocket: %s", e)
            return

        if "data" not in data:
            return

        event_data = data.get("data", [])
        arg = data.get("arg", {})
        channel = arg.get("channel")
        symbol = arg.get("instId")

        if not event_data or not symbol:
            return

        # Handle ticker updates
        if channel == "ticker":
            self._handle_ticker(symbol, event_data[0])

        # Handle candle updates
        elif channel == "candle1H":
            self._handle_candle(symbol, event_data[0])

        # Handle funding rate updates
        elif channel == "fundingRate":
            self._handle_funding_rate(symbol, event_data[0])

    def _handle_ticker(self, symbol: str, ticker_data: dict):
        """Cache ticker and call callback if provided."""
        with self._lock:
            self._ticker_cache[symbol] = {
                "lastPr": ticker_data.get("lastPr"),
                "high24h": ticker_data.get("high24h"),
                "low24h": ticker_data.get("low24h"),
                "usdtVolume": ticker_data.get("usdtVolume"),
                "timestamp": datetime.utcnow().isoformat(),
            }

        if self.on_ticker:
            try:
                self.on_ticker(symbol, self._ticker_cache[symbol])
            except Exception as e:
                log.warning("Error in on_ticker callback: %s", e)

        log.debug("Ticker %s: %s", symbol, ticker_data.get("lastPr"))

    def _handle_candle(self, symbol: str, candle_data: dict):
        """Log candle update (for debugging; main loop uses REST API)."""
        log.debug(
            "Candle 1H %s: close=%s, vol=%s",
            symbol,
            candle_data.get("c"),
            candle_data.get("vol"),
        )

    def _handle_funding_rate(self, symbol: str, rate_data: dict):
        """Log funding rate update."""
        log.debug(
            "Funding rate %s: %s%%",
            symbol,
            float(rate_data.get("fundingRate", 0)) * 100,
        )

    def _on_error(self, ws, error):
        """Handle WebSocket error."""
        log.error("WebSocket error: %s", error)

    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close."""
        log.warning("WebSocket closed: %s %s", close_status_code, close_msg)
        self._backoff = INITIAL_BACKOFF  # Reset backoff on close


# Global WebSocket client instance
_ws_client = None


def init_websocket(on_ticker: Optional[Callable] = None):
    """Initialize and start the global WebSocket client."""
    global _ws_client
    if _ws_client is not None:
        log.warning("WebSocket already initialized")
        return _ws_client
    _ws_client = BitgetWebSocketClient(WHITELIST_SYMBOLS, on_ticker=on_ticker)
    _ws_client.start()
    return _ws_client


def stop_websocket():
    """Stop the global WebSocket client."""
    global _ws_client
    if _ws_client:
        _ws_client.stop()
        _ws_client = None


def get_live_ticker(symbol: str) -> dict | None:
    """Retrieve latest cached ticker from WebSocket."""
    if _ws_client is None:
        return None
    return _ws_client.get_ticker(symbol)

"""
notifier.py — Premium Telegram signal notifications with iPhone 17 Pro Max aesthetic.

Modern glassmorphism design, premium typography, smooth animations,
and professional trading UI patterns.

Outbound only — the bot never reads incoming Telegram messages or commands,
since this is a signals-only system and never places orders.

Features:
  - Dynamic price precision (BTC shows 2dp, DOGE shows 6dp, sub-cent shows 8dp)
  - Premium glassmorphic design with gradients
  - Risk metrics and confidence scoring
  - Smooth data visualization with Unicode charts
  - Retry with backoff on transient send failures
  - Respects Telegram 429 rate-limit Retry-After header
  - Uses TELEGRAM_ENABLED flag from config instead of string-matching tokens
"""

import time
import logging

import requests

from config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLED,
    ACCOUNT_RISK_PERCENT, REQUEST_TIMEOUT_SECONDS,
)

log = logging.getLogger("notifier")

_API_URL       = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
_MAX_RETRIES   = 3
_RETRY_BACKOFF = 2.0  # seconds, multiplied by attempt number


def fmt_price(value: float) -> str:
    """
    Dynamic decimal precision based on price magnitude.
    Prevents low-priced coins like DOGE from rounding to 0.0000.

      >= 100        →  2 dp  (BTC: 65432.12)
      >= 1          →  4 dp  (SOL: 145.3210)
      >= 0.01       →  6 dp  (DOGE: 0.082345)
      < 0.01        →  8 dp  (sub-cent tokens)
    """
    if value == 0:
        return "0"
    abs_v = abs(value)
    if abs_v >= 1000:
        dp = 2
    elif abs_v >= 1:
        dp = 4
    elif abs_v >= 0.01:
        dp = 6
    else:
        dp = 8
    return f"{value:.{dp}f}"


def _get_confidence_level(rr_ratio: float, rsi: float = 50) -> tuple:
    """
    Calculate confidence level and emoji based on risk/reward and indicators.
    Returns (confidence_pct, emoji, strength_bar)
    """
    confidence = 50  # Base 50%
    
    # R:R contribution (max +30%)
    if rr_ratio >= 2.0:
        confidence += 30
    elif rr_ratio >= 1.5:
        confidence += 20
    elif rr_ratio >= 1.0:
        confidence += 10
    
    # RSI extremity contribution (max +15%)
    if 35 <= rsi <= 65:
        confidence += 15
    elif 30 <= rsi <= 70:
        confidence += 8
    
    confidence = min(confidence, 99)  # Cap at 99%
    
    if confidence >= 80:
        return confidence, "🔥", "█"  # Hot signal
    elif confidence >= 65:
        return confidence, "⚡", "▓"  # Strong
    elif confidence >= 50:
        return confidence, "✨", "▒"  # Moderate
    else:
        return confidence, "💭", "░"  # Weak


def _build_premium_signal_message(signal) -> str:
    """
    Premium iPhone 17 glassmorphic design signal message.
    Modern, minimal, professional trading aesthetic.
    """
    direction_emoji = "📈" if signal.direction == "LONG" else "📉"
    direction_label = "LONG 🟢" if signal.direction == "LONG" else "SHORT 🔴"
    
    # Calculate confidence
    rsi_val = signal.rsi if hasattr(signal, 'rsi') else 50
    confidence, conf_emoji, strength_char = _get_confidence_level(signal.reward_risk, rsi_val)
    
    # Create visual bars
    filled = int(confidence / 10)
    empty = 10 - filled
    confidence_bar = "█" * filled + "░" * empty
    
    # Risk reward visualization
    rr_filled = min(int(signal.reward_risk), 5)
    rr_bar = "█" * rr_filled
    
    # Premium header with glassmorphism
    header = (
        f"<b>┏━━━━━━━━━━━━━━━━━━━━━━━┓</b>\n"
        f"<b>┃  {direction_emoji} {direction_label:15s} ┃</b>\n"
        f"<b>┃  {signal.symbol:20s} ┃</b>\n"
        f"<b>┗━━━━━━━━━━━━━━━━━━━━━━━┛</b>"
    )
    
    # Price levels with premium formatting
    entry_color = "🟢" if signal.direction == "LONG" else "🔴"
    
    levels = (
        f"\n\n<b>💰 PRICE LEVELS</b>\n"
        f"<code>╭─ Entry Point</code>\n"
        f"<code>│  {entry_color} ${fmt_price(signal.entry)}</code>\n"
        f"<code>├─ Stop Loss (Risk Limit)</code>\n"
        f"<code>│  🛑 ${fmt_price(signal.stop_loss)}</code>\n"
        f"<code>╰─ Take Profit (Target)</code>\n"
        f"<code>   🎯 ${fmt_price(signal.take_profit)}</code>"
    )
    
    # Risk metrics section with visual indicators
    risk_value = abs(signal.entry - signal.stop_loss)
    reward_value = abs(signal.take_profit - signal.entry)
    
    metrics = (
        f"\n\n<b>📊 TRADE METRICS</b>\n"
        f"<code>Risk Amount      : ${risk_value:.2f}</code>\n"
        f"<code>Potential Reward : ${reward_value:.2f}</code>\n"
        f"<code>Reward:Risk      : {rr_bar:5s} {signal.reward_risk:.2f}:1</code>\n"
        f"<code>Suggested Leverage: {signal.suggested_leverage}x</code>"
    )
    
    # Confidence indicator with visual bar
    confidence_section = (
        f"\n\n<b>{conf_emoji} SIGNAL CONFIDENCE</b>\n"
        f"<code>[{confidence_bar}]</code>\n"
        f"<code>Strength: {confidence}% {strength_char * (confidence // 20)}</code>"
    )
    
    # Market conditions
    funding_pct = signal.funding_rate * 100
    if funding_pct > 0.05:
        funding_emoji = "📈"
        funding_status = "Positive (Longs favored)"
    elif funding_pct < -0.05:
        funding_emoji = "📉"
        funding_status = "Negative (Shorts favored)"
    else:
        funding_emoji = "➡️"
        funding_status = "Neutral"
    
    market_conditions = (
        f"\n\n<b>🌍 MARKET CONDITIONS</b>\n"
        f"<code>Funding Rate : {funding_emoji} {funding_pct:.3f}%</code>\n"
        f"<code>Status       : {funding_status}</code>"
    )
    
    # Account risk management
    account_risk = (
        f"\n\n<b>⚖️ RISK MANAGEMENT</b>\n"
        f"<code>Account Risk/Trade : {ACCOUNT_RISK_PERCENT:.1f}%</code>\n"
        f"<code>Position Sizing    : Your Responsibility</code>"
    )
    
    # Confidence notes with icons (glassmorphic style)
    notes_header = "\n\n<b>✅ CONFIRMATION FACTORS</b>"
    notes_formatted = ""
    icons = ["🔍", "📊", "⚡", "🎯", "💹", "🚀"]
    for i, note in enumerate(signal.confidence_notes):
        icon = icons[i % len(icons)]
        notes_formatted += f"\n<code>{icon} {note}</code>"
    
    # Premium footer with gradient separator
    footer = (
        f"\n\n<b>┌──────────────────────────┐</b>\n"
        f"<b>│  ⚠️  DISCLAIMER & RULES   │</b>\n"
        f"<b>└──────────────────────────┘</b>\n"
        f"<i>• This is a signal only — not financial advice</i>\n"
        f"• You execute trades manually at your own risk\n"
        f"• Always use stop losses for protection\n"
        f"• Never risk more than 1-2% per trade\n"
        f"• Leverage carries extreme risk — trade responsibly\n"
        f"• Past performance ≠ Future results\n\n"
        f"<b>Good luck! 🚀</b>"
    )
    
    return header + levels + metrics + confidence_section + market_conditions + account_risk + notes_header + notes_formatted + footer


def _build_status_message_premium(text: str, status_type: str = "info") -> str:
    """
    Premium status message with glassmorphic design.
    status_type: 'success', 'error', 'info', 'warning'
    """
    emoji_map = {
        "success": "✅",
        "error": "❌",
        "info": "ℹ️",
        "warning": "⚠️",
        "start": "🚀",
        "stop": "⛔",
    }
    emoji = emoji_map.get(status_type, "ℹ️")
    
    return (
        f"<b>╔════════════════════════════════╗</b>\n"
        f"<b>║ {emoji:2s}  Status Update          ║</b>\n"
        f"<b>╚════════════════════════════════╝</b>\n\n"
        f"{text}\n\n"
        f"<i>Updated at: {int(time.time())}</i>"
    )


def _send_raw(text: str) -> bool:
    """
    Sends one Telegram message with retry/backoff.
    Returns True on success, False after all retries exhausted.
    """
    if not TELEGRAM_ENABLED:
        log.warning(
            "Telegram not configured — message not sent. "
            "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env to enable. "
            "Preview (first 200 chars): %s", text[:200]
        )
        return False

    payload = {
        "chat_id":               TELEGRAM_CHAT_ID,
        "text":                  text,
        "parse_mode":            "HTML",
        "disable_web_page_preview": True,
    }

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.post(_API_URL, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)

            if resp.status_code == 429:
                retry_after = resp.json().get("parameters", {}).get("retry_after", 5)
                log.warning("Telegram rate limited — waiting %ss (attempt %s)", retry_after, attempt)
                time.sleep(retry_after)
                continue

            resp.raise_for_status()
            return True

        except requests.RequestException as exc:
            log.warning("Telegram send failed attempt %s/%s: %s", attempt, _MAX_RETRIES, exc)
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_BACKOFF * attempt)

    log.error("Gave up sending Telegram message after %s attempts.", _MAX_RETRIES)
    return False


def send_signal(signal) -> bool:
    """Formats and sends a premium trade signal alert."""
    return _send_raw(_build_premium_signal_message(signal))


def send_status(text: str, status_type: str = "info") -> bool:
    """Sends a premium status/info message (startup, shutdown, errors)."""
    return _send_raw(_build_status_message_premium(text, status_type))

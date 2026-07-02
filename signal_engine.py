"""
signal_engine.py — Multi-factor signal generation.

A signal only fires when ALL confirmation layers agree:
  1. Higher-timeframe trend (4H EMA crossover)
  2. Lower-timeframe alignment (1H EMA crossover matches trend)
  3. RSI not extended (not chasing an already-exhausted move)
  4. Breakout of recent high/low on a volume spike
  5. Funding rate within safe range (not an overcrowded trade)

Every signal carries ATR-based SL/TP levels and a reward:risk ratio.
No orders are placed — this is a signal/alert system only.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from config import (
    EMA_FAST, EMA_SLOW,
    RSI_OVERBOUGHT, RSI_OVERSOLD,
    VOLUME_SPIKE_MULTIPLIER,
    MAX_ABS_FUNDING_RATE,
    ATR_STOP_MULTIPLIER, ATR_TARGET_MULTIPLIER,
    MAX_LEVERAGE_SUGGESTED,
)

log = logging.getLogger("signal_engine")

# Minimum number of candles required before we trust indicator values.
# Below this the EWM warmup period means readings are unreliable.
MIN_CANDLES_REQUIRED = 60


@dataclass
class Signal:
    symbol:            str
    direction:         str        # "LONG" or "SHORT"
    entry:             float
    stop_loss:         float
    take_profit:       float
    reward_risk:       float
    funding_rate:      float
    suggested_leverage: int
    rsi:               float
    atr:               float
    confidence_notes:  list = field(default_factory=list)


def _higher_tf_trend(trend_df: pd.DataFrame) -> Optional[str]:
    """
    Determines dominant trend direction from the higher timeframe (e.g. 4H).
    Returns 'LONG', 'SHORT', or None if EMAs are flat/equal.
    """
    last = trend_df.iloc[-1]
    ema_fast = last["ema_fast"]
    ema_slow = last["ema_slow"]
    if pd.isna(ema_fast) or pd.isna(ema_slow):
        return None
    if ema_fast > ema_slow:
        return "LONG"
    if ema_fast < ema_slow:
        return "SHORT"
    return None


def evaluate_symbol(
    symbol:       str,
    signal_df:    pd.DataFrame,
    trend_df:     pd.DataFrame,
    funding_rate: float,
) -> Optional[Signal]:
    """
    Runs all signal filters for one symbol.

    Args:
        symbol:       Trading pair, e.g. "BTCUSDT"
        signal_df:    Enriched lower-TF candle DataFrame (e.g. 1H)
        trend_df:     Enriched higher-TF candle DataFrame (e.g. 4H)
        funding_rate: Current perpetual funding rate (decimal, e.g. 0.0001)

    Returns:
        Signal dataclass if all filters pass, else None.
    """
    # ── Warmup guard ─────────────────────────────────────────────────────────
    if len(signal_df) < MIN_CANDLES_REQUIRED or len(trend_df) < MIN_CANDLES_REQUIRED:
        log.debug("%s skipped: not enough candles for warmup (%s signal, %s trend)",
                  symbol, len(signal_df), len(trend_df))
        return None

    # ── Filter 1: Higher timeframe trend ─────────────────────────────────────
    trend = _higher_tf_trend(trend_df)
    if trend is None:
        log.debug("%s skipped: higher-TF trend is flat/undefined", symbol)
        return None

    notes = []
    last = signal_df.iloc[-1]

    # ── Filter 2: Lower timeframe EMA alignment ───────────────────────────────
    ema_fast = last["ema_fast"]
    ema_slow = last["ema_slow"]

    if pd.isna(ema_fast) or pd.isna(ema_slow):
        return None

    lf_direction = "LONG" if ema_fast > ema_slow else ("SHORT" if ema_fast < ema_slow else None)
    if lf_direction != trend:
        log.debug("%s skipped: 1H EMA direction (%s) conflicts with 4H trend (%s)",
                  symbol, lf_direction, trend)
        return None

    notes.append(
        f"EMA{EMA_FAST}/{EMA_SLOW} aligned on both 4H and 1H timeframes ({trend})"
    )

    # ── Filter 3: RSI not extended ────────────────────────────────────────────
    rsi = last["rsi"]
    if pd.isna(rsi):
        return None

    if trend == "LONG"  and rsi >= RSI_OVERBOUGHT:
        log.debug("%s skipped: RSI=%.1f overbought for LONG", symbol, rsi)
        return None
    if trend == "SHORT" and rsi <= RSI_OVERSOLD:
        log.debug("%s skipped: RSI=%.1f oversold for SHORT", symbol, rsi)
        return None

    notes.append(f"RSI={rsi:.1f} — not extended ({'below' if trend == 'LONG' else 'above'} "
                 f"{'overbought' if trend == 'LONG' else 'oversold'} threshold)")

    # ── Filter 4: Breakout + volume spike ────────────────────────────────────
    close        = last["close"]
    recent_high  = last["recent_high"]
    recent_low   = last["recent_low"]
    avg_volume   = last["avg_volume"]
    curr_volume  = last["quote_vol"]

    if pd.isna(recent_high) or pd.isna(recent_low) or pd.isna(avg_volume) or avg_volume <= 0:
        log.debug("%s skipped: breakout reference values not yet available", symbol)
        return None

    volume_spike = curr_volume > avg_volume * VOLUME_SPIKE_MULTIPLIER

    if trend == "LONG":
        breakout = close > recent_high
        if not (breakout and volume_spike):
            log.debug(
                "%s LONG: breakout=%s (close=%.6f > high=%.6f), vol_spike=%s (%.0f vs avg %.0f)",
                symbol, breakout, close, recent_high, volume_spike, curr_volume, avg_volume,
            )
            return None
        notes.append(
            f"Bullish breakout above {recent_high:.6f} — "
            f"volume {curr_volume:.0f} vs avg {avg_volume:.0f} "
            f"({curr_volume/avg_volume:.1f}x spike)"
        )
    else:  # SHORT
        breakout = close < recent_low
        if not (breakout and volume_spike):
            log.debug(
                "%s SHORT: breakout=%s (close=%.6f < low=%.6f), vol_spike=%s (%.0f vs avg %.0f)",
                symbol, breakout, close, recent_low, volume_spike, curr_volume, avg_volume,
            )
            return None
        notes.append(
            f"Bearish breakout below {recent_low:.6f} — "
            f"volume {curr_volume:.0f} vs avg {avg_volume:.0f} "
            f"({curr_volume/avg_volume:.1f}x spike)"
        )

    # ── Filter 5: Funding rate ────────────────────────────────────────────────
    if abs(funding_rate) > MAX_ABS_FUNDING_RATE:
        log.info("%s skipped: funding rate %.4f%% exceeds cap %.4f%%",
                 symbol, funding_rate * 100, MAX_ABS_FUNDING_RATE * 100)
        return None

    funding_direction = "positive" if funding_rate > 0 else ("negative" if funding_rate < 0 else "neutral")
    notes.append(
        f"Funding rate {funding_rate * 100:.3f}% ({funding_direction}) — within safe range"
    )

    # ── ATR-based SL / TP ────────────────────────────────────────────────────
    atr = last["atr"]
    if pd.isna(atr) or atr <= 0:
        log.debug("%s skipped: ATR is NaN or zero", symbol)
        return None

    entry = close
    if trend == "LONG":
        stop_loss   = entry - atr * ATR_STOP_MULTIPLIER
        take_profit = entry + atr * ATR_TARGET_MULTIPLIER
    else:
        stop_loss   = entry + atr * ATR_STOP_MULTIPLIER
        take_profit = entry - atr * ATR_TARGET_MULTIPLIER

    risk   = abs(entry - stop_loss)
    reward = abs(take_profit - entry)

    if risk <= 0:
        log.debug("%s skipped: computed risk distance is zero", symbol)
        return None

    reward_risk = reward / risk

    notes.append(
        f"ATR={atr:.6f} → SL {ATR_STOP_MULTIPLIER}×ATR, "
        f"TP {ATR_TARGET_MULTIPLIER}×ATR → R:R {reward_risk:.2f}"
    )

    return Signal(
        symbol=symbol,
        direction=trend,
        entry=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        reward_risk=reward_risk,
        funding_rate=funding_rate,
        suggested_leverage=MAX_LEVERAGE_SUGGESTED,
        rsi=float(rsi),
        atr=float(atr),
        confidence_notes=notes,
    )

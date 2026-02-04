"""
Never Sell At Loss Strategy

The idea: Only exit when in profit. Hold through drawdowns.

Why this might work:
- BTC is mean-reverting short term (dips recover)
- OI drop = liquidation = usually temporary oversold
- If entry is good, price should eventually come back

Why this might fail:
- Trend changes (what if we enter at the start of a bear market?)
- Capital locked up (can't take new trades while holding losers)
- Psychological torture (watching unrealized losses)

Let's test it.
"""

import pandas as pd
import numpy as np


class NeverSellLossStrategy:
    """
    Only exit when in profit - never realize a loss

    Parameters:
    -----------
    oi_drop_threshold : float
        Min OI drop to trigger entry (default: -0.2%)
    price_drop_threshold : float
        Min price drop to trigger entry (default: -0.3%)
    profit_target : float
        Exit when this profit % reached (default: 1.5%)
    lookback_hours : int
        Hours to look back for changes (default: 4)
    """

    def __init__(
        self,
        oi_drop_threshold=-0.2,
        price_drop_threshold=-0.3,
        profit_target=1.5,
        lookback_hours=4,
        min_hours_between_trades=8
    ):
        self.oi_drop_threshold = oi_drop_threshold
        self.price_drop_threshold = price_drop_threshold
        self.profit_target = profit_target
        self.lookback_hours = lookback_hours
        self.min_hours_between_trades = min_hours_between_trades

        self.name = f"NeverSellLoss_{profit_target}pct"

    def generate_signals(self, data):
        """Generate signals - only sell when profitable"""
        df = data.copy()

        if 'oi_btc' not in df.columns:
            raise ValueError("Data must contain 'oi_btc' column")

        df['oi_change'] = df['oi_btc'].pct_change(self.lookback_hours) * 100
        df['price_change'] = df['close'].pct_change(self.lookback_hours) * 100

        df['signal'] = 'HOLD'

        in_position = False
        entry_idx = None
        entry_price = None
        last_trade_idx = -self.min_hours_between_trades

        # Track stats
        max_drawdown_seen = 0
        hours_underwater = 0

        for i in range(self.lookback_hours, len(df)):
            current_price = df['close'].iloc[i]
            oi_change = df['oi_change'].iloc[i]
            price_change = df['price_change'].iloc[i]

            if pd.isna(oi_change) or pd.isna(price_change):
                continue

            # ENTRY
            if not in_position:
                if (i - last_trade_idx) < self.min_hours_between_trades:
                    continue

                if oi_change <= self.oi_drop_threshold and price_change <= self.price_drop_threshold:
                    df.iloc[i, df.columns.get_loc('signal')] = 'BUY'
                    in_position = True
                    entry_idx = i
                    entry_price = current_price
                    max_drawdown_seen = 0
                    hours_underwater = 0

            # EXIT - ONLY when profitable
            else:
                current_return = (current_price / entry_price - 1) * 100

                # Track how bad it got
                if current_return < max_drawdown_seen:
                    max_drawdown_seen = current_return

                if current_return < 0:
                    hours_underwater += 1

                # Only sell if we hit profit target
                if current_return >= self.profit_target:
                    df.iloc[i, df.columns.get_loc('signal')] = 'SELL'
                    in_position = False
                    last_trade_idx = i
                    entry_idx = None
                    entry_price = None

        return df

    def describe(self):
        return f"""
Never Sell At Loss Strategy
===========================
ENTRY: OI drops {self.oi_drop_threshold}% AND Price drops {self.price_drop_threshold}%

EXIT: ONLY when profit reaches {self.profit_target}%
      NO stop loss
      NO time limit

Philosophy: If the entry signal is good, price will eventually recover.
            Accept temporary pain for guaranteed profitable exits.

Risk: Could be stuck holding for extended periods.
      Capital is locked while underwater.
"""


class NeverSellLossWithTrailing:
    """
    Never sell at loss, but use trailing stop once in profit

    This locks in gains while still never selling at a loss.
    """

    def __init__(
        self,
        oi_drop_threshold=-0.2,
        price_drop_threshold=-0.3,
        min_profit_to_trail=0.5,  # Start trailing after this profit
        trailing_stop=0.5,  # Trail by this amount from peak
        lookback_hours=4
    ):
        self.oi_drop_threshold = oi_drop_threshold
        self.price_drop_threshold = price_drop_threshold
        self.min_profit_to_trail = min_profit_to_trail
        self.trailing_stop = trailing_stop
        self.lookback_hours = lookback_hours

        self.name = f"NeverLoss_Trail_{trailing_stop}pct"

    def generate_signals(self, data):
        df = data.copy()

        if 'oi_btc' not in df.columns:
            raise ValueError("Data must contain 'oi_btc' column")

        df['oi_change'] = df['oi_btc'].pct_change(self.lookback_hours) * 100
        df['price_change'] = df['close'].pct_change(self.lookback_hours) * 100

        df['signal'] = 'HOLD'

        in_position = False
        entry_price = None
        peak_price = None
        trailing_active = False

        for i in range(self.lookback_hours, len(df)):
            current_price = df['close'].iloc[i]
            oi_change = df['oi_change'].iloc[i]
            price_change = df['price_change'].iloc[i]

            if pd.isna(oi_change) or pd.isna(price_change):
                continue

            if not in_position:
                if oi_change <= self.oi_drop_threshold and price_change <= self.price_drop_threshold:
                    df.iloc[i, df.columns.get_loc('signal')] = 'BUY'
                    in_position = True
                    entry_price = current_price
                    peak_price = current_price
                    trailing_active = False

            else:
                current_return = (current_price / entry_price - 1) * 100

                # Update peak
                if current_price > peak_price:
                    peak_price = current_price

                # Activate trailing once we have enough profit
                if current_return >= self.min_profit_to_trail:
                    trailing_active = True

                # Check trailing stop (but never sell at loss)
                if trailing_active:
                    drawdown_from_peak = (current_price / peak_price - 1) * 100

                    # Only exit if:
                    # 1. Trailing stop triggered
                    # 2. AND we're still in profit (never sell at loss)
                    if drawdown_from_peak <= -self.trailing_stop and current_return > 0:
                        df.iloc[i, df.columns.get_loc('signal')] = 'SELL'
                        in_position = False
                        entry_price = None
                        peak_price = None
                        trailing_active = False

        return df

    def describe(self):
        return f"""
Never Sell Loss + Trailing Stop
===============================
ENTRY: OI drops {self.oi_drop_threshold}% AND Price drops {self.price_drop_threshold}%

EXIT:
1. Wait until profit reaches {self.min_profit_to_trail}%
2. Then trail {self.trailing_stop}% from peak
3. BUT only exit if still in profit (never realize a loss)

This lets winners run while guaranteeing no losing trades.
"""


class BreakevenOrBetter:
    """
    Exit at breakeven or better - accept 0% return to free up capital
    """

    def __init__(
        self,
        oi_drop_threshold=-0.2,
        price_drop_threshold=-0.3,
        profit_target=1.5,
        breakeven_after_hours=48,  # After this many hours, accept breakeven
        lookback_hours=4
    ):
        self.oi_drop_threshold = oi_drop_threshold
        self.price_drop_threshold = price_drop_threshold
        self.profit_target = profit_target
        self.breakeven_after_hours = breakeven_after_hours
        self.lookback_hours = lookback_hours

        self.name = f"BreakevenOrBetter_{profit_target}pct"

    def generate_signals(self, data):
        df = data.copy()

        if 'oi_btc' not in df.columns:
            raise ValueError("Data must contain 'oi_btc' column")

        df['oi_change'] = df['oi_btc'].pct_change(self.lookback_hours) * 100
        df['price_change'] = df['close'].pct_change(self.lookback_hours) * 100

        df['signal'] = 'HOLD'

        in_position = False
        entry_idx = None
        entry_price = None

        for i in range(self.lookback_hours, len(df)):
            current_price = df['close'].iloc[i]
            oi_change = df['oi_change'].iloc[i]
            price_change = df['price_change'].iloc[i]

            if pd.isna(oi_change) or pd.isna(price_change):
                continue

            if not in_position:
                if oi_change <= self.oi_drop_threshold and price_change <= self.price_drop_threshold:
                    df.iloc[i, df.columns.get_loc('signal')] = 'BUY'
                    in_position = True
                    entry_idx = i
                    entry_price = current_price

            else:
                hours_held = i - entry_idx
                current_return = (current_price / entry_price - 1) * 100

                should_exit = False

                # Always exit at profit target
                if current_return >= self.profit_target:
                    should_exit = True

                # After waiting period, accept breakeven or better
                elif hours_held >= self.breakeven_after_hours and current_return >= 0:
                    should_exit = True

                if should_exit:
                    df.iloc[i, df.columns.get_loc('signal')] = 'SELL'
                    in_position = False
                    entry_idx = None
                    entry_price = None

        return df

    def describe(self):
        return f"""
Breakeven Or Better Strategy
============================
ENTRY: OI drops {self.oi_drop_threshold}% AND Price drops {self.price_drop_threshold}%

EXIT:
1. If profit reaches {self.profit_target}% → SELL (profit target)
2. After {self.breakeven_after_hours}h, if return >= 0% → SELL (breakeven exit)
3. Otherwise → HOLD (never sell at loss)

This balances "never sell at loss" with capital efficiency.
"""

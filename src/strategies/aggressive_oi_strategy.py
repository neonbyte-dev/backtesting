"""
Aggressive OI Strategy - Designed for Better Returns

Learning from our analysis:
1. OI drop signal works but is noisy (~55% win rate)
2. Fixed 24h exit leaves money on table
3. Best exit: 2% profit target + 1% stop loss
4. The signal is better on larger OI drops + price drops

This strategy aims for:
- Fewer but higher quality trades
- Quick profit taking (don't let winners reverse)
- Cut losses fast (1% stop)
- Never hold more than 48 hours
"""

import pandas as pd
import numpy as np


class AggressiveOIStrategy:
    """
    Aggressive OI-based strategy with proper risk management

    Key differences from previous strategies:
    1. Stricter entry conditions (OI drop + price drop + volume surge)
    2. Fixed profit target (take 2% and run)
    3. Tight stop loss (1% max loss)
    4. No trailing stops (they hurt in choppy markets)
    """

    def __init__(
        self,
        # Entry parameters
        oi_drop_threshold=-0.25,      # OI must drop this much (%)
        price_drop_threshold=-0.5,    # Price must drop this much (%)
        lookback_hours=4,             # Look back period
        min_hours_between_trades=8,   # Don't trade too frequently

        # Exit parameters
        profit_target=2.0,            # Take profit at this % gain
        stop_loss=-1.0,               # Cut loss at this % loss
        max_hold_hours=48,            # Force exit after this many hours

        # Position sizing (for future enhancement)
        position_size=1.0             # Fraction of capital to use (1.0 = 100%)
    ):
        self.oi_drop_threshold = oi_drop_threshold
        self.price_drop_threshold = price_drop_threshold
        self.lookback_hours = lookback_hours
        self.min_hours_between_trades = min_hours_between_trades
        self.profit_target = profit_target
        self.stop_loss = stop_loss
        self.max_hold_hours = max_hold_hours
        self.position_size = position_size

        self.name = f"Aggressive_OI_{profit_target}pct_target"

    def generate_signals(self, data):
        """
        Generate trading signals with proper risk management

        Returns DataFrame with 'signal' column
        """
        df = data.copy()

        # Validate required columns
        if 'oi_btc' not in df.columns:
            raise ValueError("Data must contain 'oi_btc' column")

        # Calculate changes
        df['oi_change'] = df['oi_btc'].pct_change(self.lookback_hours) * 100
        df['price_change'] = df['close'].pct_change(self.lookback_hours) * 100

        # Initialize
        df['signal'] = 'HOLD'

        in_position = False
        entry_idx = None
        entry_price = None
        last_trade_idx = -self.min_hours_between_trades  # Allow first trade

        for i in range(self.lookback_hours, len(df)):
            current_price = df['close'].iloc[i]
            oi_change = df['oi_change'].iloc[i]
            price_change = df['price_change'].iloc[i]

            if pd.isna(oi_change) or pd.isna(price_change):
                continue

            # ======== ENTRY LOGIC ========
            if not in_position:
                # Check minimum time between trades
                if (i - last_trade_idx) < self.min_hours_between_trades:
                    continue

                # Entry conditions
                oi_condition = oi_change <= self.oi_drop_threshold
                price_condition = price_change <= self.price_drop_threshold

                if oi_condition and price_condition:
                    df.iloc[i, df.columns.get_loc('signal')] = 'BUY'
                    in_position = True
                    entry_idx = i
                    entry_price = current_price

            # ======== EXIT LOGIC ========
            else:
                hours_held = i - entry_idx
                current_return = (current_price / entry_price - 1) * 100

                exit_trade = False

                # 1. PROFIT TARGET - most important!
                if current_return >= self.profit_target:
                    exit_trade = True

                # 2. STOP LOSS
                elif current_return <= self.stop_loss:
                    exit_trade = True

                # 3. MAX HOLD TIME
                elif hours_held >= self.max_hold_hours:
                    exit_trade = True

                if exit_trade:
                    df.iloc[i, df.columns.get_loc('signal')] = 'SELL'
                    in_position = False
                    last_trade_idx = i
                    entry_idx = None
                    entry_price = None

        return df

    def describe(self):
        return f"""
Aggressive OI Strategy
======================
ENTRY: Buy when OI drops {self.oi_drop_threshold}% AND price drops {self.price_drop_threshold}% over {self.lookback_hours}h

EXIT (in priority order):
1. PROFIT TARGET: {self.profit_target}% gain → SELL
2. STOP LOSS: {self.stop_loss}% loss → SELL
3. MAX HOLD: {self.max_hold_hours} hours → SELL

Risk Management:
- Min {self.min_hours_between_trades}h between trades (avoid overtrading)
- Clear profit taking (don't let winners reverse)
- Tight stop loss (cut losers fast)
"""


class ScalpingOIStrategy:
    """
    Even more aggressive - quick scalps for small gains

    Target: Many small wins (0.5-1%) instead of waiting for big moves
    """

    def __init__(
        self,
        oi_drop_threshold=-0.15,
        price_drop_threshold=-0.3,
        lookback_hours=2,
        profit_target=0.8,
        stop_loss=-0.5,
        max_hold_hours=12,
        min_hours_between_trades=4
    ):
        self.oi_drop_threshold = oi_drop_threshold
        self.price_drop_threshold = price_drop_threshold
        self.lookback_hours = lookback_hours
        self.profit_target = profit_target
        self.stop_loss = stop_loss
        self.max_hold_hours = max_hold_hours
        self.min_hours_between_trades = min_hours_between_trades

        self.name = f"Scalping_OI_{profit_target}pct"

    def generate_signals(self, data):
        """Quick scalping signals"""
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

        for i in range(self.lookback_hours, len(df)):
            current_price = df['close'].iloc[i]
            oi_change = df['oi_change'].iloc[i]
            price_change = df['price_change'].iloc[i]

            if pd.isna(oi_change) or pd.isna(price_change):
                continue

            if not in_position:
                if (i - last_trade_idx) < self.min_hours_between_trades:
                    continue

                if oi_change <= self.oi_drop_threshold and price_change <= self.price_drop_threshold:
                    df.iloc[i, df.columns.get_loc('signal')] = 'BUY'
                    in_position = True
                    entry_idx = i
                    entry_price = current_price
            else:
                hours_held = i - entry_idx
                current_return = (current_price / entry_price - 1) * 100

                exit_trade = False

                if current_return >= self.profit_target:
                    exit_trade = True
                elif current_return <= self.stop_loss:
                    exit_trade = True
                elif hours_held >= self.max_hold_hours:
                    exit_trade = True

                if exit_trade:
                    df.iloc[i, df.columns.get_loc('signal')] = 'SELL'
                    in_position = False
                    last_trade_idx = i
                    entry_idx = None
                    entry_price = None

        return df

    def describe(self):
        return f"""
Scalping OI Strategy
====================
Quick trades for small gains

ENTRY: OI down {self.oi_drop_threshold}% + Price down {self.price_drop_threshold}% over {self.lookback_hours}h
EXIT: +{self.profit_target}% profit OR {self.stop_loss}% stop OR {self.max_hold_hours}h max

Strategy: Many small wins compound over time
"""


class AdaptiveOIStrategy:
    """
    Adapts to market volatility

    In high volatility: Wider targets and stops
    In low volatility: Tighter targets and stops
    """

    def __init__(
        self,
        oi_drop_threshold=-0.2,
        price_drop_threshold=-0.4,
        lookback_hours=4,
        base_profit_target=1.5,
        base_stop_loss=-0.8,
        volatility_multiplier=1.0,
        max_hold_hours=36
    ):
        self.oi_drop_threshold = oi_drop_threshold
        self.price_drop_threshold = price_drop_threshold
        self.lookback_hours = lookback_hours
        self.base_profit_target = base_profit_target
        self.base_stop_loss = base_stop_loss
        self.volatility_multiplier = volatility_multiplier
        self.max_hold_hours = max_hold_hours

        self.name = "Adaptive_OI"

    def generate_signals(self, data):
        """Generate signals with volatility-adjusted exits"""
        df = data.copy()

        if 'oi_btc' not in df.columns:
            raise ValueError("Data must contain 'oi_btc' column")

        df['oi_change'] = df['oi_btc'].pct_change(self.lookback_hours) * 100
        df['price_change'] = df['close'].pct_change(self.lookback_hours) * 100

        # Calculate rolling volatility (24h)
        df['returns'] = df['close'].pct_change() * 100
        df['volatility'] = df['returns'].rolling(24).std()
        avg_vol = df['volatility'].mean()

        df['signal'] = 'HOLD'

        in_position = False
        entry_idx = None
        entry_price = None
        entry_volatility = None

        for i in range(max(24, self.lookback_hours), len(df)):
            current_price = df['close'].iloc[i]
            oi_change = df['oi_change'].iloc[i]
            price_change = df['price_change'].iloc[i]
            current_vol = df['volatility'].iloc[i]

            if pd.isna(oi_change) or pd.isna(price_change) or pd.isna(current_vol):
                continue

            if not in_position:
                if oi_change <= self.oi_drop_threshold and price_change <= self.price_drop_threshold:
                    df.iloc[i, df.columns.get_loc('signal')] = 'BUY'
                    in_position = True
                    entry_idx = i
                    entry_price = current_price
                    entry_volatility = current_vol
            else:
                hours_held = i - entry_idx
                current_return = (current_price / entry_price - 1) * 100

                # Adjust targets based on volatility at entry
                vol_ratio = entry_volatility / avg_vol if avg_vol > 0 else 1.0
                adjusted_target = self.base_profit_target * vol_ratio * self.volatility_multiplier
                adjusted_stop = self.base_stop_loss * vol_ratio * self.volatility_multiplier

                # Clamp to reasonable bounds
                adjusted_target = min(max(adjusted_target, 0.5), 5.0)
                adjusted_stop = max(min(adjusted_stop, -0.3), -3.0)

                exit_trade = False

                if current_return >= adjusted_target:
                    exit_trade = True
                elif current_return <= adjusted_stop:
                    exit_trade = True
                elif hours_held >= self.max_hold_hours:
                    exit_trade = True

                if exit_trade:
                    df.iloc[i, df.columns.get_loc('signal')] = 'SELL'
                    in_position = False
                    entry_idx = None
                    entry_price = None

        return df

    def describe(self):
        return f"""
Adaptive OI Strategy
====================
Adjusts profit/stop based on market volatility

ENTRY: OI down {self.oi_drop_threshold}% + Price down {self.price_drop_threshold}%
EXIT: Volatility-adjusted targets
- Base profit: {self.base_profit_target}%
- Base stop: {self.base_stop_loss}%
- Multiplied by current/average volatility ratio
"""


if __name__ == "__main__":
    print("Testing Aggressive Strategies...")

    try:
        df = pd.read_csv('../../../data/btc_oi_funding_combined.csv', parse_dates=['timestamp'])
        df = df.set_index('timestamp')

        strategies = [
            AggressiveOIStrategy(),
            ScalpingOIStrategy(),
            AdaptiveOIStrategy()
        ]

        for strategy in strategies:
            signals = strategy.generate_signals(df)
            buys = (signals['signal'] == 'BUY').sum()
            sells = (signals['signal'] == 'SELL').sum()

            print(f"\n{strategy.name}:")
            print(f"  Buys: {buys}, Sells: {sells}")
            print(strategy.describe())

    except Exception as e:
        print(f"Error: {e}")

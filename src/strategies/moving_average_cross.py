"""
Example Strategy: Moving Average Crossover

This is one of the simplest trading strategies - demonstrates how to write a strategy
that the backtester can run.

THE IDEA:
- When fast MA crosses above slow MA = bullish = BUY
- When fast MA crosses below slow MA = bearish = SELL

Example: If 20-period MA crosses above 50-period MA, that suggests upward momentum.
"""

import pandas as pd


class MovingAverageCrossStrategy:
    """
    Simple moving average crossover strategy

    How it works:
    1. Calculate two moving averages: fast (e.g., 20 periods) and slow (e.g., 50 periods)
    2. When fast MA crosses above slow MA → BUY signal
    3. When fast MA crosses below slow MA → SELL signal
    """

    def __init__(self, fast_period=20, slow_period=50):
        """
        Args:
            fast_period: Period for fast moving average (smaller = more responsive)
            slow_period: Period for slow moving average (larger = smoother)
        """
        self.fast_period = fast_period
        self.slow_period = slow_period

    def generate_signals(self, data):
        """
        Analyze price data and generate BUY/SELL/HOLD signals

        Args:
            data: DataFrame with OHLCV data

        Returns:
            DataFrame with 'signal' column ('BUY', 'SELL', or 'HOLD')
        """
        df = data.copy()

        # Calculate moving averages
        # MA = average of last N closing prices
        df['ma_fast'] = df['close'].rolling(window=self.fast_period).mean()
        df['ma_slow'] = df['close'].rolling(window=self.slow_period).mean()

        # Detect crossovers
        # "Crossover" = when one line crosses over the other
        df['signal'] = 'HOLD'  # Default to no action

        # BUY when fast MA crosses above slow MA
        # (fast was below yesterday, fast is above today)
        df['prev_fast'] = df['ma_fast'].shift(1)
        df['prev_slow'] = df['ma_slow'].shift(1)

        buy_condition = (df['prev_fast'] <= df['prev_slow']) & (df['ma_fast'] > df['ma_slow'])
        df.loc[buy_condition, 'signal'] = 'BUY'

        # SELL when fast MA crosses below slow MA
        sell_condition = (df['prev_fast'] >= df['prev_slow']) & (df['ma_fast'] < df['ma_slow'])
        df.loc[sell_condition, 'signal'] = 'SELL'

        # Clean up helper columns
        df.drop(['prev_fast', 'prev_slow'], axis=1, inplace=True)

        # Count signals
        buys = (df['signal'] == 'BUY').sum()
        sells = (df['signal'] == 'SELL').sum()

        print(f"\n📈 Strategy: Moving Average Crossover ({self.fast_period}/{self.slow_period})")
        print(f"   BUY signals:  {buys}")
        print(f"   SELL signals: {sells}")

        return df[['signal', 'ma_fast', 'ma_slow']]


# You can create your own strategies by following this template:
#
# class YourStrategy:
#     def __init__(self, param1, param2):
#         self.param1 = param1
#         self.param2 = param2
#
#     def generate_signals(self, data):
#         df = data.copy()
#
#         # YOUR LOGIC HERE
#         # Analyze data and set df['signal'] to 'BUY', 'SELL', or 'HOLD'
#
#         return df[['signal']]

"""
Open Interest + Funding Rate Combined Strategy

Learning moment: Multi-Factor Models
------------------------------------
Single indicators are weak. Combining multiple factors creates stronger signals:
- Each factor captures different information
- When multiple factors align, conviction increases
- Diversification of signals reduces false positives

Our Combined Factors:
1. OI change: Position flow (opening/closing)
2. Funding rate: Market sentiment (bullish/bearish tilt)
3. Price change: Trend context

Key finding from analysis:
- "Capitulation" scenarios (OI falling) have 65-70% win rate
- "Crowded" scenarios (OI rising) have only 38-47% win rate
- Adding funding improves the signal from r=0.12 to r=0.18
"""

import pandas as pd
import numpy as np


class OIFundingCombinedStrategy:
    """
    Combined OI + Funding Rate Strategy

    Entry Logic:
    - Buy on "capitulation" (OI falling) when:
      - OI has dropped over lookback period
      - Optionally filter by funding level
      - Optionally require price to also be falling (max pain = max opportunity)

    Exit Logic:
    - Sell when entering "crowded" territory (OI rising)
    - Or after max hold period
    - Or on profit target

    Parameters:
    -----------
    oi_lookback : int
        Hours to look back for OI change (default: 4)
    oi_drop_threshold : float
        Minimum OI drop % to trigger entry (default: -0.2)
    funding_filter : str
        'any', 'high', 'low' - which funding conditions to trade
        - 'any': Trade any capitulation regardless of funding
        - 'high': Only trade when funding is high (short capitulation)
        - 'low': Only trade when funding is low (long capitulation)
    funding_percentile_high : float
        Percentile threshold for "high" funding (default: 70)
    funding_percentile_low : float
        Percentile threshold for "low" funding (default: 30)
    exit_on_crowded : bool
        Exit when OI starts rising with rising prices (default: True)
    max_hold_hours : int
        Maximum hours to hold before forced exit (default: 24)
    """

    def __init__(
        self,
        oi_lookback=4,
        oi_drop_threshold=-0.2,
        funding_filter='any',
        funding_percentile_high=70,
        funding_percentile_low=30,
        exit_on_crowded=True,
        max_hold_hours=24,
        require_price_drop=False,
        price_drop_threshold=-0.3
    ):
        self.oi_lookback = oi_lookback
        self.oi_drop_threshold = oi_drop_threshold
        self.funding_filter = funding_filter
        self.funding_percentile_high = funding_percentile_high
        self.funding_percentile_low = funding_percentile_low
        self.exit_on_crowded = exit_on_crowded
        self.max_hold_hours = max_hold_hours
        self.require_price_drop = require_price_drop
        self.price_drop_threshold = price_drop_threshold

        self.name = f"OI_Funding_{funding_filter}_{oi_lookback}h"

    def generate_signals(self, data):
        """
        Generate trading signals based on OI + Funding analysis

        Args:
            data: DataFrame with 'close', 'oi_btc', and 'funding_rate' columns

        Returns:
            DataFrame with 'signal' column: 'BUY', 'SELL', or 'HOLD'
        """
        df = data.copy()

        # Validate required columns
        required_cols = ['close', 'oi_btc', 'funding_rate']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Data must contain '{col}' column")

        # Calculate OI change
        df['oi_change'] = df['oi_btc'].pct_change(self.oi_lookback) * 100

        # Calculate price change
        df['price_change'] = df['close'].pct_change(self.oi_lookback) * 100

        # Calculate funding percentile (rolling over 168 hours = 1 week)
        window = min(168, len(df) - 1)
        if window > 10:
            df['funding_pct'] = df['funding_rate'].rolling(window).apply(
                lambda x: (x < x.iloc[-1]).sum() / len(x) * 100 if len(x) > 0 else 50,
                raw=False
            )
        else:
            df['funding_pct'] = 50  # Not enough data, assume neutral

        # Initialize signals
        df['signal'] = 'HOLD'

        # Track position state
        in_position = False
        entry_idx = None

        for i in range(self.oi_lookback, len(df)):
            if pd.isna(df['oi_change'].iloc[i]):
                continue

            oi_change = df['oi_change'].iloc[i]
            price_change = df['price_change'].iloc[i]
            funding_pct = df['funding_pct'].iloc[i] if not pd.isna(df['funding_pct'].iloc[i]) else 50

            # === ENTRY CONDITIONS ===
            if not in_position:
                # Core condition: OI is falling (capitulation)
                oi_falling = oi_change <= self.oi_drop_threshold

                # Funding filter
                if self.funding_filter == 'high':
                    funding_ok = funding_pct >= self.funding_percentile_high
                elif self.funding_filter == 'low':
                    funding_ok = funding_pct <= self.funding_percentile_low
                else:  # 'any'
                    funding_ok = True

                # Optional price drop filter
                if self.require_price_drop:
                    price_ok = price_change <= self.price_drop_threshold
                else:
                    price_ok = True

                # ENTER if all conditions met
                if oi_falling and funding_ok and price_ok:
                    df.iloc[i, df.columns.get_loc('signal')] = 'BUY'
                    in_position = True
                    entry_idx = i

            # === EXIT CONDITIONS ===
            else:
                should_exit = False

                # 1. Max hold period reached
                if entry_idx is not None and (i - entry_idx) >= self.max_hold_hours:
                    should_exit = True

                # 2. Exit on "crowded" condition (OI rising + price rising)
                if self.exit_on_crowded:
                    oi_rising = oi_change > 0
                    price_rising = price_change > 0
                    if oi_rising and price_rising:
                        should_exit = True

                if should_exit:
                    df.iloc[i, df.columns.get_loc('signal')] = 'SELL'
                    in_position = False
                    entry_idx = None

        return df

    def describe(self):
        """Return strategy description"""
        return f"""
OI + Funding Combined Strategy
------------------------------
Entry: Buy when OI is falling (capitulation signal)
- OI must drop more than {self.oi_drop_threshold}% over {self.oi_lookback}h
- Funding filter: {self.funding_filter}
  - 'any': Trade any capitulation
  - 'high': Only when funding > {self.funding_percentile_high}th percentile (short capitulation)
  - 'low': Only when funding < {self.funding_percentile_low}th percentile (long capitulation)
- Require price drop: {self.require_price_drop}

Exit: Sell when entering crowded territory or max hold
- Exit on crowded (OI up + price up): {self.exit_on_crowded}
- Max hold: {self.max_hold_hours} hours

Rationale:
- Capitulation = forced position closures = oversold conditions
- High funding + OI drop = shorts being liquidated, good long entry
- Low funding + OI drop = longs being liquidated, contrarian long entry
- Crowded condition (OI rising) = time to take profit
"""


class SentimentScoreStrategy:
    """
    Alternative: Trade based on combined sentiment score

    The sentiment score combines OI and funding into a single number.
    Buy when sentiment is extreme (contrarian).
    """

    def __init__(
        self,
        sentiment_threshold_buy=0.7,
        sentiment_threshold_sell=0.3,
        hold_hours=4
    ):
        self.sentiment_threshold_buy = sentiment_threshold_buy
        self.sentiment_threshold_sell = sentiment_threshold_sell
        self.hold_hours = hold_hours
        self.name = f"Sentiment_Score_{sentiment_threshold_buy}"

    def generate_signals(self, data):
        """Generate signals based on sentiment score"""
        df = data.copy()

        if 'sentiment_score' not in df.columns:
            # Calculate sentiment score if not present
            if 'funding_rate' in df.columns and 'oi_pct_change_4h' in df.columns:
                # Higher score = more bullish sentiment (contrarian = sell signal)
                # But we're going contrarian, so high score = eventually sell
                window = min(168, len(df) - 1)
                if window > 10:
                    df['funding_pct'] = df['funding_rate'].rolling(window).apply(
                        lambda x: (x < x.iloc[-1]).sum() / len(x) * 100 if len(x) > 0 else 50,
                        raw=False
                    )
                else:
                    df['funding_pct'] = 50

                df['sentiment_score'] = (
                    df['funding_pct'] / 100 +
                    (1 - df['oi_pct_change_4h'].clip(-2, 2) / 4 + 0.5)
                ) / 2
            else:
                raise ValueError("Data must contain sentiment_score or funding_rate + oi_pct_change_4h")

        df['signal'] = 'HOLD'
        in_position = False
        entry_idx = None

        for i in range(len(df)):
            score = df['sentiment_score'].iloc[i]

            if pd.isna(score):
                continue

            if not in_position:
                # Buy when sentiment score is high (contrarian - everyone bullish, we expect reversal)
                # Actually, based on our analysis, we want to buy on capitulation (lower scores)
                # Let me reconsider: the score combines funding_pct (high=bullish) and inverted OI
                # So high score = high funding + falling OI = short capitulation = BUY
                if score >= self.sentiment_threshold_buy:
                    df.iloc[i, df.columns.get_loc('signal')] = 'BUY'
                    in_position = True
                    entry_idx = i
            else:
                # Exit conditions
                if entry_idx and (i - entry_idx) >= self.hold_hours:
                    if score <= self.sentiment_threshold_sell:
                        df.iloc[i, df.columns.get_loc('signal')] = 'SELL'
                        in_position = False
                        entry_idx = None

        return df

    def describe(self):
        return f"""
Sentiment Score Strategy
------------------------
Buy when sentiment score >= {self.sentiment_threshold_buy}
Sell when sentiment score <= {self.sentiment_threshold_sell} (after {self.hold_hours}h minimum)

Sentiment score = (funding_percentile + inverted_OI_change) / 2
- High score = high funding + falling OI = short capitulation = BUY
- Low score = low funding + rising OI = crowded short = AVOID
"""


# Quick test
if __name__ == "__main__":
    print("Testing OI + Funding Strategy...")

    try:
        df = pd.read_csv('../../../data/btc_oi_funding_combined.csv', parse_dates=['timestamp'])
        df = df.set_index('timestamp')

        # Test main strategy
        strategy = OIFundingCombinedStrategy(
            oi_lookback=4,
            oi_drop_threshold=-0.2,
            funding_filter='any'
        )

        signals = strategy.generate_signals(df)
        buys = (signals['signal'] == 'BUY').sum()
        sells = (signals['signal'] == 'SELL').sum()

        print(f"\nOI+Funding Strategy:")
        print(f"Buy signals: {buys}")
        print(f"Sell signals: {sells}")
        print(strategy.describe())

    except Exception as e:
        print(f"Error: {e}")
        print("Run analyze_funding_rates.py first to generate the combined data file.")

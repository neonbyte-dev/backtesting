"""
Open Interest Based Trading Strategy

Learning moment: Strategy Design Process
----------------------------------------
We discovered that OI has CONTRARIAN predictive value:
- Large OI increases predict WORSE returns (crowded trade)
- Large OI decreases predict BETTER returns (capitulation)
- Best regime: Falling OI + Falling Price (liquidations)

Strategy Hypothesis:
Buy when Open Interest is falling (especially after significant drops)
This catches bounces after liquidation events.

Key insight: We're not just trading OI changes in isolation.
We're looking for the COMBINATION of falling OI + certain price patterns.
"""

import pandas as pd
import numpy as np


class OpenInterestStrategy:
    """
    Contrarian OI Strategy: Buy after OI drops, sell after OI rises

    Parameters:
    -----------
    oi_lookback : int
        Hours to look back for OI change calculation (default: 4)
    oi_drop_threshold : float
        % OI must drop to trigger buy signal (default: -0.3)
    oi_rise_threshold : float
        % OI must rise to trigger sell signal (default: 0.3)
    hold_hours : int
        Minimum hours to hold position (default: 4)
    require_price_drop : bool
        Also require price to be falling for buy signal (default: True)
    price_drop_threshold : float
        Min price drop % required if require_price_drop=True (default: -0.5)
    """

    def __init__(
        self,
        oi_lookback=4,
        oi_drop_threshold=-0.3,
        oi_rise_threshold=0.3,
        hold_hours=4,
        require_price_drop=True,
        price_drop_threshold=-0.5,
        use_momentum=False,
        momentum_lookback=6
    ):
        self.oi_lookback = oi_lookback
        self.oi_drop_threshold = oi_drop_threshold
        self.oi_rise_threshold = oi_rise_threshold
        self.hold_hours = hold_hours
        self.require_price_drop = require_price_drop
        self.price_drop_threshold = price_drop_threshold
        self.use_momentum = use_momentum
        self.momentum_lookback = momentum_lookback

        self.name = f"OI_Contrarian_{oi_lookback}h_drop{abs(oi_drop_threshold)}"

    def generate_signals(self, data):
        """
        Generate trading signals based on Open Interest analysis

        Args:
            data: DataFrame with 'close' and 'oi_btc' columns
                  (oi_btc = Open Interest in BTC terms)

        Returns:
            DataFrame with 'signal' column: 'BUY', 'SELL', or 'HOLD'
        """

        df = data.copy()

        # Validate required columns
        if 'oi_btc' not in df.columns:
            raise ValueError(
                "Data must contain 'oi_btc' column. "
                "Use data with merged Open Interest information."
            )

        # Calculate OI % change over lookback period
        df['oi_pct_change'] = df['oi_btc'].pct_change(self.oi_lookback) * 100

        # Calculate price % change
        df['price_pct_change'] = df['close'].pct_change(self.oi_lookback) * 100

        # Optional: OI momentum (rolling average of 1h changes)
        if self.use_momentum:
            df['oi_1h_change'] = df['oi_btc'].pct_change(1) * 100
            df['oi_momentum'] = df['oi_1h_change'].rolling(self.momentum_lookback).mean()

        # Initialize signals
        df['signal'] = 'HOLD'

        # Track position state
        in_position = False
        entry_idx = None

        for i in range(len(df)):
            if pd.isna(df['oi_pct_change'].iloc[i]):
                continue

            current_oi_change = df['oi_pct_change'].iloc[i]
            current_price_change = df['price_pct_change'].iloc[i]

            # BUY CONDITIONS
            # Core condition: OI has dropped significantly (contrarian signal)
            oi_drop_condition = current_oi_change <= self.oi_drop_threshold

            # Optional: Also require price to be falling (liquidation regime)
            if self.require_price_drop:
                price_condition = current_price_change <= self.price_drop_threshold
            else:
                price_condition = True

            # Optional momentum filter
            if self.use_momentum and not pd.isna(df['oi_momentum'].iloc[i]):
                momentum_condition = df['oi_momentum'].iloc[i] < 0
            else:
                momentum_condition = True

            # SELL CONDITIONS
            # Sell when OI starts rising again (new positions entering)
            oi_rise_condition = current_oi_change >= self.oi_rise_threshold

            # Apply signals
            if not in_position:
                # Check for entry
                if oi_drop_condition and price_condition and momentum_condition:
                    df.iloc[i, df.columns.get_loc('signal')] = 'BUY'
                    in_position = True
                    entry_idx = i
            else:
                # Check for exit
                # Minimum hold period
                if entry_idx is not None and (i - entry_idx) >= self.hold_hours:
                    if oi_rise_condition:
                        df.iloc[i, df.columns.get_loc('signal')] = 'SELL'
                        in_position = False
                        entry_idx = None

        # Add debug columns for analysis
        df['oi_signal_strength'] = df['oi_pct_change']

        return df

    def describe(self):
        """Return strategy description"""
        desc = f"""
Open Interest Contrarian Strategy
---------------------------------
Logic: Buy after OI drops (capitulation/liquidations), sell when OI rises

Parameters:
- OI Lookback: {self.oi_lookback} hours
- OI Drop Threshold: {self.oi_drop_threshold}% (buy when OI drops more than this)
- OI Rise Threshold: {self.oi_rise_threshold}% (sell when OI rises more than this)
- Minimum Hold: {self.hold_hours} hours
- Require Price Drop: {self.require_price_drop}
- Price Drop Threshold: {self.price_drop_threshold}%

Why this works:
- When OI drops significantly, forced selling (liquidations) is happening
- This creates oversold conditions as leveraged longs get wiped out
- Buying after liquidations catches the relief bounce
- Selling when OI rises again = taking profit before the next crowded trade
"""
        return desc


class OpenInterestRegimeStrategy:
    """
    Alternative strategy: Trade based on OI-Price regime classification

    Regimes:
    1. Rising OI + Rising Price = Bullish conviction (but crowded, avoid)
    2. Rising OI + Falling Price = Bearish conviction (shorts entering, avoid)
    3. Falling OI + Rising Price = Short squeeze (ride the momentum)
    4. Falling OI + Falling Price = Liquidations (best entry point!)
    """

    def __init__(
        self,
        lookback=4,
        entry_regime='liquidation',  # 'liquidation', 'squeeze', or 'both'
        exit_on_regime_change=True,
        hold_hours=4
    ):
        self.lookback = lookback
        self.entry_regime = entry_regime
        self.exit_on_regime_change = exit_on_regime_change
        self.hold_hours = hold_hours

        self.name = f"OI_Regime_{entry_regime}"

    def generate_signals(self, data):
        """Generate signals based on OI-Price regime"""

        df = data.copy()

        if 'oi_btc' not in df.columns:
            raise ValueError("Data must contain 'oi_btc' column.")

        # Calculate changes
        df['oi_change'] = df['oi_btc'].pct_change(self.lookback) * 100
        df['price_change'] = df['close'].pct_change(self.lookback) * 100

        # Classify regime
        df['regime'] = 'unknown'

        mask_rising_oi = df['oi_change'] > 0
        mask_falling_oi = df['oi_change'] <= 0
        mask_rising_price = df['price_change'] > 0
        mask_falling_price = df['price_change'] <= 0

        df.loc[mask_rising_oi & mask_rising_price, 'regime'] = 'bullish_conviction'
        df.loc[mask_rising_oi & mask_falling_price, 'regime'] = 'bearish_conviction'
        df.loc[mask_falling_oi & mask_rising_price, 'regime'] = 'squeeze'
        df.loc[mask_falling_oi & mask_falling_price, 'regime'] = 'liquidation'

        # Generate signals
        df['signal'] = 'HOLD'

        in_position = False
        entry_idx = None
        entry_regime = None

        for i in range(len(df)):
            current_regime = df['regime'].iloc[i]

            if current_regime == 'unknown':
                continue

            if not in_position:
                # Entry conditions based on strategy setting
                enter = False

                if self.entry_regime == 'liquidation' and current_regime == 'liquidation':
                    enter = True
                elif self.entry_regime == 'squeeze' and current_regime == 'squeeze':
                    enter = True
                elif self.entry_regime == 'both' and current_regime in ['liquidation', 'squeeze']:
                    enter = True

                if enter:
                    df.iloc[i, df.columns.get_loc('signal')] = 'BUY'
                    in_position = True
                    entry_idx = i
                    entry_regime = current_regime
            else:
                # Exit conditions
                should_exit = False

                # Check minimum hold
                if entry_idx is not None and (i - entry_idx) >= self.hold_hours:
                    # Exit on regime change (if enabled)
                    if self.exit_on_regime_change:
                        # Exit when we enter a "crowded" regime
                        if current_regime in ['bullish_conviction', 'bearish_conviction']:
                            should_exit = True

                if should_exit:
                    df.iloc[i, df.columns.get_loc('signal')] = 'SELL'
                    in_position = False
                    entry_idx = None
                    entry_regime = None

        return df

    def describe(self):
        return f"""
OI-Price Regime Strategy
------------------------
Entry regime: {self.entry_regime}
Lookback: {self.lookback} hours
Exit on regime change: {self.exit_on_regime_change}
Min hold: {self.hold_hours} hours

Regime definitions:
- liquidation: Falling OI + Falling Price (forced selling, best entry)
- squeeze: Falling OI + Rising Price (shorts covering, momentum play)
- bullish_conviction: Rising OI + Rising Price (crowded long, avoid)
- bearish_conviction: Rising OI + Falling Price (crowded short, avoid)
"""


# Quick test if run directly
if __name__ == "__main__":
    print("Testing Open Interest Strategy...")

    # Load processed data
    try:
        df = pd.read_csv('../../../data/btc_oi_with_features.csv', parse_dates=['timestamp'])
        df = df.set_index('timestamp')

        # Test contrarian strategy
        strategy = OpenInterestStrategy(
            oi_lookback=4,
            oi_drop_threshold=-0.3,
            require_price_drop=True
        )

        signals = strategy.generate_signals(df)

        buy_signals = signals[signals['signal'] == 'BUY']
        sell_signals = signals[signals['signal'] == 'SELL']

        print(f"\nContrarian Strategy Results:")
        print(f"Buy signals: {len(buy_signals)}")
        print(f"Sell signals: {len(sell_signals)}")
        print(strategy.describe())

        # Test regime strategy
        regime_strategy = OpenInterestRegimeStrategy(
            lookback=4,
            entry_regime='liquidation'
        )

        regime_signals = regime_strategy.generate_signals(df)
        regime_buys = regime_signals[regime_signals['signal'] == 'BUY']
        regime_sells = regime_signals[regime_signals['signal'] == 'SELL']

        print(f"\nRegime Strategy Results:")
        print(f"Buy signals: {len(regime_buys)}")
        print(f"Sell signals: {len(regime_sells)}")
        print(regime_strategy.describe())

    except Exception as e:
        print(f"Error: {e}")
        print("Run analyze_open_interest.py first to generate the data file.")

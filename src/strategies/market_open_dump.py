"""
Strategy: Market Open Dump & Recovery

THE HYPOTHESIS (from the tweet):
Bitcoin consistently dumps at 10 AM EST when US stock market opens,
then recovers over the next few hours. This may be due to large players
(possibly Jane Street) executing high-frequency trades to accumulate BTC.

THE STRATEGY:
1. Detect when market opens (10 AM EST / 9:30 AM EST depending on interpretation)
2. Buy when price dumps
3. Sell when price recovers (or at end of day)

This strategy class is flexible and can test different variations:
- Entry timing: immediate, wait for dump, buy at low
- Exit timing: end of day, fixed hours, profit target
- Dump threshold: what counts as a "dump"
"""

import pandas as pd
import numpy as np
from datetime import time


class MarketOpenDumpStrategy:
    """
    Tests the hypothesis that BTC dumps at US market open and recovers

    Parameters:
    -----------
    entry_mode : str
        How to enter the trade:
        - 'immediate': Buy right at 10 AM EST
        - 'on_dump': Buy when price drops X% from pre-market
        - 'intraday_low': Buy at the lowest point 10-11 AM (hindsight, max potential)
        - 'end_of_dump': Buy at 3 PM EST (when dump typically finishes)

    exit_mode : str
        How to exit the trade:
        - 'eod': Sell at 4 PM EST (end of day)
        - 'fixed_hours': Sell after X hours
        - 'profit_target': Sell when profit reaches X%
        - 'trailing_stop_no_loss': Never sell for loss, use trailing stop once profitable
        - 'next_day_premarket': Sell next day at 9:30 AM EST (before next dump)

    dump_threshold_pct : float
        What % drop counts as a "dump" (for entry_mode='on_dump')
        Default: -1.0 (any 1%+ drop)

    exit_hours : int
        Hours to hold position (for exit_mode='fixed_hours')
        Default: 6

    profit_target_pct : float
        Profit % to exit at (for exit_mode='profit_target')
        Default: 0.5 (exit at +0.5%)

    trailing_stop_pct : float
        Trailing stop % (for exit_mode='trailing_stop_no_loss')
        Exit if price drops X% from highest point since entry
        Default: 1.5 (exit if drops 1.5% from peak)

    market_open_hour : int
        Hour when US market opens in EST (10 for BTC context)
        Default: 10 (based on tweet pattern of "10 AM dumps")
        Note: If entry_window_end is set, this becomes the window start

    entry_window_end : int or None
        End hour for entry window (e.g., 11 for 9:30-11:30 AM window)
        If None, only trades at market_open_hour
        If set, trades anytime between market_open_hour and entry_window_end
        Default: None

    dump_end_hour : int
        Hour when dump typically finishes (for entry_mode='end_of_dump')
        Default: 15 (3 PM EST)

    max_entry_price : float or None
        Maximum price to enter trades (price filter)
        If set, will not buy if price is above this level
        Default: None (no filter)

    timezone : str
        Timezone for market hours
        Default: 'America/New_York' (EST/EDT)
    """

    def __init__(
        self,
        entry_mode='on_dump',
        exit_mode='fixed_hours',
        dump_threshold_pct=-1.0,
        exit_hours=6,
        profit_target_pct=0.5,
        trailing_stop_pct=1.5,
        market_open_hour=10,
        entry_window_end=None,
        dump_end_hour=15,
        max_entry_price=None,
        timezone='America/New_York'
    ):
        self.entry_mode = entry_mode
        self.exit_mode = exit_mode
        self.dump_threshold_pct = dump_threshold_pct
        self.exit_hours = exit_hours
        self.profit_target_pct = profit_target_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.market_open_hour = market_open_hour
        self.entry_window_end = entry_window_end
        self.dump_end_hour = dump_end_hour
        self.max_entry_price = max_entry_price
        self.timezone = timezone

    def generate_signals(self, data):
        """
        Generate BUY/SELL signals based on market open dump pattern

        Args:
            data: DataFrame with OHLCV data and timezone-aware index

        Returns:
            DataFrame with 'signal' column
        """
        df = data.copy()

        # Ensure index is timezone-aware (convert to EST)
        if df.index.tz is None:
            # Assume UTC if no timezone info
            df.index = df.index.tz_localize('UTC')
        df.index = df.index.tz_convert(self.timezone)

        # Extract time components
        df['hour'] = df.index.hour
        df['date'] = df.index.date

        # Calculate price change from previous candle
        df['price_change_pct'] = df['close'].pct_change() * 100

        # Initialize signal column
        df['signal'] = 'HOLD'
        df['entry_price'] = np.nan
        df['exit_reason'] = ''

        # Track open positions
        in_position = False
        entry_price = 0
        entry_time = None
        peak_price = 0  # Track highest price for trailing stop

        # Walk through each row
        for i in range(len(df)):
            current_hour = df.iloc[i]['hour']
            current_price = df.iloc[i]['close']
            current_time = df.index[i]

            # === ENTRY LOGIC ===
            if not in_position:
                should_buy = False

                # Mode 1: Buy immediately at market open hour
                if self.entry_mode == 'immediate':
                    if current_hour == self.market_open_hour:
                        # Only buy once per day (first candle of that hour)
                        if i == 0 or df.iloc[i-1]['hour'] != self.market_open_hour:
                            should_buy = True

                # Mode 2: Buy when dump detected
                elif self.entry_mode == 'on_dump':
                    # Check if we're in the entry time window
                    in_entry_window = False
                    if self.entry_window_end is None:
                        # Single hour entry
                        in_entry_window = (current_hour == self.market_open_hour)
                    else:
                        # Time window entry (e.g., 9:30 AM - 11:30 AM)
                        # Use minute precision for 9:30 start
                        current_minute = df.index[i].minute
                        start_hour = self.market_open_hour
                        end_hour = self.entry_window_end

                        if current_hour == start_hour:
                            # First hour: only trigger after :30 (e.g., 9:30 onwards)
                            in_entry_window = (current_minute >= 30)
                        elif current_hour > start_hour and current_hour < end_hour:
                            # Middle hours: any time
                            in_entry_window = True
                        elif current_hour == end_hour:
                            # Last hour: only before :30 (e.g., until 11:30)
                            in_entry_window = (current_minute <= 30)

                    if in_entry_window:
                        # Check if price dropped below threshold
                        # Compare to 9:30 AM open (US market open)
                        market_open_price = None

                        # Find the 9:30 AM candle's open price
                        for j in range(max(0, i-40), i):  # Look back up to 40 candles
                            check_hour = df.iloc[j]['hour']
                            check_minute = df.index[j].minute
                            # Find 9:30 AM candle
                            if check_hour == 9 and check_minute == 30:
                                market_open_price = df.iloc[j]['open']
                                break

                        if market_open_price:
                            dump_pct = ((current_price - market_open_price) / market_open_price) * 100
                            if dump_pct <= self.dump_threshold_pct:
                                should_buy = True

                # Mode 3: Buy at intraday low (hindsight - shows max potential)
                elif self.entry_mode == 'intraday_low':
                    # At end of dump window (11 AM), look back and buy at lowest point
                    if current_hour == self.market_open_hour + 1:
                        if i == 0 or df.iloc[i-1]['hour'] != self.market_open_hour + 1:
                            # Find lowest price in previous hour
                            window_start = i - 1
                            while window_start >= 0 and df.iloc[window_start]['hour'] >= self.market_open_hour:
                                window_start -= 1

                            if window_start >= 0:
                                window = df.iloc[window_start+1:i+1]
                                lowest_idx = window['close'].idxmin()
                                # Mark that past candle as BUY
                                df.at[lowest_idx, 'signal'] = 'BUY'
                                entry_price = df.loc[lowest_idx, 'close']
                                entry_time = lowest_idx
                                peak_price = entry_price  # Initialize peak at entry
                                in_position = True
                                df.at[lowest_idx, 'entry_price'] = entry_price
                                continue

                # Mode 4: Buy at end of dump (3 PM EST)
                elif self.entry_mode == 'end_of_dump':
                    if current_hour == self.dump_end_hour:
                        # Only buy once per day (first candle of that hour)
                        if i == 0 or df.iloc[i-1]['hour'] != self.dump_end_hour:
                            should_buy = True

                # Apply price filter if set
                if should_buy and self.max_entry_price is not None:
                    if current_price > self.max_entry_price:
                        should_buy = False  # Skip entry if price too high

                if should_buy:
                    df.iloc[i, df.columns.get_loc('signal')] = 'BUY'
                    entry_price = current_price
                    entry_time = current_time
                    peak_price = current_price  # Initialize peak at entry
                    in_position = True
                    df.iloc[i, df.columns.get_loc('entry_price')] = entry_price

            # === EXIT LOGIC ===
            elif in_position:
                # Update peak price (for trailing stop)
                if current_price > peak_price:
                    peak_price = current_price

                should_sell = False
                exit_reason = ''

                # Mode 1: Exit at end of day (4 PM EST)
                if self.exit_mode == 'eod':
                    if current_hour >= 16:  # 4 PM or later
                        should_sell = True
                        exit_reason = 'eod'

                # Mode 2: Exit after fixed hours
                elif self.exit_mode == 'fixed_hours':
                    hours_held = (current_time - entry_time).total_seconds() / 3600
                    if hours_held >= self.exit_hours:
                        should_sell = True
                        exit_reason = f'{self.exit_hours}h_hold'

                # Mode 3: Exit at profit target
                elif self.exit_mode == 'profit_target':
                    profit_pct = ((current_price - entry_price) / entry_price) * 100
                    if profit_pct >= self.profit_target_pct:
                        should_sell = True
                        exit_reason = f'+{self.profit_target_pct}%'

                # Mode 4: Trailing stop with no loss
                elif self.exit_mode == 'trailing_stop_no_loss':
                    profit_pct = ((current_price - entry_price) / entry_price) * 100

                    # Only exit if we're profitable
                    if profit_pct > 0:
                        # Check if price dropped from peak
                        drawdown_from_peak = ((current_price - peak_price) / peak_price) * 100

                        if drawdown_from_peak <= -self.trailing_stop_pct:
                            should_sell = True
                            exit_reason = f'trail_stop_{self.trailing_stop_pct}%'
                    # If not profitable, hold (never sell for a loss)

                # Mode 5: Exit next day at premarket (9:30 AM EST)
                elif self.exit_mode == 'next_day_premarket':
                    current_minute = df.index[i].minute
                    entry_date = entry_time.date()
                    current_date = current_time.date()

                    # Check if we're on the next day at 9:30 AM
                    if current_date > entry_date and current_hour == 9 and current_minute == 30:
                        should_sell = True
                        exit_reason = 'next_day_930am'

                if should_sell:
                    df.iloc[i, df.columns.get_loc('signal')] = 'SELL'
                    df.iloc[i, df.columns.get_loc('exit_reason')] = exit_reason
                    in_position = False
                    entry_price = 0
                    entry_time = None
                    peak_price = 0

        # Count signals
        buys = (df['signal'] == 'BUY').sum()
        sells = (df['signal'] == 'SELL').sum()

        # Print strategy configuration
        print(f"\n📈 Strategy: Market Open Dump & Recovery")
        print(f"   Entry: {self.entry_mode}")
        if self.entry_window_end is not None:
            print(f"   Entry window: {self.market_open_hour}:30 AM - {self.entry_window_end}:30 AM EST")
        if self.entry_mode == 'end_of_dump':
            print(f"   Entry time: {self.dump_end_hour}:00 PM EST (end of dump period)")
        print(f"   Exit: {self.exit_mode}")
        if self.entry_mode == 'on_dump':
            print(f"   Dump threshold: {self.dump_threshold_pct}% from 9:30 AM open")
        if self.exit_mode == 'fixed_hours':
            print(f"   Hold time: {self.exit_hours} hours")
        if self.exit_mode == 'profit_target':
            print(f"   Profit target: +{self.profit_target_pct}%")
        if self.exit_mode == 'trailing_stop_no_loss':
            print(f"   Trailing stop: {self.trailing_stop_pct}% (never sell for a loss)")
        if self.exit_mode == 'next_day_premarket':
            print(f"   Exit time: Next day 9:30 AM EST (before next dump)")
        print(f"   BUY signals:  {buys}")
        print(f"   SELL signals: {sells}")

        return df[['signal']]

    def __str__(self):
        """String representation for logging"""
        return f"MarketOpenDump(entry={self.entry_mode}, exit={self.exit_mode})"

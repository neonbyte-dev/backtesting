"""
Strategy: CME Sunday Open (Brandon Hong's Strategy)

THE HYPOTHESIS (from Brandon Hong's Twitter video):
Every Sunday at 6 PM Eastern Time, the CME (Chicago Mercantile Exchange) opens
for futures trading. This is when institutional players can execute large orders
on Bitcoin, gold, silver, and other commodities.

The direction of the first candle(s) after CME opens reveals institutional intent:
- If price GAPS UP → institutions are buying → GO LONG
- If price GAPS DOWN → institutions are selling → GO SHORT

THE STRATEGY:
1. Be online at Sunday 6 PM ET (18:00)
2. Watch the opening candle direction
3. Enter in that direction
4. Stop loss: Below/above the opening candle
5. Take profits as the trend continues

LEARNING MOMENT: Why Sunday 6 PM?
==================================
CME futures markets close Friday afternoon and reopen Sunday evening.
Over the weekend, news and events accumulate. When CME opens, institutional
traders react to all that accumulated information at once, creating
directional moves that can persist.

This is similar to "gap trading" in stocks, where overnight gaps often
indicate strong directional bias.
"""

import pandas as pd
import numpy as np
from datetime import time, timedelta


class CMESundayOpenStrategy:
    """
    Trade the CME Sunday open based on opening candle direction

    Parameters:
    -----------
    direction_mode : str
        How to determine trade direction:
        - 'first_candle': Use direction of first candle after 6 PM
        - 'first_hour': Use net direction of first hour (more confirmation)
        - 'gap': Compare 6 PM price to Friday close

    trade_direction : str
        Which directions to trade:
        - 'both': Trade both long and short (full strategy)
        - 'long_only': Only take long signals
        - 'short_only': Only take short signals

    exit_mode : str
        How to exit trades:
        - 'fixed_hours': Exit after X hours
        - 'next_cme_open': Hold until next Sunday 6 PM
        - 'stop_and_target': Use stop loss and take profit levels
        - 'friday_close': Exit Friday before weekend

    hold_hours : int
        Hours to hold position (for exit_mode='fixed_hours')
        Default: 24 (hold for one day)

    stop_loss_pct : float
        Stop loss percentage (for exit_mode='stop_and_target')
        Default: 2.0 (2% stop loss)

    take_profit_pct : float
        Take profit percentage (for exit_mode='stop_and_target')
        Default: 4.0 (4% take profit, 2:1 reward/risk)

    min_move_pct : float
        Minimum % move to trigger entry (filter weak signals)
        Default: 0.0 (any move triggers)

    timezone : str
        Timezone for CME open
        Default: 'America/New_York'
    """

    def __init__(
        self,
        direction_mode='first_candle',
        trade_direction='both',
        exit_mode='fixed_hours',
        hold_hours=24,
        stop_loss_pct=2.0,
        take_profit_pct=4.0,
        min_move_pct=0.0,
        timezone='America/New_York'
    ):
        self.direction_mode = direction_mode
        self.trade_direction = trade_direction
        self.exit_mode = exit_mode
        self.hold_hours = hold_hours
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.min_move_pct = min_move_pct
        self.timezone = timezone

    def generate_signals(self, data):
        """
        Generate trading signals based on CME Sunday open

        Args:
            data: DataFrame with OHLCV data

        Returns:
            DataFrame with 'signal' column
        """
        df = data.copy()

        # Ensure timezone-aware index (convert to ET)
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')
        df.index = df.index.tz_convert(self.timezone)

        # Extract time components
        df['hour'] = df.index.hour
        df['day_of_week'] = df.index.dayofweek  # Monday=0, Sunday=6
        df['date'] = df.index.date

        # Calculate candle direction
        df['candle_direction'] = np.where(df['close'] > df['open'], 'bullish',
                                          np.where(df['close'] < df['open'], 'bearish', 'neutral'))
        df['candle_change_pct'] = ((df['close'] - df['open']) / df['open']) * 100

        # Initialize signals
        df['signal'] = 'HOLD'

        # Track position state
        in_position = False
        position_direction = 'flat'  # 'long', 'short', or 'flat'
        entry_time = None
        entry_price = 0
        stop_loss = 0
        take_profit = 0

        # Find CME opens (Sunday 6 PM ET = Sunday 18:00)
        # Note: In pandas, Sunday = 6
        for i in range(len(df)):
            current_time = df.index[i]
            current_hour = df.iloc[i]['hour']
            current_dow = df.iloc[i]['day_of_week']
            current_price = df.iloc[i]['close']
            current_open = df.iloc[i]['open']
            current_high = df.iloc[i]['high']
            current_low = df.iloc[i]['low']

            # === EXIT LOGIC (check first before entry) ===
            if in_position:
                should_exit = False
                exit_signal = 'CLOSE'

                # Fixed hours exit
                if self.exit_mode == 'fixed_hours':
                    if entry_time is not None:
                        hours_held = (current_time - entry_time).total_seconds() / 3600
                        if hours_held >= self.hold_hours:
                            should_exit = True

                # Friday close exit
                elif self.exit_mode == 'friday_close':
                    # Friday = 4, exit around 4-5 PM
                    if current_dow == 4 and current_hour >= 16:
                        should_exit = True

                # Next CME open exit
                elif self.exit_mode == 'next_cme_open':
                    # Exit right before next Sunday 6 PM
                    if current_dow == 6 and current_hour == 17:
                        should_exit = True

                # Stop loss / Take profit exit
                elif self.exit_mode == 'stop_and_target':
                    if position_direction == 'long':
                        # Check stop loss (price went below our stop)
                        if current_low <= stop_loss:
                            should_exit = True
                        # Check take profit
                        elif current_high >= take_profit:
                            should_exit = True
                    elif position_direction == 'short':
                        # For shorts: stop loss is ABOVE entry, take profit is BELOW
                        if current_high >= stop_loss:
                            should_exit = True
                        elif current_low <= take_profit:
                            should_exit = True

                if should_exit:
                    if position_direction == 'long':
                        df.iloc[i, df.columns.get_loc('signal')] = 'SELL'
                    else:
                        df.iloc[i, df.columns.get_loc('signal')] = 'COVER'
                    in_position = False
                    position_direction = 'flat'
                    entry_time = None
                    entry_price = 0

            # === ENTRY LOGIC ===
            if not in_position:
                # Check if this is CME open time (Sunday 6 PM)
                is_cme_open = (current_dow == 6 and current_hour == 18)

                if is_cme_open:
                    # Determine direction based on mode
                    trade_signal = None

                    if self.direction_mode == 'first_candle':
                        # Use the direction of this candle
                        candle_change = df.iloc[i]['candle_change_pct']

                        # Check minimum move threshold
                        if abs(candle_change) >= self.min_move_pct:
                            if candle_change > 0:
                                trade_signal = 'LONG'
                            elif candle_change < 0:
                                trade_signal = 'SHORT'

                    elif self.direction_mode == 'first_hour':
                        # Look at net change over first hour (next few candles)
                        # For hourly data, this is just the first candle
                        # For 15-min data, this would be 4 candles
                        candle_change = df.iloc[i]['candle_change_pct']
                        if abs(candle_change) >= self.min_move_pct:
                            if candle_change > 0:
                                trade_signal = 'LONG'
                            elif candle_change < 0:
                                trade_signal = 'SHORT'

                    elif self.direction_mode == 'gap':
                        # Compare to Friday close
                        # Find Friday's last candle
                        friday_close = None
                        for j in range(i-1, max(0, i-100), -1):
                            if df.iloc[j]['day_of_week'] == 4:  # Friday
                                friday_close = df.iloc[j]['close']
                                break

                        if friday_close is not None:
                            gap_pct = ((current_open - friday_close) / friday_close) * 100
                            if abs(gap_pct) >= self.min_move_pct:
                                if gap_pct > 0:
                                    trade_signal = 'LONG'
                                elif gap_pct < 0:
                                    trade_signal = 'SHORT'

                    # Apply direction filter
                    if trade_signal == 'LONG' and self.trade_direction == 'short_only':
                        trade_signal = None
                    if trade_signal == 'SHORT' and self.trade_direction == 'long_only':
                        trade_signal = None

                    # Execute entry
                    if trade_signal == 'LONG':
                        df.iloc[i, df.columns.get_loc('signal')] = 'BUY'
                        in_position = True
                        position_direction = 'long'
                        entry_time = current_time
                        entry_price = current_price

                        # Set stop/target for stop_and_target mode
                        if self.exit_mode == 'stop_and_target':
                            # Stop below the open candle low
                            stop_loss = current_low * (1 - self.stop_loss_pct / 100)
                            take_profit = entry_price * (1 + self.take_profit_pct / 100)

                    elif trade_signal == 'SHORT':
                        df.iloc[i, df.columns.get_loc('signal')] = 'SHORT'
                        in_position = True
                        position_direction = 'short'
                        entry_time = current_time
                        entry_price = current_price

                        # Set stop/target for shorts (reversed)
                        if self.exit_mode == 'stop_and_target':
                            stop_loss = current_high * (1 + self.stop_loss_pct / 100)
                            take_profit = entry_price * (1 - self.take_profit_pct / 100)

        # Count signals
        buys = (df['signal'] == 'BUY').sum()
        shorts = (df['signal'] == 'SHORT').sum()
        sells = (df['signal'] == 'SELL').sum()
        covers = (df['signal'] == 'COVER').sum()

        print(f"\n CME Sunday Open Strategy")
        print(f"   Direction mode: {self.direction_mode}")
        print(f"   Trade direction: {self.trade_direction}")
        print(f"   Exit mode: {self.exit_mode}")
        if self.exit_mode == 'fixed_hours':
            print(f"   Hold time: {self.hold_hours} hours")
        if self.exit_mode == 'stop_and_target':
            print(f"   Stop loss: {self.stop_loss_pct}%")
            print(f"   Take profit: {self.take_profit_pct}%")
        if self.min_move_pct > 0:
            print(f"   Min move threshold: {self.min_move_pct}%")
        print(f"   LONG entries:  {buys}")
        print(f"   SHORT entries: {shorts}")
        print(f"   Exits: {sells + covers}")

        return df[['signal']]

    def __str__(self):
        return f"CMESundayOpen(direction={self.direction_mode}, trade={self.trade_direction}, exit={self.exit_mode})"


class CMESundayOpenLongOnly(CMESundayOpenStrategy):
    """Convenience class for long-only version"""
    def __init__(self, **kwargs):
        kwargs['trade_direction'] = 'long_only'
        super().__init__(**kwargs)


class CMESundayOpenShortOnly(CMESundayOpenStrategy):
    """Convenience class for short-only version"""
    def __init__(self, **kwargs):
        kwargs['trade_direction'] = 'short_only'
        super().__init__(**kwargs)

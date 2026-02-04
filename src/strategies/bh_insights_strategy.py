"""
BH Insights Discord Signal Strategy

This strategy parses trading signals from Brandon Hong's Discord messages
and converts them into backtestable signals.

LEARNING MOMENT: Social Signal Trading
======================================
This is fundamentally different from indicator-based strategies:
- Indicators derive signals from PRICE DATA (math on candles)
- Social signals derive from EXTERNAL INFORMATION (expert analysis)

The challenge: Converting unstructured text into structured signals.
We look for patterns like:
- "longed BTC", "shorted ETH" → Entry signals
- "TP'd", "took profit", "closed" → Exit signals
- "stopped out", "invalidation hit" → Stop loss exits

Trade-off: We can't know the EXACT prices Brandon entered/exited at,
so we use the market price at message timestamp as a proxy.
"""

import pandas as pd
import numpy as np
import re
from datetime import timedelta


class BHInsightsStrategy:
    """
    Parse BH Insights Discord messages for trading signals

    Parameters:
    -----------
    coin : str
        Which coin to extract signals for (e.g., 'BTC', 'ETH', 'SOL')
    messages_path : str
        Path to CSV with Discord messages
    signal_confidence : str
        'high' = only explicit entries like "longed X"
        'medium' = include "long biased", "looking for longs"
        'low' = include general bullish/bearish mentions
    hold_hours : int
        Default hours to hold if no explicit exit signal
    """

    def __init__(
        self,
        coin='BTC',
        messages_path='data/bh_insights_messages.csv',
        signal_confidence='high',
        hold_hours=24,
        include_shorts=True
    ):
        self.coin = coin.upper()
        self.messages_path = messages_path
        self.signal_confidence = signal_confidence
        self.hold_hours = hold_hours
        self.include_shorts = include_shorts

        self.name = f"BH_Insights_{coin}"

        # Load and parse messages
        self.messages = self._load_messages()
        self.parsed_signals = self._parse_all_signals()

    def _load_messages(self):
        """Load messages from CSV"""
        try:
            df = pd.read_csv(self.messages_path, parse_dates=['timestamp'])
            df = df.sort_values('timestamp')
            return df
        except Exception as e:
            print(f"Warning: Could not load messages: {e}")
            return pd.DataFrame()

    def _parse_all_signals(self):
        """Parse all messages and extract signals"""
        signals = []

        for _, row in self.messages.iterrows():
            parsed = self._parse_message(row['content'], row['timestamp'])
            if parsed:
                signals.extend(parsed)

        return pd.DataFrame(signals) if signals else pd.DataFrame()

    def _parse_message(self, content, timestamp):
        """
        Parse a single message for trading signals

        Returns list of signal dicts with:
        - timestamp
        - coin
        - action: 'LONG_ENTRY', 'LONG_EXIT', 'SHORT_ENTRY', 'SHORT_EXIT'
        - confidence: 'high', 'medium', 'low'
        - raw_text: the matched text
        """
        if not content or not isinstance(content, str):
            return None

        signals = []
        content_lower = content.lower()
        content_upper = content.upper()

        # Check if this message mentions our coin
        coin_pattern = r'\b' + self.coin + r'\b'
        if not re.search(coin_pattern, content_upper):
            return None

        # HIGH CONFIDENCE - Explicit entry signals
        # Patterns: "longed BTC", "shorted ETH", "entered long", "bought"

        long_entry_patterns = [
            r'longed\s+' + self.coin.lower(),
            r'long\s+' + self.coin.lower(),
            r'entered\s+long.*' + self.coin.lower(),
            r'bought\s+.*' + self.coin.lower(),
            r'buying\s+.*' + self.coin.lower(),
            r'added\s+.*' + self.coin.lower() + r'.*long',
            r'left\s+curve.*long.*' + self.coin.lower(),
            r're.?longed\s+' + self.coin.lower(),
            # TWAP entries (common for HYPE, SOL, etc.)
            r'started\s+.*twap.*' + self.coin.lower(),
            r'twap\s+on\s+' + self.coin.lower(),
            r'twap.*' + self.coin.lower() + r'.*long',
            # "long on X" pattern (different from "longed X")
            r'long\s+on\s+.*' + self.coin.lower(),
            r'longs?\s+on\s+.*' + self.coin.lower(),
            # "in X" with long context
            r'longed.*in\s+' + self.coin.lower(),
            r'long.*position.*' + self.coin.lower(),
        ]

        for pattern in long_entry_patterns:
            if re.search(pattern, content_lower):
                signals.append({
                    'timestamp': timestamp,
                    'coin': self.coin,
                    'action': 'LONG_ENTRY',
                    'confidence': 'high',
                    'raw_text': content[:200]
                })
                break

        short_entry_patterns = [
            r'shorted\s+' + self.coin.lower(),
            r'short\s+' + self.coin.lower(),
            r'shorting\s+' + self.coin.lower(),
            r'entered\s+short.*' + self.coin.lower(),
            r'added\s+.*' + self.coin.lower() + r'.*short',
        ]

        if self.include_shorts:
            for pattern in short_entry_patterns:
                if re.search(pattern, content_lower):
                    signals.append({
                        'timestamp': timestamp,
                        'coin': self.coin,
                        'action': 'SHORT_ENTRY',
                        'confidence': 'high',
                        'raw_text': content[:200]
                    })
                    break

        # HIGH CONFIDENCE - Exit signals
        exit_patterns = [
            (r'tp\'?d.*' + self.coin.lower(), 'POSITION_EXIT'),
            (r'tp\'?d.*from\s+' + self.coin.lower(), 'POSITION_EXIT'),
            (r'took\s+profit.*' + self.coin.lower(), 'POSITION_EXIT'),
            (r'profits.*from.*' + self.coin.lower(), 'POSITION_EXIT'),
            (r'closed.*' + self.coin.lower(), 'POSITION_EXIT'),
            (r'covered.*' + self.coin.lower(), 'SHORT_EXIT'),
            (r'exited.*' + self.coin.lower(), 'POSITION_EXIT'),
            (r'sold.*' + self.coin.lower(), 'LONG_EXIT'),
            (r'stopped\s+out.*' + self.coin.lower(), 'POSITION_EXIT'),
            # "sold almost all of my recent longs on HYPE"
            (r'sold.*longs?\s+on\s+' + self.coin.lower(), 'LONG_EXIT'),
            (r'sold.*my\s+' + self.coin.lower(), 'LONG_EXIT'),
        ]

        # Also check patterns where coin comes first
        exit_patterns_coin_first = [
            (self.coin.lower() + r'.*tp\'?d', 'POSITION_EXIT'),
            (self.coin.lower() + r'.*closed', 'POSITION_EXIT'),
            (self.coin.lower() + r'.*took\s+profit', 'POSITION_EXIT'),
            (self.coin.lower() + r'.*sold', 'LONG_EXIT'),
        ]

        for pattern, action in exit_patterns + exit_patterns_coin_first:
            if re.search(pattern, content_lower):
                signals.append({
                    'timestamp': timestamp,
                    'coin': self.coin,
                    'action': action,
                    'confidence': 'high',
                    'raw_text': content[:200]
                })
                break

        # MEDIUM CONFIDENCE - Bias signals
        if self.signal_confidence in ['medium', 'low']:
            medium_long_patterns = [
                r'long\s+biased.*' + self.coin.lower(),
                r'bullish.*' + self.coin.lower(),
                r'looking\s+for\s+longs.*' + self.coin.lower(),
                r'expecting.*up.*' + self.coin.lower(),
            ]

            for pattern in medium_long_patterns:
                if re.search(pattern, content_lower):
                    signals.append({
                        'timestamp': timestamp,
                        'coin': self.coin,
                        'action': 'LONG_BIAS',
                        'confidence': 'medium',
                        'raw_text': content[:200]
                    })
                    break

        return signals if signals else None

    def generate_signals(self, data):
        """
        Generate trading signals mapped to price data

        Args:
            data: DataFrame with OHLCV price data (index = timestamp)

        Returns:
            DataFrame with 'signal' column: 'BUY', 'SELL', 'SHORT', 'COVER', 'HOLD'
        """
        df = data.copy()
        df['signal'] = 'HOLD'

        if self.parsed_signals.empty:
            print(f"Warning: No signals found for {self.coin}")
            return df

        # Filter to high confidence signals
        if self.signal_confidence == 'high':
            signals = self.parsed_signals[self.parsed_signals['confidence'] == 'high']
        else:
            signals = self.parsed_signals

        # Filter to our coin
        signals = signals[signals['coin'] == self.coin]

        if signals.empty:
            print(f"Warning: No {self.signal_confidence} confidence signals for {self.coin}")
            return df

        # Track position state
        in_position = False
        position_type = None  # 'long' or 'short'
        entry_idx = None

        # Map signals to price data
        for i in range(len(df)):
            current_time = df.index[i]

            # Check for timeout (auto-close after hold_hours)
            if in_position and entry_idx is not None:
                hours_held = (i - entry_idx)  # Assuming hourly data
                if hours_held >= self.hold_hours:
                    if position_type == 'long':
                        df.iloc[i, df.columns.get_loc('signal')] = 'SELL'
                    elif position_type == 'short':
                        df.iloc[i, df.columns.get_loc('signal')] = 'COVER'
                    in_position = False
                    position_type = None
                    entry_idx = None
                    continue

            # Find signals within this hour
            hour_start = current_time
            hour_end = current_time + timedelta(hours=1)

            hour_signals = signals[
                (signals['timestamp'] >= hour_start) &
                (signals['timestamp'] < hour_end)
            ]

            if hour_signals.empty:
                continue

            # Process signals in this hour
            for _, sig in hour_signals.iterrows():
                action = sig['action']

                if not in_position:
                    # Entry signals
                    if action == 'LONG_ENTRY':
                        df.iloc[i, df.columns.get_loc('signal')] = 'BUY'
                        in_position = True
                        position_type = 'long'
                        entry_idx = i
                        break
                    elif action == 'SHORT_ENTRY' and self.include_shorts:
                        df.iloc[i, df.columns.get_loc('signal')] = 'SHORT'
                        in_position = True
                        position_type = 'short'
                        entry_idx = i
                        break
                else:
                    # Exit signals
                    if action in ['LONG_EXIT', 'POSITION_EXIT'] and position_type == 'long':
                        df.iloc[i, df.columns.get_loc('signal')] = 'SELL'
                        in_position = False
                        position_type = None
                        entry_idx = None
                        break
                    elif action in ['SHORT_EXIT', 'POSITION_EXIT'] and position_type == 'short':
                        df.iloc[i, df.columns.get_loc('signal')] = 'COVER'
                        in_position = False
                        position_type = None
                        entry_idx = None
                        break

        return df

    def get_signal_summary(self):
        """Get summary of parsed signals"""
        if self.parsed_signals.empty:
            return "No signals parsed"

        summary = f"""
BH Insights Signal Summary for {self.coin}
==========================================
Total signals found: {len(self.parsed_signals)}

By action:
{self.parsed_signals['action'].value_counts().to_string()}

By confidence:
{self.parsed_signals['confidence'].value_counts().to_string()}

Date range: {self.parsed_signals['timestamp'].min()} to {self.parsed_signals['timestamp'].max()}
"""
        return summary

    def describe(self):
        """Return strategy description"""
        return f"""
BH Insights Discord Signal Strategy
===================================
Coin: {self.coin}
Signal Confidence: {self.signal_confidence}
Include Shorts: {self.include_shorts}
Default Hold Hours: {self.hold_hours}

How it works:
- Parses Brandon Hong's Discord messages for trading signals
- Looks for explicit entries: "longed X", "shorted X", "bought X"
- Looks for exits: "TP'd", "took profit", "closed", "stopped out"
- Maps signals to price data for backtesting

Limitations:
- We don't know exact entry/exit prices (uses candle close)
- Some signals may be partial positions (we assume full position)
- Messages may discuss hypotheticals or analysis (not actual trades)

{self.get_signal_summary()}
"""


class BHInsightsMultiCoinStrategy:
    """
    Trade multiple coins based on BH Insights signals

    This version tracks signals across multiple coins and generates
    a unified signal stream, useful for portfolio backtesting.
    """

    def __init__(
        self,
        coins=['BTC', 'ETH', 'SOL'],
        messages_path='data/bh_insights_messages.csv',
        signal_confidence='high',
        hold_hours=24
    ):
        self.coins = [c.upper() for c in coins]
        self.strategies = {
            coin: BHInsightsStrategy(
                coin=coin,
                messages_path=messages_path,
                signal_confidence=signal_confidence,
                hold_hours=hold_hours
            )
            for coin in self.coins
        }
        self.name = "BH_Insights_Multi"

    def get_all_signals(self):
        """Get all signals across all coins"""
        all_signals = []
        for coin, strategy in self.strategies.items():
            if not strategy.parsed_signals.empty:
                all_signals.append(strategy.parsed_signals)

        if all_signals:
            return pd.concat(all_signals).sort_values('timestamp')
        return pd.DataFrame()

    def describe(self):
        """Summary of all coin strategies"""
        desc = "BH Insights Multi-Coin Strategy\n"
        desc += "=" * 40 + "\n"
        desc += f"Coins: {', '.join(self.coins)}\n\n"

        for coin, strategy in self.strategies.items():
            desc += f"\n{strategy.get_signal_summary()}\n"

        return desc


if __name__ == "__main__":
    # Test the strategy
    print("Testing BH Insights Strategy...")

    strategy = BHInsightsStrategy(coin='BTC')
    print(strategy.describe())

    # Show sample signals
    if not strategy.parsed_signals.empty:
        print("\nSample signals:")
        print(strategy.parsed_signals.head(20).to_string())

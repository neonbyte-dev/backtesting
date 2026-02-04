"""
BH Insights Strategy V2 - Improved Signal Extraction

Major improvements over V1:
1. More comprehensive entry/exit patterns matching Brandon's actual language
2. Support for commodities (GOLD, SILVER)
3. Better handling of partial exits ("TP'd some", "sold more")
4. Capture of TWAP entries
5. Asset-specific patterns

LEARNING MOMENT: Pattern Matching Order Matters
===============================================
We check patterns in order from most specific to least specific.
"sold a significant amount of HYPE" should match before "sold" alone.
"""

import pandas as pd
import numpy as np
import re
from datetime import timedelta


class BHInsightsStrategyV2:
    """
    Improved signal extraction from BH Insights Discord messages
    """

    # All tradeable assets
    # Note: Single-letter tickers (S, IP, OM) excluded due to false positive risk
    CRYPTO_ASSETS = [
        'BTC', 'ETH', 'SOL', 'SUI', 'PEPE', 'HYPE', 'PUMP', 'ZEC',
        'ENA', 'MKR', 'SEI', 'LTC', 'DOGE', 'XRP', 'AVAX', 'LINK',
        'ARB', 'OP', 'BONK', 'WIF', 'FARTCOIN', 'VIRTUAL', 'TRUMP',
        'ONDO', 'AAVE', 'UNI', 'CRV', 'FTM', 'NEAR', 'APT', 'INJ',
        'PENGU', 'KAITO', 'POPCAT', 'BCH', 'SHIB',
        'AI16Z', 'RNDR', 'FET', 'TAO', 'GRASS', 'GOAT', 'PNUT',
    ]

    COMMODITY_ASSETS = ['GOLD', 'SILVER']

    ALL_ASSETS = CRYPTO_ASSETS + COMMODITY_ASSETS

    # Aliases for commodities (people often write "gold" or "silver" lowercase)
    ASSET_ALIASES = {
        'gold': 'GOLD',
        'silver': 'SILVER',
        'xau': 'GOLD',
        'xag': 'SILVER',
    }

    def __init__(self, messages_path='data/bh_insights_messages.csv', hold_hours=None):
        """
        Initialize BH Insights Strategy

        Args:
            messages_path: Path to CSV with Discord messages
            hold_hours: Max hours to hold position before auto-close.
                       None = no timeout (only exit on explicit signals)
        """
        self.messages_path = messages_path
        self.hold_hours = hold_hours  # None means no timeout
        self.messages = self._load_messages()
        self.all_signals = self._parse_all_signals()

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
        all_signals = []

        for _, row in self.messages.iterrows():
            signals = self._parse_message(row['content'], row['timestamp'])
            all_signals.extend(signals)

        if all_signals:
            df = pd.DataFrame(all_signals)
            df = df.sort_values('timestamp')
            return df
        return pd.DataFrame()

    def _parse_message(self, content, timestamp):
        """
        Parse a single message for trading signals

        Returns list of signal dicts
        """
        if not content or not isinstance(content, str):
            return []

        signals = []
        content_lower = content.lower()

        # Build asset pattern for regex (case insensitive)
        # Include aliases (gold, silver, xau, xag)
        all_names = [a.lower() for a in self.ALL_ASSETS] + list(self.ASSET_ALIASES.keys())
        asset_pattern = '(' + '|'.join(all_names) + ')'

        # ========== LONG ENTRY PATTERNS ==========
        long_patterns = [
            # Explicit "longed X"
            rf'longed\s+{asset_pattern}',
            rf're-?longed\s+{asset_pattern}',
            rf'giga\s+longed\s+.*?{asset_pattern}',
            # "long X with/at/from"
            rf'long\s+{asset_pattern}\s+(?:with|at|@|from)',
            # "entered long on X"
            rf'entered\s+(?:a\s+)?long\s+(?:on\s+|in\s+)?{asset_pattern}',
            # "left curve X" / "left curved X"
            rf'left\s+curve[d]?\s+(?:some\s+)?{asset_pattern}',
            # "bought X" / "bought some X" - expanded patterns
            rf'bought\s+(?:some\s+|a\s+decent\s+amount\s+(?:of\s+)?)?{asset_pattern}',
            rf'bought\s+(?:some\s+)?(?:of\s+)?this.*{asset_pattern}',  # "bought some of this as well"
            rf'{asset_pattern}.*?bought\s+(?:some|a\s+decent)',  # "Gold... bought some"
            # TWAP patterns - expanded
            rf'started\s+(?:a\s+)?twap\s+(?:on\s+)?{asset_pattern}',
            rf'twap\s+(?:on\s+)?{asset_pattern}',
            rf'twaping\s+{asset_pattern}',  # "TWAPing ENA"
            rf'twap\s+above\s+.*?{asset_pattern}',  # "TWAP above $30...HYPE"
            rf'{asset_pattern}.*?twap\s+(?:from|at|above)',  # "HYPE...twap from 24"
            # "back in X"
            rf'back\s+in\s+{asset_pattern}',
            # "positioned long" / "positioned in"
            rf'positioned\s+long\s+(?:on\s+|with\s+)?{asset_pattern}',
            rf'positioned\s+in\s+{asset_pattern}',
            # "nibble some longs on X"
            rf'nibble\s+(?:some\s+)?(?:ltf\s+)?longs?\s+(?:on\s+)?{asset_pattern}',
            # "added to X" / "adding" patterns
            rf'added\s+(?:to\s+)?(?:my\s+)?{asset_pattern}',
            rf'adding\s+(?:to\s+)?(?:my\s+)?{asset_pattern}',
            # "moved...to gold/silver" (commodities)
            rf'moved\s+.*?(?:to|into)\s+{asset_pattern}',
            # "starter/small position on X"
            rf'(?:starter|small)\s+position\s+(?:on\s+)?{asset_pattern}',
            # "long on X" / "longs on X"
            rf'long\s+on\s+{asset_pattern}',
            # Note: Removed "longs on X" - too prone to false positives like "longs on silver and gold"
            # "longed some" with asset context - must be direct object
            rf'longed\s+some\s+{asset_pattern}',
        ]

        # Patterns that should NOT match (false positive filters)
        # These indicate the asset is mentioned in context, not as a direct entry
        false_positive_patterns = [
            # "positioned in X and Y" - stating existing positions, not new entry
            rf'positioned\s+in\s+{asset_pattern}\s+and',
            # "I did with X" - referencing past action on X while doing something else
            rf'did\s+with\s+{asset_pattern}',
            # "like X did" - comparing to X
            rf'like\s+{asset_pattern}\s+did',
        ]

        # ========== SHORT ENTRY PATTERNS ==========
        short_patterns = [
            rf'shorted\s+{asset_pattern}',
            rf'shorting\s+{asset_pattern}',
            rf'short\s+{asset_pattern}\s+(?:with|at|@|from)',
            rf'entered\s+(?:a\s+)?short\s+(?:on\s+|in\s+)?{asset_pattern}',
            rf'short\s+trigger\s+(?:on\s+)?{asset_pattern}',
            # "Short triggers played out on these" (indirect short entry confirmation)
            rf'short\s+triggers?\s+(?:played\s+out|triggered).*{asset_pattern}',
        ]

        # ========== EXIT PATTERNS (Long or Short) ==========
        exit_patterns = [
            # TP'd variations - very flexible
            rf"tp'?d\s+.*?{asset_pattern}",  # Catch-all for TP'd...ASSET
            # "took profit on X"
            rf'took\s+(?:some\s+)?profit[s]?\s+(?:on\s+|from\s+)?{asset_pattern}',
            # "sold X" variations - more flexible
            rf'sold\s+(?:a\s+significant\s+amount\s+of\s+)?{asset_pattern}',
            rf'sold\s+(?:some\s+)?(?:more\s+)?(?:of\s+)?(?:my\s+)?{asset_pattern}',
            rf'sold\s+(?:my\s+)?{asset_pattern}',
            rf'sold\s+(?:recent\s+)?longs?\s+(?:on\s+)?.*?{asset_pattern}',
            # "closed X" - more flexible to catch "closed...longs on CRV HYPE"
            rf'closed\s+.*?longs?\s+(?:on\s+)?.*?{asset_pattern}',
            rf'closed\s+(?:my\s+)?{asset_pattern}',
            # "exited X"
            rf'exited\s+{asset_pattern}',
            # "covered X" (for shorts)
            rf'covered\s+(?:my\s+)?(?:\w+\s+)?shorts?\s+(?:on\s+)?{asset_pattern}',
            rf'covered\s+(?:some\s+)?{asset_pattern}',
            # "out of X"
            rf'(?:mostly\s+)?out\s+of\s+{asset_pattern}',
            # "started to sell X"
            rf'started\s+to\s+sell\s+(?:some\s+)?{asset_pattern}',
            # "sold more from" patterns
            rf'sold\s+more\s+from\s+.*?{asset_pattern}',
            # "scaled out" patterns
            rf'scaled\s+out\s+.*?{asset_pattern}',
            rf'scaled\s+out\s+.*?longs.*?{asset_pattern}',
        ]

        # Process patterns and extract signals
        found_assets = set()  # Track to avoid duplicates in same message

        def normalize_asset(name):
            """Convert aliases to canonical asset name"""
            name_lower = name.lower()
            if name_lower in self.ASSET_ALIASES:
                return self.ASSET_ALIASES[name_lower]
            return name.upper()

        def is_false_positive(asset_name, content):
            """Check if this asset match is a false positive"""
            asset_lower = asset_name.lower()
            for fp_pattern in false_positive_patterns:
                # Replace the asset_pattern placeholder with the actual asset
                fp_check = fp_pattern.replace(asset_pattern, f'({asset_lower})')
                if re.search(fp_check, content):
                    return True
            return False

        # LONG entries
        for pattern in long_patterns:
            matches = re.findall(pattern, content_lower)
            for match in matches:
                asset = normalize_asset(match)
                if asset in self.ALL_ASSETS and (asset, 'LONG') not in found_assets:
                    # Check for false positives
                    if is_false_positive(asset, content_lower):
                        continue
                    signals.append({
                        'timestamp': timestamp,
                        'asset': asset,
                        'action': 'LONG',
                        'raw_text': content[:400]
                    })
                    found_assets.add((asset, 'LONG'))

        # SHORT entries
        for pattern in short_patterns:
            matches = re.findall(pattern, content_lower)
            for match in matches:
                asset = normalize_asset(match)
                if asset in self.ALL_ASSETS and (asset, 'SHORT') not in found_assets:
                    signals.append({
                        'timestamp': timestamp,
                        'asset': asset,
                        'action': 'SHORT',
                        'raw_text': content[:400]
                    })
                    found_assets.add((asset, 'SHORT'))

        # EXITs
        for pattern in exit_patterns:
            matches = re.findall(pattern, content_lower)
            for match in matches:
                asset = normalize_asset(match)
                if asset in self.ALL_ASSETS and (asset, 'EXIT') not in found_assets:
                    signals.append({
                        'timestamp': timestamp,
                        'asset': asset,
                        'action': 'EXIT',
                        'raw_text': content[:400]
                    })
                    found_assets.add((asset, 'EXIT'))

        return signals

    def get_signals_for_asset(self, asset):
        """Get all signals for a specific asset"""
        if self.all_signals.empty:
            return pd.DataFrame()
        return self.all_signals[self.all_signals['asset'] == asset.upper()].copy()

    def get_signal_summary(self):
        """Summary of signals by asset"""
        if self.all_signals.empty:
            return pd.DataFrame()

        summary = self.all_signals.groupby(['asset', 'action']).size().unstack(fill_value=0)
        summary['TOTAL'] = summary.sum(axis=1)
        return summary.sort_values('TOTAL', ascending=False)

    def generate_signals(self, data, asset):
        """
        Generate trading signals mapped to price data

        Args:
            data: DataFrame with OHLCV price data (index = timestamp)
            asset: Asset symbol

        Returns:
            DataFrame with 'signal' column
        """
        df = data.copy()
        df['signal'] = 'HOLD'

        asset_signals = self.get_signals_for_asset(asset)
        if asset_signals.empty:
            return df

        # Track position state
        in_position = False
        position_type = None
        entry_time = None

        for i in range(len(df)):
            current_time = df.index[i]

            # Auto-close after hold_hours (only if hold_hours is set)
            if in_position and entry_time is not None and self.hold_hours is not None:
                # Calculate actual hours elapsed using timestamps
                time_held = (current_time - entry_time).total_seconds() / 3600
                if time_held >= self.hold_hours:
                    if position_type == 'long':
                        df.iloc[i, df.columns.get_loc('signal')] = 'SELL'
                    elif position_type == 'short':
                        df.iloc[i, df.columns.get_loc('signal')] = 'COVER'
                    in_position = False
                    position_type = None
                    entry_time = None
                    continue

            # Find signals within this candle period
            # Detect candle size from data index
            if i < len(df) - 1:
                candle_hours = (df.index[i + 1] - df.index[i]).total_seconds() / 3600
            else:
                candle_hours = 1  # Default to 1 hour

            window_start = current_time
            window_end = current_time + timedelta(hours=max(candle_hours, 1))

            window_signals = asset_signals[
                (asset_signals['timestamp'] >= window_start) &
                (asset_signals['timestamp'] < window_end)
            ]

            if window_signals.empty:
                continue

            for _, sig in window_signals.iterrows():
                action = sig['action']

                if not in_position:
                    if action == 'LONG':
                        df.iloc[i, df.columns.get_loc('signal')] = 'BUY'
                        in_position = True
                        position_type = 'long'
                        entry_time = current_time
                        break
                    elif action == 'SHORT':
                        df.iloc[i, df.columns.get_loc('signal')] = 'SHORT'
                        in_position = True
                        position_type = 'short'
                        entry_time = current_time
                        break
                else:
                    if action == 'EXIT':
                        if position_type == 'long':
                            df.iloc[i, df.columns.get_loc('signal')] = 'SELL'
                        elif position_type == 'short':
                            df.iloc[i, df.columns.get_loc('signal')] = 'COVER'
                        in_position = False
                        position_type = None
                        entry_time = None
                        break

        return df


class SingleAssetStrategy:
    """Wrapper for single asset backtesting"""

    def __init__(self, asset, strategy):
        self.asset = asset
        self.strategy = strategy
        self.name = f"BH_V2_{asset}"

    def generate_signals(self, data):
        return self.strategy.generate_signals(data, self.asset)


if __name__ == "__main__":
    print("Testing BH Insights Strategy V2...\n")

    strategy = BHInsightsStrategyV2()

    print("=== SIGNAL SUMMARY ===\n")
    summary = strategy.get_signal_summary()
    print(summary)

    print("\n\n=== SAMPLE SIGNALS FOR KEY ASSETS ===\n")

    for asset in ['BTC', 'ETH', 'SOL', 'HYPE', 'GOLD', 'SILVER', 'FARTCOIN']:
        signals = strategy.get_signals_for_asset(asset)
        if not signals.empty:
            print(f"\n--- {asset}: {len(signals)} signals ---")
            for _, sig in signals.head(5).iterrows():
                print(f"  [{sig['timestamp']}] {sig['action']}")
                print(f"    {sig['raw_text'][:100]}...")

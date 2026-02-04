"""
BH Insights Multi-Asset Strategy - Improved Signal Extraction

LEARNING MOMENT: Natural Language Signal Parsing
================================================
Parsing trading signals from chat messages is challenging because:
1. Language is ambiguous ("longed" vs "looking to long")
2. Context matters ("sold some" vs "sold all")
3. Multiple assets mentioned in one message
4. Price levels may or may not be explicit

We use regex patterns ranked by confidence:
- HIGH: "longed BTC", "shorted ETH" (explicit action + asset)
- MEDIUM: "long BTC with 0.5% risk" (clear intent)
- LOW: "long biased on BTC" (sentiment, not action)
"""

import pandas as pd
import numpy as np
import re
from datetime import timedelta


class BHInsightsMultiAssetStrategy:
    """
    Improved signal extraction across multiple assets

    Key improvements:
    - Better regex patterns for entry/exit detection
    - Extracts invalidation (stop loss) levels when mentioned
    - Extracts target prices when mentioned
    - Handles position sizing hints (0.25%, 0.5%, 1% risk)
    """

    # Tradeable assets on major exchanges + commodities
    SUPPORTED_ASSETS = [
        # Major crypto
        'BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'LTC', 'BCH', 'ETC',
        # L1s
        'SUI', 'SEI', 'AVAX', 'NEAR', 'APT', 'INJ', 'FTM', 'ADA', 'DOT', 'ATOM',
        # L2s
        'ARB', 'OP', 'BASE', 'BLAST', 'STRK', 'MANTA',
        # DeFi
        'LINK', 'UNI', 'AAVE', 'MKR', 'CRV', 'ENA', 'ONDO', 'JUP', 'RAY',
        # Memes
        'PEPE', 'BONK', 'WIF', 'SHIB', 'FARTCOIN', 'TRUMP', 'MELANIA', 'PNUT', 'PENGU',
        # AI / New narrative
        'HYPE', 'VIRTUAL', 'AI16Z', 'ZEREBRO', 'RENDER', 'FET', 'GOAT',
        # Others mentioned frequently
        'PUMP', 'ZEC', 'MOVE', 'ME', 'USUAL', 'BIO', 'ENS', 'W', 'JTO',
        # Commodities (traded on HyperLiquid as GOLD, SILVER)
        'GOLD', 'SILVER',
        # Indices (for reference, may not be directly tradeable)
        'SPY', 'QQQ', 'DXY',
    ]

    def __init__(self, messages_path='data/bh_insights_messages.csv', hold_hours=720):  # 30 days default - positions close on EXIT signal, not timeout
        self.messages_path = messages_path
        self.hold_hours = hold_hours
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
        """Parse all messages and extract signals for all assets"""
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
        Parse a single message for trading signals across all assets

        Returns list of signal dicts
        """
        if not content or not isinstance(content, str):
            return []

        signals = []
        content_lower = content.lower()

        # === ASSET-FIRST SEMANTIC MATCHING ===
        # First find which supported assets are mentioned, then check for signal phrases
        # This catches signals like "HYPE...best long in the market" where asset comes first

        mentioned_assets = []
        for asset in self.SUPPORTED_ASSETS:
            # Check if asset is mentioned (word boundary match)
            if re.search(r'\b' + asset.lower() + r'\b', content_lower):
                mentioned_assets.append(asset)

        # Strong LONG signal phrases (asset-agnostic)
        strong_long_phrases = [
            r'best\s+long',
            r'literally\s+the\s+best\s+long',
            r'comfiest\s+(?:coin|bag|hold|swing)',
            r'decent\s+long',
            r'would\s+(?:be\s+)?(?:a\s+)?long',
            r'easiest\s+(?:trade|long)',
            r'strong(?:est)?\s+(?:alt|coin)',
            r'clear\s+(?:long|winner)',
            r'obvious\s+long',
            r'clean\s+(?:long|breakout|setup)',
            r'looks\s+(?:good|great|constructive)',
            r'going\s+(?:insane|crazy|ballistic)',
            r'impuls(?:e|ed|ing)',
            r'breakout\s+above',
            r'reclaim(?:ed|ing)?',
        ]

        for asset in mentioned_assets:
            for phrase in strong_long_phrases:
                if re.search(phrase, content_lower):
                    # Check it's not an exit message
                    exit_indicators = [r'\bsold\b', r'\btp\'?d\b', r'\bclosed\b', r'\bexited\b', r'\bout\s+of\b']
                    is_exit = any(re.search(ind, content_lower) for ind in exit_indicators)

                    if not is_exit:
                        signals.append({
                            'timestamp': timestamp,
                            'asset': asset,
                            'action': 'LONG',
                            'confidence': 'high',
                            'invalidation': self._extract_invalidation(content_lower, asset),
                            'target': self._extract_target(content_lower, asset),
                            'risk_pct': self._extract_risk_pct(content_lower),
                            'raw_text': content[:300]
                        })
                        break  # Only one signal per asset per message

        # === LONG ENTRY PATTERNS ===
        long_patterns = [
            # Explicit entries with asset capture
            (r'longed\s+(\w+)', 'high'),
            (r're-?longed\s+(\w+)', 'high'),
            (r'long\s+(\w+)\s+(?:with|at|@|from)', 'high'),
            (r'entered\s+long\s+(?:on\s+)?(\w+)', 'high'),
            (r'left\s+curve[d]?\s+(?:some\s+)?(\w+)', 'high'),
            (r'bought\s+(?:some\s+)?(\w+)', 'medium'),
            (r'added\s+(?:to\s+)?(\w+)\s+long', 'medium'),
            (r'adding\s+(?:to\s+)?(\w+)', 'medium'),
            # TWAP entries (common for HYPE, SOL, etc.) - "Started a TWAP on HYPE from 24"
            (r'started\s+(?:a\s+)?twap\s+on\s+(\w+)', 'high'),
            (r'twap\s+on\s+(\w+)', 'high'),
            (r'twap.*(\w+)\s+from\s+\d+', 'high'),
            (r'twaping\s+(\w+)', 'high'),  # "TWAPing ENA"
            (r'twap(?:ing)?\s+(?:into\s+)?(\w+)', 'high'),
            # "long on X" without price qualifier
            (r'long\s+on\s+(\w+)', 'high'),
            (r'longs?\s+on\s+(\w+)', 'medium'),
            # "positioned in X"
            (r'positioned\s+in\s+(\w+)', 'medium'),
            (r'most\s+positioned\s+in\s+(\w+)', 'medium'),
            # Commodity-style entries - "Back in silver", "got back into gold"
            (r'back\s+in\s+(\w+)', 'high'),
            (r'back\s+into\s+(\w+)', 'high'),
            (r'got\s+back\s+in(?:to)?\s+(\w+)', 'high'),
            # "in GOLD/SILVER" with size context
            (r'biggest\s+position.*in\s+(\w+)', 'medium'),
            # Price-based entry signals - "would be a decent long", "good long at X"
            (r'decent\s+long.*(\w+)', 'high'),
            (r'would\s+(?:be\s+)?(?:a\s+)?(?:decent\s+)?long.*(\w+)', 'high'),
            (r'good\s+long\s+(?:on\s+)?(\w+)', 'high'),
            # "comfiest coin/bag" - indicates strong conviction hold
            (r'comfiest\s+(?:coin|bag).*(\w+)', 'high'),
            (r'(\w+).*comfiest\s+(?:coin|bag)', 'high'),
            # "best long in the market" style
            (r'best\s+long.*(\w+)', 'high'),
            (r'(\w+).*best\s+long', 'high'),
            # "literally the best long" - explicit strong signal
            (r'literally\s+the\s+best\s+long.*(\w+)', 'high'),
            # Building/accumulating position patterns
            (r'building\s+(?:a\s+)?position\s+(?:in\s+|on\s+)?(\w+)', 'high'),
            (r'accumulating\s+(\w+)', 'high'),
            (r'accumulate\s+(\w+)', 'medium'),
            (r'nibbling\s+(\w+)', 'high'),
            (r'nibble\s+(?:on\s+|some\s+)?(\w+)', 'medium'),
            (r'bidding\s+(\w+)', 'high'),
            (r'bid\s+(?:a\s+)?(?:breakout\s+)?(?:on\s+|above\s+)?.*(\w+)', 'medium'),
            (r'scaling\s+into\s+(\w+)', 'high'),
            (r'scale\s+into\s+(\w+)', 'medium'),
            (r'dipping\s+into\s+(\w+)', 'high'),
            (r'getting\s+(?:some\s+)?(?:exposure\s+)?(?:to\s+|in\s+)?(\w+)', 'medium'),
            (r'exposure\s+(?:to\s+|in\s+)(\w+)', 'medium'),
            # "interested in longs on X"
            (r'interested\s+in\s+longs?\s+(?:on\s+)?(\w+)', 'medium'),
            (r'looking\s+to\s+long\s+(\w+)', 'medium'),
            (r'eyeing\s+(\w+)', 'medium'),
            # "will long X if..."
            (r'will\s+long\s+(\w+)', 'medium'),
            (r"i'?ll\s+long\s+(\w+)", 'medium'),
        ]

        # === SHORT ENTRY PATTERNS ===
        short_patterns = [
            (r'shorted\s+(\w+)', 'high'),
            (r'shorting\s+(\w+)', 'high'),
            (r'short\s+(\w+)\s+(?:with|at|@|from)', 'high'),
            (r'entered\s+short\s+(?:on\s+)?(\w+)', 'high'),
        ]

        # === EXIT PATTERNS (apply to most recent position type) ===
        exit_patterns = [
            # TP patterns - various forms
            (r"tp'?d\s+(?:some\s+|more\s+|most\s+|majority\s+|partials?\s+)?(?:of\s+)?(?:my\s+)?(?:\w+\s+)?(\w+)", 'high'),
            (r"tp'?d\s+more\s+from\s+(\w+)", 'high'),  # "TP'd more from HYPE"
            (r"tp'?d\s+more\s+of\s+(\w+)", 'high'),  # "TP'd more of HYPE"
            (r"also\s+tp'?d\s+(?:more\s+)?(?:from\s+)?(\w+)", 'high'),  # "Also TP'd more from HYPE"
            (r'took\s+profit\s+(?:on\s+)?(\w+)', 'high'),
            (r'took\s+some\s+profits\s+from\s+(\w+)', 'high'),
            # Sold patterns
            (r'sold\s+(?:a\s+)?(?:significant\s+)?(?:amount\s+)?(?:of\s+)?(\w+)', 'high'),  # "sold a significant amount of HYPE"
            (r'sold\s+(?:the\s+rest\s+of\s+)?(?:my\s+)?(\w+)', 'high'),
            (r'sold\s+(\w+)\s+for\s+now', 'high'),  # "Sold silver for now"
            (r'sold\s+(?:recent\s+)?longs\s+on.*(\w+)', 'high'),  # "sold recent longs on ETH"
            # Closed patterns
            (r'closed\s+(?:my\s+)?(\w+)', 'high'),
            (r'closed\s+(?:some\s+)?(?:of\s+)?(?:my\s+)?(?:recent\s+)?(?:lower\s+)?(?:conviction\s+)?longs\s+on.*(\w+)', 'high'),  # "Closed some of my recent lower conviction longs on CRV HYPE"
            # Other exits
            (r'exited\s+(\w+)', 'high'),
            (r'covered\s+(?:my\s+)?(?:\w+\s+)?shorts?\s+(?:on\s+)?(\w+)', 'high'),
            (r'covered\s+(?:some\s+)?(\w+)', 'medium'),
            (r'stopped\s+out\s+(?:of\s+)?(\w+)', 'high'),
            # TWAP exits
            (r'twaping\s+out\s+of.*(\w+)', 'high'),
            (r'started\s+twap(?:ing)?\s+out.*(\w+)', 'high'),
            # "mostly out of X"
            (r'mostly\s+out\s+of\s+(\w+)', 'high'),
            # Scaling out / taking profits patterns
            (r'scaled\s+(?:some\s+)?(?:more\s+)?out\s+(?:of\s+)?(\w+)', 'high'),
            (r'scaling\s+out\s+(?:of\s+)?(\w+)', 'high'),
            (r'scale\s+out\s+(?:of\s+)?(\w+)', 'medium'),
            (r'chips?\s+off\s+(?:the\s+)?table.*(\w+)', 'high'),
            (r'took\s+(?:some\s+)?chips?\s+off.*(\w+)', 'high'),
            (r'removed\s+risk.*(\w+)', 'high'),
            (r'risk\s+(?:has\s+been\s+)?removed.*(\w+)', 'high'),
            (r'shaved\s+off\s+(?:longs?\s+)?(?:on\s+)?(\w+)', 'high'),
            (r'trimm(?:ed|ing)\s+(?:the\s+)?(?:rest\s+)?(?:of\s+)?(?:my\s+)?(?:longs?\s+)?(?:on\s+)?(\w+)', 'high'),
            # "satisfied with X" / "done with X"
            (r'satisfied\s+with\s+(\w+)', 'medium'),
            (r'done\s+with\s+(\w+)', 'high'),
            (r'out\s+of\s+(\w+)', 'high'),
        ]

        # Process LONG entries
        for pattern, confidence in long_patterns:
            matches = re.findall(pattern, content_lower)
            for match in matches:
                asset = match.upper()
                if asset in self.SUPPORTED_ASSETS:
                    # Extract additional info
                    invalidation = self._extract_invalidation(content_lower, asset)
                    target = self._extract_target(content_lower, asset)
                    risk_pct = self._extract_risk_pct(content_lower)

                    signals.append({
                        'timestamp': timestamp,
                        'asset': asset,
                        'action': 'LONG',
                        'confidence': confidence,
                        'invalidation': invalidation,
                        'target': target,
                        'risk_pct': risk_pct,
                        'raw_text': content[:300]
                    })

        # Process SHORT entries
        for pattern, confidence in short_patterns:
            matches = re.findall(pattern, content_lower)
            for match in matches:
                asset = match.upper()
                if asset in self.SUPPORTED_ASSETS:
                    invalidation = self._extract_invalidation(content_lower, asset)
                    target = self._extract_target(content_lower, asset)
                    risk_pct = self._extract_risk_pct(content_lower)

                    signals.append({
                        'timestamp': timestamp,
                        'asset': asset,
                        'action': 'SHORT',
                        'confidence': confidence,
                        'invalidation': invalidation,
                        'target': target,
                        'risk_pct': risk_pct,
                        'raw_text': content[:300]
                    })

        # Process EXITs
        for pattern, confidence in exit_patterns:
            matches = re.findall(pattern, content_lower)
            for match in matches:
                asset = match.upper()
                if asset in self.SUPPORTED_ASSETS:
                    signals.append({
                        'timestamp': timestamp,
                        'asset': asset,
                        'action': 'EXIT',
                        'confidence': confidence,
                        'invalidation': None,
                        'target': None,
                        'risk_pct': None,
                        'raw_text': content[:300]
                    })

        return signals

    def _extract_invalidation(self, content, asset):
        """Extract invalidation/stop loss price from message"""
        asset_lower = asset.lower()

        patterns = [
            r'invalidation\s+(?:below\s+|at\s+|around\s+)?(\d+\.?\d*)',
            r'inval\s+(?:below\s+|at\s+)?(\d+\.?\d*)',
            r'invalid\s+(?:below\s+|if\s+)?(\d+\.?\d*)',
            r'stop\s+(?:at\s+|below\s+)?(\d+\.?\d*)',
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                try:
                    return float(match.group(1))
                except:
                    pass
        return None

    def _extract_target(self, content, asset):
        """Extract target price from message"""
        patterns = [
            r'target(?:ing)?\s+(\d+\.?\d*)',
            r'tp\s+(?:at\s+)?(\d+\.?\d*)',
            r'looking\s+for\s+(\d+\.?\d*)',
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                try:
                    return float(match.group(1))
                except:
                    pass
        return None

    def _extract_risk_pct(self, content):
        """Extract risk percentage from message"""
        patterns = [
            r'(\d+\.?\d*)%\s+risk',
            r'with\s+(\d+\.?\d*)%',
            r'(\d+/\d+)\s+(?:usual\s+)?risk',  # e.g., "1/2 usual risk"
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                try:
                    val = match.group(1)
                    if '/' in val:
                        # Handle fractions like "1/2"
                        num, denom = val.split('/')
                        return float(num) / float(denom)
                    return float(val)
                except:
                    pass
        return None

    def get_signals_for_asset(self, asset):
        """Get all signals for a specific asset"""
        if self.all_signals.empty:
            return pd.DataFrame()

        asset_signals = self.all_signals[self.all_signals['asset'] == asset.upper()]
        return asset_signals.copy()

    def get_signal_summary(self):
        """Summary of all signals by asset"""
        if self.all_signals.empty:
            return "No signals found"

        summary = self.all_signals.groupby(['asset', 'action']).size().unstack(fill_value=0)
        return summary

    def generate_signals(self, data, asset):
        """
        Generate trading signals mapped to price data for a specific asset

        Args:
            data: DataFrame with OHLCV price data (index = timestamp)
            asset: Asset symbol (e.g., 'BTC', 'ETH')

        Returns:
            DataFrame with 'signal' column
        """
        df = data.copy()
        df['signal'] = 'HOLD'

        asset_signals = self.get_signals_for_asset(asset)

        if asset_signals.empty:
            print(f"Warning: No signals found for {asset}")
            return df

        # Only use high confidence signals
        signals = asset_signals[asset_signals['confidence'] == 'high']

        if signals.empty:
            print(f"Warning: No high-confidence signals for {asset}")
            return df

        # Detect timeframe from data (hours between candles)
        if len(df) >= 2:
            time_diff = (df.index[1] - df.index[0]).total_seconds() / 3600
            candle_hours = max(1, int(time_diff))  # At least 1 hour
        else:
            candle_hours = 1

        # Track position state
        in_position = False
        position_type = None  # 'long' or 'short'
        entry_idx = None

        for i in range(len(df)):
            current_time = df.index[i]

            # Auto-close after hold_hours (adjusted for candle size)
            if in_position and entry_idx is not None:
                candles_held = (i - entry_idx)
                hours_held = candles_held * candle_hours
                if hours_held >= self.hold_hours:
                    if position_type == 'long':
                        df.iloc[i, df.columns.get_loc('signal')] = 'SELL'
                    elif position_type == 'short':
                        df.iloc[i, df.columns.get_loc('signal')] = 'COVER'
                    in_position = False
                    position_type = None
                    entry_idx = None
                    continue

            # Find signals within this candle's time window
            candle_start = current_time
            candle_end = current_time + timedelta(hours=candle_hours)

            candle_signals = signals[
                (signals['timestamp'] >= candle_start) &
                (signals['timestamp'] < candle_end)
            ]

            if candle_signals.empty:
                continue

            # Process first signal in this candle
            for _, sig in candle_signals.iterrows():
                action = sig['action']

                if not in_position:
                    if action == 'LONG':
                        df.iloc[i, df.columns.get_loc('signal')] = 'BUY'
                        in_position = True
                        position_type = 'long'
                        entry_idx = i
                        break
                    elif action == 'SHORT':
                        df.iloc[i, df.columns.get_loc('signal')] = 'SHORT'
                        in_position = True
                        position_type = 'short'
                        entry_idx = i
                        break
                else:
                    if action == 'EXIT':
                        if position_type == 'long':
                            df.iloc[i, df.columns.get_loc('signal')] = 'SELL'
                        elif position_type == 'short':
                            df.iloc[i, df.columns.get_loc('signal')] = 'COVER'
                        in_position = False
                        position_type = None
                        entry_idx = None
                        break
                    # Allow flipping positions
                    elif action == 'SHORT' and position_type == 'long':
                        df.iloc[i, df.columns.get_loc('signal')] = 'SELL'
                        in_position = False
                        position_type = None
                        entry_idx = None
                        break
                    elif action == 'LONG' and position_type == 'short':
                        df.iloc[i, df.columns.get_loc('signal')] = 'COVER'
                        in_position = False
                        position_type = None
                        entry_idx = None
                        break

        return df


class SingleAssetBHStrategy:
    """Wrapper to make multi-asset strategy work with single-asset backtester"""

    def __init__(self, asset, multi_strategy):
        self.asset = asset
        self.multi_strategy = multi_strategy
        self.name = f"BH_Insights_{asset}"

    def generate_signals(self, data):
        return self.multi_strategy.generate_signals(data, self.asset)


if __name__ == "__main__":
    # Test the improved strategy
    print("Testing improved BH Insights Multi-Asset Strategy...\n")

    strategy = BHInsightsMultiAssetStrategy()

    print("=== SIGNAL SUMMARY BY ASSET ===\n")
    print(strategy.get_signal_summary())

    print("\n\n=== SAMPLE SIGNALS WITH DETAILS ===\n")

    for asset in ['BTC', 'ETH', 'SOL']:
        signals = strategy.get_signals_for_asset(asset)
        if not signals.empty:
            print(f"\n--- {asset} ({len(signals)} signals) ---")
            high_conf = signals[signals['confidence'] == 'high']
            print(f"High confidence: {len(high_conf)}")

            # Show samples with invalidation/target
            with_inval = high_conf[high_conf['invalidation'].notna()]
            if not with_inval.empty:
                print(f"\nSample with invalidation levels:")
                for _, sig in with_inval.head(3).iterrows():
                    print(f"  [{sig['timestamp']}] {sig['action']} @ invalidation: {sig['invalidation']}")

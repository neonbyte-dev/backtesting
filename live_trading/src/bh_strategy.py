"""
BH Insights Strategy - Live Trading

Monitors Clickhouse for new Discord messages from Brandon Hong,
parses signals, and executes trades on HyperLiquid.

How it works:
1. Each loop iteration, poll Clickhouse for new messages
2. Parse new messages for LONG/SHORT/EXIT signals
3. If signal matches tracked asset, trigger entry/exit
4. Position tracking per asset with state persistence

Key difference from backtest:
- Backtest: All data available upfront, process sequentially
- Live: Poll for new data, react in real-time
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pytz
import clickhouse_connect


class BHInsightsStrategy:
    """
    Live trading strategy based on BH Insights Discord signals.

    Monitors Clickhouse for new messages, parses trading signals,
    and provides entry/exit recommendations.
    """

    # Assets we can trade on HyperLiquid
    TRADEABLE_ASSETS = [
        'BTC', 'ETH', 'SOL', 'SUI', 'PEPE', 'HYPE', 'DOGE', 'XRP',
        'AVAX', 'LINK', 'ARB', 'OP', 'BONK', 'WIF', 'AAVE', 'UNI',
        'LTC', 'BCH', 'APT', 'INJ', 'SEI', 'NEAR', 'FTM', 'CRV',
        'ONDO', 'ENA', 'PENGU', 'TAO', 'FET', 'RNDR',
        # Commodities via HyperLiquid (if available)
        # 'GOLD', 'SILVER'  - check availability
    ]

    # Asset aliases (lowercase versions and alternatives)
    ASSET_ALIASES = {
        'bitcoin': 'BTC',
        'ethereum': 'ETH',
        'solana': 'SOL',
    }

    def __init__(self, config: dict):
        """
        Initialize BH Insights Strategy

        Args:
            config: Strategy configuration containing:
                - clickhouse_host: Clickhouse server host
                - clickhouse_port: Clickhouse server port
                - clickhouse_user: Database username
                - clickhouse_password: Database password
                - clickhouse_database: Database name
                - tracked_assets: List of assets to trade (default: ['BTC', 'ETH'])
                - poll_interval_seconds: How often to check for new messages
        """
        # Clickhouse connection settings
        self.ch_host = config.get('clickhouse_host', 'ch.ops.xexlab.com')
        self.ch_port = config.get('clickhouse_port', 443)
        self.ch_user = config.get('clickhouse_user', 'dev_ado')
        self.ch_password = config.get('clickhouse_password', '')
        self.ch_database = config.get('clickhouse_database', 'crush_ats')

        # Trading settings
        self.tracked_assets = config.get('tracked_assets', ['BTC', 'ETH'])
        self.poll_interval = config.get('poll_interval_seconds', 30)

        # State tracking
        self.last_message_timestamp = None
        self.pending_signals: Dict[str, dict] = {}  # asset -> signal info
        self.client = None

        # Initialize Clickhouse client
        self._init_clickhouse()

    def _init_clickhouse(self):
        """Initialize Clickhouse connection"""
        try:
            self.client = clickhouse_connect.get_client(
                host=self.ch_host,
                port=self.ch_port,
                username=self.ch_user,
                password=self.ch_password,
                database=self.ch_database,
                secure=True
            )
            print(f"[BH] Connected to Clickhouse: {self.ch_host}")
        except Exception as e:
            print(f"[BH] Failed to connect to Clickhouse: {e}")
            self.client = None

    def _fetch_new_messages(self) -> List[dict]:
        """
        Fetch new messages from Clickhouse since last check

        Returns:
            List of message dicts with timestamp and content
        """
        if not self.client:
            self._init_clickhouse()
            if not self.client:
                return []

        try:
            # Build query - get messages from BH Insights chat
            # Column mapping from Clickhouse schema:
            # - created_at (DateTime64) = message timestamp
            # - raw (String) = message text (message_content is often empty)
            # - user_name (String) = author name
            # - chat_name (String) = chat/group name (e.g., 'BH Insights')
            if self.last_message_timestamp:
                # Add 1 second to avoid re-processing the same message
                since_ts = self.last_message_timestamp + timedelta(seconds=1)
                query = f"""
                    SELECT created_at, raw, user_name, message_id
                    FROM messages
                    WHERE chat_name = 'BH Insights'
                    AND created_at > '{since_ts.strftime('%Y-%m-%d %H:%M:%S')}'
                    ORDER BY created_at ASC
                    LIMIT 100
                """
            else:
                # First run - only get messages from last 24 hours to avoid
                # processing old signals
                since_ts = datetime.now(pytz.UTC) - timedelta(hours=24)
                query = f"""
                    SELECT created_at, raw, user_name, message_id
                    FROM messages
                    WHERE chat_name = 'BH Insights'
                    AND created_at > '{since_ts.strftime('%Y-%m-%d %H:%M:%S')}'
                    ORDER BY created_at ASC
                    LIMIT 100
                """

            result = self.client.query(query)

            messages = []
            for row in result.result_rows:
                msg = {
                    'timestamp': row[0] if isinstance(row[0], datetime) else datetime.fromisoformat(str(row[0])),
                    'content': row[1],
                    'author': row[2],
                    'message_id': row[3]
                }
                messages.append(msg)

                # Update last processed timestamp
                if msg['timestamp']:
                    if not self.last_message_timestamp or msg['timestamp'] > self.last_message_timestamp:
                        self.last_message_timestamp = msg['timestamp']

            if messages:
                print(f"[BH] Fetched {len(messages)} new messages")

            return messages

        except Exception as e:
            print(f"[BH] Error fetching messages: {e}")
            return []

    def _parse_message(self, content: str, timestamp: datetime) -> List[dict]:
        """
        Parse a message for trading signals

        Uses same pattern matching as bh_insights_v2.py backtest

        Args:
            content: Message text
            timestamp: Message timestamp

        Returns:
            List of signal dicts with asset, action, timestamp
        """
        if not content or not isinstance(content, str):
            return []

        signals = []
        content_lower = content.lower()

        # Build asset pattern for tracked assets only
        tracked_lower = [a.lower() for a in self.tracked_assets]
        asset_pattern = '(' + '|'.join(tracked_lower) + ')'

        # ========== LONG ENTRY PATTERNS ==========
        long_patterns = [
            rf'longed\s+{asset_pattern}',
            rf're-?longed\s+{asset_pattern}',
            rf'giga\s+longed\s+.*?{asset_pattern}',
            rf'long\s+{asset_pattern}\s+(?:with|at|@|from)',
            rf'entered\s+(?:a\s+)?long\s+(?:on\s+|in\s+)?{asset_pattern}',
            rf'left\s+curve[d]?\s+(?:some\s+)?{asset_pattern}',
            rf'bought\s+(?:some\s+|a\s+decent\s+amount\s+(?:of\s+)?)?{asset_pattern}',
            rf'started\s+(?:a\s+)?twap\s+(?:on\s+)?{asset_pattern}',
            rf'twap\s+(?:on\s+)?{asset_pattern}',
            rf'twaping\s+{asset_pattern}',
            rf'back\s+in\s+{asset_pattern}',
            rf'positioned\s+long\s+(?:on\s+|with\s+)?{asset_pattern}',
            rf'nibble\s+(?:some\s+)?(?:ltf\s+)?longs?\s+(?:on\s+)?{asset_pattern}',
            rf'added\s+(?:to\s+)?(?:my\s+)?{asset_pattern}',
            rf'long\s+on\s+{asset_pattern}',
            rf'longed\s+some\s+{asset_pattern}',
        ]

        # ========== SHORT ENTRY PATTERNS ==========
        short_patterns = [
            rf'shorted\s+{asset_pattern}',
            rf'shorting\s+{asset_pattern}',
            rf'short\s+{asset_pattern}\s+(?:with|at|@|from)',
            rf'entered\s+(?:a\s+)?short\s+(?:on\s+|in\s+)?{asset_pattern}',
            rf'short\s+trigger\s+(?:on\s+)?{asset_pattern}',
        ]

        # ========== EXIT PATTERNS ==========
        exit_patterns = [
            rf"tp'?d\s+.*?{asset_pattern}",
            rf'took\s+(?:some\s+)?profit[s]?\s+(?:on\s+|from\s+)?{asset_pattern}',
            rf'sold\s+(?:a\s+significant\s+amount\s+of\s+)?{asset_pattern}',
            rf'sold\s+(?:some\s+)?(?:more\s+)?(?:of\s+)?(?:my\s+)?{asset_pattern}',
            rf'closed\s+.*?longs?\s+(?:on\s+)?.*?{asset_pattern}',
            rf'closed\s+(?:my\s+)?{asset_pattern}',
            rf'exited\s+{asset_pattern}',
            rf'covered\s+(?:my\s+)?(?:\w+\s+)?shorts?\s+(?:on\s+)?{asset_pattern}',
            rf'(?:mostly\s+)?out\s+of\s+{asset_pattern}',
            rf'scaled\s+out\s+.*?{asset_pattern}',
        ]

        # False positive patterns to filter out
        false_positive_patterns = [
            rf'positioned\s+in\s+{asset_pattern}\s+and',
            rf'did\s+with\s+{asset_pattern}',
            rf'like\s+{asset_pattern}\s+did',
        ]

        found_signals = set()

        def is_false_positive(asset_name: str) -> bool:
            """Check if match is a false positive"""
            asset_lower = asset_name.lower()
            for fp_pattern in false_positive_patterns:
                fp_check = fp_pattern.replace(asset_pattern, f'({asset_lower})')
                if re.search(fp_check, content_lower):
                    return True
            return False

        # Check LONG patterns
        for pattern in long_patterns:
            matches = re.findall(pattern, content_lower)
            for match in matches:
                asset = match.upper()
                if asset in self.tracked_assets and (asset, 'LONG') not in found_signals:
                    if not is_false_positive(asset):
                        signals.append({
                            'timestamp': timestamp,
                            'asset': asset,
                            'action': 'LONG',
                            'raw_text': content[:200]
                        })
                        found_signals.add((asset, 'LONG'))

        # Check SHORT patterns
        for pattern in short_patterns:
            matches = re.findall(pattern, content_lower)
            for match in matches:
                asset = match.upper()
                if asset in self.tracked_assets and (asset, 'SHORT') not in found_signals:
                    signals.append({
                        'timestamp': timestamp,
                        'asset': asset,
                        'action': 'SHORT',
                        'raw_text': content[:200]
                    })
                    found_signals.add((asset, 'SHORT'))

        # Check EXIT patterns
        for pattern in exit_patterns:
            matches = re.findall(pattern, content_lower)
            for match in matches:
                asset = match.upper()
                if asset in self.tracked_assets and (asset, 'EXIT') not in found_signals:
                    signals.append({
                        'timestamp': timestamp,
                        'asset': asset,
                        'action': 'EXIT',
                        'raw_text': content[:200]
                    })
                    found_signals.add((asset, 'EXIT'))

        return signals

    def check_for_signals(self) -> List[dict]:
        """
        Poll Clickhouse and check for new trading signals

        Called by the main bot loop. Returns any new signals found.

        Returns:
            List of signal dicts with asset, action, timestamp
        """
        all_signals = []

        # Fetch new messages
        messages = self._fetch_new_messages()

        # Parse each message for signals
        for msg in messages:
            signals = self._parse_message(msg['content'], msg['timestamp'])
            if signals:
                for sig in signals:
                    print(f"[BH] Signal detected: {sig['action']} {sig['asset']}")
                    print(f"     Text: {sig['raw_text'][:100]}...")
                all_signals.extend(signals)

        return all_signals

    def should_enter(self, current_time: datetime, current_price: float,
                     asset: str = 'BTC') -> Tuple[bool, str]:
        """
        Check if we should enter a position for given asset

        Called by the main bot loop for each tracked asset.

        Args:
            current_time: Current timestamp
            current_price: Current asset price
            asset: Asset symbol (e.g., 'BTC', 'ETH')

        Returns:
            (should_enter, reason) tuple
        """
        # Check for pending signals for this asset
        if asset in self.pending_signals:
            signal = self.pending_signals[asset]

            if signal['action'] == 'LONG':
                # Clear the pending signal
                del self.pending_signals[asset]
                return True, f"BH Insights LONG signal: {signal['raw_text'][:100]}"

            elif signal['action'] == 'SHORT':
                del self.pending_signals[asset]
                return True, f"BH Insights SHORT signal: {signal['raw_text'][:100]}"

        return False, "No BH Insights signal"

    def should_exit(self, current_price: float, entry_price: float,
                    peak_price: float, asset: str = 'BTC',
                    position_type: str = 'long') -> Tuple[bool, str]:
        """
        Check if we should exit a position for given asset

        Args:
            current_price: Current asset price
            entry_price: Our entry price
            peak_price: Highest price since entry
            asset: Asset symbol
            position_type: 'long' or 'short'

        Returns:
            (should_exit, reason) tuple
        """
        # Check for EXIT signal for this asset
        if asset in self.pending_signals:
            signal = self.pending_signals[asset]

            if signal['action'] == 'EXIT':
                # Clear the pending signal
                del self.pending_signals[asset]
                return True, f"BH Insights EXIT signal: {signal['raw_text'][:100]}"

        # No signal-based exit
        profit_pct = ((current_price - entry_price) / entry_price) * 100
        if position_type == 'short':
            profit_pct = -profit_pct

        return False, f"Holding - {profit_pct:+.2f}% from entry, waiting for BH exit signal"

    def process_new_signals(self, signals: List[dict]):
        """
        Process new signals and queue them for entry/exit

        Called after check_for_signals() to store pending signals.

        Args:
            signals: List of signal dicts from check_for_signals()
        """
        for signal in signals:
            asset = signal['asset']
            action = signal['action']

            # Store the signal for the asset
            # If there's already a pending signal, the new one overrides
            self.pending_signals[asset] = signal
            print(f"[BH] Queued signal: {action} {asset}")

    def get_pending_signals(self) -> Dict[str, dict]:
        """Get all pending signals"""
        return self.pending_signals.copy()

    def clear_signal(self, asset: str):
        """Clear pending signal for an asset after it's been processed"""
        if asset in self.pending_signals:
            del self.pending_signals[asset]

    def reset_daily_state(self):
        """Reset daily state - called at midnight"""
        # For BH strategy, we don't reset signals daily
        # They persist until processed or manually cleared
        pass

    def __str__(self):
        return f"BHInsights(tracked={self.tracked_assets}, pending={len(self.pending_signals)})"


# Module testing
if __name__ == '__main__':
    import os
    from dotenv import load_dotenv

    # Load credentials from master file
    load_dotenv('/Users/chrisl/Claude Code/master-credentials.env')

    config = {
        'clickhouse_host': os.getenv('CLICKHOUSE_HOST', 'ch.ops.xexlab.com'),
        'clickhouse_port': int(os.getenv('CLICKHOUSE_PORT', 443)),
        'clickhouse_user': os.getenv('CLICKHOUSE_USER', 'dev_ado'),
        'clickhouse_password': os.getenv('CLICKHOUSE_PASSWORD', ''),
        'clickhouse_database': os.getenv('CLICKHOUSE_DATABASE', 'crush_ats'),
        'tracked_assets': ['BTC', 'ETH', 'SOL', 'HYPE'],
    }

    strategy = BHInsightsStrategy(config)
    print(f"Strategy: {strategy}")

    # Test fetching messages
    print("\nChecking for signals...")
    signals = strategy.check_for_signals()

    if signals:
        print(f"\nFound {len(signals)} signals:")
        for sig in signals:
            print(f"  {sig['action']} {sig['asset']} at {sig['timestamp']}")
    else:
        print("No signals found in last 24 hours")

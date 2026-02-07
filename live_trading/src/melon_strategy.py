"""
Melon Strategy - Live Trading for Pastel Degen Calls

Monitors Clickhouse for Melon's token calls in Pastel degen channel.
Trades on Solana via Jupiter aggregator.

Strategy:
- Entry: Buy at Rick bot's FDV when Melon posts an address
- Exit: Tiered exits at 2x, 5x, 10x (sell 33% at each target)

How it works:
1. Poll Clickhouse every 30 seconds for new Rick bot messages
2. Attribute calls to Melon using 5-second time window
3. Extract token address, FDV, ticker from Rick bot
4. Monitor price every 10 seconds for exit triggers
5. Execute tiered sells when targets hit
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pytz
import clickhouse_connect


class MelonStrategy:
    """
    Live trading strategy based on Melon's Pastel degen calls.

    Monitors Clickhouse for Rick bot messages, attributes them to Melon,
    and manages tiered exit positions.
    """

    def __init__(self, config: dict):
        """
        Initialize Melon Strategy

        Args:
            config: Strategy configuration containing:
                - clickhouse_host: Clickhouse server host
                - clickhouse_port: Clickhouse server port
                - clickhouse_user: Database username
                - clickhouse_password: Database password
                - clickhouse_database: Database name
                - poll_interval_seconds: How often to check for new signals
                - price_check_interval_seconds: How often to check prices
                - tranche_targets: List of exit multiples [2, 5, 10]
                - tranche_sizes: List of tranche sizes [0.33, 0.33, 0.34]
                - position_size_pct: Percentage of capital per trade
                - min_liquidity_usd: Minimum liquidity to trade
        """
        # Clickhouse connection settings
        self.ch_host = config.get('clickhouse_host', 'ch.ops.xexlab.com')
        self.ch_port = config.get('clickhouse_port', 443)
        self.ch_user = config.get('clickhouse_user', 'dev_ado')
        self.ch_password = config.get('clickhouse_password', '')
        self.ch_database = config.get('clickhouse_database', 'crush_ats')

        # Strategy settings
        self.poll_interval = config.get('poll_interval_seconds', 30)
        self.price_check_interval = config.get('price_check_interval_seconds', 10)
        self.tranche_targets = config.get('tranche_targets', [2, 5, 10])
        self.tranche_sizes = config.get('tranche_sizes', [0.33, 0.33, 0.34])
        self.position_size_pct = config.get('position_size_pct', 0.10)
        self.min_liquidity = config.get('min_liquidity_usd', 10000)

        # State tracking
        self.last_message_timestamp = None
        self.pending_signals: Dict[str, dict] = {}  # address -> signal info
        self.active_positions: Dict[str, dict] = {}  # address -> position info
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
            print(f"[Pastel Melon] Connected to Clickhouse: {self.ch_host}")
        except Exception as e:
            print(f"[Pastel Melon] Failed to connect to Clickhouse: {e}")
            self.client = None

    def _parse_rick_message(self, content: str) -> Optional[Dict]:
        """
        Extract token info from Rick bot message

        Rick bot format example:
        "Farmer Ben [976.3K/30.9K%] - BEN/SOL
        FDV: $976.3K ➡︎ ATH: $4.7M [2h]
        CA: 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"

        Args:
            content: Message text

        Returns:
            Dict with address, ticker, entry_fdv, chain or None if not parseable
        """
        if not content or not isinstance(content, str):
            return None

        info = {}

        # Token name and ticker - e.g., "Farmer Ben [976.3K/30.9K%] - BEN/SOL"
        ticker_match = re.search(r'-\s*(\w+)/(?:SOL|WETH|ETH|SUI)', content)
        if ticker_match:
            info['ticker'] = ticker_match.group(1)

        # FDV (market cap) - e.g., "FDV: $976.3K" or "FDV: 976.3K"
        fdv_match = re.search(r'FDV:\s*\$?([\d.]+)([KMB])?', content)
        if fdv_match:
            fdv_val = float(fdv_match.group(1))
            multiplier = {'K': 1000, 'M': 1000000, 'B': 1000000000}.get(fdv_match.group(2), 1)
            info['entry_fdv'] = fdv_val * multiplier

        # Contract address - Solana (32-44 chars base58) or ETH (0x + 40 hex)
        # Solana addresses: base58, typically 32-44 chars
        solana_match = re.search(r'([1-9A-HJ-NP-Za-km-z]{32,44}(?:pump)?)', content)
        eth_match = re.search(r'(0x[a-fA-F0-9]{40})', content)

        if solana_match:
            info['address'] = solana_match.group(1)
            info['chain'] = 'solana'
        elif eth_match:
            info['address'] = eth_match.group(1)
            info['chain'] = 'ethereum'

        # ATH - e.g., "ATH: $4.7M" - comes AFTER the arrow in FDV line
        # Format: "FDV: $X ➡︎ ATH: $Y [time]"
        ath_match = re.search(r'ATH:\s*\$?([\d.]+)([KMB])?', content)
        if ath_match:
            ath_val = float(ath_match.group(1))
            multiplier = {'K': 1000, 'M': 1000000, 'B': 1000000000}.get(ath_match.group(2), 1)
            info['ath'] = ath_val * multiplier

        # Must have address and FDV to be valid
        if info.get('address') and info.get('entry_fdv'):
            return info

        return None

    def _is_melon_call(self, rick_time: datetime, all_messages: List[dict]) -> Tuple[bool, Optional[str]]:
        """
        Check if a Rick bot message was triggered by Melon

        Looks for a message from Melon in the 5 seconds before Rick's response.

        Args:
            rick_time: Timestamp of Rick bot message
            all_messages: List of all recent messages

        Returns:
            (is_melon, caller_content) tuple
        """
        time_window = timedelta(seconds=5)

        for msg in all_messages:
            # Skip bot messages
            caller = msg.get('author', '').lower()
            if 'rick' in caller or 'bot' in caller:
                continue

            # Check if Melon posted just before
            if 'melon' in caller:
                msg_time = msg['timestamp']
                if msg_time < rick_time and (rick_time - msg_time) <= time_window:
                    return True, msg.get('content', '')[:100]

        return False, None

    def _fetch_new_messages(self) -> List[dict]:
        """
        Fetch new messages from Clickhouse since last check

        Returns:
            List of message dicts with timestamp, author, content
        """
        if not self.client:
            self._init_clickhouse()
            if not self.client:
                return []

        try:
            # Build query - get messages from Pastel degen channel
            if self.last_message_timestamp:
                # Add 1 second to avoid re-processing
                since_ts = self.last_message_timestamp + timedelta(seconds=1)
                query = f"""
                    SELECT created_at, raw, user_name, message_id
                    FROM messages
                    WHERE chat_name = 'Pastel'
                      AND sub_chat_name = '❗｜degen'
                      AND created_at > '{since_ts.strftime('%Y-%m-%d %H:%M:%S')}'
                      AND raw != ''
                    ORDER BY created_at ASC
                    LIMIT 100
                """
            else:
                # First run - only get messages from last 24 hours
                since_ts = datetime.now(pytz.UTC) - timedelta(hours=24)
                query = f"""
                    SELECT created_at, raw, user_name, message_id
                    FROM messages
                    WHERE chat_name = 'Pastel'
                      AND sub_chat_name = '❗｜degen'
                      AND created_at > '{since_ts.strftime('%Y-%m-%d %H:%M:%S')}'
                      AND raw != ''
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
                print(f"[Pastel Melon] Fetched {len(messages)} new messages")

            return messages

        except Exception as e:
            print(f"[Pastel Melon] Error fetching messages: {e}")
            return []

    def check_for_signals(self) -> List[dict]:
        """
        Poll Clickhouse and check for new Melon calls

        Called by the main bot loop. Returns any new signals found.

        Returns:
            List of signal dicts with address, ticker, entry_fdv, chain
        """
        signals = []

        # Fetch new messages
        messages = self._fetch_new_messages()
        if not messages:
            return []

        # Find Rick bot messages
        rick_messages = [m for m in messages if 'rick' in m.get('author', '').lower()]

        for rick_msg in rick_messages:
            # Parse Rick bot message for token info
            token_info = self._parse_rick_message(rick_msg['content'])
            if not token_info:
                continue

            # Only handle Solana tokens for now
            if token_info.get('chain') != 'solana':
                continue

            # Check if this was triggered by Melon
            is_melon, caller_content = self._is_melon_call(rick_msg['timestamp'], messages)

            if is_melon:
                signal = {
                    'address': token_info['address'],
                    'ticker': token_info.get('ticker', 'UNK'),
                    'entry_fdv': token_info['entry_fdv'],
                    'chain': token_info['chain'],
                    'timestamp': rick_msg['timestamp'],
                    'caller_content': caller_content,
                    'raw_text': rick_msg['content'][:200]
                }

                print(f"[Pastel Melon] Signal detected: {signal['ticker']} @ ${signal['entry_fdv']:,.0f} FDV")
                print(f"        Address: {signal['address'][:20]}...")
                signals.append(signal)

        return signals

    def process_new_signals(self, signals: List[dict]):
        """
        Store new signals for processing

        Args:
            signals: List of signal dicts from check_for_signals()
        """
        for signal in signals:
            address = signal['address']

            # Skip if already have active position in this token
            if address in self.active_positions:
                print(f"[Pastel Melon] Already in position for {signal['ticker']}, skipping")
                continue

            # Store as pending
            self.pending_signals[address] = signal
            print(f"[Pastel Melon] Queued signal: BUY {signal['ticker']}")

    def get_pending_signals(self) -> Dict[str, dict]:
        """Get all pending signals"""
        return self.pending_signals.copy()

    def clear_signal(self, address: str):
        """Clear pending signal after processing"""
        if address in self.pending_signals:
            del self.pending_signals[address]

    def create_position(self, address: str, entry_price: float, tokens_bought: float,
                       usdc_spent: float, signal: dict) -> Dict:
        """
        Create a new position with tiered exit tranches

        Args:
            address: Token address
            entry_price: Price per token at entry
            tokens_bought: Total tokens purchased
            usdc_spent: USD amount spent
            signal: Original signal dict

        Returns:
            Position dict
        """
        # Create tranches
        tranches = []
        remaining = tokens_bought

        for i, (target, size_pct) in enumerate(zip(self.tranche_targets, self.tranche_sizes)):
            if i < len(self.tranche_targets) - 1:
                tranche_size = tokens_bought * size_pct
            else:
                tranche_size = remaining  # Last tranche gets remainder

            tranches.append({
                'target_multiple': target,
                'size': tranche_size,
                'sold': False,
                'sold_at': None,
                'sold_price': None
            })
            remaining -= tranche_size

        position = {
            'address': address,
            'ticker': signal.get('ticker', 'UNK'),
            'chain': signal.get('chain', 'solana'),
            'entry_price': entry_price,
            'entry_fdv': signal.get('entry_fdv', 0),
            'total_size': tokens_bought,
            'remaining_size': tokens_bought,
            'usdc_spent': usdc_spent,
            'entry_time': datetime.now(pytz.UTC).isoformat(),
            'tranches': tranches,
            'last_price_check': None,
            'peak_price': entry_price,
            'status': 'active'
        }

        self.active_positions[address] = position
        print(f"[Pastel Melon] Position created: {position['ticker']}")
        print(f"        Entry: ${entry_price:.8f} | Size: {tokens_bought:,.2f} tokens")
        print(f"        Tranches: {[t['target_multiple'] for t in tranches]}x")

        return position

    def check_exit_targets(self, address: str, current_price: float) -> List[dict]:
        """
        Check if any tranches hit their exit targets

        Args:
            address: Token address
            current_price: Current token price

        Returns:
            List of tranches that should be sold
        """
        if address not in self.active_positions:
            return []

        position = self.active_positions[address]
        position['last_price_check'] = datetime.now(pytz.UTC).isoformat()

        # Update peak price
        if current_price > position['peak_price']:
            position['peak_price'] = current_price

        entry_price = position['entry_price']
        current_multiple = current_price / entry_price if entry_price > 0 else 0

        tranches_to_sell = []

        for tranche in position['tranches']:
            if tranche['sold']:
                continue

            if current_multiple >= tranche['target_multiple']:
                tranches_to_sell.append({
                    'target_multiple': tranche['target_multiple'],
                    'size': tranche['size'],
                    'current_price': current_price,
                    'current_multiple': current_multiple
                })

        return tranches_to_sell

    def record_tranche_exit(self, address: str, target_multiple: float,
                            sold_price: float, usdc_received: float):
        """
        Record that a tranche was sold

        Args:
            address: Token address
            target_multiple: Which tranche target was hit
            sold_price: Price at which tranche was sold
            usdc_received: USDC received from sale
        """
        if address not in self.active_positions:
            return

        position = self.active_positions[address]

        for tranche in position['tranches']:
            if tranche['target_multiple'] == target_multiple and not tranche['sold']:
                tranche['sold'] = True
                tranche['sold_at'] = datetime.now(pytz.UTC).isoformat()
                tranche['sold_price'] = sold_price
                tranche['usdc_received'] = usdc_received

                position['remaining_size'] -= tranche['size']

                print(f"[Pastel Melon] Tranche exit: {position['ticker']} @ {target_multiple}x")
                print(f"        Price: ${sold_price:.8f} | Received: ${usdc_received:.2f}")
                break

        # Check if all tranches are sold
        all_sold = all(t['sold'] for t in position['tranches'])
        if all_sold:
            position['status'] = 'closed'
            print(f"[Pastel Melon] Position fully closed: {position['ticker']}")

    def check_dead_token(self, address: str, current_fdv: float, liquidity: float) -> bool:
        """
        Check if a token is dead (should stop monitoring)

        Args:
            address: Token address
            current_fdv: Current FDV
            liquidity: Current liquidity

        Returns:
            True if token is dead
        """
        if address not in self.active_positions:
            return False

        # Token is dead if no liquidity or extremely low FDV
        if liquidity < 100 or current_fdv < 1000:
            position = self.active_positions[address]
            position['status'] = 'dead'
            print(f"[Pastel Melon] Token dead: {position['ticker']} (liquidity: ${liquidity:.0f})")
            return True

        return False

    def get_active_positions(self) -> Dict[str, dict]:
        """Get all active positions"""
        return {addr: pos for addr, pos in self.active_positions.items()
                if pos['status'] == 'active'}

    def get_position(self, address: str) -> Optional[dict]:
        """Get specific position"""
        return self.active_positions.get(address)

    def reset_daily_state(self):
        """Reset daily state - called at midnight"""
        # Melon strategy doesn't reset daily
        pass

    def __str__(self):
        active_count = len(self.get_active_positions())
        pending_count = len(self.pending_signals)
        return f"Melon(active={active_count}, pending={pending_count})"


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
        'tranche_targets': [2, 5, 10],
        'tranche_sizes': [0.33, 0.33, 0.34],
    }

    strategy = MelonStrategy(config)
    print(f"Strategy: {strategy}")

    # Test fetching messages
    print("\nChecking for Melon signals...")
    signals = strategy.check_for_signals()

    if signals:
        print(f"\nFound {len(signals)} signals:")
        for sig in signals:
            print(f"  {sig['ticker']} @ ${sig['entry_fdv']:,.0f} FDV")
            print(f"  Address: {sig['address'][:30]}...")
    else:
        print("No Melon signals found in last 24 hours")

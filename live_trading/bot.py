"""
Multi-Strategy Trading Bot
Main orchestrator that runs 24/7

Supports multiple strategies running simultaneously, each with:
- Its own capital allocation (fixed USD amount)
- Independent position tracking
- Individual entry/exit logic

How it works:
1. Load configuration and credentials
2. Initialize all strategy instances
3. Enter main loop:
   - Every 5 minutes: For each ENABLED strategy, check entry/exit
   - Every hour: Send heartbeat
   - On errors: Alert and pause
4. Loop forever (until manually stopped)
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict
import pytz
from dotenv import load_dotenv

# Add src to path
sys.path.append(str(Path(__file__).parent / 'src'))

from src.exchange import HyperLiquidClient
from src.strategy import OvernightRecoveryStrategy
from src.oi_strategy import OIStrategy
from src.bh_strategy import BHInsightsStrategy
from src.melon_strategy import MelonStrategy
from src.state_manager import StateManager
from src.notifier import TelegramNotifier
from src.risk_manager import RiskManager
from src.command_handler import CommandHandler

# Solana client - only imported if enabled
SolanaDEXClient = None


# Strategy registry - maps names to classes
STRATEGY_CLASSES = {
    'overnight': OvernightRecoveryStrategy,
    'oi': OIStrategy,
    'bh': BHInsightsStrategy,
    'pastel_melon': MelonStrategy
}

STRATEGY_DESCRIPTIONS = {
    'overnight': 'Buy at 3 PM EST, trailing stop 1%',
    'oi': 'Open Interest signals, never sell at loss',
    'bh': 'BH Insights Discord signals (multi-asset)',
    'pastel_melon': 'Pastel Melon - Solana memecoin calls'
}


class TradingBot:
    """
    Multi-strategy trading bot orchestrator

    Manages multiple strategies, each with its own capital pool.
    """

    def __init__(self, config_path: str = './config.json'):
        """
        Initialize trading bot

        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path

        # Load configuration
        print("Loading configuration...")
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        # Load environment variables (.env file)
        load_dotenv()

        # Setup logging
        self._setup_logging()

        # Initialize components
        print("Initializing components...")
        self._initialize_components()

        # Bot state
        self.is_running = True
        self.is_paused = False
        self.last_heartbeat = None
        self.loop_count = 0

        # Track balance for daily reset
        self.daily_start_balance = None
        self.last_daily_reset = None

        self.logger.info("Bot initialized successfully")

    def _setup_logging(self):
        """Setup logging to file and console"""
        log_dir = Path('./logs')
        log_dir.mkdir(exist_ok=True)

        self.logger = logging.getLogger('TradingBot')
        self.logger.setLevel(logging.INFO)

        # Avoid duplicate handlers
        if not self.logger.handlers:
            log_file = log_dir / f"trades_{datetime.now().strftime('%Y-%m-%d')}.log"
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.INFO)

            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)

            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)

            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

    def _initialize_components(self):
        """Initialize all bot components"""
        # Exchange client (HyperLiquid for perps)
        self.exchange = HyperLiquidClient(
            api_key=os.getenv('HYPERLIQUID_API_KEY'),
            api_secret=os.getenv('HYPERLIQUID_API_SECRET'),
            testnet=self.config['exchange']['testnet'],
            retry_attempts=self.config['exchange']['retry_attempts'],
            timeout=self.config['exchange']['request_timeout_seconds']
        )
        self.logger.info(f"Exchange: {'TESTNET' if self.config['exchange']['testnet'] else 'MAINNET'}")

        # Solana DEX client (for Pastel Melon strategy)
        self.solana_client = None
        if self.config.get('solana', {}).get('enabled'):
            try:
                global SolanaDEXClient
                from src.solana_client import SolanaDEXClient
                self.solana_client = SolanaDEXClient(
                    private_key=os.getenv('SOLANA_PRIVATE_KEY'),
                    rpc_url=os.getenv('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com'),
                    slippage_bps=self.config.get('solana', {}).get('slippage_bps', 100),
                    priority_fee_lamports=self.config.get('solana', {}).get('priority_fee_lamports', 100000)
                )
                self.logger.info("Solana DEX client initialized (high priority fees enabled)")
            except Exception as e:
                self.logger.error(f"Failed to initialize Solana client: {e}")

        # Initialize ALL strategy instances
        self.strategies: Dict[str, object] = {}
        for name, strategy_config in self.config.get('strategies', {}).items():
            if name in STRATEGY_CLASSES:
                strategy_class = STRATEGY_CLASSES[name]
                params = strategy_config.get('params', {}).copy()

                # Special handling for BH strategy - inject Clickhouse password from env
                if name == 'bh':
                    params['clickhouse_password'] = os.getenv('CLICKHOUSE_PASSWORD', '')

                # Special handling for Pastel Melon strategy - inject Clickhouse password from env
                if name == 'pastel_melon':
                    params['clickhouse_password'] = os.getenv('CLICKHOUSE_PASSWORD', '')

                self.strategies[name] = strategy_class(params)
                self.logger.info(f"Strategy loaded: {name}")

        # State manager
        self.state_manager = StateManager('./state')
        self.state_manager.load_state()
        self.logger.info(f"State: {self.state_manager}")

        # Notifier
        self.notifier = TelegramNotifier(
            bot_token=os.getenv('TELEGRAM_BOT_TOKEN'),
            chat_id=os.getenv('TELEGRAM_CHAT_ID'),
            enabled=True
        )
        self.logger.info("Telegram notifier initialized")

        # Risk manager
        self.risk_manager = RiskManager(self.config['risk'])
        self.logger.info(f"Risk Manager: {self.risk_manager}")

        # Command handler (for Telegram commands)
        self.command_handler = CommandHandler(self, self.config)
        self.logger.info("Command handler initialized")

        # Register bot commands with Telegram (for dropdown menu)
        self.notifier.set_bot_commands()

        # Start listening for Telegram commands in background
        self.notifier.start_listening_for_commands(self.command_handler)
        self.logger.info("Telegram command listener started")

    def save_config(self):
        """Save current config to disk"""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)

    def _check_stop_file(self) -> bool:
        """Check if STOP file exists (emergency shutdown)"""
        stop_file = Path('./STOP')
        if stop_file.exists():
            self.logger.warning("STOP file detected - shutting down")
            return True
        return False

    def _handle_bh_strategy(self, current_time: datetime):
        """
        Handle BH Insights strategy specially - it monitors Clickhouse for signals
        and can trade multiple assets.

        Called each loop iteration to:
        1. Check Clickhouse for new messages
        2. Parse signals from new messages
        3. Execute any pending signals
        """
        strategy = self.strategies.get('bh')
        if not strategy:
            return

        # Check for new signals from Clickhouse
        try:
            new_signals = strategy.check_for_signals()
            if new_signals:
                strategy.process_new_signals(new_signals)
        except Exception as e:
            self.logger.error(f"[BH] Error checking signals: {e}")

        # Get pending signals
        pending = strategy.get_pending_signals()

        for asset, signal in pending.items():
            action = signal['action']

            # Create position key for this asset under BH strategy
            position_key = f"bh_{asset.lower()}"

            if action in ['LONG', 'SHORT']:
                # Check if already in position for this asset
                if self.state_manager.is_in_position(position_key):
                    self.logger.info(f"[BH] Already in {asset} position, ignoring signal")
                    strategy.clear_signal(asset)
                    continue

                # Get allocated capital for BH strategy
                allocated_capital = self.state_manager.get_strategy_capital('bh')
                if allocated_capital <= 0:
                    self.logger.warning(f"[BH] No capital allocated")
                    continue

                # Calculate per-asset capital (divide by number of tracked assets)
                per_asset_capital = allocated_capital / len(strategy.tracked_assets)
                position_size_usd = per_asset_capital * 0.999  # Leave 0.1% for fees

                # Place order
                self.logger.info(f"[BH] Placing {action} order on {asset} for ${position_size_usd:,.0f}")

                try:
                    # Get current price
                    current_price = self.exchange.get_price(asset)

                    # Place order (LONG = BUY, SHORT = SELL to open)
                    side = 'BUY' if action == 'LONG' else 'SELL'
                    order_id, fill_price, fill_size = self.exchange.place_market_order(
                        side, position_size_usd, asset
                    )

                    # Ensure position key exists
                    self.state_manager.ensure_strategy_exists(position_key)
                    self.state_manager.enable_strategy(position_key, per_asset_capital)

                    # Store position type (long/short) in state
                    self.state_manager.state['strategies'][position_key]['position_type'] = action.lower()

                    # Record entry
                    self.state_manager.enter_position(
                        strategy_name=position_key,
                        entry_time=current_time,
                        entry_price=fill_price,
                        size_btc=fill_size,  # Actually asset size, not BTC
                        size_usd=position_size_usd
                    )

                    # Clear the pending signal
                    strategy.clear_signal(asset)

                    # Send notification
                    emoji = "📈" if action == 'LONG' else "📉"
                    self.notifier.send_message(
                        f"{emoji} <b>[BH] {action} {asset}</b>\n\n"
                        f"<b>Price:</b> ${fill_price:,.2f}\n"
                        f"<b>Size:</b> {fill_size:.4f} {asset} (${position_size_usd:,.0f})\n"
                        f"<b>Signal:</b> {signal['raw_text'][:100]}..."
                    )

                    self.logger.info(f"[BH] {action} {asset}: {fill_size:.4f} @ ${fill_price:,.2f}")

                except Exception as e:
                    self.logger.error(f"[BH] Failed to place {action} order on {asset}: {e}")
                    self.notifier.send_error_alert(f"[BH] {action} {asset} failed: {str(e)}", None)

            elif action == 'EXIT':
                # Check if in position for this asset
                position_key = f"bh_{asset.lower()}"
                if not self.state_manager.is_in_position(position_key):
                    self.logger.info(f"[BH] No {asset} position to exit")
                    strategy.clear_signal(asset)
                    continue

                # Get position details
                position = self.state_manager.get_position_details(position_key)
                entry_price = position['entry_price']
                size = position['size_btc']  # Actually asset size
                position_type = self.state_manager.state['strategies'][position_key].get('position_type', 'long')

                # Place exit order
                try:
                    current_price = self.exchange.get_price(asset)

                    # EXIT: reverse of position (LONG exit = SELL, SHORT exit = BUY)
                    side = 'SELL' if position_type == 'long' else 'BUY'
                    order_id, fill_price, fill_size = self.exchange.place_market_order(
                        side, size * current_price, asset
                    )

                    # Calculate profit
                    if position_type == 'long':
                        profit_pct = ((fill_price - entry_price) / entry_price) * 100
                    else:
                        profit_pct = ((entry_price - fill_price) / entry_price) * 100

                    profit_usd = (fill_price - entry_price) * size
                    if position_type == 'short':
                        profit_usd = -profit_usd

                    # Record exit
                    self.state_manager.exit_position(
                        strategy_name=position_key,
                        exit_time=current_time,
                        exit_price=fill_price,
                        profit_pct=profit_pct
                    )

                    # Clear the pending signal
                    strategy.clear_signal(asset)

                    # Send notification
                    emoji = "🟢" if profit_pct >= 0 else "🔴"
                    self.notifier.send_message(
                        f"{emoji} <b>[BH] EXIT {asset}</b>\n\n"
                        f"<b>Entry:</b> ${entry_price:,.2f}\n"
                        f"<b>Exit:</b> ${fill_price:,.2f}\n"
                        f"<b>P&L:</b> {profit_pct:+.2f}% (${profit_usd:+,.2f})\n"
                        f"<b>Signal:</b> {signal['raw_text'][:100]}..."
                    )

                    self.logger.info(f"[BH] EXIT {asset}: ${fill_price:,.2f} ({profit_pct:+.2f}%)")

                except Exception as e:
                    self.logger.error(f"[BH] Failed to exit {asset}: {e}")
                    self.notifier.send_error_alert(f"[BH] EXIT {asset} failed: {str(e)}", None)

    def _handle_melon_strategy(self, current_time: datetime):
        """
        Handle Pastel Melon strategy - Solana DEX trading based on Pastel degen calls.

        Trades on Solana via Jupiter aggregator (not HyperLiquid).

        Called each loop iteration to:
        1. Check Clickhouse for new Melon calls
        2. Parse signals from Rick bot responses
        3. Execute buys for new signals
        4. Monitor positions for tiered exits (2x, 5x, 10x)
        """
        strategy = self.strategies.get('pastel_melon')
        if not strategy:
            return

        if not self.solana_client:
            self.logger.warning("[Pastel Melon] Solana client not initialized - check config")
            return

        # Check for new signals from Clickhouse
        try:
            new_signals = strategy.check_for_signals()
            if new_signals:
                strategy.process_new_signals(new_signals)
        except Exception as e:
            self.logger.error(f"[Pastel Melon] Error checking signals: {e}")

        # Get pending signals and process them
        pending = strategy.get_pending_signals()

        for address, signal in pending.items():
            # Skip if already in position
            if address in strategy.active_positions:
                strategy.clear_signal(address)
                continue

            # Get allocated capital for Pastel Melon strategy
            allocated_capital = self.state_manager.get_strategy_capital('pastel_melon')
            if allocated_capital <= 0:
                self.logger.warning("[Pastel Melon] No capital allocated")
                continue

            # Calculate position size
            position_size_pct = strategy.position_size_pct
            usdc_to_spend = allocated_capital * position_size_pct * 0.999  # Leave 0.1% for fees

            # Check liquidity
            try:
                token_info = self.solana_client.get_token_info(address)
                if token_info['liquidity'] < strategy.min_liquidity:
                    self.logger.info(f"[Pastel Melon] Skipping {signal['ticker']} - low liquidity: ${token_info['liquidity']:,.0f}")
                    strategy.clear_signal(address)
                    continue
            except Exception as e:
                self.logger.error(f"[Pastel Melon] Failed to get token info for {address}: {e}")
                strategy.clear_signal(address)
                continue

            # Execute buy
            self.logger.info(f"[Pastel Melon] Buying {signal['ticker']} for ${usdc_to_spend:,.0f}")

            try:
                tx_sig, fill_price, tokens_received = self.solana_client.buy_token(
                    token_address=address,
                    usdc_amount=usdc_to_spend,
                    min_liquidity=strategy.min_liquidity
                )

                # Create position with tranches
                position = strategy.create_position(
                    address=address,
                    entry_price=fill_price,
                    tokens_bought=tokens_received,
                    usdc_spent=usdc_to_spend,
                    signal=signal
                )

                # Clear the pending signal
                strategy.clear_signal(address)

                # Send notification
                self.notifier.send_message(
                    f"🍈 <b>[PASTEL MELON] BUY {signal['ticker']}</b>\n\n"
                    f"<b>Price:</b> ${fill_price:.8f}\n"
                    f"<b>Size:</b> {tokens_received:,.2f} tokens (${usdc_to_spend:,.0f})\n"
                    f"<b>FDV at call:</b> ${signal['entry_fdv']:,.0f}\n"
                    f"<b>Targets:</b> 2x, 5x, 10x\n"
                    f"<b>TX:</b> {tx_sig[:16]}..."
                )

                self.logger.info(f"[Pastel Melon] BUY {signal['ticker']}: {tokens_received:,.2f} @ ${fill_price:.8f}")

            except Exception as e:
                self.logger.error(f"[Pastel Melon] Failed to buy {signal['ticker']}: {e}")
                self.notifier.send_error_alert(f"[Pastel Melon] BUY {signal['ticker']} failed: {str(e)}", None)
                strategy.clear_signal(address)

        # Check exit targets for active positions
        active_positions = strategy.get_active_positions()

        for address, position in active_positions.items():
            try:
                # Get current price
                current_price = self.solana_client.get_price(address)
                token_info = self.solana_client.get_token_info(address)

                # Check if token is dead
                if strategy.check_dead_token(address, token_info['fdv'], token_info['liquidity']):
                    self.notifier.send_message(
                        f"💀 <b>[MELON] TOKEN DEAD: {position['ticker']}</b>\n\n"
                        f"<b>Entry:</b> ${position['entry_price']:.8f}\n"
                        f"<b>Spent:</b> ${position['usdc_spent']:,.0f}\n"
                        f"<b>Liquidity:</b> ${token_info['liquidity']:.0f}"
                    )
                    continue

                # Check which tranches to sell
                tranches_to_sell = strategy.check_exit_targets(address, current_price)

                for tranche in tranches_to_sell:
                    target = tranche['target_multiple']
                    size = tranche['size']

                    self.logger.info(f"[Pastel Melon] Selling tranche {target}x for {position['ticker']}")

                    try:
                        tx_sig, sell_price, usdc_received = self.solana_client.sell_token(
                            token_address=address,
                            token_amount=size
                        )

                        # Record the exit
                        strategy.record_tranche_exit(
                            address=address,
                            target_multiple=target,
                            sold_price=sell_price,
                            usdc_received=usdc_received
                        )

                        # Calculate profit
                        entry_value = size * position['entry_price']
                        profit_usd = usdc_received - entry_value
                        profit_pct = (profit_usd / entry_value) * 100 if entry_value > 0 else 0

                        emoji = "🟢" if profit_pct >= 0 else "🔴"
                        self.notifier.send_message(
                            f"{emoji} <b>[MELON] {target}x EXIT {position['ticker']}</b>\n\n"
                            f"<b>Entry:</b> ${position['entry_price']:.8f}\n"
                            f"<b>Exit:</b> ${sell_price:.8f}\n"
                            f"<b>Size:</b> {size:,.2f} tokens\n"
                            f"<b>Received:</b> ${usdc_received:,.2f}\n"
                            f"<b>P&L:</b> {profit_pct:+.1f}% (${profit_usd:+,.2f})"
                        )

                        self.logger.info(f"[Pastel Melon] EXIT {position['ticker']} tranche {target}x: ${sell_price:.8f} (+{profit_pct:.1f}%)")

                    except Exception as e:
                        self.logger.error(f"[Pastel Melon] Failed to sell tranche {target}x for {position['ticker']}: {e}")
                        self.notifier.send_error_alert(
                            f"[Pastel Melon] SELL {position['ticker']} {target}x failed: {str(e)}", None
                        )

            except Exception as e:
                self.logger.error(f"[Pastel Melon] Error checking position {address}: {e}")

    def _handle_strategy_entry(self, strategy_name: str, strategy, current_price: float, current_time: datetime):
        """
        Handle entry logic for a specific strategy

        Args:
            strategy_name: Name of the strategy
            strategy: Strategy instance
            current_price: Current BTC price
            current_time: Current timestamp
        """
        # Check if already in position for this strategy
        if self.state_manager.is_in_position(strategy_name):
            return

        # Get allocated capital for this strategy
        allocated_capital = self.state_manager.get_strategy_capital(strategy_name)
        if allocated_capital <= 0:
            return

        # Check if should enter
        should_enter, reason = strategy.should_enter(current_time, current_price)

        self.logger.info(f"[{strategy_name}] Entry check: {should_enter} - {reason}")

        # Record entry check
        if not reason.startswith("Not entry hour") and not reason.startswith("Cooldown"):
            self.state_manager.record_entry_check(strategy_name, current_time, should_enter, reason)

        if not should_enter:
            return

        # Check risk conditions
        is_safe, risk_reason = self.risk_manager.should_allow_entry(
            current_balance=allocated_capital,
            initial_balance=allocated_capital,
            consecutive_losses=self.state_manager.get_risk_metrics(strategy_name).get('consecutive_losses', 0),
            last_data_update=current_time
        )

        if not is_safe:
            self.logger.warning(f"[{strategy_name}] Entry blocked by risk manager: {risk_reason}")
            return

        # Use the allocated capital for position size
        position_size_usd = allocated_capital * 0.999  # Leave 0.1% for fees

        # Place order
        self.logger.info(f"[{strategy_name}] Placing BUY order for ${position_size_usd:,.0f}")

        try:
            order_id, fill_price, fill_size = self.exchange.place_market_order(
                'BUY', position_size_usd
            )

            # Update state
            self.state_manager.enter_position(
                strategy_name=strategy_name,
                entry_time=current_time,
                entry_price=fill_price,
                size_btc=fill_size,
                size_usd=position_size_usd
            )

            # Send notification
            self.notifier.send_message(
                f"📈 <b>[{strategy_name.upper()}] ENTRY</b>\n\n"
                f"<b>Price:</b> ${fill_price:,.2f}\n"
                f"<b>Size:</b> {fill_size:.4f} BTC (${position_size_usd:,.0f})\n"
                f"<b>Time:</b> {current_time.strftime('%H:%M UTC')}\n"
                f"<b>Reason:</b> {reason[:100]}"
            )

            self.logger.info(f"[{strategy_name}] ENTRY: {fill_size:.4f} BTC @ ${fill_price:,.2f}")

        except Exception as e:
            self.logger.error(f"[{strategy_name}] Failed to place entry order: {e}")
            self.notifier.send_error_alert(
                f"[{strategy_name}] Entry order failed: {str(e)}",
                None
            )

    def _handle_strategy_exit(self, strategy_name: str, strategy, current_price: float, current_time: datetime):
        """
        Handle exit logic for a specific strategy

        Args:
            strategy_name: Name of the strategy
            strategy: Strategy instance
            current_price: Current BTC price
            current_time: Current timestamp
        """
        # Get position details for this strategy
        position = self.state_manager.get_position_details(strategy_name)
        if not position:
            return

        entry_price = position['entry_price']
        peak_price = position['peak_price']
        size_btc = position['size_btc']

        # Update peak price
        new_peak = self.state_manager.update_peak_price(strategy_name, current_price)
        if new_peak and new_peak > peak_price:
            self.logger.info(f"[{strategy_name}] New peak: ${new_peak:,.2f}")
            peak_price = new_peak

        # Check if should exit
        should_exit, reason = strategy.should_exit(current_price, entry_price, peak_price)

        self.logger.info(f"[{strategy_name}] Exit check: {should_exit} - {reason}")

        if not should_exit:
            return

        # Place sell order
        self.logger.info(f"[{strategy_name}] Placing SELL order for {size_btc:.4f} BTC")

        try:
            order_id, fill_price, fill_size = self.exchange.place_market_order(
                'SELL', size_btc * current_price
            )

            # Calculate profit
            profit_pct = ((fill_price - entry_price) / entry_price) * 100
            profit_usd = (fill_price - entry_price) * size_btc

            # Update state
            self.state_manager.exit_position(
                strategy_name=strategy_name,
                exit_time=current_time,
                exit_price=fill_price,
                profit_pct=profit_pct
            )

            # Send notification
            emoji = "🟢" if profit_pct >= 0 else "🔴"
            self.notifier.send_message(
                f"{emoji} <b>[{strategy_name.upper()}] EXIT</b>\n\n"
                f"<b>Entry:</b> ${entry_price:,.2f}\n"
                f"<b>Exit:</b> ${fill_price:,.2f}\n"
                f"<b>P&L:</b> {profit_pct:+.2f}% (${profit_usd:+,.2f})\n"
                f"<b>Reason:</b> {reason[:100]}"
            )

            self.logger.info(f"[{strategy_name}] EXIT: {fill_size:.4f} BTC @ ${fill_price:,.2f} ({profit_pct:+.2f}%)")

        except Exception as e:
            self.logger.error(f"[{strategy_name}] Failed to place exit order: {e}")
            self.notifier.send_error_alert(
                f"[{strategy_name}] Exit order failed: {str(e)}",
                position
            )

    def _send_heartbeat(self, current_price: float):
        """Send daily heartbeat (once per day)"""
        now = datetime.now(pytz.UTC)

        if self.last_heartbeat:
            time_since = (now - self.last_heartbeat).total_seconds()
            # Only send once per day (86400 seconds) unless in position
            if time_since < 86400 and not self.state_manager.is_in_position():
                return

        # Prepare state for heartbeat
        positions = self.state_manager.get_all_positions()
        state = {
            'current_price': current_price,
            'positions': positions,
            'enabled_strategies': self.state_manager.get_enabled_strategies()
        }

        self.notifier.send_heartbeat(state)
        self.last_heartbeat = now

    def _check_daily_reset(self):
        """Check if we need to reset daily statistics"""
        now_est = datetime.now(pytz.timezone('America/New_York'))
        current_date = now_est.date()

        if self.last_daily_reset is None:
            self.last_daily_reset = current_date
            balance = self.exchange.get_account_balance()
            self.daily_start_balance = balance
            self.risk_manager.reset_daily_limits(balance)
            return

        if current_date > self.last_daily_reset:
            self.logger.info(f"Daily reset triggered - new day: {current_date}")
            balance = self.exchange.get_account_balance()
            self.daily_start_balance = balance
            self.risk_manager.reset_daily_limits(balance)
            self.state_manager.reset_daily_stats()

            # Reset daily state for all strategies
            for strategy in self.strategies.values():
                if hasattr(strategy, 'reset_daily_state'):
                    strategy.reset_daily_state()

            self.last_daily_reset = current_date

    def run_loop_iteration(self):
        """
        Run one iteration of the main loop

        For each enabled strategy:
        - If in position: check exit
        - If not in position: check entry
        """
        self.loop_count += 1
        current_time = datetime.now(pytz.UTC)

        self.logger.info(f"=== Loop {self.loop_count} - {current_time.strftime('%Y-%m-%d %H:%M:%S UTC')} ===")

        try:
            if self._check_stop_file():
                self.is_running = False
                return

            if self.is_paused:
                self.logger.warning("Bot is PAUSED - use /enable to resume")
                return

            self._check_daily_reset()

            # Get current price
            current_price = self.exchange.get_btc_price()
            self.logger.info(f"BTC Price: ${current_price:,.2f}")

            # Get enabled strategies
            enabled_strategies = self.state_manager.get_enabled_strategies()

            if not enabled_strategies:
                self.logger.info("No strategies enabled")
            else:
                self.logger.info(f"Enabled strategies: {', '.join(enabled_strategies)}")

            # Handle BH strategy specially (if enabled) - it has its own signal loop
            if 'bh' in enabled_strategies and 'bh' in self.strategies:
                self._handle_bh_strategy(current_time)

            # Handle Pastel Melon strategy specially (if enabled) - it trades on Solana DEX
            if 'pastel_melon' in enabled_strategies and 'pastel_melon' in self.strategies:
                self._handle_melon_strategy(current_time)

            # Process each enabled strategy (except BH and Pastel Melon which are handled above)
            for strategy_name in enabled_strategies:
                if strategy_name in ('bh', 'pastel_melon'):
                    continue  # Handled above

                if strategy_name not in self.strategies:
                    self.logger.warning(f"Strategy {strategy_name} enabled but not loaded")
                    continue

                strategy = self.strategies[strategy_name]

                # Check if in position for this strategy
                if self.state_manager.is_in_position(strategy_name):
                    self._handle_strategy_exit(strategy_name, strategy, current_price, current_time)
                else:
                    self._handle_strategy_entry(strategy_name, strategy, current_price, current_time)

            # Heartbeat disabled - only send alerts on entries/exits/errors
            # self._send_heartbeat(current_price)

        except Exception as e:
            self.logger.error(f"ERROR in loop iteration: {e}", exc_info=True)
            self.notifier.send_error_alert(
                f"Loop error: {str(e)}",
                None
            )
            self.is_paused = True

    # ===== TELEGRAM COMMAND METHODS =====

    def enable_trading(self):
        """Enable trading (unpause bot)"""
        self.is_paused = False
        self.logger.info("Trading ENABLED via Telegram command")

    def disable_trading(self):
        """Disable trading (pause bot)"""
        self.is_paused = True
        self.logger.info("Trading DISABLED via Telegram command")

    def enable_strategy(self, strategy_name: str, capital_usd: float) -> str:
        """
        Enable a strategy with allocated capital

        Args:
            strategy_name: Name of strategy to enable
            capital_usd: USD amount to allocate

        Returns:
            Status message
        """
        if strategy_name not in STRATEGY_CLASSES:
            available = ', '.join(STRATEGY_CLASSES.keys())
            return f"Unknown strategy: {strategy_name}\n\nAvailable: {available}"

        # Check total allocation doesn't exceed balance
        current_total = self.state_manager.get_total_allocated_capital()
        try:
            account_balance = self.exchange.get_account_balance()
        except:
            account_balance = None

        if account_balance and (current_total + capital_usd) > account_balance:
            return (f"Cannot allocate ${capital_usd:,.0f}\n\n"
                    f"Current allocation: ${current_total:,.0f}\n"
                    f"Account balance: ${account_balance:,.0f}\n"
                    f"Available: ${account_balance - current_total:,.0f}")

        # Enable the strategy
        self.state_manager.enable_strategy(strategy_name, capital_usd)

        # Update config
        if 'strategies' not in self.config:
            self.config['strategies'] = {}
        if strategy_name not in self.config['strategies']:
            self.config['strategies'][strategy_name] = {}
        self.config['strategies'][strategy_name]['enabled'] = True
        self.config['strategies'][strategy_name]['allocated_capital_usd'] = capital_usd
        self.save_config()

        self.logger.info(f"Strategy '{strategy_name}' enabled with ${capital_usd:,.0f}")

        return (f"Strategy <b>{strategy_name}</b> enabled\n\n"
                f"<b>Allocated Capital:</b> ${capital_usd:,.0f}\n"
                f"<b>Description:</b> {STRATEGY_DESCRIPTIONS.get(strategy_name, 'N/A')}")

    def reallocate_strategy(self, strategy_name: str, new_capital: float) -> str:
        """
        Change the allocated capital for a running strategy

        Unlike enable_strategy, this accounts for the existing allocation
        so the balance check is accurate.

        Args:
            strategy_name: Name of strategy to reallocate
            new_capital: New USD amount to allocate

        Returns:
            Status message
        """
        if strategy_name not in STRATEGY_CLASSES:
            available = ', '.join(STRATEGY_CLASSES.keys())
            return f"Unknown strategy: {strategy_name}\n\nAvailable: {available}"

        # Get current allocation for this strategy
        current_allocation = self.state_manager.get_strategy_capital(strategy_name)

        # Check total allocation doesn't exceed balance
        # Subtract current allocation since it will be replaced
        current_total = self.state_manager.get_total_allocated_capital()
        other_strategies_total = current_total - current_allocation

        try:
            account_balance = self.exchange.get_account_balance()
        except:
            account_balance = None

        if account_balance and (other_strategies_total + new_capital) > account_balance:
            available = account_balance - other_strategies_total
            return (f"Cannot allocate ${new_capital:,.0f}\n\n"
                    f"Account balance: ${account_balance:,.0f}\n"
                    f"Other strategies: ${other_strategies_total:,.0f}\n"
                    f"Available: ${available:,.0f}")

        # Update the allocation
        old_capital = current_allocation
        self.state_manager.enable_strategy(strategy_name, new_capital)

        # Update config
        if 'strategies' in self.config and strategy_name in self.config['strategies']:
            self.config['strategies'][strategy_name]['allocated_capital_usd'] = new_capital
        self.save_config()

        self.logger.info(f"Strategy '{strategy_name}' reallocated: ${old_capital:,.0f} → ${new_capital:,.0f}")

        return (f"Strategy <b>{strategy_name}</b> reallocated\n\n"
                f"<b>Previous:</b> ${old_capital:,.0f}\n"
                f"<b>New:</b> ${new_capital:,.0f}")

    def disable_strategy(self, strategy_name: str) -> str:
        """
        Disable a strategy

        Args:
            strategy_name: Name of strategy to disable

        Returns:
            Status message
        """
        # Check if in position
        if self.state_manager.is_in_position(strategy_name):
            position = self.state_manager.get_position_details(strategy_name)
            return (f"Cannot disable - strategy has open position\n\n"
                    f"Position: {position['size_btc']:.4f} BTC @ ${position['entry_price']:,.0f}\n\n"
                    f"Close position first with /close {strategy_name}")

        self.state_manager.disable_strategy(strategy_name)

        # Update config
        if 'strategies' in self.config and strategy_name in self.config['strategies']:
            self.config['strategies'][strategy_name]['enabled'] = False
        self.save_config()

        self.logger.info(f"Strategy '{strategy_name}' disabled")

        return f"Strategy <b>{strategy_name}</b> disabled"

    def emergency_close_position(self, strategy_name: str = None) -> str:
        """
        Force close position(s)

        Args:
            strategy_name: If provided, close only this strategy's position.
                          If None, close all positions.

        Returns:
            Status message
        """
        if strategy_name:
            # Close specific strategy's position
            position = self.state_manager.get_position_details(strategy_name)
            if not position:
                return f"No position for strategy: {strategy_name}"

            return self._close_position(strategy_name, position)
        else:
            # Close all positions
            positions = self.state_manager.get_all_positions()
            if not positions:
                return "No positions to close"

            results = []
            for pos in positions:
                result = self._close_position(pos['strategy'], pos)
                results.append(result)

            return "\n\n".join(results)

    def _close_position(self, strategy_name: str, position: dict) -> str:
        """Close a specific position"""
        try:
            size_btc = position['size_btc']
            entry_price = position['entry_price']

            current_price = self.exchange.get_btc_price()

            profit_pct = ((current_price - entry_price) / entry_price) * 100
            profit_usd = (current_price - entry_price) * size_btc

            self.logger.info(f"[{strategy_name}] Emergency close: Selling {size_btc:.4f} BTC")
            order_id, fill_price, fill_size = self.exchange.place_market_order(
                'SELL',
                size_btc * current_price
            )

            self.state_manager.exit_position(
                strategy_name=strategy_name,
                exit_time=datetime.now(pytz.UTC),
                exit_price=fill_price,
                profit_pct=profit_pct
            )

            self.logger.info(f"[{strategy_name}] Emergency close completed")

            emoji = "🟢" if profit_pct >= 0 else "🔴"
            return (f"{emoji} <b>[{strategy_name.upper()}] CLOSED</b>\n\n"
                    f"<b>Entry:</b> ${entry_price:,.2f}\n"
                    f"<b>Exit:</b> ${fill_price:,.2f}\n"
                    f"<b>P&L:</b> {profit_pct:+.2f}% (${profit_usd:+,.2f})")

        except Exception as e:
            self.logger.error(f"[{strategy_name}] Emergency close failed: {e}")
            return f"Close failed for {strategy_name}: {str(e)}"

    def get_strategies_summary(self) -> list:
        """Get summary of all strategies for display"""
        summaries = []
        for name in STRATEGY_CLASSES.keys():
            state = self.state_manager.get_strategy_state(name)
            summaries.append({
                'name': name,
                'description': STRATEGY_DESCRIPTIONS.get(name, ''),
                'enabled': state.get('enabled', False),
                'allocated_capital_usd': state.get('allocated_capital_usd', 0),
                'in_position': state.get('in_position', False),
                'entry_price': state.get('entry_price'),
                'position_size_btc': state.get('position_size_btc')
            })
        return summaries

    def switch_account(self, account_name: str) -> str:
        """Switch to different HyperLiquid account"""
        if self.state_manager.is_in_position():
            return "Cannot switch account - close all positions first"

        try:
            account_key_var = f"{account_name.upper()}_API_KEY"
            account_secret_var = f"{account_name.upper()}_API_SECRET"

            new_api_key = os.getenv(account_key_var)
            new_api_secret = os.getenv(account_secret_var)

            if not new_api_key or not new_api_secret:
                return f"Account '{account_name}' not found in .env"

            self.exchange = HyperLiquidClient(
                api_key=new_api_key,
                api_secret=new_api_secret,
                testnet=self.config['exchange']['testnet'],
                retry_attempts=self.config['exchange']['retry_attempts'],
                timeout=self.config['exchange']['request_timeout_seconds']
            )

            new_balance = self.exchange.get_account_balance()
            self.logger.info(f"Switched to account: {account_name}")

            return f"Account switched to {account_name}\nBalance: ${new_balance:,.2f}"

        except Exception as e:
            self.logger.error(f"Account switch failed: {e}")
            return f"Switch failed: {str(e)}"

    def run(self):
        """Main bot loop - runs forever"""
        self.logger.info("=" * 70)
        self.logger.info("MULTI-STRATEGY TRADING BOT STARTED")
        self.logger.info("=" * 70)

        enabled = self.state_manager.get_enabled_strategies()
        strategies_info = f"{len(enabled)} strategies enabled" if enabled else "No strategies enabled"

        self.notifier.send_message(
            "🤖 <b>Bot Started</b>\n\n"
            f"Environment: {'TESTNET' if self.config['exchange']['testnet'] else 'MAINNET'}\n"
            f"Strategies: {strategies_info}\n"
            f"State: {self.state_manager}\n\n"
            "Use /strategy to configure strategies."
        )

        try:
            while self.is_running:
                self.run_loop_iteration()

                sleep_seconds = self.config['bot']['loop_interval_seconds']
                self.logger.info(f"Sleeping {sleep_seconds}s until next check...\n")
                time.sleep(sleep_seconds)

        except KeyboardInterrupt:
            self.logger.info("\nShutdown requested by user (Ctrl+C)")

        finally:
            self.logger.info("=" * 70)
            self.logger.info("TRADING BOT STOPPED")
            self.logger.info("=" * 70)

            self.notifier.send_message(
                "🛑 <b>Bot Stopped</b>\n\n"
                f"Final state: {self.state_manager}\n\n"
                "Bot is no longer monitoring."
            )


# Entry point
if __name__ == '__main__':
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║        MULTI-STRATEGY TRADING BOT                         ║
║                                                           ║
║        Strategies:                                        ║
║        - overnight: Buy 3PM EST, trailing stop            ║
║        - oi: Open Interest signals, never sell loss       ║
║                                                           ║
║        Use /strategy in Telegram to configure             ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)

    # Skip confirmation on Railway (non-interactive environment)
    if not os.getenv('RAILWAY_ENVIRONMENT'):
        response = input("Start trading bot? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            sys.exit(0)

    bot = TradingBot()
    bot.run()

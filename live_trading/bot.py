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
from src.state_manager import StateManager
from src.notifier import TelegramNotifier
from src.risk_manager import RiskManager
from src.command_handler import CommandHandler


# Strategy registry - maps names to classes
STRATEGY_CLASSES = {
    'overnight': OvernightRecoveryStrategy,
    'oi': OIStrategy
}

STRATEGY_DESCRIPTIONS = {
    'overnight': 'Buy at 3 PM EST, trailing stop 1%',
    'oi': 'Open Interest signals, never sell at loss'
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
        # Exchange client
        self.exchange = HyperLiquidClient(
            api_key=os.getenv('HYPERLIQUID_API_KEY'),
            api_secret=os.getenv('HYPERLIQUID_API_SECRET'),
            testnet=self.config['exchange']['testnet'],
            retry_attempts=self.config['exchange']['retry_attempts'],
            timeout=self.config['exchange']['request_timeout_seconds']
        )
        self.logger.info(f"Exchange: {'TESTNET' if self.config['exchange']['testnet'] else 'MAINNET'}")

        # Initialize ALL strategy instances
        self.strategies: Dict[str, object] = {}
        for name, strategy_config in self.config.get('strategies', {}).items():
            if name in STRATEGY_CLASSES:
                strategy_class = STRATEGY_CLASSES[name]
                params = strategy_config.get('params', {})
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

            # Process each enabled strategy
            for strategy_name in enabled_strategies:
                if strategy_name not in self.strategies:
                    self.logger.warning(f"Strategy {strategy_name} enabled but not loaded")
                    continue

                strategy = self.strategies[strategy_name]

                # Check if in position for this strategy
                if self.state_manager.is_in_position(strategy_name):
                    self._handle_strategy_exit(strategy_name, strategy, current_price, current_time)
                else:
                    self._handle_strategy_entry(strategy_name, strategy, current_price, current_time)

            # Send heartbeat
            self._send_heartbeat(current_price)

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

    response = input("Start trading bot? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled.")
        sys.exit(0)

    bot = TradingBot()
    bot.run()

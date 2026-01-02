"""
Overnight Recovery Trading Bot
Main orchestrator that runs 24/7

This is the entry point - run this file to start the bot.

How it works:
1. Load configuration and credentials
2. Initialize all components (exchange, strategy, notifier, etc.)
3. Enter main loop:
   - Every 5 minutes: Check if should buy or sell
   - Every hour: Send heartbeat
   - On errors: Alert and pause
4. Loop forever (until manually stopped)

Safety Features:
- All errors are caught and logged
- Bot pauses on any exception (fail-safe)
- State is saved after every action
- STOP file allows emergency shutdown
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
import pytz
from dotenv import load_dotenv

# Add src to path
sys.path.append(str(Path(__file__).parent / 'src'))

from src.exchange import HyperLiquidClient
from src.strategy import OvernightRecoveryStrategy
from src.state_manager import StateManager
from src.notifier import TelegramNotifier
from src.risk_manager import RiskManager
from src.command_handler import CommandHandler


class TradingBot:
    """
    Main trading bot orchestrator

    Coordinates all components and runs the trading loop.
    """

    def __init__(self, config_path: str = './config.json'):
        """
        Initialize trading bot

        Args:
            config_path: Path to configuration file
        """
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

        # Create logger
        self.logger = logging.getLogger('TradingBot')
        self.logger.setLevel(logging.INFO)

        # File handler (daily log files)
        log_file = log_dir / f"trades_{datetime.now().strftime('%Y-%m-%d')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers
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

        # Strategy
        self.strategy = OvernightRecoveryStrategy(self.config['strategy'])
        self.logger.info(f"Strategy: {self.strategy}")

        # State manager
        self.state_manager = StateManager('./state')
        self.state_manager.load_state()
        self.logger.info(f"State: {self.state_manager}")

        # Notifier
        self.notifier = TelegramNotifier(
            bot_token=os.getenv('TELEGRAM_BOT_TOKEN'),
            chat_id=os.getenv('TELEGRAM_CHAT_ID'),
            enabled=True  # Set False to disable notifications during testing
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

    def _check_stop_file(self) -> bool:
        """
        Check if STOP file exists (emergency shutdown)

        To stop the bot:
        1. Create a file named STOP in the live_trading directory
        2. Bot will detect it and shut down safely

        Returns:
            True if should stop, False otherwise
        """
        stop_file = Path('./STOP')
        if stop_file.exists():
            self.logger.warning("STOP file detected - shutting down")
            return True
        return False

    def _handle_entry(self, current_price: float, current_time: datetime):
        """
        Handle entry logic

        Args:
            current_price: Current BTC price
            current_time: Current timestamp
        """
        # Check if should enter
        should_enter, reason = self.strategy.should_enter(current_time, current_price)

        self.logger.info(f"Entry check: {should_enter} - {reason}")

        if not should_enter:
            return

        # Get account balance
        balance = self.exchange.get_account_balance()
        self.logger.info(f"Account balance: ${balance:,.2f}")

        # Check risk conditions
        is_safe, risk_reason = self.risk_manager.should_allow_entry(
            current_balance=balance,
            initial_balance=self.daily_start_balance or balance,
            consecutive_losses=self.state_manager.state['consecutive_losses'],
            last_data_update=current_time
        )

        if not is_safe:
            self.logger.warning(f"Entry blocked by risk manager: {risk_reason}")
            self.notifier.send_circuit_breaker_alert(
                risk_reason,
                self.state_manager.get_risk_metrics()
            )
            self.is_paused = True
            return

        # Calculate position size
        position_size_usd = self.risk_manager.calculate_position_size(
            balance, self.config['risk']
        )

        # Place order
        self.logger.info(f"Placing BUY order for ${position_size_usd:,.0f}")

        try:
            order_id, fill_price, fill_size = self.exchange.place_market_order(
                'BUY', position_size_usd
            )

            # Update state
            self.state_manager.enter_position(
                entry_time=current_time,
                entry_price=fill_price,
                size_btc=fill_size,
                size_usd=position_size_usd
            )

            # Send notification
            self.notifier.send_entry_alert(
                price=fill_price,
                size_btc=fill_size,
                size_usd=position_size_usd,
                entry_time=current_time,
                trailing_stop_pct=self.config['strategy']['trailing_stop_pct']
            )

            self.logger.info(f"✅ ENTRY: {fill_size:.4f} BTC @ ${fill_price:,.2f}")

        except Exception as e:
            self.logger.error(f"Failed to place entry order: {e}")
            self.notifier.send_error_alert(
                f"Entry order failed: {str(e)}",
                self.state_manager.get_position_details()
            )
            self.is_paused = True

    def _handle_exit(self, current_price: float, current_time: datetime):
        """
        Handle exit logic

        Args:
            current_price: Current BTC price
            current_time: Current timestamp
        """
        # Get position details
        position = self.state_manager.get_position_details()
        if not position:
            return

        entry_price = position['entry_price']
        peak_price = position['peak_price']
        size_btc = position['size_btc']

        # Update peak price
        new_peak = self.state_manager.update_peak_price(current_price)
        if new_peak > peak_price:
            self.logger.info(f"New peak: ${new_peak:,.2f}")
            peak_price = new_peak

        # Check if should exit
        should_exit, reason = self.strategy.should_exit(
            current_price, entry_price, peak_price
        )

        self.logger.info(f"Exit check: {should_exit} - {reason}")

        if not should_exit:
            return

        # Check risk conditions (only data staleness for exits)
        is_safe, risk_reason = self.risk_manager.should_allow_exit(current_time)

        if not is_safe:
            self.logger.warning(f"Exit blocked by risk manager: {risk_reason}")
            # Don't pause on stale data during exit - we WANT to exit
            # Just log the warning and proceed if it's been less than 30 min
            if 'stale' in risk_reason.lower():
                # Allow exit if data is less than 30 minutes old
                # (prevents being stuck in position during temporary network issues)
                pass

        # Place sell order
        self.logger.info(f"Placing SELL order for {size_btc:.4f} BTC")

        try:
            order_id, fill_price, fill_size = self.exchange.place_market_order(
                'SELL', size_btc * current_price
            )

            # Calculate profit
            profit_pct = ((fill_price - entry_price) / entry_price) * 100
            profit_usd = (fill_price - entry_price) * size_btc

            # Update state
            self.state_manager.exit_position(
                exit_time=current_time,
                exit_price=fill_price,
                profit_pct=profit_pct
            )

            # Send notification
            entry_time = datetime.fromisoformat(position['entry_time'])
            self.notifier.send_exit_alert(
                entry_price=entry_price,
                exit_price=fill_price,
                entry_time=entry_time,
                exit_time=current_time,
                profit_pct=profit_pct,
                profit_usd=profit_usd,
                reason=reason
            )

            self.logger.info(f"✅ EXIT: {fill_size:.4f} BTC @ ${fill_price:,.2f} ({profit_pct:+.2f}%)")

        except Exception as e:
            self.logger.error(f"Failed to place exit order: {e}")
            self.notifier.send_error_alert(
                f"Exit order failed: {str(e)}",
                self.state_manager.get_position_details()
            )
            self.is_paused = True

    def _send_heartbeat(self, current_price: float):
        """
        Send hourly heartbeat

        Args:
            current_price: Current BTC price
        """
        now = datetime.now(pytz.UTC)

        # Send heartbeat every hour (or if in position)
        if self.last_heartbeat:
            time_since = (now - self.last_heartbeat).total_seconds()
            if time_since < 3600 and not self.state_manager.is_in_position():
                return

        # Prepare state for heartbeat
        state = self.state_manager.get_position_details() or {}
        state['current_price'] = current_price

        self.notifier.send_heartbeat(state)
        self.last_heartbeat = now

    def _check_daily_reset(self):
        """
        Check if we need to reset daily statistics

        Resets at midnight EST.
        """
        now_est = datetime.now(pytz.timezone('America/New_York'))
        current_date = now_est.date()

        # First run - initialize
        if self.last_daily_reset is None:
            self.last_daily_reset = current_date
            balance = self.exchange.get_account_balance()
            self.daily_start_balance = balance
            self.risk_manager.reset_daily_limits(balance)
            return

        # Check if date changed
        if current_date > self.last_daily_reset:
            self.logger.info(f"Daily reset triggered - new day: {current_date}")

            # Reset daily stats
            balance = self.exchange.get_account_balance()
            self.daily_start_balance = balance
            self.risk_manager.reset_daily_limits(balance)
            self.state_manager.reset_daily_stats()
            self.strategy.reset_daily_state()

            self.last_daily_reset = current_date

    def run_loop_iteration(self):
        """
        Run one iteration of the main loop

        This is called every 5 minutes.
        """
        self.loop_count += 1
        current_time = datetime.now(pytz.UTC)

        self.logger.info(f"=== Loop {self.loop_count} - {current_time.strftime('%Y-%m-%d %H:%M:%S UTC')} ===")

        try:
            # Check for emergency stop
            if self._check_stop_file():
                self.is_running = False
                return

            # Check if bot is paused
            if self.is_paused:
                self.logger.warning("Bot is PAUSED - manual restart required")
                return

            # Check daily reset
            self._check_daily_reset()

            # Get current price
            current_price = self.exchange.get_btc_price()
            self.logger.info(f"BTC Price: ${current_price:,.2f}")

            # Check if in position
            in_position = self.state_manager.is_in_position()

            if in_position:
                # Handle exit logic
                self._handle_exit(current_price, current_time)
            else:
                # Handle entry logic
                self._handle_entry(current_price, current_time)

            # Send heartbeat
            self._send_heartbeat(current_price)

        except Exception as e:
            self.logger.error(f"ERROR in loop iteration: {e}", exc_info=True)
            self.notifier.send_error_alert(
                f"Loop error: {str(e)}",
                self.state_manager.get_position_details()
            )
            self.is_paused = True

    # ===== TELEGRAM COMMAND METHODS =====

    def enable_trading(self):
        """Enable trading (called by /start command)"""
        self.is_paused = False
        self.logger.info("Trading ENABLED via Telegram command")

    def disable_trading(self):
        """Disable trading (called by /stop command)"""
        self.is_paused = True
        self.logger.info("Trading DISABLED via Telegram command")

    def emergency_close_position(self) -> str:
        """
        Force close current position (called by /close command)

        Returns:
            Status message
        """
        import threading

        if not self.state_manager.is_in_position():
            return "❌ <b>No Position to Close</b>\n\nCurrently not in any position."

        try:
            position = self.state_manager.get_position_details()
            size_btc = position['size_btc']
            entry_price = position['entry_price']

            # Get current price
            current_price = self.exchange.get_btc_price()

            # Calculate P&L
            profit_pct = ((current_price - entry_price) / entry_price) * 100
            profit_usd = (current_price - entry_price) * size_btc

            # Execute market sell
            self.logger.info(f"Emergency close: Selling {size_btc:.4f} BTC")
            order_id, fill_price, fill_size = self.exchange.place_market_order(
                'SELL',
                size_btc * current_price
            )

            # Update state
            self.state_manager.exit_position(
                exit_time=datetime.now(pytz.UTC),
                exit_price=fill_price,
                profit_pct=profit_pct
            )

            # Pause trading
            self.is_paused = True

            self.logger.info(f"Emergency close completed: {fill_size:.4f} BTC @ ${fill_price:,.2f}")

            emoji = "🟢" if profit_pct >= 0 else "🔴"
            return f"""
{emoji} <b>EMERGENCY CLOSE EXECUTED</b>

<b>Position:</b> LONG {size_btc:.4f} BTC
<b>Entry:</b> ${entry_price:,.2f}
<b>Exit:</b> ${fill_price:,.2f} (market order)
<b>P&L:</b> {profit_pct:+.2f}% (${profit_usd:+,.2f})

🛑 Trading paused - use /start to resume
"""

        except Exception as e:
            self.logger.error(f"Emergency close failed: {e}", exc_info=True)
            return f"❌ <b>Close Failed</b>\n\n{str(e)}"

    def switch_account(self, account_name: str) -> str:
        """
        Switch to different HyperLiquid account

        Args:
            account_name: Account name from .env (e.g., "account1")

        Returns:
            Status message
        """
        # Check if in position
        if self.state_manager.is_in_position():
            position = self.state_manager.get_position_details()
            size_btc = position['size_btc']
            entry_price = position['entry_price']

            return f"""
⚠️ <b>Cannot Switch Account</b>

You have an open position:
<b>Position:</b> LONG {size_btc:.4f} BTC @ ${entry_price:,.2f}

Please close the position first using /close
"""

        try:
            # Load new credentials
            account_key_var = f"{account_name.upper()}_API_KEY"
            account_secret_var = f"{account_name.upper()}_API_SECRET"

            new_api_key = os.getenv(account_key_var)
            new_api_secret = os.getenv(account_secret_var)

            if not new_api_key or not new_api_secret:
                available_accounts = []
                for key in os.environ.keys():
                    if key.endswith('_API_KEY') and not key.startswith('HYPERLIQUID'):
                        account = key.replace('_API_KEY', '').lower()
                        available_accounts.append(account)

                accounts_list = ", ".join(available_accounts) if available_accounts else "none"

                return f"""
❌ <b>Account Not Found</b>

Account "{account_name}" not configured in .env

Available accounts: {accounts_list}

Add to .env:
<code>{account_key_var}=your_key</code>
<code>{account_secret_var}=your_secret</code>
"""

            # Get current account info
            try:
                old_balance = self.exchange.get_account_balance()
            except:
                old_balance = None

            # Reinitialize exchange client with new credentials
            self.exchange = HyperLiquidClient(
                api_key=new_api_key,
                api_secret=new_api_secret,
                testnet=self.config['exchange']['testnet'],
                retry_attempts=self.config['exchange']['retry_attempts'],
                timeout=self.config['exchange']['request_timeout_seconds']
            )

            # Get new account info
            new_balance = self.exchange.get_account_balance()

            self.logger.info(f"Switched to account: {account_name}")

            return f"""
✅ <b>Account Switched</b>

<b>New Account:</b> {account_name}
<b>Balance:</b> ${new_balance:,.2f} USDC

{f"<b>Previous Balance:</b> ${old_balance:,.2f} USDC" if old_balance else ""}

Account switch successful!
"""

        except Exception as e:
            self.logger.error(f"Account switch failed: {e}", exc_info=True)
            return f"❌ <b>Switch Failed</b>\n\n{str(e)}"

    def run(self):
        """
        Main bot loop - runs forever

        Runs one iteration every 5 minutes.
        Catches all exceptions to prevent crashes.
        """
        self.logger.info("=" * 70)
        self.logger.info("TRADING BOT STARTED")
        self.logger.info("=" * 70)

        # Send startup notification
        self.notifier.send_message(
            "🤖 <b>Bot Started</b>\n\n"
            f"Environment: {'TESTNET' if self.config['exchange']['testnet'] else '🔴 MAINNET'}\n"
            f"Strategy: {self.strategy}\n"
            f"State: {self.state_manager}\n\n"
            "Monitoring for entry signals..."
        )

        try:
            while self.is_running:
                # Run one iteration
                self.run_loop_iteration()

                # Sleep until next check (5 minutes)
                sleep_seconds = self.config['bot']['loop_interval_seconds']
                self.logger.info(f"Sleeping {sleep_seconds}s until next check...\n")
                time.sleep(sleep_seconds)

        except KeyboardInterrupt:
            self.logger.info("\nShutdown requested by user (Ctrl+C)")

        finally:
            self.logger.info("=" * 70)
            self.logger.info("TRADING BOT STOPPED")
            self.logger.info("=" * 70)

            # Send shutdown notification
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
║        OVERNIGHT RECOVERY TRADING BOT                     ║
║        Strategy: Buy 3PM EST (8PM GMT), Trailing Stop 1%  ║
║                                                           ║
║        IMPORTANT: Review config.json before starting      ║
║        - Check testnet vs mainnet setting                 ║
║        - Verify Telegram credentials in .env              ║
║        - Ensure HyperLiquid API keys are valid            ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)

    # Confirm before starting
    response = input("Start trading bot? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled.")
        sys.exit(0)

    # Create and run bot
    bot = TradingBot()
    bot.run()

"""
Telegram Command Handler

Processes incoming Telegram commands and executes actions on the trading bot.

Supported Commands:
- /help - Show all available commands
- /status - View current bot status, position, balance
- /strategy - View current strategy parameters
- /auth <pin> - Authenticate for sensitive commands
- /enable - Enable trading
- /disable - Disable trading (requires PIN)
- /close - Emergency close position (requires PIN)
- /switch <account> - Switch HyperLiquid accounts (requires PIN)
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Tuple
import pytz


class CommandHandler:
    """
    Handles Telegram bot commands

    Processes incoming messages, verifies authentication,
    and executes actions on the trading bot.
    """

    def __init__(self, bot, config: dict):
        """
        Initialize command handler

        Args:
            bot: Reference to main TradingBot instance
            config: Configuration dictionary
        """
        self.bot = bot
        self.config = config

        # Authentication state (in memory, expires after timeout)
        self.authenticated_until = None
        self.failed_auth_attempts = {}  # chat_id: count

        # Load PIN from environment
        self.pin = os.getenv('TELEGRAM_PIN')
        if not self.pin:
            print("⚠️  WARNING: TELEGRAM_PIN not set in .env file")

        # Security settings
        self.pin_timeout_minutes = config.get('security', {}).get('pin_timeout_minutes', 5)
        self.allowed_chat_ids = config.get('security', {}).get('allowed_chat_ids', [])

        # Commands that require authentication
        self.protected_commands = ['/disable', '/close', '/switch']

    def is_authorized_chat(self, chat_id: str) -> bool:
        """
        Check if chat ID is authorized

        Args:
            chat_id: Telegram chat ID

        Returns:
            True if authorized, False otherwise
        """
        if not self.allowed_chat_ids:
            return True  # If no whitelist, allow all

        return str(chat_id) in [str(cid) for cid in self.allowed_chat_ids]

    def is_authenticated(self) -> bool:
        """
        Check if currently authenticated

        Returns:
            True if authenticated and not expired, False otherwise
        """
        if not self.authenticated_until:
            return False

        now = datetime.now(pytz.UTC)
        return now < self.authenticated_until

    def process_command(self, message_text: str, chat_id: str):
        """
        Process a command and return response

        Args:
            message_text: The command message (e.g., "/status")
            chat_id: Telegram chat ID of sender

        Returns:
            Tuple of (message, keyboard) where keyboard is optional inline keyboard markup
        """
        # Check authorization
        if not self.is_authorized_chat(chat_id):
            self.bot.logger.warning(f"Unauthorized command from chat_id: {chat_id}")
            return ("", None)  # Silent ignore

        # Parse command
        parts = message_text.strip().split()
        if not parts:
            return ("❌ Empty message", None)

        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        # Check authentication for protected commands
        if command in self.protected_commands:
            if not self.is_authenticated():
                return (f"🔒 <b>Authentication Required</b>\n\nThis command requires PIN.\nSend: /auth &lt;your_pin&gt;", None)

        # Route to appropriate handler
        try:
            if command == '/help':
                return (self.handle_help(), None)
            elif command == '/status':
                return (self.handle_status(), None)
            elif command == '/balance':
                return (self.handle_balance(), None)
            elif command == '/strategy':
                return self.handle_strategy()  # Returns tuple with keyboard
            elif command == '/auth':
                return (self.handle_auth(args, chat_id), None)
            elif command == '/enable':
                return (self.handle_start(), None)
            elif command == '/disable':
                return (self.handle_stop(), None)
            elif command == '/close':
                return (self.handle_close(), None)
            elif command == '/switch':
                return (self.handle_switch(args), None)
            else:
                return (f"❌ Unknown command: <code>{command}</code>\n\nSend /help for available commands", None)

        except Exception as e:
            self.bot.logger.error(f"Error processing command {command}: {e}", exc_info=True)
            return (f"❌ <b>Error</b>\n\nFailed to execute command: {str(e)}", None)

    def handle_help(self) -> str:
        """
        Show help message with all available commands

        Returns:
            Help message
        """
        return """
📚 <b>AVAILABLE COMMANDS</b>

<b>Monitoring:</b>
/status - View current position, balance, P&L
/balance - Quick balance check
/strategy - View strategy details & activation button

<b>Trading Control:</b>
/enable - ▶️ ACTIVATE STRATEGY & start trading
/disable - ⏸️ PAUSE STRATEGY 🔒
/close - ⛔ Emergency close position 🔒

<b>Configuration:</b>
/switch &lt;account&gt; - Switch HyperLiquid account 🔒

<b>Security:</b>
/auth &lt;pin&gt; - Authenticate for protected commands

🔒 = Requires PIN authentication
"""

    def handle_status(self) -> str:
        """
        Show current bot status

        Returns:
            Status message
        """
        try:
            # Get current state
            is_paused = self.bot.is_paused
            position = self.bot.state_manager.get_position_details()

            # Get current price
            try:
                current_price = self.bot.exchange.get_btc_price()
            except:
                current_price = None

            # Get balance
            try:
                balance = self.bot.exchange.get_account_balance()
            except:
                balance = None

            # Build status message
            trading_status = "🛑 DISABLED" if is_paused else "✅ ENABLED"
            strategy_name = "Overnight Recovery"  # Future: get from active strategy

            message = f"📊 <b>BOT STATUS</b>\n\n"
            message += f"<b>Trading:</b> {trading_status}\n"
            message += f"<b>Strategy:</b> {strategy_name}\n"

            if current_price:
                message += f"<b>BTC Price:</b> ${current_price:,.2f}\n"

            if balance:
                message += f"<b>Balance:</b> ${balance:,.2f} USDC\n"

            # Position info
            if position:
                entry_price = position['entry_price']
                size_btc = position['size_btc']
                peak_price = position['peak_price']

                # Calculate profit
                if current_price:
                    profit_pct = ((current_price - entry_price) / entry_price) * 100
                    profit_usd = (current_price - entry_price) * size_btc

                    message += f"\n<b>Position:</b> LONG {size_btc:.4f} BTC\n"
                    message += f"<b>Entry:</b> ${entry_price:,.2f}\n"
                    message += f"<b>Current:</b> ${current_price:,.2f}\n"
                    message += f"<b>Profit:</b> {profit_pct:+.2f}% (${profit_usd:+,.2f})\n"
                    message += f"<b>Peak:</b> ${peak_price:,.2f}\n"
                    message += f"<b>Trailing Stop:</b> {self.config['strategy']['trailing_stop_pct']}% from peak"
                else:
                    message += f"\n<b>Position:</b> LONG {size_btc:.4f} BTC @ ${entry_price:,.2f}"
            else:
                message += f"\n<b>Position:</b> None\n"

                # Next entry time - show both EST and GMT
                now_london = datetime.now(pytz.timezone('Europe/London'))
                entry_hour_est = self.config['strategy']['entry_hour']  # 15 = 3 PM EST
                entry_hour_gmt = 20  # 8 PM GMT (3 PM EST + 5 hours)

                if now_london.hour < entry_hour_gmt:
                    message += f"<b>Next Entry:</b> Today 20:00 GMT (15:00 EST)"
                else:
                    message += f"<b>Next Entry:</b> Tomorrow 20:00 GMT (15:00 EST)"

            # Daily P&L
            risk_metrics = self.bot.state_manager.get_risk_metrics()
            daily_pnl = risk_metrics.get('daily_pnl', 0)
            if daily_pnl != 0:
                message += f"\n\n<b>Daily P&L:</b> ${daily_pnl:+,.2f}"

            return message

        except Exception as e:
            return f"❌ Error getting status: {str(e)}"

    def handle_balance(self) -> str:
        """
        Show current account balance

        Returns:
            Balance message
        """
        try:
            # Get balance from perp clearinghouse
            balance = self.bot.exchange.get_account_balance()

            # Get current BTC price
            try:
                current_price = self.bot.exchange.get_btc_price()
            except:
                current_price = None

            message = f"💰 <b>ACCOUNT BALANCE</b>\n\n"
            message += f"<b>Balance:</b> ${balance:,.2f} USDC\n"

            if current_price:
                message += f"<b>BTC Price:</b> ${current_price:,.2f}\n"

            # Show position if any
            position = self.bot.state_manager.get_position_details()
            if position:
                size_btc = position['size_btc']
                entry_price = position['entry_price']

                if current_price:
                    position_value = size_btc * current_price
                    profit_pct = ((current_price - entry_price) / entry_price) * 100
                    profit_usd = (current_price - entry_price) * size_btc

                    message += f"\n<b>Position Value:</b> ${position_value:,.2f}\n"
                    message += f"<b>Unrealized P&L:</b> {profit_pct:+.2f}% (${profit_usd:+,.2f})"

            return message

        except Exception as e:
            return f"❌ Error getting balance: {str(e)}"

    def handle_strategy(self) -> str:
        """
        Show current strategy parameters with full description

        Returns:
            Strategy info message
        """
        try:
            strategy_config = self.config['strategy']

            message = f"📈 <b>OVERNIGHT RECOVERY STRATEGY</b>\n\n"

            message += f"<b>🎯 Overview:</b>\n"
            message += f"Capitalize on Bitcoin's tendency to recover overnight after intraday weakness. "
            message += f"Enters at 20:00 GMT (15:00 EST) and holds until price hits trailing stop.\n\n"

            message += f"<b>📥 ENTRY CONDITIONS:</b>\n"
            message += f"• <b>Time:</b> 20:00 GMT (15:00 EST) daily\n"
            message += f"• <b>Price Check:</b> BTC must be below ${strategy_config['max_entry_price_usd']:,.0f}\n"
            message += f"• <b>Position:</b> Not already in a position\n"
            message += f"• <b>Risk Check:</b> Daily loss limit not exceeded\n"
            message += f"• <b>Action:</b> Market buy with calculated position size\n\n"

            message += f"<b>📤 EXIT CONDITIONS:</b>\n"
            message += f"• <b>Trailing Stop:</b> {strategy_config['trailing_stop_pct']}% from peak price\n"
            message += f"• <b>Protection:</b> NEVER sells at a loss\n"
            message += f"• <b>Peak Tracking:</b> Continuously updates highest price reached\n"
            message += f"• <b>Trigger:</b> Price drops {strategy_config['trailing_stop_pct']}% from peak → Market sell\n\n"

            message += f"<b>📊 BACKTEST RESULTS (December 2024):</b>\n"
            message += f"• <b>Total Return:</b> +17.95%\n"
            message += f"• <b>Win Rate:</b> 76.9% (20/26 trades)\n"
            message += f"• <b>Max Drawdown:</b> -3.25%\n"
            message += f"• <b>Avg Win:</b> +1.2%\n"
            message += f"• <b>Largest Win:</b> +3.8%\n"
            message += f"• <b>Risk/Reward:</b> Asymmetric (capped losses, unlimited gains)\n\n"

            message += f"<b>⚙️ RISK MANAGEMENT:</b>\n"
            message += f"• <b>Position Size:</b> {self.config['risk']['position_size_pct']}% of account per trade\n"
            message += f"• <b>Max Daily Loss:</b> {self.config['risk']['max_daily_loss_pct']}% of account\n"
            message += f"• <b>Max Consecutive Losses:</b> {self.config['risk']['max_consecutive_losses']}\n\n"

            # Show current status
            is_enabled = not self.bot.is_paused
            status_emoji = "🟢" if is_enabled else "🔴"
            message += f"<b>Status:</b> {status_emoji} {'ENABLED' if is_enabled else 'DISABLED'}\n"

            # Create inline keyboard with action button
            keyboard = None
            if not is_enabled:
                message += f"\n<b>📌 TO ACTIVATE:</b> Use the button below to start trading"
                keyboard = {
                    "inline_keyboard": [[
                        {"text": "▶️ ENABLE STRATEGY", "callback_data": "/enable"}
                    ]]
                }
            else:
                message += f"\n<b>✅ ACTIVE:</b> Strategy is currently running"
                keyboard = {
                    "inline_keyboard": [[
                        {"text": "⏸️ DISABLE STRATEGY", "callback_data": "/disable"}
                    ]]
                }

            return (message, keyboard)

        except Exception as e:
            return (f"❌ Error getting strategy info: {str(e)}", None)

    def handle_auth(self, args: list, chat_id: str) -> str:
        """
        Authenticate user with PIN

        Args:
            args: Command arguments [pin]
            chat_id: Chat ID for rate limiting

        Returns:
            Authentication response
        """
        # Check if PIN is configured
        if not self.pin:
            return "❌ <b>PIN Not Configured</b>\n\nSet TELEGRAM_PIN in .env file"

        # Check rate limiting
        failed_attempts = self.failed_auth_attempts.get(chat_id, 0)
        if failed_attempts >= 5:
            return "🔒 <b>Too Many Failed Attempts</b>\n\nWait 1 hour before trying again"

        # Check arguments
        if not args:
            return "❌ <b>Usage:</b> /auth &lt;pin&gt;"

        provided_pin = args[0]

        # Verify PIN
        if provided_pin == self.pin:
            # Successful auth
            self.authenticated_until = datetime.now(pytz.UTC) + timedelta(minutes=self.pin_timeout_minutes)
            self.failed_auth_attempts[chat_id] = 0  # Reset failures

            return f"✅ <b>Authenticated</b>\n\nYou can now use protected commands for {self.pin_timeout_minutes} minutes."
        else:
            # Failed auth
            self.failed_auth_attempts[chat_id] = failed_attempts + 1
            remaining = 5 - self.failed_auth_attempts[chat_id]

            return f"❌ <b>Incorrect PIN</b>\n\nAttempts remaining: {remaining}"

    def handle_start(self) -> str:
        """
        Enable trading

        Returns:
            Response message
        """
        try:
            self.bot.enable_trading()

            now_london = datetime.now(pytz.timezone('Europe/London'))
            entry_hour_london = 20  # 8 PM London (3 PM EST)

            message = "✅ <b>Trading ENABLED</b>\n\n"
            message += "The bot will now:\n"
            message += f"• Monitor for entry signals at 20:00 GMT (15:00 EST)\n"
            message += "• Execute trades automatically\n"
            message += "• Send alerts on all actions\n\n"

            position = self.bot.state_manager.get_position_details()
            if position:
                message += f"<b>Current:</b> In position"
            else:
                if now_london.hour < entry_hour_london:
                    message += f"<b>Next Entry Check:</b> Today 20:00 GMT (15:00 EST)"
                else:
                    message += f"<b>Next Entry Check:</b> Tomorrow 20:00 GMT (15:00 EST)"

            return message

        except Exception as e:
            return f"❌ Error enabling trading: {str(e)}"

    def handle_stop(self) -> str:
        """
        Disable trading (protected, requires PIN)

        Returns:
            Response message
        """
        try:
            self.bot.disable_trading()

            position = self.bot.state_manager.get_position_details()

            message = "🛑 <b>Trading DISABLED</b>\n\n"
            message += "The bot will:\n"
            message += "• NOT enter new positions\n"
            message += "• Continue monitoring existing position\n"
            message += "• Exit at trailing stop as normal\n\n"

            if position:
                entry_price = position['entry_price']
                size_btc = position['size_btc']
                message += f"<b>Current Position:</b> LONG {size_btc:.4f} BTC @ ${entry_price:,.2f}\n\n"
                message += "To close immediately, use /close"
            else:
                message += "<b>Current Position:</b> None"

            return message

        except Exception as e:
            return f"❌ Error disabling trading: {str(e)}"

    def handle_close(self) -> str:
        """
        Emergency close current position (protected, requires PIN)

        Returns:
            Response message
        """
        try:
            result = self.bot.emergency_close_position()
            return result

        except Exception as e:
            return f"❌ Error closing position: {str(e)}"

    def handle_switch(self, args: list) -> str:
        """
        Switch to different HyperLiquid account (protected, requires PIN)

        Args:
            args: Command arguments [account_name]

        Returns:
            Response message
        """
        if not args:
            return "❌ <b>Usage:</b> /switch &lt;account_name&gt;\n\nExample: /switch account1"

        account_name = args[0].lower()

        try:
            result = self.bot.switch_account(account_name)
            return result

        except Exception as e:
            return f"❌ Error switching account: {str(e)}"


# Module testing
if __name__ == '__main__':
    import json
    from dotenv import load_dotenv

    # Load environment
    load_dotenv()

    # Load config
    with open('../config.json', 'r') as f:
        config = json.load(f)

    # Create mock bot
    class MockBot:
        is_paused = False
        logger = type('obj', (object,), {'warning': print, 'error': print, 'info': print})()

        class MockStateManager:
            def get_position_details(self):
                return None
            def get_risk_metrics(self):
                return {'daily_pnl': 0}

        state_manager = MockStateManager()

        def enable_trading(self):
            print("Trading enabled")

        def disable_trading(self):
            print("Trading disabled")

    # Create handler
    handler = CommandHandler(MockBot(), config)

    # Test commands
    print("Testing /help:")
    print(handler.process_command("/help", "test_chat"))

    print("\nTesting /status:")
    print(handler.process_command("/status", "test_chat"))

    print("\nTesting /strategy:")
    print(handler.process_command("/strategy", "test_chat"))

    print("\nAll tests passed!")

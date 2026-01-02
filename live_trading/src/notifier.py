"""
Telegram Notification System

This module sends alerts to your Telegram account.

Alert Types:
1. Trade Entry/Exit - When bot buys or sells
2. Error Alerts - When something goes wrong
3. Daily Summary - Performance recap at 9 AM
4. Heartbeat - "I'm alive" message every hour

WHY THIS MATTERS:
- You need to know if bot is trading (especially with $100K!)
- Errors need immediate attention
- Heartbeat confirms bot is running (if you don't get one, bot crashed)
"""

import requests
from datetime import datetime, timedelta
from typing import Optional
import pytz


class TelegramNotifier:
    """
    Sends notifications via Telegram Bot API

    Setup:
    1. Create bot at https://t.me/BotFather
    2. Get your chat_id by messaging @userinfobot
    3. Put token and chat_id in .env file
    """

    def __init__(self, bot_token: str, chat_id: str, enabled: bool = True):
        """
        Initialize Telegram notifier

        Args:
            bot_token: Your Telegram bot token from BotFather
            chat_id: Your Telegram chat ID
            enabled: Set False to disable all notifications (for testing)
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

        # Track last heartbeat to avoid spam
        self.last_heartbeat = None

    def _send_message(self, text: str, parse_mode: str = 'HTML') -> bool:
        """
        Send message to Telegram

        Args:
            text: Message text (supports HTML formatting)
            parse_mode: 'HTML' or 'Markdown'

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            print(f"[TELEGRAM DISABLED] {text}")
            return False

        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': parse_mode
            }

            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True

        except Exception as e:
            print(f"❌ Failed to send Telegram message: {e}")
            return False

    def send_entry_alert(self, price: float, size_btc: float, size_usd: float,
                        entry_time: datetime, trailing_stop_pct: float):
        """
        Send trade entry notification

        Example message:
            🟢 ENTRY EXECUTED
            Time: 3:00 PM EST
            Price: $87,432
            Size: 1.1435 BTC ($100,000)

            Stop: 1% trailing stop
            Strategy: Overnight Recovery
        """
        est_time = entry_time.astimezone(pytz.timezone('America/New_York'))

        message = f"""
🟢 <b>ENTRY EXECUTED</b>

⏰ Time: {est_time.strftime('%I:%M %p %Z')}
💰 Price: ${price:,.2f}
📊 Size: {size_btc:.4f} BTC (${size_usd:,.0f})

🛡️ Stop: {trailing_stop_pct}% trailing stop
📈 Strategy: Overnight Recovery
"""
        return self._send_message(message)

    def send_exit_alert(self, entry_price: float, exit_price: float,
                       entry_time: datetime, exit_time: datetime,
                       profit_pct: float, profit_usd: float, reason: str):
        """
        Send trade exit notification

        Example message:
            🔴 EXIT EXECUTED
            Entry: $87,432 (3:00 PM Jan 2)
            Exit: $89,127 (9:15 AM Jan 3)

            Profit: +$1,695 (+1.94%)
            Hold: 18h 15m
            Reason: Trailing stop hit
        """
        est_entry = entry_time.astimezone(pytz.timezone('America/New_York'))
        est_exit = exit_time.astimezone(pytz.timezone('America/New_York'))

        # Calculate hold duration
        hold_duration = exit_time - entry_time
        hours = int(hold_duration.total_seconds() // 3600)
        minutes = int((hold_duration.total_seconds() % 3600) // 60)

        # Emoji based on profit/loss
        emoji = "🟢" if profit_pct >= 0 else "🔴"
        sign = "+" if profit_usd >= 0 else ""

        message = f"""
{emoji} <b>EXIT EXECUTED</b>

📊 Entry: ${entry_price:,.2f} ({est_entry.strftime('%I:%M %p %b %d')})
📊 Exit: ${exit_price:,.2f} ({est_exit.strftime('%I:%M %p %b %d')})

💰 Profit: {sign}${profit_usd:,.2f} ({profit_pct:+.2f}%)
⏱️ Hold: {hours}h {minutes}m
ℹ️ Reason: {reason}
"""
        return self._send_message(message)

    def send_error_alert(self, error_msg: str, current_position: Optional[dict] = None):
        """
        Send error alert

        Example message:
            ⚠️ ERROR - BOT PAUSED
            Error: HyperLiquid API timeout
            Time: 2:45 PM EST

            Current Position: LONG 1.1435 BTC
            Entry: $87,432 | Current: $88,102
            Unrealized P&L: +$670 (+0.77%)

            Action: Manual check required
        """
        now_est = datetime.now(pytz.timezone('America/New_York'))

        message = f"""
⚠️ <b>ERROR - BOT PAUSED</b>

❌ Error: {error_msg}
⏰ Time: {now_est.strftime('%I:%M %p %Z')}
"""

        # Add position info if in a position
        if current_position and current_position.get('in_position'):
            entry_price = current_position['entry_price']
            size_btc = current_position['size_btc']
            message += f"""
📊 Current Position: LONG {size_btc:.4f} BTC
💰 Entry: ${entry_price:,.2f}

⚠️ Action: Manual check required
"""
        else:
            message += "\n✅ No open position\n"

        message += "\n🔧 Action: Check logs and restart bot"

        return self._send_message(message)

    def send_daily_summary(self, stats: dict):
        """
        Send daily summary (at 9 AM EST)

        Example message:
            📊 DAILY SUMMARY - Jan 3

            Yesterday: +$1,695 (+1.69%)
            MTD: +$3,200 (+3.20%)
            Trades: 2 (2W, 0L)

            Current: No position
            Next entry: Today 3 PM
        """
        now_est = datetime.now(pytz.timezone('America/New_York'))

        position_status = "In position" if stats.get('in_position') else "No position"
        next_entry = "Today 3 PM" if not stats.get('in_position') else "After current exit"

        message = f"""
📊 <b>DAILY SUMMARY</b> - {now_est.strftime('%b %d')}

💰 Yesterday: ${stats.get('daily_pnl', 0):+,.2f}
📈 MTD: ${stats.get('mtd_pnl', 0):+,.2f}
📊 Trades: {stats.get('total_trades', 0)} ({stats.get('wins', 0)}W, {stats.get('losses', 0)}L)

🎯 Current: {position_status}
⏰ Next entry: {next_entry}
"""
        return self._send_message(message)

    def send_heartbeat(self, state: dict):
        """
        Send hourly heartbeat

        Only sends if:
        - 1 hour has passed since last heartbeat
        - OR we're in a position (send every heartbeat)

        Example message:
            💚 Bot Active - 4:00 PM EST

            Status: In position
            Entry: $87,432 (1h ago)
            Current: $88,200 (+0.88%)
        """
        now = datetime.now(pytz.timezone('UTC'))

        # Check if we should send (1 hour since last)
        if self.last_heartbeat:
            time_since_last = (now - self.last_heartbeat).total_seconds()
            # Only send every hour (unless in position, then send every check)
            if time_since_last < 3600 and not state.get('in_position'):
                return False

        now_est = now.astimezone(pytz.timezone('America/New_York'))

        if state.get('in_position'):
            entry_price = state['entry_price']
            # Assume current price is passed in state
            current_price = state.get('current_price', entry_price)
            profit_pct = ((current_price - entry_price) / entry_price) * 100

            entry_time = datetime.fromisoformat(state['entry_time'])
            time_in_position = now - entry_time.replace(tzinfo=pytz.UTC)
            hours = int(time_in_position.total_seconds() // 3600)

            message = f"""
💚 <b>Bot Active</b> - {now_est.strftime('%I:%M %p %Z')}

📊 Status: In position
💰 Entry: ${entry_price:,.0f} ({hours}h ago)
📈 Profit: {profit_pct:+.2f}%
"""
        else:
            message = f"""
💚 <b>Bot Active</b> - {now_est.strftime('%I:%M %p %Z')}

✅ Status: Monitoring
⏰ Next entry window: Today 3:00 PM EST
"""

        self.last_heartbeat = now
        return self._send_message(message)

    def send_circuit_breaker_alert(self, reason: str, metrics: dict):
        """
        Send circuit breaker alert

        Example message:
            🛑 CIRCUIT BREAKER TRIGGERED

            Reason: 3 consecutive losses
            Daily P&L: -$4,800 (-4.8%)

            Bot trading paused
            Manual review required
        """
        message = f"""
🛑 <b>CIRCUIT BREAKER TRIGGERED</b>

⚠️ Reason: {reason}
📊 Daily P&L: ${metrics.get('daily_pnl', 0):+,.2f}
📉 Consecutive Losses: {metrics.get('consecutive_losses', 0)}

🔒 Bot trading paused
🔧 Manual review required
"""
        return self._send_message(message)

    def test_connection(self) -> bool:
        """
        Test Telegram connection

        Sends a test message to verify setup.

        Returns:
            True if connection works, False otherwise
        """
        message = """
🤖 <b>Bot Setup Test</b>

✅ Telegram connection successful!
✅ You will receive notifications here

Bot is ready to trade.
"""
        result = self._send_message(message)

        if result:
            print("✅ Telegram test message sent successfully")
        else:
            print("❌ Failed to send Telegram test message")

        return result

    def get_updates(self, offset: Optional[int] = None, timeout: int = 30) -> list:
        """
        Get updates (messages) from Telegram using long polling

        Args:
            offset: Update ID to start from (for acknowledging received messages)
            timeout: Long polling timeout in seconds

        Returns:
            List of updates (messages)
        """
        try:
            url = f"{self.base_url}/getUpdates"
            params = {
                'timeout': timeout,
                'allowed_updates': ['message']
            }

            if offset:
                params['offset'] = offset

            response = requests.get(url, params=params, timeout=timeout + 5)
            response.raise_for_status()

            result = response.json()

            if result.get('ok'):
                return result.get('result', [])
            else:
                print(f"❌ Telegram getUpdates failed: {result}")
                return []

        except requests.exceptions.Timeout:
            # Timeout is normal for long polling
            return []
        except Exception as e:
            print(f"❌ Error getting Telegram updates: {e}")
            return []

    def start_listening_for_commands(self, command_handler):
        """
        Start listening for incoming Telegram commands in background thread

        Args:
            command_handler: CommandHandler instance to process commands

        This starts a background thread that continuously polls Telegram
        for new messages and processes them as commands.
        """
        import threading

        def polling_loop():
            """Background thread for polling Telegram"""
            print("📱 Telegram command listener started")

            offset = None  # Track last update ID

            while True:
                try:
                    # Get updates from Telegram
                    updates = self.get_updates(offset, timeout=30)

                    for update in updates:
                        # Update offset to acknowledge this message
                        offset = update['update_id'] + 1

                        # Extract message
                        if 'message' not in update:
                            continue

                        message = update['message']

                        # Only process text messages
                        if 'text' not in message:
                            continue

                        # Extract details
                        chat_id = message['chat']['id']
                        text = message['text']

                        # Process command
                        print(f"📨 Received command: {text} from {chat_id}")
                        response = command_handler.process_command(text, str(chat_id))

                        # Send response
                        if response:
                            self._send_message(response)

                except KeyboardInterrupt:
                    print("\n🛑 Telegram listener stopped")
                    break
                except Exception as e:
                    print(f"❌ Error in Telegram polling loop: {e}")
                    import time
                    time.sleep(5)  # Wait before retrying

        # Start polling thread
        thread = threading.Thread(target=polling_loop, daemon=True)
        thread.start()

    def send_message(self, text: str) -> bool:
        """
        Public method to send message to Telegram

        Args:
            text: Message text (supports HTML formatting)

        Returns:
            True if sent successfully, False otherwise
        """
        return self._send_message(text)


# Module testing
if __name__ == '__main__':
    import os
    from dotenv import load_dotenv

    # Load credentials
    load_dotenv()
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')

    if not bot_token or not chat_id:
        print("ERROR: Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env file")
        exit(1)

    # Create notifier
    notifier = TelegramNotifier(bot_token, chat_id)

    # Test connection
    print("Testing Telegram notifications...")
    notifier.test_connection()

    # Test entry alert
    notifier.send_entry_alert(
        price=87432.50,
        size_btc=1.1435,
        size_usd=100000,
        entry_time=datetime.now(pytz.UTC),
        trailing_stop_pct=1.0
    )

    print("Check your Telegram for test messages!")

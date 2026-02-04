"""
Telegram Command Handler

Button-based interface for strategy management.

Flow:
1. /strategy → Shows strategy buttons
2. Tap strategy → Shows details + Deploy button
3. Tap Deploy → Asks for capital amount
4. User types amount → Strategy enabled
"""

import os
import platform
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict
import pytz


class CommandHandler:
    """
    Handles Telegram bot commands with button-based UI
    """

    def __init__(self, bot, config: dict):
        self.bot = bot
        self.config = config

        # Authentication
        self.authenticated_until = None
        self.failed_auth_attempts = {}
        self.pin = os.getenv('TELEGRAM_PIN')
        self.pin_timeout_minutes = config.get('security', {}).get('pin_timeout_minutes', 5)
        self.allowed_chat_ids = config.get('security', {}).get('allowed_chat_ids', [])

        # Conversation state - tracks what user is doing
        # e.g., {'chat_id': {'action': 'awaiting_capital', 'strategy': 'oi'}}
        self.conversation_state: Dict[str, dict] = {}

        # Protected commands
        self.protected_commands = ['/disable', '/close', '/withdraw']

    def is_authorized_chat(self, chat_id: str) -> bool:
        if not self.allowed_chat_ids:
            return True
        return str(chat_id) in [str(cid) for cid in self.allowed_chat_ids]

    def is_authenticated(self) -> bool:
        if not self.authenticated_until:
            return False
        return datetime.now(pytz.UTC) < self.authenticated_until

    def process_command(self, message_text: str, chat_id: str):
        """
        Process incoming message

        Returns:
            Tuple of (message, keyboard)
        """
        if not self.is_authorized_chat(chat_id):
            return ("", None)

        chat_id = str(chat_id)
        text = message_text.strip()

        # Check if user is in a conversation flow (e.g., entering capital)
        if chat_id in self.conversation_state:
            return self._handle_conversation_input(chat_id, text)

        # Check authentication for protected commands
        parts = text.split()
        command = parts[0].lower() if parts else ""

        if command in self.protected_commands:
            if not self.is_authenticated():
                return ("🔒 <b>Authentication Required</b>\n\nSend: /auth <pin>", None)

        try:
            if command == '/start':
                return (self._start_message(), None)
            elif command == '/help':
                return (self._help_message(), None)
            elif command == '/status':
                return (self._bot_status_message(), None)
            elif command == '/positions' or command == '/position':
                return (self._positions_message(), None)
            elif command == '/balance':
                return (self._balance_message(), None)
            elif command == '/history':
                return (self._history_message(parts[1:]), None)
            elif command == '/strategy':
                return self._strategy_list()
            elif command == '/auth':
                return (self._handle_auth(parts[1:], chat_id), None)
            elif command == '/enable':
                return (self._handle_enable(), None)
            elif command == '/disable':
                return (self._handle_disable(), None)
            elif command == '/close':
                return (self._handle_close(), None)
            elif command == '/deposit':
                return (self._deposit_message(), None)
            elif command == '/withdraw':
                return (self._handle_withdraw(parts[1:]), None)
            else:
                return (f"Unknown command. Send /help", None)

        except Exception as e:
            self.bot.logger.error(f"Error: {e}", exc_info=True)
            return (f"Error: {str(e)}", None)

    def process_callback(self, callback_data: str, chat_id: str):
        """
        Process button callback

        Returns:
            Tuple of (message, keyboard)
        """
        chat_id = str(chat_id)
        data = callback_data.strip()

        try:
            # Strategy list
            if data == 'strategy_list':
                return self._strategy_list()

            # View specific strategy
            elif data.startswith('strategy_view_'):
                strategy_name = data.replace('strategy_view_', '')
                return self._strategy_details(strategy_name)

            # Deploy strategy (ask for capital)
            elif data.startswith('strategy_deploy_'):
                strategy_name = data.replace('strategy_deploy_', '')
                return self._ask_for_capital(chat_id, strategy_name)

            # Reallocate strategy capital
            elif data.startswith('strategy_reallocate_'):
                strategy_name = data.replace('strategy_reallocate_', '')
                return self._ask_for_reallocate(chat_id, strategy_name)

            # Disable strategy
            elif data.startswith('strategy_disable_'):
                strategy_name = data.replace('strategy_disable_', '')
                return self._disable_strategy(strategy_name)

            # Close position for strategy
            elif data.startswith('close_'):
                strategy_name = data.replace('close_', '')
                result = self.bot.emergency_close_position(strategy_name)
                return (result, None)

            # Back to strategy list
            elif data == 'back_to_strategies':
                return self._strategy_list()

            else:
                return (f"Unknown action: {data}", None)

        except Exception as e:
            self.bot.logger.error(f"Callback error: {e}", exc_info=True)
            return (f"Error: {str(e)}", None)

    def _handle_conversation_input(self, chat_id: str, text: str):
        """Handle input when user is in a conversation flow"""
        state = self.conversation_state.get(chat_id)

        if not state:
            return ("", None)

        action = state.get('action')

        if action == 'awaiting_capital':
            strategy_name = state.get('strategy')

            # Clear conversation state
            del self.conversation_state[chat_id]

            # Parse amount
            try:
                amount = float(text.replace(',', '').replace('$', '').strip())
            except ValueError:
                return (f"❌ Invalid amount: {text}\n\nPlease enter a number (e.g., 50000)", None)

            if amount <= 0:
                return ("❌ Amount must be greater than 0", None)

            # Enable the strategy
            result = self.bot.enable_strategy(strategy_name, amount)

            # Show success with back button
            keyboard = {
                "inline_keyboard": [[
                    {"text": "◀️ Back to Strategies", "callback_data": "strategy_list"}
                ]]
            }

            return (f"✅ {result}", keyboard)

        elif action == 'awaiting_reallocate':
            strategy_name = state.get('strategy')

            # Clear conversation state
            del self.conversation_state[chat_id]

            # Parse amount
            try:
                amount = float(text.replace(',', '').replace('$', '').strip())
            except ValueError:
                return (f"Invalid amount: {text}\n\nPlease enter a number (e.g., 100)", None)

            if amount <= 0:
                return ("Amount must be greater than 0", None)

            # Reallocate the strategy
            result = self.bot.reallocate_strategy(strategy_name, amount)

            keyboard = {
                "inline_keyboard": [[
                    {"text": "Back to Strategies", "callback_data": "strategy_list"}
                ]]
            }

            return (result, keyboard)

        # Unknown state
        del self.conversation_state[chat_id]
        return ("", None)

    def _start_message(self) -> str:
        return """🤖 <b>TRADING BOT</b>

Multi-strategy BTC trading bot on HyperLiquid.

<b>Quick Start:</b>
• /status - Check bot status
• /strategy - Deploy a strategy
• /positions - View P&amp;L

Send /help for all commands."""

    def _help_message(self) -> str:
        return """
📚 <b>COMMANDS</b>

<b>Status</b>
/status - Bot status & environment
/positions - View all positions & P&L
/history - Trade history
/balance - Quick balance check

<b>Trading</b>
/strategy - Manage strategies
/enable - Unpause bot
/disable - Pause bot 🔒
/close - Close all positions 🔒

<b>Funds</b>
/deposit - Get deposit address
/withdraw &lt;amount&gt; - Withdraw USDC 🔒

/auth &lt;pin&gt; - Authenticate

🔒 = Requires PIN
"""

    def _bot_status_message(self) -> str:
        """Simple bot status - running state and environment"""
        try:
            is_paused = self.bot.is_paused
            status = "🛑 PAUSED" if is_paused else "✅ RUNNING"
            env = "🖥️ Local" if platform.system() == "Darwin" else "☁️ Railway"

            enabled = self.bot.state_manager.get_enabled_strategies()
            strategies = ", ".join(enabled) if enabled else "None"

            return f"""🤖 <b>BOT STATUS</b>

<b>State:</b> {status}
<b>Environment:</b> {env}
<b>Strategies:</b> {strategies}"""
        except Exception as e:
            return f"Error: {str(e)}"

    def _positions_message(self) -> str:
        try:
            try:
                current_price = self.bot.exchange.get_btc_price()
            except:
                current_price = None

            try:
                balance = self.bot.exchange.get_account_balance()
            except:
                balance = None

            msg = f"📊 <b>POSITIONS</b>\n\n"

            if current_price:
                msg += f"<b>BTC:</b> ${current_price:,.2f}\n"
            if balance:
                msg += f"<b>Balance:</b> ${balance:,.2f}\n"

            # Get all strategy states for detailed view
            enabled_strategies = self.bot.state_manager.get_enabled_strategies()

            if enabled_strategies:
                msg += f"\n{'─'*25}\n"
                msg += f"<b>ACTIVE STRATEGIES</b>\n"

                total_allocated = 0
                total_unrealized = 0
                total_realized = 0

                for strategy_name in enabled_strategies:
                    state = self.bot.state_manager.get_strategy_state(strategy_name)

                    capital = state.get('allocated_capital_usd', 0)
                    trade_count = state.get('trade_count', 0)
                    realized_pnl = state.get('total_realized_pnl', 0)
                    enabled_since = state.get('enabled_since')
                    in_position = state.get('in_position', False)

                    total_allocated += capital
                    total_realized += realized_pnl

                    msg += f"\n<b>▸ {strategy_name.upper()}</b>\n"
                    msg += f"   Capital: ${capital:,.0f}\n"

                    # Running since
                    if enabled_since:
                        try:
                            start = datetime.fromisoformat(enabled_since)
                            days = (datetime.utcnow() - start).days
                            if days == 0:
                                msg += f"   Running: Today\n"
                            elif days == 1:
                                msg += f"   Running: 1 day\n"
                            else:
                                msg += f"   Running: {days} days\n"
                        except:
                            pass

                    msg += f"   Trades: {trade_count}\n"

                    # Last trade time
                    last_trade_time = state.get('last_trade_time')
                    if last_trade_time:
                        try:
                            last_trade = datetime.fromisoformat(last_trade_time)
                            time_ago = datetime.utcnow() - last_trade
                            hours_ago = int(time_ago.total_seconds() // 3600)
                            if hours_ago < 1:
                                mins_ago = int(time_ago.total_seconds() // 60)
                                msg += f"   Last trade: {mins_ago}m ago\n"
                            elif hours_ago < 24:
                                msg += f"   Last trade: {hours_ago}h ago\n"
                            else:
                                days_ago = hours_ago // 24
                                msg += f"   Last trade: {days_ago}d ago\n"
                        except:
                            pass
                    else:
                        msg += f"   Last trade: None yet\n"

                    # Position & P&L
                    if in_position:
                        entry = state.get('entry_price', 0)
                        size = state.get('position_size_btc', 0)

                        if current_price and entry:
                            unrealized_pnl = (current_price - entry) * size
                            unrealized_pct = ((current_price - entry) / entry) * 100
                            total_unrealized += unrealized_pnl

                            emoji = "🟢" if unrealized_pnl >= 0 else "🔴"
                            msg += f"   {emoji} Position: {size:.4f} BTC @ ${entry:,.0f}\n"
                            msg += f"   {emoji} Unrealized: {unrealized_pct:+.2f}% (${unrealized_pnl:+,.0f})\n"
                    else:
                        msg += f"   Position: None\n"
                        # Show what conditions we're monitoring for
                        if strategy_name == 'overnight':
                            params = self.config.get('strategies', {}).get('overnight', {}).get('params', {})
                            max_price = params.get('max_entry_price_usd', 90000)
                            msg += f"   ⏳ Waiting: 20:00 GMT + BTC &lt; ${max_price:,.0f}\n"
                        elif strategy_name == 'oi':
                            params = self.config.get('strategies', {}).get('oi', {}).get('params', {})
                            oi_thresh = abs(params.get('oi_drop_threshold', 0.15))
                            price_thresh = abs(params.get('price_drop_threshold', 0.3))
                            msg += f"   👁️ Monitoring: OI drop ≥{oi_thresh}% + Price drop ≥{price_thresh}%\n"

                    # Realized P&L
                    if realized_pnl != 0:
                        roi = (realized_pnl / capital * 100) if capital > 0 else 0
                        emoji = "🟢" if realized_pnl >= 0 else "🔴"
                        msg += f"   {emoji} Realized: ${realized_pnl:+,.0f} ({roi:+.1f}% ROI)\n"

                # Totals
                msg += f"\n{'─'*25}\n"
                msg += f"<b>TOTALS</b>\n"
                msg += f"   Allocated: ${total_allocated:,.0f}\n"
                if total_unrealized != 0:
                    emoji = "🟢" if total_unrealized >= 0 else "🔴"
                    msg += f"   {emoji} Unrealized: ${total_unrealized:+,.0f}\n"
                if total_realized != 0:
                    emoji = "🟢" if total_realized >= 0 else "🔴"
                    msg += f"   {emoji} Realized: ${total_realized:+,.0f}\n"

            else:
                msg += f"\n<b>Strategies:</b> None active\n"
                msg += f"Use /strategy to deploy"

            return msg

        except Exception as e:
            return f"Error: {str(e)}"

    def _balance_message(self) -> str:
        try:
            balance = self.bot.exchange.get_account_balance()
            allocated = self.bot.state_manager.get_total_allocated_capital()
            available = balance - allocated

            return f"""💰 <b>BALANCE</b>

<b>Total:</b> ${balance:,.2f}
<b>Allocated:</b> ${allocated:,.2f}
<b>Available:</b> ${available:,.2f}"""

        except Exception as e:
            return f"Error: {str(e)}"

    def _history_message(self, args: list) -> str:
        """Show trade history grouped by strategy"""
        try:
            # Get locally tracked trades (have strategy names)
            local_trades = self.bot.state_manager.get_trade_history(limit=50)

            # Get API trades (have fees, cover pre-tracking history)
            api_trades = self.bot.exchange.get_trade_history()

            if not local_trades and not api_trades:
                return "📜 No trade history yet"

            msg = "📜 <b>TRADE HISTORY</b>\n"
            total_pnl = 0
            total_fees = 0
            wins = 0
            trade_count = 0

            # Group local trades by strategy
            by_strategy = {}
            local_exit_times = set()
            for t in local_trades:
                name = t.get('strategy', 'unknown')
                if name not in by_strategy:
                    by_strategy[name] = []
                by_strategy[name].append(t)
                # Track exit times to identify API-only trades
                if t.get('exit_time'):
                    local_exit_times.add(t['exit_time'])

            # Show each strategy's trades
            for strategy_name, trades in by_strategy.items():
                msg += f"\n<b>▸ {strategy_name.upper()}</b>\n"

                for t in trades:
                    emoji = "🟢" if t['profit_pct'] >= 0 else "🔴"
                    if t['profit_pct'] >= 0:
                        wins += 1
                    total_pnl += t.get('profit_usd', 0)
                    trade_count += 1

                    try:
                        exit_dt = datetime.fromisoformat(t['exit_time'])
                        date_str = exit_dt.strftime('%b %d %H:%M')
                    except:
                        date_str = "?"

                    msg += f"  {emoji} {date_str} UTC\n"
                    msg += f"     ${t['entry_price']:,.0f} → ${t['exit_price']:,.0f}"
                    msg += f"  {t['profit_pct']:+.2f}% (${t.get('profit_usd', 0):+,.2f})\n"

            # Find API trades not in local history (pre-tracking)
            unmatched_api = []
            for api_t in api_trades:
                # Convert API ms timestamp to ISO for comparison
                try:
                    api_exit_iso = datetime.utcfromtimestamp(
                        api_t['exit_time_ms'] / 1000
                    ).isoformat()
                except:
                    api_exit_iso = None

                # Check if this trade is already in local history
                matched = False
                if api_exit_iso:
                    for local_time in local_exit_times:
                        # Match within 60 seconds
                        try:
                            local_dt = datetime.fromisoformat(local_time)
                            api_dt = datetime.fromisoformat(api_exit_iso)
                            if abs((local_dt - api_dt).total_seconds()) < 60:
                                matched = True
                                break
                        except:
                            pass
                if not matched:
                    unmatched_api.append(api_t)

            # Show pre-tracking trades from API
            if unmatched_api:
                msg += f"\n<b>▸ EARLIER (pre-tracking)</b>\n"
                for t in unmatched_api:
                    emoji = "🟢" if t['profit_pct'] >= 0 else "🔴"
                    if t['profit_pct'] >= 0:
                        wins += 1
                    total_pnl += t.get('profit_usd', 0)
                    total_fees += t.get('fees', 0)
                    trade_count += 1

                    try:
                        exit_dt = datetime.utcfromtimestamp(t['exit_time_ms'] / 1000)
                        date_str = exit_dt.strftime('%b %d %H:%M')
                    except:
                        date_str = "?"

                    msg += f"  {emoji} {t['coin']} {date_str} UTC\n"
                    msg += f"     ${t['entry_price']:,.0f} → ${t['exit_price']:,.0f}"
                    msg += f"  {t['profit_pct']:+.2f}% (${t.get('profit_usd', 0):+,.2f})\n"

            # Also tally fees from API trades that matched local ones
            for api_t in api_trades:
                if api_t not in unmatched_api:
                    total_fees += api_t.get('fees', 0)

            # Summary
            msg += f"\n{'─'*25}\n"
            msg += f"<b>Trades:</b> {trade_count}"
            if trade_count:
                msg += f" | <b>Win Rate:</b> {wins}/{trade_count} ({wins/trade_count*100:.0f}%)"
            net_pnl = total_pnl - total_fees
            msg += f"\n<b>Gross P&L:</b> ${total_pnl:+,.2f}"
            msg += f"\n<b>Fees:</b> -${total_fees:,.2f}"
            msg += f"\n<b>Net P&L:</b> ${net_pnl:+,.2f}"

            return msg

        except Exception as e:
            return f"Error: {str(e)}"

    def _strategy_list(self) -> Tuple[str, dict]:
        """Show list of strategies as buttons"""
        try:
            summaries = self.bot.get_strategies_summary()

            msg = "📈 <b>STRATEGIES</b>\n\n"
            msg += "Select a strategy to view details:\n"

            buttons = []
            for s in summaries:
                name = s['name']
                enabled = s['enabled']
                capital = s['allocated_capital_usd']

                if enabled:
                    label = f"🟢 {name.upper()} (${capital:,.0f})"
                else:
                    label = f"⚪ {name.upper()}"

                buttons.append([{
                    "text": label,
                    "callback_data": f"strategy_view_{name}"
                }])

            keyboard = {"inline_keyboard": buttons}

            return (msg, keyboard)

        except Exception as e:
            return (f"Error: {str(e)}", None)

    def _strategy_details(self, strategy_name: str) -> Tuple[str, dict]:
        """Show strategy details with action buttons"""
        try:
            summaries = self.bot.get_strategies_summary()
            strategy = next((s for s in summaries if s['name'] == strategy_name), None)

            if not strategy:
                return (f"Strategy not found: {strategy_name}", None)

            enabled = strategy['enabled']
            capital = strategy['allocated_capital_usd']
            in_position = strategy['in_position']

            status = "🟢 DEPLOYED" if enabled else "⚪ NOT DEPLOYED"

            msg = f"📊 <b>{strategy_name.upper()}</b>\n"
            msg += f"{status}\n\n"

            # Strategy-specific FULL descriptions
            if strategy_name == 'overnight':
                params = self.config.get('strategies', {}).get('overnight', {}).get('params', {})
                entry_hour = params.get('entry_hour', 15)
                trailing_stop = params.get('trailing_stop_pct', 1.0)
                max_price = params.get('max_entry_price_usd', 90000)

                msg += f"<b>🎯 Overview:</b>\n"
                msg += f"Capitalize on Bitcoin's tendency to recover overnight after intraday weakness. "
                msg += f"Enters at a fixed time daily and holds until trailing stop hits.\n\n"

                msg += f"<b>📥 ENTRY CONDITIONS:</b>\n"
                msg += f"• <b>Time:</b> {entry_hour}:00 EST (20:00 GMT) daily\n"
                msg += f"• <b>Price Filter:</b> BTC must be below ${max_price:,.0f}\n"
                msg += f"• <b>Position Check:</b> Not already in a position\n"
                msg += f"• <b>Action:</b> Market buy with allocated capital\n\n"

                msg += f"<b>📤 EXIT CONDITIONS:</b>\n"
                msg += f"• <b>Trailing Stop:</b> {trailing_stop}% from peak price\n"
                msg += f"• <b>Protection:</b> NEVER sells at a loss\n"
                msg += f"• <b>Peak Tracking:</b> Continuously updates highest price\n"
                msg += f"• <b>Trigger:</b> Price drops {trailing_stop}% from peak → sell\n\n"

                msg += f"<b>📊 BACKTEST (Dec 2024, 1-month):</b>\n"
                msg += f"• <b>Return:</b> +17.95%\n"
                msg += f"• <b>Win Rate:</b> 76.9% (20/26 trades)\n"
                msg += f"• <b>Max Drawdown:</b> -3.25%\n"
                msg += f"• <b>Avg Win:</b> +1.2% | <b>Largest:</b> +3.8%\n"

            elif strategy_name == 'oi':
                params = self.config.get('strategies', {}).get('oi', {}).get('params', {})
                oi_drop = abs(params.get('oi_drop_threshold', 0.15))
                price_drop = abs(params.get('price_drop_threshold', 0.3))
                profit_target = params.get('profit_target_pct', 1.0)
                cooldown = params.get('cooldown_minutes', 60)

                msg += f"<b>🎯 Overview:</b>\n"
                msg += f"Detects forced liquidations via Open Interest drops. "
                msg += f"When OI drops sharply with price, it signals forced selling → buy the dip.\n\n"

                msg += f"<b>📥 ENTRY CONDITIONS:</b>\n"
                msg += f"• <b>OI Drop:</b> ≥{oi_drop}% in 5 minutes\n"
                msg += f"• <b>Price Drop:</b> ≥{price_drop}% in 5 minutes\n"
                msg += f"• <b>Cooldown:</b> {cooldown} min between trades\n"
                msg += f"• <b>Action:</b> Market buy on signal\n\n"

                msg += f"<b>📤 EXIT CONDITIONS:</b>\n"
                msg += f"• <b>Profit Target:</b> +{profit_target}% from entry\n"
                msg += f"• <b>Stop Loss:</b> NONE (never sell at loss)\n"
                msg += f"• <b>Hold:</b> Until profit target reached\n\n"

                msg += f"<b>📊 BACKTEST (Dec 2024, 1-month):</b>\n"
                msg += f"• <b>Return:</b> +8.2%\n"
                msg += f"• <b>Win Rate:</b> 100% (12/12 trades)\n"
                msg += f"• <b>Max Drawdown:</b> -4.1%\n"
                msg += f"• <b>Avg Hold:</b> 2-6 hours\n"

            if enabled:
                msg += f"\n<b>💰 Allocated Capital:</b> ${capital:,.0f}\n"

            # Position info
            if in_position:
                entry = strategy['entry_price']
                size = strategy['position_size_btc']

                try:
                    price = self.bot.exchange.get_btc_price()
                    pnl_pct = ((price - entry) / entry) * 100
                    pnl_usd = (price - entry) * size
                    emoji = "🟢" if pnl_pct >= 0 else "🔴"

                    msg += f"\n{emoji} <b>POSITION:</b>\n"
                    msg += f"   Entry: ${entry:,.0f}\n"
                    msg += f"   Size: {size:.4f} BTC\n"
                    msg += f"   P&L: {pnl_pct:+.2f}% (${pnl_usd:+,.0f})\n"
                except:
                    msg += f"\n<b>Position:</b> {size:.4f} BTC @ ${entry:,.0f}\n"

            # Build action buttons
            buttons = []

            if enabled:
                if in_position:
                    # Has position - show close button
                    buttons.append([{
                        "text": "🛑 Close Position",
                        "callback_data": f"close_{strategy_name}"
                    }])
                # Show update capital button
                buttons.append([{
                    "text": "💰 Update Capital",
                    "callback_data": f"strategy_reallocate_{strategy_name}"
                }])
                # Show disable button
                buttons.append([{
                    "text": "⏹️ Stop Strategy",
                    "callback_data": f"strategy_disable_{strategy_name}"
                }])
            else:
                # Not deployed - show deploy button
                buttons.append([{
                    "text": "🚀 Deploy Strategy",
                    "callback_data": f"strategy_deploy_{strategy_name}"
                }])

            # Back button
            buttons.append([{
                "text": "◀️ Back",
                "callback_data": "strategy_list"
            }])

            keyboard = {"inline_keyboard": buttons}

            return (msg, keyboard)

        except Exception as e:
            return (f"Error: {str(e)}", None)

    def _ask_for_capital(self, chat_id: str, strategy_name: str) -> Tuple[str, dict]:
        """Ask user to enter capital amount"""
        # Set conversation state
        self.conversation_state[chat_id] = {
            'action': 'awaiting_capital',
            'strategy': strategy_name
        }

        try:
            balance = self.bot.exchange.get_account_balance()
            allocated = self.bot.state_manager.get_total_allocated_capital()
            available = balance - allocated

            msg = f"💵 <b>DEPLOY {strategy_name.upper()}</b>\n\n"
            msg += f"<b>Available Balance:</b> ${available:,.0f}\n\n"
            msg += f"Enter the amount of capital to allocate:\n\n"
            msg += f"<i>Example: 50000</i>"

            # Cancel button
            keyboard = {
                "inline_keyboard": [[{
                    "text": "❌ Cancel",
                    "callback_data": f"strategy_view_{strategy_name}"
                }]]
            }

            return (msg, keyboard)

        except Exception as e:
            del self.conversation_state[chat_id]
            return (f"Error: {str(e)}", None)

    def _ask_for_reallocate(self, chat_id: str, strategy_name: str) -> Tuple[str, dict]:
        """Ask user to enter new capital amount for reallocation"""
        self.conversation_state[chat_id] = {
            'action': 'awaiting_reallocate',
            'strategy': strategy_name
        }

        try:
            balance = self.bot.exchange.get_account_balance()
            current_capital = self.bot.state_manager.get_strategy_capital(strategy_name)
            total_allocated = self.bot.state_manager.get_total_allocated_capital()
            other_allocated = total_allocated - current_capital
            available = balance - other_allocated

            msg = f"💰 <b>REALLOCATE {strategy_name.upper()}</b>\n\n"
            msg += f"<b>Current Allocation:</b> ${current_capital:,.0f}\n"
            msg += f"<b>Account Balance:</b> ${balance:,.0f}\n"
            msg += f"<b>Other Strategies:</b> ${other_allocated:,.0f}\n"
            msg += f"<b>Max Available:</b> ${available:,.0f}\n\n"
            msg += f"Enter the new capital amount:\n\n"
            msg += f"<i>Example: {int(available)}</i>"

            keyboard = {
                "inline_keyboard": [[{
                    "text": "Cancel",
                    "callback_data": f"strategy_view_{strategy_name}"
                }]]
            }

            return (msg, keyboard)

        except Exception as e:
            del self.conversation_state[chat_id]
            return (f"Error: {str(e)}", None)

    def _disable_strategy(self, strategy_name: str) -> Tuple[str, dict]:
        """Disable a strategy"""
        result = self.bot.disable_strategy(strategy_name)

        keyboard = {
            "inline_keyboard": [[{
                "text": "◀️ Back to Strategies",
                "callback_data": "strategy_list"
            }]]
        }

        return (result, keyboard)

    def _handle_auth(self, args: list, chat_id: str) -> str:
        if not self.pin:
            return "PIN not configured"

        failed = self.failed_auth_attempts.get(chat_id, 0)
        if failed >= 5:
            return "🔒 Too many attempts. Wait 1 hour."

        if not args:
            return "Usage: /auth <pin>"

        if args[0] == self.pin:
            self.authenticated_until = datetime.now(pytz.UTC) + timedelta(minutes=self.pin_timeout_minutes)
            self.failed_auth_attempts[chat_id] = 0
            return f"✅ Authenticated for {self.pin_timeout_minutes} minutes"
        else:
            self.failed_auth_attempts[chat_id] = failed + 1
            return f"❌ Wrong PIN. {5 - failed - 1} attempts left."

    def _handle_enable(self) -> str:
        self.bot.enable_trading()
        enabled = self.bot.state_manager.get_enabled_strategies()
        if enabled:
            return f"✅ Bot unpaused\n\nActive: {', '.join(enabled)}"
        return "✅ Bot unpaused\n\nNo strategies deployed. Use /strategy"

    def _handle_disable(self) -> str:
        self.bot.disable_trading()
        return "🛑 Bot paused"

    def _handle_close(self) -> str:
        return self.bot.emergency_close_position()

    def _deposit_message(self) -> str:
        """Show deposit information"""
        try:
            balance = self.bot.exchange.get_account_balance()
            wallet = self.bot.exchange.wallet_address

            msg = "💰 <b>DEPOSIT USDC</b>\n\n"
            msg += f"<b>Current Balance:</b> ${balance:,.2f}\n\n"

            msg += "<b>Option 1: Send USDC on HyperLiquid L1</b>\n"
            msg += f"<code>{wallet}</code>\n"
            msg += "Send USDC directly on HyperLiquid L1 (not HyperEVM).\n"
            msg += "Lands in your trading account instantly.\n\n"

            msg += "<b>Option 2: Bridge from Arbitrum</b>\n"
            msg += "Go to <a href='https://app.hyperliquid.xyz/portfolio'>app.hyperliquid.xyz</a>\n"
            msg += "Connect wallet → Deposit → Follow prompts.\n"
            msg += "Takes 1-5 minutes.\n\n"

            msg += "⚠️ Do NOT send on HyperEVM — that's a different chain.\n\n"
            msg += "🔑 Wallet is under <b>Bob McGee</b> Chrome profile."

            return msg

        except Exception as e:
            return f"Error: {str(e)}"

    def _handle_withdraw(self, args: list) -> str:
        """Handle withdraw command"""
        try:
            if not args:
                # Show current balance and usage
                balance = self.bot.exchange.get_account_balance()
                allocated = self.bot.state_manager.get_total_allocated_capital()
                available = balance - allocated

                return f"""💸 <b>WITHDRAW USDC</b>

<b>Balance:</b> ${balance:,.2f}
<b>Allocated:</b> ${allocated:,.2f}
<b>Available:</b> ${available:,.2f}

<b>Usage:</b>
<code>/withdraw &lt;amount&gt;</code>

<b>Example:</b>
<code>/withdraw 100</code>

⚠️ Withdrawals go to your connected wallet on Arbitrum.
Processing time: 1-10 minutes."""

            # Parse amount
            try:
                amount = float(args[0].replace(',', '').replace('$', '').strip())
            except ValueError:
                return f"❌ Invalid amount: {args[0]}\n\nUsage: /withdraw 100"

            if amount <= 0:
                return "❌ Amount must be greater than 0"

            # Check available balance
            balance = self.bot.exchange.get_account_balance()
            allocated = self.bot.state_manager.get_total_allocated_capital()
            available = balance - allocated

            if amount > available:
                return f"""❌ <b>Insufficient funds</b>

<b>Requested:</b> ${amount:,.2f}
<b>Available:</b> ${available:,.2f}

You can only withdraw unallocated funds.
Disable strategies first to free up capital."""

            # Execute withdrawal
            result = self.bot.exchange.withdraw(amount)

            if result.get('success'):
                return f"""✅ <b>WITHDRAWAL INITIATED</b>

<b>Amount:</b> ${amount:,.2f} USDC
<b>Network:</b> Arbitrum One
<b>Destination:</b> Your connected wallet

⏳ Processing time: 1-10 minutes

Check your wallet for the funds."""
            else:
                error = result.get('error', 'Unknown error')
                return f"""❌ <b>WITHDRAWAL FAILED</b>

<b>Amount:</b> ${amount:,.2f}
<b>Error:</b> {error}

Please try again or check HyperLiquid status."""

        except Exception as e:
            return f"Error: {str(e)}"

"""
Backtesting Engine with Short Selling Support

Extended version of the backtester that can handle both LONG and SHORT positions.
This enables testing strategies that profit from price declines (like Brandon Hong's
CME Sunday Open strategy for Bitcoin shorts).

LEARNING MOMENT: Long vs Short Trading
=========================================
LONG: Buy first, sell later. Profit when price goes UP.
      Buy at $100 → Sell at $110 → Profit = $10

SHORT: Sell first (borrowed), buy later. Profit when price goes DOWN.
       Short at $100 → Cover at $90 → Profit = $10

In practice: When you short, you're borrowing the asset and immediately selling it,
then buying it back later to return what you borrowed. If price dropped, you
pocket the difference.
"""

import pandas as pd
import numpy as np
from datetime import datetime


class BacktesterWithShorts:
    """
    Backtester that supports both LONG and SHORT positions

    Signals:
    - 'BUY' or 'LONG': Open a long position (buy the asset)
    - 'SELL' or 'CLOSE_LONG': Close a long position
    - 'SHORT': Open a short position (sell borrowed asset)
    - 'COVER' or 'CLOSE_SHORT': Close a short position (buy back)
    - 'HOLD': Do nothing
    """

    def __init__(self, initial_capital=10000, fee_percent=0.1, display_timezone='UTC'):
        """
        Args:
            initial_capital: Starting money (e.g., $10,000)
            fee_percent: Trading fee per trade (0.1% = Binance standard)
            display_timezone: Timezone for displaying trade times
        """
        self.initial_capital = initial_capital
        self.fee_percent = fee_percent / 100
        self.display_timezone = display_timezone
        self._reset()

    def _reset(self):
        """Reset portfolio state for a new backtest"""
        self.cash = self.initial_capital
        self.position = 0  # Positive = long, Negative = short, 0 = flat
        self.position_entry_price = 0
        self.position_direction = 'flat'  # 'long', 'short', or 'flat'
        self.trades = []
        self.portfolio_values = []

    def run(self, data, strategy, silent=False):
        """
        Run backtest on historical data

        Args:
            data: DataFrame with OHLCV data
            strategy: Strategy object with generate_signals() method
            silent: If True, suppress print output

        Returns:
            Dictionary with results and metrics
        """
        self._reset()

        if not silent:
            print(f"\n{'='*60}")
            print(f"Starting Backtest")
            print(f"{'='*60}")
            print(f"Initial Capital: ${self.initial_capital:,.2f}")
            print(f"Trading Fee: {self.fee_percent*100}%")
            print(f"Data Period: {data.index[0]} to {data.index[-1]}")
            print(f"Total Candles: {len(data)}")
            print(f"{'='*60}\n")

        # Generate signals from strategy
        signals = strategy.generate_signals(data)

        # Walk through each candle
        for i in range(len(data)):
            timestamp = data.index[i]
            candle = data.iloc[i]
            signal = signals.iloc[i]['signal'] if 'signal' in signals.columns else signals.iloc[i]

            # Calculate current portfolio value
            portfolio_value = self._calculate_portfolio_value(candle['close'])
            self.portfolio_values.append({
                'timestamp': timestamp,
                'value': portfolio_value,
                'cash': self.cash,
                'position': self.position,
                'position_direction': self.position_direction,
                'price': candle['close']
            })

            # Execute trade based on signal
            self._process_signal(signal, timestamp, candle['close'], silent)

        # Calculate final metrics
        results = self._calculate_metrics(data, silent)
        return results

    def _calculate_portfolio_value(self, current_price):
        """Calculate total portfolio value including open positions"""
        if self.position_direction == 'flat':
            return self.cash
        elif self.position_direction == 'long':
            return self.cash + (self.position * current_price)
        elif self.position_direction == 'short':
            # Short position: We have cash from selling, but owe the asset
            # Value = cash we have - cost to buy back the asset
            # When we shorted, we got cash. Now we need to buy back.
            # If price dropped, we profit. If price rose, we lose.
            short_liability = abs(self.position) * current_price
            return self.cash - short_liability
        return self.cash

    def _process_signal(self, signal, timestamp, price, silent):
        """Process a trading signal"""
        signal = signal.upper() if isinstance(signal, str) else signal

        # LONG ENTRY
        if signal in ['BUY', 'LONG'] and self.position_direction == 'flat':
            self._open_long(timestamp, price, silent)

        # LONG EXIT
        elif signal in ['SELL', 'CLOSE_LONG'] and self.position_direction == 'long':
            self._close_long(timestamp, price, silent)

        # SHORT ENTRY
        elif signal == 'SHORT' and self.position_direction == 'flat':
            self._open_short(timestamp, price, silent)

        # SHORT EXIT
        elif signal in ['COVER', 'CLOSE_SHORT'] and self.position_direction == 'short':
            self._close_short(timestamp, price, silent)

        # UNIVERSAL CLOSE (close any position)
        elif signal == 'CLOSE':
            if self.position_direction == 'long':
                self._close_long(timestamp, price, silent)
            elif self.position_direction == 'short':
                self._close_short(timestamp, price, silent)

    def _open_long(self, timestamp, price, silent):
        """Open a long position (buy)"""
        cost_with_fee = price * (1 + self.fee_percent)
        coins_to_buy = self.cash / cost_with_fee

        if coins_to_buy > 0:
            self.position = coins_to_buy
            self.position_entry_price = price
            self.position_direction = 'long'
            self.cash = 0

            self.trades.append({
                'timestamp': timestamp,
                'type': 'LONG_OPEN',
                'price': price,
                'amount': coins_to_buy,
                'fee': coins_to_buy * price * self.fee_percent,
                'portfolio_value': self.position * price
            })

            if not silent:
                display_time = self._format_timestamp(timestamp)
                print(f"LONG  | {display_time} | Entry: ${price:,.2f} | Amount: {coins_to_buy:.6f}")

    def _close_long(self, timestamp, price, silent):
        """Close a long position (sell)"""
        proceeds = self.position * price
        fee = proceeds * self.fee_percent
        self.cash = proceeds - fee

        cost_basis = self.position * self.position_entry_price
        pnl = self.cash - cost_basis
        pnl_percent = (pnl / cost_basis) * 100 if cost_basis > 0 else 0

        self.trades.append({
            'timestamp': timestamp,
            'type': 'LONG_CLOSE',
            'price': price,
            'amount': self.position,
            'fee': fee,
            'pnl': pnl,
            'pnl_percent': pnl_percent,
            'portfolio_value': self.cash
        })

        if not silent:
            display_time = self._format_timestamp(timestamp)
            emoji = "+" if pnl >= 0 else ""
            print(f"CLOSE | {display_time} | Exit: ${price:,.2f} | P&L: ${pnl:,.2f} ({emoji}{pnl_percent:.2f}%)")

        self.position = 0
        self.position_entry_price = 0
        self.position_direction = 'flat'

    def _open_short(self, timestamp, price, silent):
        """
        Open a short position (sell borrowed asset)

        How it works:
        1. We "borrow" coins and immediately sell them
        2. We receive cash from the sale
        3. We now owe the coins (negative position)
        4. Later we buy back (cover) to return the borrowed coins
        """
        # Calculate how many coins we can short with our capital
        # We need margin to cover potential losses - using 1:1 for simplicity
        coins_to_short = self.cash / price
        proceeds = coins_to_short * price
        fee = proceeds * self.fee_percent

        # After shorting: we have our original cash + proceeds from short sale - fee
        # But we owe the coins
        self.cash = self.cash + proceeds - fee
        self.position = -coins_to_short  # Negative = short
        self.position_entry_price = price
        self.position_direction = 'short'

        self.trades.append({
            'timestamp': timestamp,
            'type': 'SHORT_OPEN',
            'price': price,
            'amount': coins_to_short,
            'fee': fee,
            'portfolio_value': self._calculate_portfolio_value(price)
        })

        if not silent:
            display_time = self._format_timestamp(timestamp)
            print(f"SHORT | {display_time} | Entry: ${price:,.2f} | Amount: {coins_to_short:.6f}")

    def _close_short(self, timestamp, price, silent):
        """
        Close a short position (buy back to cover)

        If price dropped since we shorted: we profit
        If price rose: we lose
        """
        coins_to_cover = abs(self.position)
        cost_to_cover = coins_to_cover * price
        fee = cost_to_cover * self.fee_percent

        # P&L calculation for short:
        # We sold at entry_price, now buying back at current price
        # Profit = (entry_price - current_price) * coins
        pnl = (self.position_entry_price - price) * coins_to_cover - fee

        # Update cash
        self.cash = self.cash - cost_to_cover - fee

        # Calculate P&L percentage based on initial margin
        initial_margin = coins_to_cover * self.position_entry_price
        pnl_percent = (pnl / initial_margin) * 100 if initial_margin > 0 else 0

        self.trades.append({
            'timestamp': timestamp,
            'type': 'SHORT_CLOSE',
            'price': price,
            'amount': coins_to_cover,
            'fee': fee,
            'pnl': pnl,
            'pnl_percent': pnl_percent,
            'portfolio_value': self.cash
        })

        if not silent:
            display_time = self._format_timestamp(timestamp)
            emoji = "+" if pnl >= 0 else ""
            print(f"COVER | {display_time} | Exit: ${price:,.2f} | P&L: ${pnl:,.2f} ({emoji}{pnl_percent:.2f}%)")

        self.position = 0
        self.position_entry_price = 0
        self.position_direction = 'flat'

    def _format_timestamp(self, timestamp):
        """Convert timestamp to display timezone"""
        if hasattr(timestamp, 'tz_localize'):
            if timestamp.tz is None:
                timestamp = timestamp.tz_localize('UTC')
            if self.display_timezone != 'UTC':
                timestamp = timestamp.tz_convert(self.display_timezone)
        return timestamp

    def _calculate_metrics(self, data, silent):
        """Calculate performance metrics"""
        portfolio_df = pd.DataFrame(self.portfolio_values)

        if len(portfolio_df) == 0:
            return {'error': 'No data to calculate metrics'}

        final_value = portfolio_df['value'].iloc[-1]
        total_return = final_value - self.initial_capital
        total_return_pct = (total_return / self.initial_capital) * 100

        # Buy & Hold comparison
        buy_hold_return_pct = ((data['close'].iloc[-1] - data['close'].iloc[0]) / data['close'].iloc[0]) * 100

        # Win rate - count trades with closing (LONG_CLOSE or SHORT_CLOSE)
        closing_trades = [t for t in self.trades if t['type'] in ['LONG_CLOSE', 'SHORT_CLOSE']]
        winning_trades = [t for t in closing_trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in closing_trades if t.get('pnl', 0) <= 0]
        total_closed = len(closing_trades)
        win_rate = (len(winning_trades) / total_closed * 100) if total_closed > 0 else 0

        # Separate long vs short stats
        long_trades = [t for t in closing_trades if t['type'] == 'LONG_CLOSE']
        short_trades = [t for t in closing_trades if t['type'] == 'SHORT_CLOSE']

        long_wins = len([t for t in long_trades if t.get('pnl', 0) > 0])
        short_wins = len([t for t in short_trades if t.get('pnl', 0) > 0])

        # Max drawdown
        portfolio_df['peak'] = portfolio_df['value'].cummax()
        portfolio_df['drawdown'] = (portfolio_df['value'] - portfolio_df['peak']) / portfolio_df['peak'] * 100
        max_drawdown = portfolio_df['drawdown'].min()

        # Average win/loss
        avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t['pnl'] for t in losing_trades]) if losing_trades else 0

        if not silent:
            print(f"\n{'='*60}")
            print(f"BACKTEST RESULTS")
            print(f"{'='*60}")
            print(f"Initial Capital:     ${self.initial_capital:,.2f}")
            print(f"Final Value:         ${final_value:,.2f}")
            print(f"Total Return:        ${total_return:,.2f} ({total_return_pct:+.2f}%)")
            print(f"Buy & Hold Return:   {buy_hold_return_pct:+.2f}%")
            print(f"")
            print(f"Total Trades:        {total_closed}")
            print(f"  Long Trades:       {len(long_trades)} ({long_wins} wins)")
            print(f"  Short Trades:      {len(short_trades)} ({short_wins} wins)")
            print(f"Win Rate:            {win_rate:.1f}%")
            print(f"Avg Win:             ${avg_win:,.2f}")
            print(f"Avg Loss:            ${avg_loss:,.2f}")
            print(f"Max Drawdown:        {max_drawdown:.2f}%")
            print(f"{'='*60}\n")

        return {
            'initial_capital': self.initial_capital,
            'final_value': final_value,
            'total_return': total_return,
            'total_return_pct': total_return_pct,
            'buy_hold_return_pct': buy_hold_return_pct,
            'total_trades': total_closed,
            'long_trades': len(long_trades),
            'short_trades': len(short_trades),
            'long_wins': long_wins,
            'short_wins': short_wins,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'max_drawdown': max_drawdown,
            'trades': self.trades,
            'portfolio_history': portfolio_df
        }

"""
Backtesting Engine - Simulates trading strategies on historical data

The core logic: walk through historical price data, let your strategy decide
when to buy/sell, track those trades, and calculate how much you would have made.
"""

import pandas as pd
import numpy as np
from datetime import datetime


class Backtester:
    """
    Simulates trading a strategy on historical data

    How it works:
    1. Takes price data (OHLCV candles)
    2. Steps through time, candle by candle
    3. At each candle, asks your strategy: "buy, sell, or hold?"
    4. Executes trades and tracks portfolio value
    5. Calculates performance metrics
    """

    def __init__(self, initial_capital=10000, fee_percent=0.1, display_timezone='UTC'):
        """
        Args:
            initial_capital: Starting money (e.g., $10,000)
            fee_percent: Trading fee per trade (0.1% = Binance standard)
            display_timezone: Timezone for displaying trade times (e.g., 'America/New_York')
        """
        self.initial_capital = initial_capital
        self.fee_percent = fee_percent / 100  # Convert to decimal
        self.display_timezone = display_timezone

        # Portfolio state
        self.cash = initial_capital
        self.position = 0  # How many coins we own
        self.position_entry_price = 0  # Price we bought at

        # Trade history
        self.trades = []
        self.portfolio_values = []

    def run(self, data, strategy):
        """
        Run backtest on historical data using provided strategy

        Args:
            data: DataFrame with OHLCV data (from DataFetcher)
            strategy: Strategy object with a generate_signals() method

        Returns:
            Dictionary with results and metrics
        """
        print(f"\n{'='*60}")
        print(f"🚀 Starting Backtest")
        print(f"{'='*60}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"Trading Fee: {self.fee_percent*100}%")
        print(f"Data Period: {data.index[0]} to {data.index[-1]}")
        print(f"Total Candles: {len(data)}")
        print(f"{'='*60}\n")

        # Let strategy analyze data and generate buy/sell signals
        signals = strategy.generate_signals(data)

        # Walk through each candle
        for i in range(len(data)):
            timestamp = data.index[i]
            candle = data.iloc[i]
            signal = signals.iloc[i]

            # Calculate current portfolio value
            portfolio_value = self.cash + (self.position * candle['close'])
            self.portfolio_values.append({
                'timestamp': timestamp,
                'value': portfolio_value,
                'cash': self.cash,
                'position': self.position,
                'price': candle['close']
            })

            # Execute trade based on signal
            if signal['signal'] == 'BUY' and self.position == 0:
                self._execute_buy(timestamp, candle['close'])

            elif signal['signal'] == 'SELL' and self.position > 0:
                self._execute_sell(timestamp, candle['close'])

        # Calculate final metrics
        results = self._calculate_metrics(data)

        return results

    def _format_timestamp(self, timestamp):
        """Convert timestamp to display timezone for readability"""
        if hasattr(timestamp, 'tz_localize'):
            # Timezone-naive timestamp - assume UTC
            if timestamp.tz is None:
                timestamp = timestamp.tz_localize('UTC')
            # Convert to display timezone
            if self.display_timezone != 'UTC':
                timestamp = timestamp.tz_convert(self.display_timezone)
        return timestamp

    def _execute_buy(self, timestamp, price):
        """Buy coins with all available cash"""
        # Calculate how many coins we can buy (accounting for fees)
        cost_with_fee = price * (1 + self.fee_percent)
        coins_to_buy = self.cash / cost_with_fee

        if coins_to_buy > 0:
            self.position = coins_to_buy
            self.position_entry_price = price
            self.cash = 0  # Spent all cash

            self.trades.append({
                'timestamp': timestamp,
                'type': 'BUY',
                'price': price,
                'amount': coins_to_buy,
                'fee': coins_to_buy * price * self.fee_percent,
                'portfolio_value': self.position * price
            })

            display_time = self._format_timestamp(timestamp)
            print(f"🟢 BUY  | {display_time} | Price: ${price:,.2f} | Amount: {coins_to_buy:.6f}")

    def _execute_sell(self, timestamp, price):
        """Sell all coins back to cash"""
        # Calculate proceeds (accounting for fees)
        proceeds = self.position * price
        fee = proceeds * self.fee_percent
        self.cash = proceeds - fee

        # Calculate profit/loss from this trade
        cost_basis = self.position * self.position_entry_price
        pnl = self.cash - cost_basis
        pnl_percent = (pnl / cost_basis) * 100

        self.trades.append({
            'timestamp': timestamp,
            'type': 'SELL',
            'price': price,
            'amount': self.position,
            'fee': fee,
            'pnl': pnl,
            'pnl_percent': pnl_percent,
            'portfolio_value': self.cash
        })

        display_time = self._format_timestamp(timestamp)
        print(f"🔴 SELL | {display_time} | Price: ${price:,.2f} | P&L: ${pnl:,.2f} ({pnl_percent:+.2f}%)")

        # Reset position
        self.position = 0
        self.position_entry_price = 0

    def _calculate_metrics(self, data):
        """Calculate performance metrics"""
        portfolio_df = pd.DataFrame(self.portfolio_values)

        # Final portfolio value
        final_value = portfolio_df['value'].iloc[-1]
        total_return = final_value - self.initial_capital
        total_return_pct = (total_return / self.initial_capital) * 100

        # Buy & Hold comparison (what if we just bought and held?)
        buy_hold_return_pct = ((data['close'].iloc[-1] - data['close'].iloc[0]) / data['close'].iloc[0]) * 100

        # Win rate
        winning_trades = [t for t in self.trades if t['type'] == 'SELL' and t.get('pnl', 0) > 0]
        losing_trades = [t for t in self.trades if t['type'] == 'SELL' and t.get('pnl', 0) <= 0]
        total_trades = len(winning_trades) + len(losing_trades)
        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0

        # Max drawdown (largest peak-to-trough decline)
        portfolio_df['peak'] = portfolio_df['value'].cummax()
        portfolio_df['drawdown'] = (portfolio_df['value'] - portfolio_df['peak']) / portfolio_df['peak'] * 100
        max_drawdown = portfolio_df['drawdown'].min()

        # Print summary
        print(f"\n{'='*60}")
        print(f"📊 BACKTEST RESULTS")
        print(f"{'='*60}")
        print(f"Initial Capital:     ${self.initial_capital:,.2f}")
        print(f"Final Value:         ${final_value:,.2f}")
        print(f"Total Return:        ${total_return:,.2f} ({total_return_pct:+.2f}%)")
        print(f"Buy & Hold Return:   {buy_hold_return_pct:+.2f}%")
        print(f"Total Trades:        {total_trades}")
        print(f"Winning Trades:      {len(winning_trades)}")
        print(f"Losing Trades:       {len(losing_trades)}")
        print(f"Win Rate:            {win_rate:.1f}%")
        print(f"Max Drawdown:        {max_drawdown:.2f}%")
        print(f"{'='*60}\n")

        return {
            'initial_capital': self.initial_capital,
            'final_value': final_value,
            'total_return': total_return,
            'total_return_pct': total_return_pct,
            'buy_hold_return_pct': buy_hold_return_pct,
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'max_drawdown': max_drawdown,
            'trades': self.trades,
            'portfolio_history': portfolio_df
        }

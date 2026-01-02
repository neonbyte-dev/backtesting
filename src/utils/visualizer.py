"""
Performance Visualizer - Creates charts to see how strategies performed

Visualization helps you understand:
- Is your strategy actually making money over time?
- When did it make/lose the most?
- How does it compare to just buying and holding?
"""

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from datetime import datetime


class PerformanceVisualizer:
    """Creates charts and plots for backtest results"""

    def __init__(self):
        # Set style for prettier charts
        sns.set_style("darkgrid")
        plt.rcParams['figure.figsize'] = (14, 10)

    def plot_results(self, results, data, save_path=None):
        """
        Create comprehensive performance visualization

        Args:
            results: Results dictionary from Backtester
            data: Original OHLCV data
            save_path: Optional path to save chart (e.g., 'results/my_strategy.png')
        """
        fig, axes = plt.subplots(3, 1, figsize=(14, 10))

        portfolio_df = results['portfolio_history']

        # ----------------
        # Chart 1: Portfolio Value Over Time
        # ----------------
        ax1 = axes[0]
        ax1.plot(portfolio_df['timestamp'], portfolio_df['value'],
                 label='Strategy Portfolio', color='#2E86AB', linewidth=2)
        ax1.axhline(y=results['initial_capital'], color='gray',
                    linestyle='--', label='Initial Capital', alpha=0.5)

        # Calculate buy & hold for comparison
        buy_hold_value = results['initial_capital'] * (data['close'] / data['close'].iloc[0])
        ax1.plot(data.index, buy_hold_value,
                 label='Buy & Hold', color='orange', linewidth=1.5, alpha=0.7)

        ax1.set_title('Portfolio Value Over Time', fontsize=14, fontweight='bold')
        ax1.set_ylabel('Portfolio Value ($)', fontsize=11)
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # ----------------
        # Chart 2: Price with Buy/Sell Signals
        # ----------------
        ax2 = axes[1]
        ax2.plot(data.index, data['close'], label='Price', color='black', linewidth=1.5)

        # Mark buy and sell points
        buys = [t for t in results['trades'] if t['type'] == 'BUY']
        sells = [t for t in results['trades'] if t['type'] == 'SELL']

        if buys:
            buy_times = [t['timestamp'] for t in buys]
            buy_prices = [t['price'] for t in buys]
            ax2.scatter(buy_times, buy_prices, color='green',
                       marker='^', s=100, label='BUY', zorder=5)

        if sells:
            sell_times = [t['timestamp'] for t in sells]
            sell_prices = [t['price'] for t in sells]
            ax2.scatter(sell_times, sell_prices, color='red',
                       marker='v', s=100, label='SELL', zorder=5)

        ax2.set_title('Price Chart with Trade Signals', fontsize=14, fontweight='bold')
        ax2.set_ylabel('Price ($)', fontsize=11)
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        # ----------------
        # Chart 3: Drawdown (How much did we lose from peak?)
        # ----------------
        ax3 = axes[2]
        ax3.fill_between(portfolio_df['timestamp'], portfolio_df['drawdown'], 0,
                         color='red', alpha=0.3)
        ax3.plot(portfolio_df['timestamp'], portfolio_df['drawdown'],
                 color='darkred', linewidth=1)

        ax3.set_title('Drawdown (Loss from Peak)', fontsize=14, fontweight='bold')
        ax3.set_ylabel('Drawdown (%)', fontsize=11)
        ax3.set_xlabel('Date', fontsize=11)
        ax3.grid(True, alpha=0.3)

        # Add summary stats as text box
        stats_text = (
            f"Total Return: {results['total_return_pct']:+.2f}%\n"
            f"Buy & Hold: {results['buy_hold_return_pct']:+.2f}%\n"
            f"Win Rate: {results['win_rate']:.1f}%\n"
            f"Max Drawdown: {results['max_drawdown']:.2f}%\n"
            f"Total Trades: {results['total_trades']}"
        )

        fig.text(0.02, 0.98, stats_text,
                transform=fig.transFigure,
                fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        plt.tight_layout()

        # Save or show
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"📊 Chart saved to {save_path}")
        else:
            plt.show()

    def print_trade_log(self, results):
        """Print detailed trade-by-trade log"""
        print(f"\n{'='*80}")
        print(f"DETAILED TRADE LOG")
        print(f"{'='*80}")

        for i, trade in enumerate(results['trades'], 1):
            if trade['type'] == 'BUY':
                print(f"{i}. BUY  @ ${trade['price']:,.2f} | {trade['timestamp']} | Amount: {trade['amount']:.6f}")
            else:
                pnl_sign = '+' if trade['pnl'] > 0 else ''
                print(f"{i}. SELL @ ${trade['price']:,.2f} | {trade['timestamp']} | "
                      f"P&L: {pnl_sign}${trade['pnl']:,.2f} ({trade['pnl_percent']:+.2f}%)")

        print(f"{'='*80}\n")

    def plot_intraday_analysis(self, results, data, save_path=None):
        """
        Visualize intraday trading patterns - perfect for time-based strategies

        Shows:
        1. When during the day trades happen (scatter plot)
        2. Profitability by entry hour (heatmap)
        3. Hold duration distribution

        This helps answer:
        - Are my entries/exits happening at the right times?
        - Which entry hours are most profitable?
        - How long am I typically holding positions?

        Args:
            results: Results dictionary from Backtester
            data: Original OHLCV data
            save_path: Optional path to save chart
        """
        fig = plt.figure(figsize=(16, 10))
        gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3)

        trades_df = pd.DataFrame(results['trades'])

        if len(trades_df) == 0:
            print("⚠️  No trades to visualize")
            return

        # Extract hour and minute from timestamps
        trades_df['hour'] = pd.to_datetime(trades_df['timestamp']).dt.hour
        trades_df['minute'] = pd.to_datetime(trades_df['timestamp']).dt.minute
        trades_df['time_decimal'] = trades_df['hour'] + trades_df['minute'] / 60

        # ----------------
        # Chart 1: Trade Timing Throughout Day (Top Left)
        # ----------------
        ax1 = fig.add_subplot(gs[0, 0])

        buys = trades_df[trades_df['type'] == 'BUY']
        sells = trades_df[trades_df['type'] == 'SELL']

        if len(buys) > 0:
            ax1.scatter(buys['time_decimal'], buys['price'],
                       color='green', marker='^', s=100, alpha=0.6, label='BUY')
        if len(sells) > 0:
            ax1.scatter(sells['time_decimal'], sells['price'],
                       color='red', marker='v', s=100, alpha=0.6, label='SELL')

        ax1.set_xlabel('Time of Day (Hour)', fontsize=11)
        ax1.set_ylabel('Price ($)', fontsize=11)
        ax1.set_title('Trade Timing During the Day', fontsize=12, fontweight='bold')
        ax1.set_xlim(0, 24)
        ax1.set_xticks(range(0, 25, 3))
        ax1.grid(True, alpha=0.3)
        ax1.legend()

        # ----------------
        # Chart 2: Entry Hour Distribution (Top Right)
        # ----------------
        ax2 = fig.add_subplot(gs[0, 1])

        if len(buys) > 0:
            buy_hours = buys['hour'].value_counts().sort_index()
            ax2.bar(buy_hours.index, buy_hours.values, color='green', alpha=0.6)
            ax2.set_xlabel('Hour of Day', fontsize=11)
            ax2.set_ylabel('Number of Entries', fontsize=11)
            ax2.set_title('Entry Distribution by Hour', fontsize=12, fontweight='bold')
            ax2.set_xlim(-0.5, 23.5)
            ax2.grid(True, alpha=0.3, axis='y')

        # ----------------
        # Chart 3: Profitability by Entry Hour (Middle Left)
        # ----------------
        ax3 = fig.add_subplot(gs[1, 0])

        # Match each sell with its corresponding buy
        paired_trades = []
        for i in range(0, len(trades_df) - 1, 2):
            if trades_df.iloc[i]['type'] == 'BUY' and i+1 < len(trades_df) and trades_df.iloc[i+1]['type'] == 'SELL':
                paired_trades.append({
                    'entry_hour': trades_df.iloc[i]['hour'],
                    'exit_hour': trades_df.iloc[i+1]['hour'],
                    'pnl_percent': trades_df.iloc[i+1].get('pnl_percent', 0)
                })

        if paired_trades:
            paired_df = pd.DataFrame(paired_trades)
            hourly_pnl = paired_df.groupby('entry_hour')['pnl_percent'].agg(['mean', 'count'])

            colors = ['green' if x > 0 else 'red' for x in hourly_pnl['mean']]
            bars = ax3.bar(hourly_pnl.index, hourly_pnl['mean'], color=colors, alpha=0.6)

            # Add count labels on bars
            for i, (idx, row) in enumerate(hourly_pnl.iterrows()):
                ax3.text(idx, row['mean'], f"n={int(row['count'])}",
                        ha='center', va='bottom' if row['mean'] > 0 else 'top', fontsize=8)

            ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            ax3.set_xlabel('Entry Hour', fontsize=11)
            ax3.set_ylabel('Avg Return (%)', fontsize=11)
            ax3.set_title('Average Return by Entry Hour', fontsize=12, fontweight='bold')
            ax3.grid(True, alpha=0.3, axis='y')

        # ----------------
        # Chart 4: Exit Hour Distribution (Middle Right)
        # ----------------
        ax4 = fig.add_subplot(gs[1, 1])

        if len(sells) > 0:
            sell_hours = sells['hour'].value_counts().sort_index()
            ax4.bar(sell_hours.index, sell_hours.values, color='red', alpha=0.6)
            ax4.set_xlabel('Hour of Day', fontsize=11)
            ax4.set_ylabel('Number of Exits', fontsize=11)
            ax4.set_title('Exit Distribution by Hour', fontsize=12, fontweight='bold')
            ax4.set_xlim(-0.5, 23.5)
            ax4.grid(True, alpha=0.3, axis='y')

        # ----------------
        # Chart 5: Hold Duration Distribution (Bottom Left)
        # ----------------
        ax5 = fig.add_subplot(gs[2, 0])

        if paired_trades:
            # Calculate hold duration in hours
            hold_durations = []
            for i in range(0, len(trades_df) - 1, 2):
                if trades_df.iloc[i]['type'] == 'BUY' and i+1 < len(trades_df):
                    entry_time = pd.to_datetime(trades_df.iloc[i]['timestamp'])
                    exit_time = pd.to_datetime(trades_df.iloc[i+1]['timestamp'])
                    duration_hours = (exit_time - entry_time).total_seconds() / 3600
                    hold_durations.append(duration_hours)

            if hold_durations:
                ax5.hist(hold_durations, bins=20, color='blue', alpha=0.6, edgecolor='black')
                ax5.axvline(x=np.mean(hold_durations), color='red', linestyle='--',
                           linewidth=2, label=f'Mean: {np.mean(hold_durations):.1f}h')
                ax5.set_xlabel('Hold Duration (hours)', fontsize=11)
                ax5.set_ylabel('Frequency', fontsize=11)
                ax5.set_title('Position Hold Duration', fontsize=12, fontweight='bold')
                ax5.legend()
                ax5.grid(True, alpha=0.3, axis='y')

        # ----------------
        # Chart 6: Entry vs Exit Time Scatter (Bottom Right)
        # ----------------
        ax6 = fig.add_subplot(gs[2, 1])

        if paired_trades:
            entry_hours = [t['entry_hour'] for t in paired_trades]
            exit_hours = [t['exit_hour'] for t in paired_trades]
            pnl_percents = [t['pnl_percent'] for t in paired_trades]

            scatter = ax6.scatter(entry_hours, exit_hours, c=pnl_percents,
                                 cmap='RdYlGn', s=100, alpha=0.6, edgecolors='black')

            # Add diagonal line (same hour entry/exit)
            ax6.plot([0, 24], [0, 24], 'k--', alpha=0.3, linewidth=1)

            ax6.set_xlabel('Entry Hour', fontsize=11)
            ax6.set_ylabel('Exit Hour', fontsize=11)
            ax6.set_title('Entry vs Exit Hour (colored by P&L %)', fontsize=12, fontweight='bold')
            ax6.set_xlim(-0.5, 23.5)
            ax6.set_ylim(-0.5, 23.5)
            ax6.grid(True, alpha=0.3)

            # Add colorbar
            cbar = plt.colorbar(scatter, ax=ax6)
            cbar.set_label('P&L %', fontsize=10)

        # Add summary stats
        if paired_trades:
            paired_df = pd.DataFrame(paired_trades)
            winning_pct = (paired_df['pnl_percent'] > 0).sum() / len(paired_df) * 100
            avg_pnl = paired_df['pnl_percent'].mean()

            stats_text = (
                f"Total Trades: {len(paired_df)}\n"
                f"Win Rate: {winning_pct:.1f}%\n"
                f"Avg Return: {avg_pnl:+.2f}%\n"
                f"Avg Hold: {np.mean(hold_durations):.1f}h"
            )

            fig.text(0.02, 0.98, stats_text,
                    transform=fig.transFigure,
                    fontsize=10, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))

        plt.suptitle('Intraday Trading Pattern Analysis', fontsize=14, fontweight='bold', y=0.995)

        # Save or show
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"📊 Intraday analysis saved to {save_path}")
        else:
            plt.show()

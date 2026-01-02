"""
December-only visualization: BTC price with buy/sell markers
"""

import sys
sys.path.append('src')

import pandas as pd
import matplotlib.pyplot as plt
from utils.data_fetcher import DataFetcher
from backtester import Backtester
from strategies.market_open_dump import MarketOpenDumpStrategy

# Fetch data
print("Fetching data...")
fetcher = DataFetcher()
data = fetcher.fetch_ohlcv('BTC/USDT', '5m', days_back=90)

# Filter to December 2025 only
print("Filtering to December 2025...")
data = data.loc['2025-12-01':'2025-12-31']
print(f"December data: {len(data)} candles from {data.index[0]} to {data.index[-1]}")

# Run strategy
print("Running strategy...")
strategy = MarketOpenDumpStrategy(
    entry_mode='end_of_dump',
    exit_mode='next_day_premarket',
    dump_end_hour=15,
    timezone='America/New_York'
)

backtester = Backtester(
    initial_capital=10000,
    fee_percent=0.1,
    display_timezone='America/New_York'
)

results = backtester.run(data, strategy)

# Create focused price chart with trades
print("\nCreating December visualization...")
fig, ax = plt.subplots(figsize=(20, 10))

# Plot price
ax.plot(data.index, data['close'], color='black', linewidth=2, label='BTC Price', alpha=0.8)

# Extract buy and sell trades
buys = [t for t in results['trades'] if t['type'] == 'BUY']
sells = [t for t in results['trades'] if t['type'] == 'SELL']

# Plot buy signals
if buys:
    buy_times = [t['timestamp'] for t in buys]
    buy_prices = [t['price'] for t in buys]
    ax.scatter(buy_times, buy_prices, color='green', marker='^',
              s=250, label='BUY (3 PM EST)', zorder=5, edgecolors='darkgreen', linewidth=2)

# Plot sell signals
if sells:
    sell_times = [t['timestamp'] for t in sells]
    sell_prices = [t['price'] for t in sells]
    ax.scatter(sell_times, sell_prices, color='red', marker='v',
              s=250, label='SELL (9:30 AM EST)', zorder=5, edgecolors='darkred', linewidth=2)

# Formatting
ax.set_xlabel('Date (December 2025)', fontsize=14, fontweight='bold')
ax.set_ylabel('Bitcoin Price (USD)', fontsize=14, fontweight='bold')
ax.set_title('Bitcoin Price in DECEMBER 2025 - Overnight Strategy Trades\n(Buy 3PM EST → Sell 9:30AM EST Next Day)',
            fontsize=18, fontweight='bold', pad=20)
ax.legend(fontsize=13, loc='best')
ax.grid(True, alpha=0.3)

# Format y-axis as currency
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

# Add summary stats box
stats_text = (
    f"DECEMBER 2025 ONLY\n"
    f"Period: {data.index[0].strftime('%b %d')} to {data.index[-1].strftime('%b %d, %Y')}\n"
    f"Total Trades: {len(buys)} round trips\n"
    f"Win Rate: {results['win_rate']:.1f}%\n"
    f"Total Return: {results['total_return_pct']:+.2f}%\n"
    f"Buy & Hold: {results['buy_hold_return_pct']:+.2f}%"
)

ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
       fontsize=12, verticalalignment='top',
       bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.9))

plt.tight_layout()

# Save
save_path = 'results/price_with_trades_DECEMBER.png'
plt.savefig(save_path, dpi=150, bbox_inches='tight')
print(f"\n✅ Chart saved to {save_path}")
print("Opening chart...")

plt.close()

# Open the image
import subprocess
subprocess.run(['open', save_path])

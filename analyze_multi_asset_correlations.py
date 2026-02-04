"""
Multi-Asset Correlation Analysis

Compares correlations across different asset classes:
- Crypto (BTC, ETH, SOL, BNB)
- Defense/Drones (ONDS, PLTR)
- AI/Tech (NVDA, INTC, META, GLXY)
- Robotics (FANUC)
- Commodities (Gold, Silver, Uranium, Oil)
- Energy (AES)
- Market Index (S&P 500)

WHY COMPARE ACROSS ASSET CLASSES?
- Diversification: Find assets that DON'T move together
- Risk management: Understand what hedges what
- Macro insight: See how different sectors respond to market conditions
"""

import pandas as pd
import numpy as np
import requests
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import seaborn as sns
from datetime import datetime, timedelta
import sys
import os
import time

# Add src to path for ccxt data fetcher
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from utils.data_fetcher import DataFetcher

DAYS_BACK = 90

# Define assets by category - ORDER MATTERS for grouping on heatmap
# Format: (display_name, ticker, source)
# source: 'crypto' uses ccxt/Binance, 'stock' uses yfinance

ASSET_CATEGORIES = {
    'Crypto': [
        ('BTC', 'BTC/USDT', 'crypto'),
        ('ETH', 'ETH/USDT', 'crypto'),
        ('SOL', 'SOL/USDT', 'crypto'),
        ('BNB', 'BNB/USDT', 'crypto'),
        ('HYPE', 'HYPER/USDT', 'crypto'),  # Hyperliquid token (listed as HYPER on Binance)
    ],
    'Defense': [
        ('ONDS', 'ONDS', 'stock'),      # Ondas Holdings - counter-drone
        ('PLTR', 'PLTR', 'stock'),      # Palantir - military AI/software
        ('LMT', 'LMT', 'stock'),        # Lockheed Martin - defense
    ],
    'AI/Tech': [
        ('NVDA', 'NVDA', 'stock'),      # Nvidia
        ('INTC', 'INTC', 'stock'),      # Intel
        ('META', 'META', 'stock'),      # Meta/Facebook
        ('GLXY', 'GLXY.TO', 'stock'),   # Galaxy Digital (Toronto)
        ('MSFT', 'MSFT', 'stock'),      # Microsoft
        ('GOOGL', 'GOOGL', 'stock'),    # Google
    ],
    'Robotics': [
        ('FANUC', 'FANUY', 'stock'),    # FANUC (ADR)
    ],
    'Commodities': [
        ('Gold', 'GLD', 'stock'),       # Gold ETF
        ('Silver', 'SLV', 'stock'),     # Silver ETF
        ('URA', 'URA', 'stock'),        # Uranium ETF
        ('Oil', 'USO', 'stock'),        # Oil ETF
    ],
    'Energy': [
        ('AES', 'AES', 'stock'),        # AES Corporation
    ],
    'Index': [
        ('S&P500', 'SPY', 'stock'),     # S&P 500 ETF
    ],
}

# Colors for each category
CATEGORY_COLORS = {
    'Crypto': '#F7931A',      # Bitcoin orange
    'Defense': '#4A5568',     # Military gray
    'AI/Tech': '#00D4AA',     # Tech teal
    'Robotics': '#8B5CF6',    # Purple
    'Commodities': '#FFD700', # Gold
    'Energy': '#22C55E',      # Green
    'Index': '#3B82F6',       # Blue
}


def fetch_crypto_data(symbol, days_back):
    """Fetch crypto data using ccxt/Binance"""
    fetcher = DataFetcher()
    try:
        df = fetcher.fetch_ohlcv(symbol=symbol, timeframe='1d', days_back=days_back)
        close = df['close']
        # Normalize to date-only index for alignment with stocks
        close.index = close.index.normalize()
        return close
    except Exception as e:
        print(f"   Failed: {e}")
        return None


def fetch_stock_data(ticker, days_back):
    """Fetch stock/ETF data using Yahoo Finance chart API directly"""
    try:
        # Calculate timestamps
        end_ts = int(datetime.now().timestamp())
        start_ts = int((datetime.now() - timedelta(days=days_back + 10)).timestamp())

        # Yahoo Finance chart API
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        params = {
            'period1': start_ts,
            'period2': end_ts,
            'interval': '1d',
            'events': 'history'
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }

        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()

        if 'chart' not in data or 'result' not in data['chart'] or not data['chart']['result']:
            print(f"   No data returned")
            return None

        result = data['chart']['result'][0]
        timestamps = result['timestamp']
        closes = result['indicators']['quote'][0]['close']

        # Create series
        dates = pd.to_datetime(timestamps, unit='s')
        close_series = pd.Series(closes, index=dates, name=ticker)
        close_series = close_series.dropna()
        # Normalize to date-only index for alignment with crypto
        close_series.index = close_series.index.normalize()

        print(f"   Fetched {len(close_series)} days")
        time.sleep(0.3)  # Rate limiting
        return close_series

    except Exception as e:
        print(f"   Failed: {e}")
        return None


def fetch_all_assets():
    """Fetch data for all assets across categories"""
    all_prices = {}
    asset_order = []  # Track order for plotting
    asset_categories_map = {}  # Map asset name to category

    print(f"\n{'='*60}")
    print(f"Fetching {DAYS_BACK} days of daily data")
    print(f"{'='*60}\n")

    for category, assets in ASSET_CATEGORIES.items():
        print(f"\n--- {category} ---")

        for display_name, ticker, source in assets:
            print(f"  {display_name} ({ticker}): ", end="")

            if source == 'crypto':
                prices = fetch_crypto_data(ticker, DAYS_BACK)
            else:
                prices = fetch_stock_data(ticker, DAYS_BACK)

            if prices is not None and len(prices) > 0:
                all_prices[display_name] = prices
                asset_order.append(display_name)
                asset_categories_map[display_name] = category

    # Combine into DataFrame, aligning by date
    prices_df = pd.DataFrame(all_prices)

    # Keep only dates where we have data for most assets (allow some missing)
    min_assets = len(asset_order) * 0.7  # At least 70% of assets
    prices_df = prices_df.dropna(thresh=int(min_assets))

    # Forward fill any remaining gaps (weekends, holidays)
    prices_df = prices_df.ffill().bfill()

    print(f"\n{'='*60}")
    print(f"Successfully loaded {len(prices_df.columns)} assets")
    print(f"Date range: {prices_df.index[0]} to {prices_df.index[-1]}")
    print(f"Total data points: {len(prices_df)} days")
    print(f"{'='*60}")

    return prices_df, asset_order, asset_categories_map


def calculate_returns(prices_df):
    """Convert prices to daily percentage returns"""
    returns_df = prices_df.pct_change(fill_method=None).dropna()

    print(f"\nDaily Return Stats:")
    avg_returns = returns_df.mean() * 100
    valid_returns = avg_returns.dropna()
    if len(valid_returns) > 0:
        print(f"  Best performer:  {valid_returns.idxmax()} ({valid_returns.max():.3f}%/day)")
        print(f"  Worst performer: {valid_returns.idxmin()} ({valid_returns.min():.3f}%/day)")
    else:
        print(f"  No valid return data")

    return returns_df


def calculate_correlation(returns_df):
    """Calculate correlation matrix"""
    corr_matrix = returns_df.corr()

    # Stats on correlations (excluding diagonal)
    mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
    flat_corr = corr_matrix.where(mask).values.flatten()
    flat_corr = flat_corr[~np.isnan(flat_corr)]

    print(f"\nCorrelation Stats:")
    if len(flat_corr) > 0:
        print(f"  Mean: {flat_corr.mean():.3f}")
        print(f"  Min:  {flat_corr.min():.3f}")
        print(f"  Max:  {flat_corr.max():.3f}")

        # Find extreme pairs
        corr_values = corr_matrix.where(mask)
        stacked = corr_values.stack()
        if len(stacked) > 0:
            max_idx = stacked.idxmax()
            min_idx = stacked.idxmin()
            print(f"\n  Most correlated:  {max_idx[0]} & {max_idx[1]} ({corr_matrix.loc[max_idx]:.3f})")
            print(f"  Least correlated: {min_idx[0]} & {min_idx[1]} ({corr_matrix.loc[min_idx]:.3f})")
    else:
        print(f"  No valid correlations computed")

    return corr_matrix


def plot_grouped_heatmap(corr_matrix, asset_order, asset_categories_map, output_path):
    """
    Create heatmap with color-coded category labels and group separators
    """
    # Reorder correlation matrix by our asset order (grouped by category)
    corr_ordered = corr_matrix.loc[asset_order, asset_order]

    fig, ax = plt.subplots(figsize=(16, 14))

    # Create custom colormap: red -> white -> green
    colors = ['#d73027', '#f7f7f7', '#1a9850']
    cmap = LinearSegmentedColormap.from_list('correlation', colors, N=256)

    # Draw heatmap
    sns.heatmap(
        corr_ordered,
        annot=True,
        fmt='.2f',
        cmap=cmap,
        center=0,
        vmin=-1,
        vmax=1,
        square=True,
        linewidths=0.5,
        linecolor='white',
        cbar_kws={'label': 'Correlation', 'shrink': 0.8},
        annot_kws={'size': 8},
        ax=ax
    )

    # Color-code the axis labels by category
    x_labels = ax.get_xticklabels()
    y_labels = ax.get_yticklabels()

    for label in x_labels:
        asset = label.get_text()
        if asset in asset_categories_map:
            category = asset_categories_map[asset]
            label.set_color(CATEGORY_COLORS[category])
            label.set_fontweight('bold')

    for label in y_labels:
        asset = label.get_text()
        if asset in asset_categories_map:
            category = asset_categories_map[asset]
            label.set_color(CATEGORY_COLORS[category])
            label.set_fontweight('bold')

    ax.set_xticklabels(x_labels, rotation=45, ha='right')
    ax.set_yticklabels(y_labels, rotation=0)

    # Draw category group separators
    current_category = None
    category_starts = {}
    category_ends = {}

    for i, asset in enumerate(asset_order):
        cat = asset_categories_map[asset]
        if cat != current_category:
            if current_category is not None:
                category_ends[current_category] = i
            category_starts[cat] = i
            current_category = cat
    category_ends[current_category] = len(asset_order)

    # Draw separator lines between categories
    for cat, start in category_starts.items():
        if start > 0:
            ax.axhline(y=start, color='black', linewidth=2)
            ax.axvline(x=start, color='black', linewidth=2)

    # Create legend for categories
    legend_patches = [
        mpatches.Patch(color=color, label=cat)
        for cat, color in CATEGORY_COLORS.items()
        if cat in asset_categories_map.values()
    ]
    ax.legend(
        handles=legend_patches,
        loc='upper left',
        bbox_to_anchor=(1.15, 1),
        title='Asset Class',
        frameon=True
    )

    # Title
    ax.set_title(
        f'Multi-Asset Correlation Matrix\n{DAYS_BACK} Days of Daily Returns',
        fontsize=16,
        fontweight='bold',
        pad=20
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f"\nSaved heatmap to: {output_path}")


def print_category_insights(corr_matrix, asset_categories_map):
    """Print average correlations between categories"""
    print(f"\n{'='*60}")
    print("CROSS-ASSET CLASS CORRELATIONS")
    print("(Average correlation between assets in each category pair)")
    print(f"{'='*60}\n")

    categories = list(ASSET_CATEGORIES.keys())
    category_corrs = {}

    for i, cat1 in enumerate(categories):
        for cat2 in categories[i:]:
            assets1 = [a for a, c in asset_categories_map.items() if c == cat1]
            assets2 = [a for a, c in asset_categories_map.items() if c == cat2]

            if not assets1 or not assets2:
                continue

            # Get correlations between these asset groups
            corrs = []
            for a1 in assets1:
                for a2 in assets2:
                    if a1 != a2 and a1 in corr_matrix.columns and a2 in corr_matrix.columns:
                        corrs.append(corr_matrix.loc[a1, a2])

            if corrs:
                avg_corr = np.mean(corrs)
                key = f"{cat1} vs {cat2}" if cat1 != cat2 else f"{cat1} (internal)"
                category_corrs[key] = avg_corr

    # Sort by correlation
    sorted_corrs = sorted(category_corrs.items(), key=lambda x: x[1], reverse=True)

    print(f"{'Category Pair':<35} {'Avg Correlation':>15}")
    print("-" * 52)
    for pair, corr in sorted_corrs:
        bar = "+" * int(abs(corr) * 20) if corr > 0 else "-" * int(abs(corr) * 20)
        print(f"{pair:<35} {corr:>+.3f}  {bar}")


def main():
    print("\n" + "="*60)
    print("   MULTI-ASSET CORRELATION ANALYSIS")
    print("   Crypto | Defense | AI/Tech | Robotics | Commodities")
    print("="*60)

    # Fetch data
    prices_df, asset_order, asset_categories_map = fetch_all_assets()

    # Calculate returns
    returns_df = calculate_returns(prices_df)

    # Calculate correlations
    corr_matrix = calculate_correlation(returns_df)

    # Create visualization
    output_path = 'results/multi_asset_correlation_matrix.png'
    os.makedirs('results', exist_ok=True)
    plot_grouped_heatmap(corr_matrix, asset_order, asset_categories_map, output_path)

    # Save raw data
    csv_path = 'results/multi_asset_correlation_matrix.csv'
    corr_matrix.to_csv(csv_path)
    print(f"Saved correlation data to: {csv_path}")

    # Print insights
    print_category_insights(corr_matrix, asset_categories_map)

    print("\n" + "="*60)
    print("   ANALYSIS COMPLETE")
    print("="*60 + "\n")

    return corr_matrix


if __name__ == "__main__":
    corr = main()

"""
Crypto Correlation Analysis - Top 30 Tokens by Market Cap

This script fetches 90 days of daily price data for the top 30 cryptocurrencies,
calculates their correlation matrix based on daily returns, and outputs a
clustered heatmap visualization.

WHY DAILY RETURNS (not prices)?
- Raw prices have different scales ($90K BTC vs $0.00001 SHIB)
- Returns normalize everything to percentage moves
- Correlation of returns answers: "When BTC goes up 2%, does ETH also tend to go up?"

WHY CLUSTERING?
- Groups tokens that behave similarly together on the heatmap
- Visually reveals "families" of correlated assets
- Example: Altcoins might cluster together, stablecoins separately
"""

import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from scipy.cluster.hierarchy import linkage, dendrogram
from scipy.spatial.distance import squareform
import sys
import os

# Add src to path so we can import data_fetcher
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from utils.data_fetcher import DataFetcher


# Top 30 tokens by market cap (as of late 2024)
# Using /USDT pairs since those have the best liquidity on Binance
TOP_30_TOKENS = [
    'BTC', 'ETH', 'BNB', 'XRP', 'SOL',
    'ADA', 'DOGE', 'AVAX', 'DOT', 'LINK',
    'TRX', 'MATIC', 'SHIB', 'LTC', 'BCH',
    'ATOM', 'UNI', 'XLM', 'ETC', 'NEAR',
    'ICP', 'FIL', 'HBAR', 'APT', 'ARB',
    'OP', 'MKR', 'AAVE', 'INJ', 'RNDR'
]

DAYS_BACK = 90  # 3 months of data


def fetch_all_tokens():
    """
    Fetch daily close prices for all tokens.

    Returns a DataFrame where:
    - Each column is a token (BTC, ETH, etc.)
    - Each row is a date
    - Values are closing prices
    """
    fetcher = DataFetcher()
    all_prices = {}
    failed_tokens = []

    print(f"\n{'='*60}")
    print(f"Fetching {DAYS_BACK} days of daily data for {len(TOP_30_TOKENS)} tokens")
    print(f"{'='*60}\n")

    for i, token in enumerate(TOP_30_TOKENS, 1):
        symbol = f"{token}/USDT"
        print(f"[{i}/{len(TOP_30_TOKENS)}] ", end="")

        try:
            df = fetcher.fetch_ohlcv(symbol=symbol, timeframe='1d', days_back=DAYS_BACK)
            all_prices[token] = df['close']
        except Exception as e:
            print(f"⚠️  Failed to fetch {token}: {e}")
            failed_tokens.append(token)

    if failed_tokens:
        print(f"\n⚠️  Could not fetch: {', '.join(failed_tokens)}")

    # Combine into single DataFrame, aligning by date
    prices_df = pd.DataFrame(all_prices)

    # Drop any rows with missing data (ensures all tokens have same dates)
    prices_df = prices_df.dropna()

    print(f"\n✅ Successfully loaded {len(prices_df.columns)} tokens")
    print(f"   Date range: {prices_df.index[0]} to {prices_df.index[-1]}")
    print(f"   Total data points: {len(prices_df)} days")

    return prices_df


def calculate_returns(prices_df):
    """
    Convert prices to daily percentage returns.

    Formula: return = (today's close - yesterday's close) / yesterday's close

    Example: If BTC was $50,000 yesterday and $51,000 today:
             return = (51000 - 50000) / 50000 = 0.02 = 2%
    """
    returns_df = prices_df.pct_change().dropna()

    print(f"\n📊 Calculated daily returns")
    print(f"   Average daily return by token:")
    avg_returns = returns_df.mean() * 100
    print(f"   Best:  {avg_returns.idxmax()} ({avg_returns.max():.2f}%/day)")
    print(f"   Worst: {avg_returns.idxmin()} ({avg_returns.min():.2f}%/day)")

    return returns_df


def calculate_correlation(returns_df):
    """
    Calculate correlation matrix.

    Correlation ranges from -1 to +1:
    - +1.0: Perfect positive correlation (move together exactly)
    - 0.0:  No correlation (independent movements)
    - -1.0: Perfect negative correlation (move opposite)

    In practice for crypto:
    - Most tokens are positively correlated (crypto moves together)
    - Correlations of 0.7-0.9 are common between major alts
    - Truly uncorrelated assets (<0.3) are rare in crypto
    """
    corr_matrix = returns_df.corr()

    print(f"\n🔗 Correlation Matrix Stats:")

    # Find highest and lowest correlations (excluding self-correlation on diagonal)
    mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
    corr_values = corr_matrix.where(mask)

    # Flatten and remove NaN
    flat_corr = corr_values.values.flatten()
    flat_corr = flat_corr[~np.isnan(flat_corr)]

    print(f"   Mean correlation: {flat_corr.mean():.3f}")
    print(f"   Min correlation:  {flat_corr.min():.3f}")
    print(f"   Max correlation:  {flat_corr.max():.3f}")

    # Find the most and least correlated pairs
    max_idx = corr_values.stack().idxmax()
    min_idx = corr_values.stack().idxmin()

    print(f"\n   Most correlated pair:  {max_idx[0]}-{max_idx[1]} ({corr_matrix.loc[max_idx]:.3f})")
    print(f"   Least correlated pair: {min_idx[0]}-{min_idx[1]} ({corr_matrix.loc[min_idx]:.3f})")

    return corr_matrix


def plot_correlation_heatmap(corr_matrix, output_path):
    """
    Create a clustered heatmap visualization.

    Clustering groups similar tokens together by their correlation patterns.
    This uses hierarchical clustering on the distance matrix derived from
    correlations.
    """
    # Set up the figure
    fig, ax = plt.subplots(figsize=(16, 14))

    # Create clustered heatmap
    # clustermap handles both the clustering and the heatmap
    g = sns.clustermap(
        corr_matrix,
        method='average',          # Clustering method
        metric='correlation',       # Distance metric
        cmap='RdYlGn',             # Red (negative) -> Yellow (0) -> Green (positive)
        center=0,                   # Center colormap at 0
        vmin=-1, vmax=1,           # Full correlation range
        annot=True,                # Show values in cells
        fmt='.2f',                 # 2 decimal places
        annot_kws={'size': 6},     # Small font for values
        linewidths=0.5,            # Grid lines between cells
        figsize=(18, 16),
        dendrogram_ratio=(0.15, 0.15),  # Size of dendrograms
        cbar_pos=(0.02, 0.8, 0.03, 0.15),  # Colorbar position
    )

    # Title
    g.fig.suptitle(
        f'Crypto Correlation Matrix - Top 30 Tokens\n(Based on {DAYS_BACK} days of daily returns)',
        fontsize=16,
        fontweight='bold',
        y=1.02
    )

    # Rotate labels for readability
    g.ax_heatmap.set_xticklabels(g.ax_heatmap.get_xticklabels(), rotation=45, ha='right')
    g.ax_heatmap.set_yticklabels(g.ax_heatmap.get_yticklabels(), rotation=0)

    # Save
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f"\n💾 Saved heatmap to: {output_path}")

    return g


def main():
    """Main execution flow"""

    print("\n" + "="*60)
    print("   CRYPTO CORRELATION ANALYSIS")
    print("   Top 30 Tokens by Market Cap")
    print("="*60)

    # Step 1: Fetch price data
    prices_df = fetch_all_tokens()

    # Step 2: Calculate returns
    returns_df = calculate_returns(prices_df)

    # Step 3: Calculate correlations
    corr_matrix = calculate_correlation(returns_df)

    # Step 4: Create visualization
    output_path = 'results/crypto_correlation_matrix.png'
    os.makedirs('results', exist_ok=True)
    plot_correlation_heatmap(corr_matrix, output_path)

    # Save raw correlation data as CSV for reference
    csv_path = 'results/crypto_correlation_matrix.csv'
    corr_matrix.to_csv(csv_path)
    print(f"💾 Saved correlation data to: {csv_path}")

    print("\n" + "="*60)
    print("   ANALYSIS COMPLETE")
    print("="*60 + "\n")

    return corr_matrix


if __name__ == "__main__":
    corr = main()

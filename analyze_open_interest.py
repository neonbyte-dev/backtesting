"""
Open Interest Analysis for BTC

Learning moment: What is Open Interest?
--------------------------------------
Open Interest (OI) = total number of outstanding derivative contracts (futures/options)
that have NOT been settled.

Think of it this way:
- When you BUY a futures contract, someone else SELLS it to you
- This creates 1 new contract → OI increases by 1
- When one party closes their position, OI decreases by 1
- OI ≠ Volume (volume counts each trade, OI counts outstanding positions)

Why might OI predict price?
---------------------------
1. Rising OI + Rising Price = New money entering long (bullish conviction)
2. Rising OI + Falling Price = New shorts opening (bearish conviction)
3. Falling OI + Rising Price = Short squeeze (forced buying)
4. Falling OI + Falling Price = Long liquidations (forced selling)

The hypothesis: Changes in OI might lead price moves because they show
what big traders are positioning for.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
from datetime import datetime, timedelta
import ccxt
import warnings
warnings.filterwarnings('ignore')

# Set style
plt.style.use('seaborn-v0_8-whitegrid')


def load_oi_data():
    """Load the Open Interest data we collected"""
    df = pd.read_csv('data/btc_open_interest_hourly.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp')
    df = df.sort_index()

    # Clean column names
    df = df.rename(columns={
        'sumOpenInterest': 'oi_btc',  # OI in BTC terms
        'sumOpenInterestValue': 'oi_usd'  # OI in USD terms
    })

    print(f"Loaded OI data: {len(df)} records")
    print(f"Date range: {df.index.min()} to {df.index.max()}")

    return df


def fetch_price_data(start_date, end_date):
    """Fetch BTC price data to match our OI data period"""
    exchange = ccxt.binance({'enableRateLimit': True})

    # Calculate days back from end_date
    days_back = (end_date - start_date).days + 1

    since = exchange.parse8601(start_date.isoformat())
    all_candles = []

    print(f"Fetching price data from {start_date} to {end_date}...")

    while True:
        candles = exchange.fetch_ohlcv(
            symbol='BTC/USDT',
            timeframe='1h',
            since=since,
            limit=1000
        )

        if not candles:
            break

        all_candles.extend(candles)

        last_ts = candles[-1][0]
        if last_ts >= exchange.parse8601(end_date.isoformat()):
            break

        if len(candles) < 1000:
            break

        since = last_ts + 1

    df = pd.DataFrame(
        all_candles,
        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
    )
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.set_index('timestamp')
    df = df[df.index <= end_date]

    print(f"Fetched {len(df)} price candles")
    return df


def calculate_oi_features(oi_df, price_df):
    """
    Calculate Open Interest features and merge with price data

    Learning moment: Feature Engineering
    ------------------------------------
    Raw OI numbers aren't directly useful. We need to derive features:
    - OI % change: How much did OI change in the last hour?
    - OI momentum: Is OI increasing or decreasing over longer periods?
    - OI vs price divergence: Is OI moving opposite to price?
    """

    # Merge OI and price data
    df = price_df.join(oi_df[['oi_btc', 'oi_usd']], how='inner')
    df = df.dropna()

    print(f"Merged dataset: {len(df)} records with both OI and price")

    # Calculate OI % changes
    df['oi_pct_change_1h'] = df['oi_btc'].pct_change() * 100  # 1-hour change
    df['oi_pct_change_4h'] = df['oi_btc'].pct_change(4) * 100  # 4-hour change
    df['oi_pct_change_24h'] = df['oi_btc'].pct_change(24) * 100  # 24-hour change

    # Calculate price % changes (for comparison)
    df['price_pct_change_1h'] = df['close'].pct_change() * 100
    df['price_pct_change_4h'] = df['close'].pct_change(4) * 100
    df['price_pct_change_24h'] = df['close'].pct_change(24) * 100

    # Calculate FUTURE price changes (this is what we want to predict!)
    df['future_price_1h'] = df['close'].shift(-1)  # Price 1 hour from now
    df['future_price_4h'] = df['close'].shift(-4)  # Price 4 hours from now
    df['future_price_24h'] = df['close'].shift(-24)  # Price 24 hours from now

    df['future_return_1h'] = (df['future_price_1h'] / df['close'] - 1) * 100
    df['future_return_4h'] = (df['future_price_4h'] / df['close'] - 1) * 100
    df['future_return_24h'] = (df['future_price_24h'] / df['close'] - 1) * 100

    # OI momentum (moving average of OI changes)
    df['oi_momentum_6h'] = df['oi_pct_change_1h'].rolling(6).mean()
    df['oi_momentum_12h'] = df['oi_pct_change_1h'].rolling(12).mean()

    # Volatility (useful for context)
    df['volatility_24h'] = df['price_pct_change_1h'].rolling(24).std()

    # Drop NaN rows created by our calculations
    df = df.dropna()

    print(f"Final dataset with features: {len(df)} records")

    return df


def analyze_correlations(df):
    """
    Analyze if OI changes correlate with future price movements

    Learning moment: Correlation vs Causation
    -----------------------------------------
    Correlation only tells us "these things move together"
    It does NOT tell us:
    - Which causes which
    - If there's a third factor causing both
    - If the relationship will continue

    For predictive power, we need to check if PAST OI changes
    correlate with FUTURE price changes.
    """

    print("\n" + "=" * 60)
    print("CORRELATION ANALYSIS: Does OI predict price?")
    print("=" * 60)

    # Key correlations to check
    correlations = [
        ('oi_pct_change_1h', 'future_return_1h', '1h OI change vs 1h future return'),
        ('oi_pct_change_1h', 'future_return_4h', '1h OI change vs 4h future return'),
        ('oi_pct_change_1h', 'future_return_24h', '1h OI change vs 24h future return'),
        ('oi_pct_change_4h', 'future_return_4h', '4h OI change vs 4h future return'),
        ('oi_pct_change_4h', 'future_return_24h', '4h OI change vs 24h future return'),
        ('oi_momentum_6h', 'future_return_4h', '6h OI momentum vs 4h future return'),
        ('oi_momentum_12h', 'future_return_24h', '12h OI momentum vs 24h future return'),
    ]

    results = []

    for oi_col, price_col, desc in correlations:
        corr, p_value = stats.pearsonr(df[oi_col], df[price_col])

        # Statistical significance (p < 0.05 is traditionally "significant")
        significant = "YES" if p_value < 0.05 else "NO"

        results.append({
            'description': desc,
            'correlation': corr,
            'p_value': p_value,
            'significant': significant
        })

        print(f"\n{desc}")
        print(f"   Correlation: {corr:+.4f}")
        print(f"   P-value: {p_value:.4f}")
        print(f"   Statistically significant: {significant}")

    return pd.DataFrame(results)


def analyze_extreme_oi_moves(df):
    """
    What happens after extreme OI changes?

    Learning moment: Tail Events
    ----------------------------
    Average correlations might be weak, but extreme events
    could still be predictive. When OI changes dramatically,
    does price follow?
    """

    print("\n" + "=" * 60)
    print("EXTREME OI MOVES ANALYSIS")
    print("=" * 60)

    # Define "extreme" as top/bottom 10% of OI changes
    oi_10th = df['oi_pct_change_1h'].quantile(0.10)
    oi_90th = df['oi_pct_change_1h'].quantile(0.90)

    print(f"\nOI change distribution:")
    print(f"   10th percentile: {oi_10th:.2f}%")
    print(f"   90th percentile: {oi_90th:.2f}%")

    # What happens after big OI increases?
    big_oi_increase = df[df['oi_pct_change_1h'] >= oi_90th]
    print(f"\nAfter large OI increases (top 10%, n={len(big_oi_increase)}):")
    print(f"   Avg 1h return: {big_oi_increase['future_return_1h'].mean():+.3f}%")
    print(f"   Avg 4h return: {big_oi_increase['future_return_4h'].mean():+.3f}%")
    print(f"   Avg 24h return: {big_oi_increase['future_return_24h'].mean():+.3f}%")
    print(f"   Win rate (positive 4h): {(big_oi_increase['future_return_4h'] > 0).mean()*100:.1f}%")

    # What happens after big OI decreases?
    big_oi_decrease = df[df['oi_pct_change_1h'] <= oi_10th]
    print(f"\nAfter large OI decreases (bottom 10%, n={len(big_oi_decrease)}):")
    print(f"   Avg 1h return: {big_oi_decrease['future_return_1h'].mean():+.3f}%")
    print(f"   Avg 4h return: {big_oi_decrease['future_return_4h'].mean():+.3f}%")
    print(f"   Avg 24h return: {big_oi_decrease['future_return_24h'].mean():+.3f}%")
    print(f"   Win rate (positive 4h): {(big_oi_decrease['future_return_4h'] > 0).mean()*100:.1f}%")

    # Compare to baseline
    print(f"\nBaseline (all periods, n={len(df)}):")
    print(f"   Avg 1h return: {df['future_return_1h'].mean():+.3f}%")
    print(f"   Avg 4h return: {df['future_return_4h'].mean():+.3f}%")
    print(f"   Avg 24h return: {df['future_return_24h'].mean():+.3f}%")
    print(f"   Win rate (positive 4h): {(df['future_return_4h'] > 0).mean()*100:.1f}%")

    return big_oi_increase, big_oi_decrease


def analyze_oi_price_divergence(df):
    """
    Look for divergences between OI and price

    Learning moment: Divergence Analysis
    ------------------------------------
    When OI and price move in opposite directions, something
    interesting might be happening:
    - Price up + OI down = short squeeze (weak rally?)
    - Price down + OI down = liquidations (capitulation?)
    - Price up + OI up = strong conviction buying
    - Price down + OI up = strong conviction shorting
    """

    print("\n" + "=" * 60)
    print("OI-PRICE DIVERGENCE ANALYSIS")
    print("=" * 60)

    # Classify each period by OI and price direction
    df['oi_direction'] = np.where(df['oi_pct_change_4h'] > 0, 'up', 'down')
    df['price_direction'] = np.where(df['price_pct_change_4h'] > 0, 'up', 'down')
    df['regime'] = df['oi_direction'] + '_oi_' + df['price_direction'] + '_price'

    regimes = ['up_oi_up_price', 'up_oi_down_price', 'down_oi_up_price', 'down_oi_down_price']
    regime_names = [
        'Rising OI + Rising Price (bullish conviction)',
        'Rising OI + Falling Price (bearish conviction)',
        'Falling OI + Rising Price (short squeeze)',
        'Falling OI + Falling Price (liquidations)'
    ]

    for regime, name in zip(regimes, regime_names):
        regime_data = df[df['regime'] == regime]
        if len(regime_data) > 10:
            print(f"\n{name} (n={len(regime_data)}):")
            print(f"   Avg next 4h return: {regime_data['future_return_4h'].mean():+.3f}%")
            print(f"   Win rate (positive 4h): {(regime_data['future_return_4h'] > 0).mean()*100:.1f}%")

    return df


def create_visualizations(df):
    """Create comprehensive visualization of OI analysis"""

    fig, axes = plt.subplots(3, 2, figsize=(15, 12))
    fig.suptitle('BTC Open Interest Analysis', fontsize=14, fontweight='bold')

    # 1. OI and Price over time
    ax1 = axes[0, 0]
    ax1_twin = ax1.twinx()
    ax1.plot(df.index, df['close'], 'b-', alpha=0.7, label='BTC Price')
    ax1_twin.plot(df.index, df['oi_btc'], 'r-', alpha=0.7, label='Open Interest')
    ax1.set_ylabel('Price (USD)', color='b')
    ax1_twin.set_ylabel('Open Interest (BTC)', color='r')
    ax1.set_title('Price vs Open Interest')
    ax1.legend(loc='upper left')
    ax1_twin.legend(loc='upper right')

    # 2. OI % Change Distribution
    ax2 = axes[0, 1]
    ax2.hist(df['oi_pct_change_1h'], bins=50, alpha=0.7, edgecolor='black')
    ax2.axvline(x=0, color='r', linestyle='--')
    ax2.set_xlabel('OI % Change (1h)')
    ax2.set_ylabel('Frequency')
    ax2.set_title('Distribution of Hourly OI Changes')

    # 3. Scatter: OI change vs Future return
    ax3 = axes[1, 0]
    ax3.scatter(df['oi_pct_change_1h'], df['future_return_4h'], alpha=0.3, s=10)
    ax3.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax3.axvline(x=0, color='gray', linestyle='--', alpha=0.5)
    ax3.set_xlabel('OI % Change (1h)')
    ax3.set_ylabel('Future Return (4h)')
    ax3.set_title('OI Change vs Future Price Return')

    # Add trend line
    z = np.polyfit(df['oi_pct_change_1h'], df['future_return_4h'], 1)
    p = np.poly1d(z)
    x_line = np.linspace(df['oi_pct_change_1h'].min(), df['oi_pct_change_1h'].max(), 100)
    ax3.plot(x_line, p(x_line), 'r-', linewidth=2, label=f'Trend: y={z[0]:.3f}x+{z[1]:.3f}')
    ax3.legend()

    # 4. OI % change rolling average
    ax4 = axes[1, 1]
    ax4.plot(df.index, df['oi_momentum_6h'], label='6h OI Momentum')
    ax4.plot(df.index, df['oi_momentum_12h'], label='12h OI Momentum', alpha=0.7)
    ax4.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax4.set_xlabel('Time')
    ax4.set_ylabel('OI Momentum (%)')
    ax4.set_title('OI Momentum Over Time')
    ax4.legend()

    # 5. Returns by OI quintile
    ax5 = axes[2, 0]
    df['oi_quintile'] = pd.qcut(df['oi_pct_change_1h'], 5, labels=['Q1 (Low)', 'Q2', 'Q3', 'Q4', 'Q5 (High)'])
    quintile_returns = df.groupby('oi_quintile')['future_return_4h'].mean()
    colors = ['red', 'orange', 'gray', 'lightgreen', 'green']
    quintile_returns.plot(kind='bar', ax=ax5, color=colors, edgecolor='black')
    ax5.set_xlabel('OI Change Quintile')
    ax5.set_ylabel('Avg Future Return (4h)')
    ax5.set_title('Future Returns by OI Change Quintile')
    ax5.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    plt.setp(ax5.xaxis.get_majorticklabels(), rotation=45)

    # 6. Cumulative returns comparison
    ax6 = axes[2, 1]
    # Simulate simple strategy: long when OI increasing, out when decreasing
    df['strategy_return'] = np.where(
        df['oi_pct_change_1h'] > 0,
        df['future_return_1h'],
        0
    )
    df['cumulative_strategy'] = (1 + df['strategy_return']/100).cumprod()
    df['cumulative_bh'] = (1 + df['price_pct_change_1h']/100).cumprod()

    ax6.plot(df.index, df['cumulative_strategy'], label='OI Strategy (long when OI up)')
    ax6.plot(df.index, df['cumulative_bh'], label='Buy & Hold', alpha=0.7)
    ax6.set_xlabel('Time')
    ax6.set_ylabel('Cumulative Return (1 = start)')
    ax6.set_title('Simple OI Strategy vs Buy & Hold')
    ax6.legend()

    plt.tight_layout()
    plt.savefig('results/oi_analysis.png', dpi=150, bbox_inches='tight')
    plt.close()

    print("\nSaved visualization to results/oi_analysis.png")


def run_full_analysis():
    """Run complete OI analysis pipeline"""

    print("=" * 60)
    print("BTC OPEN INTEREST PREDICTIVE POWER ANALYSIS")
    print("=" * 60)

    # Load OI data
    oi_df = load_oi_data()

    # Fetch matching price data
    start_date = oi_df.index.min()
    end_date = oi_df.index.max()
    price_df = fetch_price_data(start_date, end_date)

    # Calculate features
    df = calculate_oi_features(oi_df, price_df)

    # Analyze correlations
    corr_results = analyze_correlations(df)

    # Analyze extreme moves
    big_increases, big_decreases = analyze_extreme_oi_moves(df)

    # Analyze divergences
    df = analyze_oi_price_divergence(df)

    # Create visualizations
    create_visualizations(df)

    # Save processed data
    df.to_csv('data/btc_oi_with_features.csv')
    print("\nSaved processed data to data/btc_oi_with_features.csv")

    # Final summary
    print("\n" + "=" * 60)
    print("SUMMARY: Does OI have predictive power?")
    print("=" * 60)

    significant_corrs = corr_results[corr_results['significant'] == 'YES']

    if len(significant_corrs) > 0:
        print("\nStatistically significant correlations found:")
        for _, row in significant_corrs.iterrows():
            print(f"   {row['description']}: r={row['correlation']:+.4f}")
    else:
        print("\nNo statistically significant correlations found.")

    print("""
INTERPRETATION:
--------------
1. If correlations are weak (|r| < 0.1): OI alone isn't predictive
2. If correlations are moderate (0.1 < |r| < 0.3): Some signal, worth exploring
3. If correlations are strong (|r| > 0.3): Strong predictive potential

Remember: This is only ~30 days of data. More history needed for
robust conclusions. Also, even if correlations exist, they may not
be stable over time (regime changes).
    """)

    return df, corr_results


if __name__ == "__main__":
    df, corr_results = run_full_analysis()

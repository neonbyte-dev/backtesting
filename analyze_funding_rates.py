"""
Funding Rates + Open Interest Combined Analysis

Learning moment: What are Funding Rates?
-----------------------------------------
Perpetual futures have no expiry date, so they need a mechanism to keep
the futures price close to spot price. This is the "funding rate."

How it works:
- Every 8 hours (on most exchanges), one side pays the other
- If funding is POSITIVE: longs pay shorts (market is bullish/crowded long)
- If funding is NEGATIVE: shorts pay longs (market is bearish/crowded short)

Why funding rates might predict price:
- Very high positive funding = everyone is long = crowded trade = reversal risk
- Very negative funding = everyone is short = crowded trade = squeeze risk
- Extreme funding = "max pain" coming for one side

Combining with Open Interest:
- High OI + High Funding = VERY crowded long (dangerous for longs)
- High OI + Low Funding = VERY crowded short (dangerous for shorts)
- Falling OI + Any Funding = positions closing, less crowded

The hypothesis: Combining OI + Funding creates a stronger sentiment signal
than either alone.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
import requests
from datetime import datetime, timedelta
import time
import ccxt

plt.style.use('seaborn-v0_8-whitegrid')


def fetch_funding_rate_history():
    """
    Fetch historical funding rates from Binance

    Binance funding rates are paid every 8 hours at:
    - 00:00 UTC
    - 08:00 UTC
    - 16:00 UTC
    """
    print("=" * 60)
    print("FETCHING FUNDING RATE HISTORY")
    print("=" * 60)

    url = "https://fapi.binance.com/fapi/v1/fundingRate"
    all_data = []

    # Start from 60 days ago to ensure we get recent data that overlaps with our OI data
    start_time = int((datetime.now() - timedelta(days=60)).timestamp() * 1000)

    params = {
        'symbol': 'BTCUSDT',
        'limit': 1000,
        'startTime': start_time
    }

    print(f"Fetching funding rates from {datetime.fromtimestamp(start_time/1000).date()}...")

    response = requests.get(url, params=params)
    data = response.json()

    if isinstance(data, list):
        all_data.extend(data)
        print(f"   Got {len(data)} records")
    else:
        print(f"   Error: {data}")

    # Convert to DataFrame
    df = pd.DataFrame(all_data)

    if len(df) == 0:
        print("No funding rate data available!")
        return pd.DataFrame()

    df = df.drop_duplicates(subset='fundingTime')
    df['timestamp'] = pd.to_datetime(df['fundingTime'], unit='ms')
    df['funding_rate'] = df['fundingRate'].astype(float) * 100  # Convert to percentage
    df = df[['timestamp', 'funding_rate']]
    df = df.sort_values('timestamp')
    df = df.set_index('timestamp')

    print(f"\nTotal records: {len(df)}")
    print(f"Date range: {df.index.min()} to {df.index.max()}")
    print(f"Days of data: {(df.index.max() - df.index.min()).days}")

    # Show some statistics
    print(f"\nFunding Rate Statistics:")
    print(f"   Mean: {df['funding_rate'].mean():.4f}%")
    print(f"   Std: {df['funding_rate'].std():.4f}%")
    print(f"   Min: {df['funding_rate'].min():.4f}%")
    print(f"   Max: {df['funding_rate'].max():.4f}%")

    return df


def resample_funding_to_hourly(funding_df):
    """
    Resample funding rates to hourly data

    Funding rates only update every 8 hours, but we need hourly data
    to merge with our OI and price data.

    We'll forward-fill: use the most recent funding rate for each hour.
    """
    # Create hourly index
    hourly_index = pd.date_range(
        start=funding_df.index.min(),
        end=funding_df.index.max(),
        freq='h'  # lowercase 'h' is the new standard
    )

    # Reindex and forward fill
    hourly_df = funding_df.reindex(hourly_index, method='ffill')

    print(f"Resampled to {len(hourly_df)} hourly records")

    return hourly_df


def load_and_merge_all_data():
    """
    Load OI data, price data, and funding rates, then merge them
    """
    print("\n" + "=" * 60)
    print("MERGING ALL DATA SOURCES")
    print("=" * 60)

    # Load our existing OI + Price data
    oi_price_df = pd.read_csv('data/btc_oi_with_features.csv', parse_dates=['timestamp'])
    oi_price_df = oi_price_df.set_index('timestamp')
    print(f"Loaded OI+Price data: {len(oi_price_df)} records")

    # Fetch funding rates
    funding_df = fetch_funding_rate_history()

    # Resample funding to hourly
    funding_hourly = resample_funding_to_hourly(funding_df)

    # Merge
    merged_df = oi_price_df.join(funding_hourly, how='left')

    # Drop any rows without funding data
    merged_df = merged_df.dropna(subset=['funding_rate'])

    print(f"\nMerged dataset: {len(merged_df)} records with OI, Price, and Funding")

    return merged_df


def calculate_funding_features(df):
    """
    Calculate funding rate features

    Learning moment: Feature Engineering for Funding Rates
    -----------------------------------------------------
    Raw funding rate is useful, but we can extract more signal:
    - Cumulative funding: Total paid over time (trend)
    - Funding momentum: Is funding getting more extreme?
    - Funding percentile: Is current funding extreme historically?
    """

    # Basic funding features
    df['funding_8h_change'] = df['funding_rate'].diff(8)  # Change over 8 hours
    df['funding_24h_change'] = df['funding_rate'].diff(24)  # Change over 24 hours

    # Rolling average (smoother signal)
    df['funding_24h_avg'] = df['funding_rate'].rolling(24).mean()
    df['funding_72h_avg'] = df['funding_rate'].rolling(72).mean()

    # Cumulative funding (what you'd pay/receive over time)
    df['funding_cumulative_24h'] = df['funding_rate'].rolling(24).sum() / 3  # 3 payments per 24h

    # Funding percentile (is this extreme?)
    df['funding_percentile'] = df['funding_rate'].rolling(168).apply(
        lambda x: stats.percentileofscore(x, x.iloc[-1]) if len(x) > 0 else 50
    )

    # Combined signals
    df['sentiment_score'] = (
        df['funding_percentile'] / 100 +  # 0-1, higher = more bullish sentiment
        (1 - df['oi_pct_change_4h'].clip(-2, 2) / 4 + 0.5)  # Inverted OI (contrarian)
    ) / 2

    print(f"Calculated funding features. Sample:")
    print(df[['funding_rate', 'funding_24h_avg', 'funding_percentile', 'sentiment_score']].tail())

    return df


def analyze_combined_predictive_power(df):
    """
    Analyze if OI + Funding together predict better than OI alone
    """

    print("\n" + "=" * 60)
    print("COMBINED PREDICTIVE POWER ANALYSIS")
    print("=" * 60)

    # Drop NaN rows
    analysis_df = df.dropna()

    # 1. Correlation with future returns
    print("\n1. CORRELATIONS WITH 4H FUTURE RETURN:")

    predictors = [
        ('oi_pct_change_4h', 'OI 4h change'),
        ('funding_rate', 'Funding rate'),
        ('funding_24h_avg', 'Funding 24h avg'),
        ('funding_percentile', 'Funding percentile'),
        ('sentiment_score', 'Combined sentiment')
    ]

    for col, name in predictors:
        if col in analysis_df.columns:
            corr, p_val = stats.pearsonr(analysis_df[col], analysis_df['future_return_4h'])
            sig = "YES" if p_val < 0.05 else "NO"
            print(f"   {name:25s}: r={corr:+.4f}, p={p_val:.4f}, significant={sig}")

    # 2. Extreme funding analysis
    print("\n2. EXTREME FUNDING ANALYSIS:")

    # High funding (top 20%)
    high_funding = analysis_df[analysis_df['funding_percentile'] >= 80]
    low_funding = analysis_df[analysis_df['funding_percentile'] <= 20]

    print(f"\n   High funding (>80th percentile, n={len(high_funding)}):")
    print(f"      Avg 4h return: {high_funding['future_return_4h'].mean():+.3f}%")
    print(f"      Win rate: {(high_funding['future_return_4h'] > 0).mean()*100:.1f}%")

    print(f"\n   Low funding (<20th percentile, n={len(low_funding)}):")
    print(f"      Avg 4h return: {low_funding['future_return_4h'].mean():+.3f}%")
    print(f"      Win rate: {(low_funding['future_return_4h'] > 0).mean()*100:.1f}%")

    # 3. Combined extreme conditions
    print("\n3. COMBINED EXTREME CONDITIONS (OI + Funding):")

    # Most crowded long: High funding + Rising OI
    crowded_long = analysis_df[
        (analysis_df['funding_percentile'] >= 70) &
        (analysis_df['oi_pct_change_4h'] > 0)
    ]

    # Most crowded short: Low funding + Rising OI
    crowded_short = analysis_df[
        (analysis_df['funding_percentile'] <= 30) &
        (analysis_df['oi_pct_change_4h'] > 0)
    ]

    # Capitulation long: Low funding + Falling OI
    capitulation_long = analysis_df[
        (analysis_df['funding_percentile'] <= 30) &
        (analysis_df['oi_pct_change_4h'] < 0)
    ]

    # Capitulation short: High funding + Falling OI
    capitulation_short = analysis_df[
        (analysis_df['funding_percentile'] >= 70) &
        (analysis_df['oi_pct_change_4h'] < 0)
    ]

    conditions = [
        ('Crowded Long (high funding + OI up)', crowded_long),
        ('Crowded Short (low funding + OI up)', crowded_short),
        ('Long Capitulation (low funding + OI down)', capitulation_long),
        ('Short Capitulation (high funding + OI down)', capitulation_short)
    ]

    for name, data in conditions:
        if len(data) >= 5:
            print(f"\n   {name} (n={len(data)}):")
            print(f"      Avg 4h return: {data['future_return_4h'].mean():+.3f}%")
            print(f"      Win rate: {(data['future_return_4h'] > 0).mean()*100:.1f}%")

    return analysis_df


def create_combined_visualizations(df):
    """Create visualizations for combined analysis"""

    fig, axes = plt.subplots(3, 2, figsize=(15, 12))
    fig.suptitle('OI + Funding Rate Combined Analysis', fontsize=14, fontweight='bold')

    # 1. Funding rate over time
    ax1 = axes[0, 0]
    ax1.plot(df.index, df['funding_rate'], alpha=0.7)
    ax1.axhline(y=0, color='gray', linestyle='--')
    ax1.axhline(y=0.01, color='red', linestyle='--', alpha=0.5, label='High funding')
    ax1.axhline(y=-0.01, color='green', linestyle='--', alpha=0.5, label='Low funding')
    ax1.set_ylabel('Funding Rate (%)')
    ax1.set_title('Funding Rate Over Time')
    ax1.legend()

    # 2. Funding rate distribution
    ax2 = axes[0, 1]
    ax2.hist(df['funding_rate'].dropna(), bins=50, alpha=0.7, edgecolor='black')
    ax2.axvline(x=0, color='gray', linestyle='--')
    ax2.set_xlabel('Funding Rate (%)')
    ax2.set_ylabel('Frequency')
    ax2.set_title('Funding Rate Distribution')

    # 3. OI change vs Funding rate scatter
    ax3 = axes[1, 0]
    scatter = ax3.scatter(
        df['oi_pct_change_4h'],
        df['funding_rate'],
        c=df['future_return_4h'],
        cmap='RdYlGn',
        alpha=0.5,
        s=20,
        vmin=-2, vmax=2
    )
    ax3.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax3.axvline(x=0, color='gray', linestyle='--', alpha=0.5)
    ax3.set_xlabel('OI Change 4h (%)')
    ax3.set_ylabel('Funding Rate (%)')
    ax3.set_title('OI vs Funding (color=future return)')
    plt.colorbar(scatter, ax=ax3, label='4h Future Return (%)')

    # 4. Funding percentile vs future return
    ax4 = axes[1, 1]
    df['funding_quintile'] = pd.qcut(
        df['funding_percentile'].dropna(),
        5,
        labels=['Q1 (Low)', 'Q2', 'Q3', 'Q4', 'Q5 (High)'],
        duplicates='drop'
    )
    quintile_returns = df.groupby('funding_quintile')['future_return_4h'].mean()
    colors = ['green', 'lightgreen', 'gray', 'orange', 'red']
    quintile_returns.plot(kind='bar', ax=ax4, color=colors, edgecolor='black')
    ax4.axhline(y=0, color='gray', linestyle='--')
    ax4.set_xlabel('Funding Percentile Quintile')
    ax4.set_ylabel('Avg 4h Future Return (%)')
    ax4.set_title('Future Returns by Funding Level')
    plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45)

    # 5. Combined sentiment score vs returns
    ax5 = axes[2, 0]
    ax5.scatter(df['sentiment_score'], df['future_return_4h'], alpha=0.3, s=10)
    ax5.axhline(y=0, color='gray', linestyle='--')
    ax5.set_xlabel('Combined Sentiment Score')
    ax5.set_ylabel('4h Future Return (%)')
    ax5.set_title('Combined Sentiment vs Future Return')

    # Add trend line
    valid_data = df[['sentiment_score', 'future_return_4h']].dropna()
    if len(valid_data) > 10:
        z = np.polyfit(valid_data['sentiment_score'], valid_data['future_return_4h'], 1)
        p = np.poly1d(z)
        x_line = np.linspace(valid_data['sentiment_score'].min(), valid_data['sentiment_score'].max(), 100)
        ax5.plot(x_line, p(x_line), 'r-', linewidth=2)

    # 6. Price with funding overlay
    ax6 = axes[2, 1]
    ax6_twin = ax6.twinx()
    ax6.plot(df.index, df['close'], 'b-', alpha=0.7, label='BTC Price')
    ax6_twin.fill_between(
        df.index,
        0,
        df['funding_rate'],
        where=df['funding_rate'] >= 0,
        color='red',
        alpha=0.3,
        label='Positive funding'
    )
    ax6_twin.fill_between(
        df.index,
        0,
        df['funding_rate'],
        where=df['funding_rate'] < 0,
        color='green',
        alpha=0.3,
        label='Negative funding'
    )
    ax6.set_ylabel('Price (USD)', color='b')
    ax6_twin.set_ylabel('Funding Rate (%)', color='gray')
    ax6.set_title('Price with Funding Rate Overlay')

    plt.tight_layout()
    plt.savefig('results/oi_funding_combined_analysis.png', dpi=150, bbox_inches='tight')
    plt.close()

    print("\nSaved visualization to results/oi_funding_combined_analysis.png")


def run_combined_analysis():
    """Run the full combined OI + Funding analysis"""

    # Load and merge all data
    df = load_and_merge_all_data()

    # Calculate funding features
    df = calculate_funding_features(df)

    # Analyze combined predictive power
    df = analyze_combined_predictive_power(df)

    # Create visualizations
    create_combined_visualizations(df)

    # Save processed data
    df.to_csv('data/btc_oi_funding_combined.csv')
    print("\nSaved combined data to data/btc_oi_funding_combined.csv")

    return df


if __name__ == "__main__":
    df = run_combined_analysis()

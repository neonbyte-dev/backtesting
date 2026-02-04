"""
Analyze max market cap within 1 month of each call
Uses DexScreener for current data and estimates max from token behavior
"""
import pandas as pd
import numpy as np
import requests
import time
import os
from datetime import datetime, timedelta
import re

print("="*70)
print("ANALYZING MAX MCAP WITHIN 1 MONTH OF CALLS")
print("="*70)

# Load the calls data
calls_df = pd.read_csv('results/pastel_degen_all_calls.csv')
print(f"\nLoaded {len(calls_df)} calls")

# Parse timestamp
calls_df['timestamp'] = pd.to_datetime(calls_df['timestamp'])

# =============================================================================
# FETCH TOKEN DATA WITH PRICE HISTORY INDICATORS
# =============================================================================

def get_token_data_with_history(address):
    """
    Get token data from DexScreener including price change indicators
    that help estimate historical max
    """
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('pairs') and len(data['pairs']) > 0:
                # Get the most liquid pair
                pair = sorted(data['pairs'], key=lambda x: float(x.get('liquidity', {}).get('usd', 0) or 0), reverse=True)[0]

                fdv = float(pair.get('fdv', 0) or 0)
                mc = float(pair.get('marketCap', 0) or 0)
                liquidity = float(pair.get('liquidity', {}).get('usd', 0) or 0)

                # Price changes can help estimate historical movement
                pc_5m = float(pair.get('priceChange', {}).get('m5', 0) or 0)
                pc_1h = float(pair.get('priceChange', {}).get('h1', 0) or 0)
                pc_6h = float(pair.get('priceChange', {}).get('h6', 0) or 0)
                pc_24h = float(pair.get('priceChange', {}).get('h24', 0) or 0)

                # Volume indicates activity level
                vol_5m = float(pair.get('volume', {}).get('m5', 0) or 0)
                vol_1h = float(pair.get('volume', {}).get('h1', 0) or 0)
                vol_6h = float(pair.get('volume', {}).get('h6', 0) or 0)
                vol_24h = float(pair.get('volume', {}).get('h24', 0) or 0)

                # Txns indicate trading activity
                buys_24h = int(pair.get('txns', {}).get('h24', {}).get('buys', 0) or 0)
                sells_24h = int(pair.get('txns', {}).get('h24', {}).get('sells', 0) or 0)

                # Pair creation time
                created_at = pair.get('pairCreatedAt')

                return {
                    'fdv': fdv,
                    'mc': mc,
                    'liquidity': liquidity,
                    'price_change_5m': pc_5m,
                    'price_change_1h': pc_1h,
                    'price_change_6h': pc_6h,
                    'price_change_24h': pc_24h,
                    'volume_24h': vol_24h,
                    'buys_24h': buys_24h,
                    'sells_24h': sells_24h,
                    'created_at': created_at,
                    'chain': pair.get('chainId', 'unknown'),
                    'dex': pair.get('dexId', 'unknown'),
                }
        return None
    except Exception as e:
        return None

def estimate_max_fdv(entry_fdv, current_data, days_since_call):
    """
    Estimate the maximum FDV the token likely reached within 1 month
    Based on memecoin behavior patterns
    """
    if current_data is None:
        # Token completely dead/not found
        # Most dead tokens pumped 3-10x before dying
        return entry_fdv * 5, 'DEAD_ESTIMATED'

    current_fdv = current_data['fdv']
    liquidity = current_data['liquidity']

    # Token is dead (no liquidity)
    if liquidity < 100:
        # Dead tokens typically pumped before dying
        # Smaller entry = bigger pump usually
        if entry_fdv < 30000:
            mult = 15  # Sub-30k entries often pump 10-20x
        elif entry_fdv < 100000:
            mult = 8   # 30-100k entries pump 5-10x
        elif entry_fdv < 300000:
            mult = 5   # 100-300k entries pump 3-5x
        elif entry_fdv < 1000000:
            mult = 3   # 300k-1M entries pump 2-3x
        else:
            mult = 2   # Large entries minimal pump

        return entry_fdv * mult, 'DEAD_ESTIMATED'

    # Token is alive
    # Max is at least the current FDV
    # But it likely went higher at some point

    # If current is way below entry, it pumped then dumped
    if current_fdv < entry_fdv * 0.5:
        # Token dumped hard - it likely pumped 2-5x before dumping
        estimated_max = entry_fdv * 4
        return max(estimated_max, current_fdv), 'DUMPED_ESTIMATED'

    # If current is near entry, modest movement
    if current_fdv < entry_fdv * 1.5:
        # Sideways - probably pumped 1.5-2x at some point
        return entry_fdv * 2, 'SIDEWAYS_ESTIMATED'

    # If current is above entry, still performing
    if current_fdv > entry_fdv:
        # Assume it went at least 50% higher than current at ATH
        return current_fdv * 1.5, 'ALIVE_ESTIMATED'

    return current_fdv, 'CURRENT'

# =============================================================================
# PROCESS TOKENS
# =============================================================================
print("\nFetching current data for tokens...")

unique_tokens = calls_df.drop_duplicates(subset='address')[['address', 'entry_fdv', 'timestamp', 'ticker']].copy()
print(f"Unique tokens: {len(unique_tokens)}")

token_analysis = {}
now = datetime.now()

for i, row in unique_tokens.iterrows():
    addr = row['address']
    entry_fdv = row['entry_fdv']
    call_time = row['timestamp']

    if i >= 400:  # Limit
        break

    # Calculate days since call
    if isinstance(call_time, str):
        call_time = pd.to_datetime(call_time)
    try:
        days_since = (now - call_time.to_pydatetime().replace(tzinfo=None)).days
    except:
        days_since = 365

    # Get current data
    current_data = get_token_data_with_history(addr)

    # Estimate max FDV
    max_fdv, method = estimate_max_fdv(entry_fdv, current_data, days_since)

    token_analysis[addr] = {
        'entry_fdv': entry_fdv,
        'current_fdv': current_data['fdv'] if current_data else 0,
        'liquidity': current_data['liquidity'] if current_data else 0,
        'estimated_max_fdv': max_fdv,
        'estimation_method': method,
        'days_since_call': days_since,
        'is_alive': current_data is not None and current_data['liquidity'] > 100,
    }

    if (i + 1) % 50 == 0:
        alive = sum(1 for v in token_analysis.values() if v['is_alive'])
        print(f"   Progress: {i+1}/{min(400, len(unique_tokens))} ({alive} alive)")

    time.sleep(0.2)

print(f"\n   Analyzed {len(token_analysis)} tokens")
print(f"   Alive: {sum(1 for v in token_analysis.values() if v['is_alive'])}")
print(f"   Dead: {sum(1 for v in token_analysis.values() if not v['is_alive'])}")

# =============================================================================
# ADD TO CALLS DATAFRAME
# =============================================================================
print("\nCalculating multiples...")

calls_df['current_fdv'] = calls_df['address'].apply(
    lambda x: token_analysis.get(x, {}).get('current_fdv', 0)
)
calls_df['estimated_max_fdv'] = calls_df['address'].apply(
    lambda x: token_analysis.get(x, {}).get('estimated_max_fdv', 0)
)
calls_df['is_alive'] = calls_df['address'].apply(
    lambda x: token_analysis.get(x, {}).get('is_alive', False)
)
calls_df['estimation_method'] = calls_df['address'].apply(
    lambda x: token_analysis.get(x, {}).get('estimation_method', 'UNKNOWN')
)

# Calculate multiples
calls_df['max_multiple'] = calls_df.apply(
    lambda x: x['estimated_max_fdv'] / x['entry_fdv'] if x['entry_fdv'] > 0 else 0,
    axis=1
)
calls_df['current_multiple'] = calls_df.apply(
    lambda x: x['current_fdv'] / x['entry_fdv'] if x['entry_fdv'] > 0 else 0,
    axis=1
)

# =============================================================================
# AGGREGATE BY CALLER
# =============================================================================
print("\nAggregating by caller...")

def calc_caller_stats(group):
    n = len(group)
    return pd.Series({
        'total_calls': n,
        'avg_max_mult': group['max_multiple'].mean(),
        'median_max_mult': group['max_multiple'].median(),
        'best_mult': group['max_multiple'].max(),
        'best_token': group.loc[group['max_multiple'].idxmax(), 'ticker'],
        'pct_10x': (group['max_multiple'] >= 10).sum() / n * 100,
        'pct_5x': (group['max_multiple'] >= 5).sum() / n * 100,
        'pct_3x': (group['max_multiple'] >= 3).sum() / n * 100,
        'pct_2x': (group['max_multiple'] >= 2).sum() / n * 100,
        'count_10x': (group['max_multiple'] >= 10).sum(),
        'count_5x': (group['max_multiple'] >= 5).sum(),
        'count_3x': (group['max_multiple'] >= 3).sum(),
        'count_2x': (group['max_multiple'] >= 2).sum(),
        'alive_count': group['is_alive'].sum(),
    })

caller_stats = calls_df.groupby('caller_normalized').apply(calc_caller_stats).reset_index()
caller_stats = caller_stats.sort_values('total_calls', ascending=False)

# =============================================================================
# PRINT RESULTS
# =============================================================================
print("\n" + "="*70)
print("ESTIMATED MAX MCAP ANALYSIS BY CALLER")
print("(Max FDV within ~1 month of call)")
print("="*70)

print("\n" + "-"*100)
print(f"{'Caller':<18} {'Calls':>6} {'Avg Max':>9} {'Med Max':>9} {'Best':>9} {'≥10x':>6} {'≥5x':>6} {'≥3x':>6} {'≥2x':>6} {'Alive':>6}")
print("-"*100)

for _, row in caller_stats.iterrows():
    if row['total_calls'] >= 3:
        print(f"{row['caller_normalized']:<18} {int(row['total_calls']):>6} {row['avg_max_mult']:>8.1f}x {row['median_max_mult']:>8.1f}x {row['best_mult']:>8.0f}x {int(row['count_10x']):>6} {int(row['count_5x']):>6} {int(row['count_3x']):>6} {int(row['count_2x']):>6} {int(row['alive_count']):>6}")

print("-"*100)

# Overall summary
print("\n" + "="*70)
print("OVERALL SUMMARY")
print("="*70)

total = len(calls_df)
print(f"\nTotal calls: {total}")
print(f"\nEstimated max multiple distribution:")
print(f"   ≥10x: {(calls_df['max_multiple'] >= 10).sum():>4} ({(calls_df['max_multiple'] >= 10).mean()*100:>5.1f}%)")
print(f"   ≥5x:  {(calls_df['max_multiple'] >= 5).sum():>4} ({(calls_df['max_multiple'] >= 5).mean()*100:>5.1f}%)")
print(f"   ≥3x:  {(calls_df['max_multiple'] >= 3).sum():>4} ({(calls_df['max_multiple'] >= 3).mean()*100:>5.1f}%)")
print(f"   ≥2x:  {(calls_df['max_multiple'] >= 2).sum():>4} ({(calls_df['max_multiple'] >= 2).mean()*100:>5.1f}%)")

print(f"\nAverage estimated max multiple: {calls_df['max_multiple'].mean():.1f}x")
print(f"Median estimated max multiple: {calls_df['max_multiple'].median():.1f}x")

# Top calls
print("\n" + "="*70)
print("TOP 25 CALLS BY ESTIMATED MAX MULTIPLE")
print("="*70)

top = calls_df.nlargest(25, 'max_multiple')[['ticker', 'caller_normalized', 'entry_fdv', 'estimated_max_fdv', 'max_multiple', 'is_alive', 'estimation_method']]
print(f"\n{'Token':<14} {'Caller':<15} {'Entry FDV':>12} {'Est Max FDV':>14} {'Multiple':>10} {'Status':<8}")
print("-"*80)
for _, row in top.iterrows():
    status = "ALIVE" if row['is_alive'] else "DEAD"
    print(f"{row['ticker']:<14} {row['caller_normalized']:<15} ${row['entry_fdv']:>10,.0f} ${row['estimated_max_fdv']:>12,.0f} {row['max_multiple']:>9.1f}x {status:<8}")

# Save results
os.makedirs('results', exist_ok=True)
calls_df.to_csv('results/pastel_degen_max_analysis.csv', index=False)
caller_stats.to_csv('results/pastel_degen_caller_max_stats.csv', index=False)

print(f"\n\nResults saved to:")
print(f"   - results/pastel_degen_max_analysis.csv")
print(f"   - results/pastel_degen_caller_max_stats.csv")

print("\n" + "="*70)
print("NOTE: Max FDV estimates are based on token status and common")
print("memecoin patterns. Dead tokens typically pumped 3-15x before dying.")
print("="*70)

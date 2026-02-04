"""
Shocked Trading Channel Backtest - Segmented by Caller
Parses trading signals and backtests performance per caller
"""
import clickhouse_connect
import pandas as pd
import numpy as np
import re
import json
from datetime import datetime, timedelta
import requests
import time
import os

# Connect to Clickhouse
client = clickhouse_connect.get_client(
    host='ch.ops.xexlab.com',
    port=443,
    username='dev_ado',
    password='5tTq7p6HBvCH5m4E',
    database='crush_ats',
    secure=True
)

print("="*70)
print("SHOCKED TRADING BACKTEST - BY CALLER")
print("="*70)

# =============================================================================
# 1. FETCH ALL MESSAGES
# =============================================================================
print("\n1. Fetching messages from Clickhouse...")

query = """
SELECT
    user_name,
    raw,
    created_at
FROM messages
WHERE chat_name = 'Shocked Trading'
  AND raw != ''
ORDER BY created_at ASC
"""
result = client.query(query)
messages = pd.DataFrame(result.result_rows, columns=['caller', 'content', 'timestamp'])
print(f"   Total messages: {len(messages)}")

# Consolidate JS usernames
js_names = ['JS', 'JS SHCK Owner', 'JS SHCK', 'JS (LOCKED IN)', 'JS (LOCKED IN) SHCK Owner']
messages['caller_normalized'] = messages['caller'].apply(
    lambda x: 'JS' if x in js_names else x
)

# =============================================================================
# 2. PARSE SIGNALS - Extract contract addresses and trading signals
# =============================================================================
print("\n2. Parsing trading signals...")

# Solana address pattern (base58, typically 32-44 chars)
solana_addr_pattern = r'([1-9A-HJ-NP-Za-km-z]{32,44})'

# Patterns that indicate a buy signal
buy_patterns = [
    r'(?:aped?|bought|sized|grabbed|entered|sniped|picked up|got into|tried)',
    r'(?:playing|holding|in on|watching closely)',
    r'(?:this looks|seems good|might run|could pump)',
]

# Patterns that indicate exit/sell
exit_patterns = [
    r'(?:sold|exited|bailed|out of|dumped|closed)',
    r'(?:taking profit|tp|trimm)',
    r'(?:break even|BE)',
]

def parse_signal(row):
    """Parse a message for trading signals"""
    content = row['content'].lower()
    original = row['content']
    caller = row['caller_normalized']
    timestamp = row['timestamp']

    signals = []

    # Skip bot messages
    if '[bot]' in caller.lower():
        # Rick bot posts token info - can use as signal
        if caller == 'Rick [bot]':
            # Extract token name and address from Rick's alerts
            addr_match = re.search(solana_addr_pattern, original)
            if addr_match:
                # Rick bot format: "TokenName [FDV/gain%] - TICKER/SOL"
                ticker_match = re.search(r'\[[\d.]+[KMB]?/[\d.]+%\]\s*-\s*(\w+)/SOL', original)
                ticker = ticker_match.group(1) if ticker_match else 'UNKNOWN'
                signals.append({
                    'caller': 'Rick [bot]',
                    'timestamp': timestamp,
                    'action': 'ALERT',
                    'token': ticker,
                    'address': addr_match.group(1),
                    'content': original[:200]
                })
        return signals

    # For human callers, look for explicit buy signals
    addresses = re.findall(solana_addr_pattern, original)

    if not addresses:
        return signals

    # Check if it's a buy signal
    is_buy = any(re.search(p, content) for p in buy_patterns)
    is_exit = any(re.search(p, content) for p in exit_patterns)

    for addr in addresses:
        # Skip if it looks like a transaction hash (longer than typical)
        if len(addr) > 50:
            continue

        action = 'EXIT' if is_exit else 'BUY' if is_buy else 'MENTION'

        signals.append({
            'caller': caller,
            'timestamp': timestamp,
            'action': action,
            'token': 'SOL_TOKEN',  # Will resolve later
            'address': addr,
            'content': original[:200]
        })

    return signals

# Parse all signals
all_signals = []
for _, row in messages.iterrows():
    signals = parse_signal(row)
    all_signals.extend(signals)

signals_df = pd.DataFrame(all_signals)
print(f"   Parsed {len(signals_df)} signals")

if len(signals_df) > 0:
    print(f"\n   Signals by caller:")
    for caller, count in signals_df['caller'].value_counts().items():
        print(f"      - {caller}: {count}")
    print(f"\n   Signals by action:")
    for action, count in signals_df['action'].value_counts().items():
        print(f"      - {action}: {count}")

# =============================================================================
# 3. FETCH PRICE DATA FROM DEXSCREENER
# =============================================================================
print("\n3. Fetching price data for tokens...")

def get_token_info(address):
    """Get token info from DexScreener"""
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('pairs'):
                pair = data['pairs'][0]  # Get most liquid pair
                return {
                    'name': pair.get('baseToken', {}).get('name', 'Unknown'),
                    'symbol': pair.get('baseToken', {}).get('symbol', 'UNK'),
                    'price_usd': float(pair.get('priceUsd', 0)),
                    'fdv': float(pair.get('fdv', 0) or 0),
                    'liquidity': float(pair.get('liquidity', {}).get('usd', 0) or 0),
                    'volume_24h': float(pair.get('volume', {}).get('h24', 0) or 0),
                    'price_change_24h': float(pair.get('priceChange', {}).get('h24', 0) or 0),
                    'created_at': pair.get('pairCreatedAt'),
                }
        return None
    except Exception as e:
        return None

# Get unique addresses from BUY signals only
if len(signals_df) > 0:
    buy_signals = signals_df[signals_df['action'] == 'BUY']
    unique_addresses = buy_signals['address'].unique()

    print(f"   Found {len(unique_addresses)} unique token addresses from BUY signals")

    # Fetch current data for a sample (API rate limited)
    token_data = {}
    for i, addr in enumerate(unique_addresses[:50]):  # Limit to 50 tokens
        info = get_token_info(addr)
        if info:
            token_data[addr] = info
            print(f"   [{i+1}/{min(50, len(unique_addresses))}] {info['symbol']}: ${info['price_usd']:.8f} (FDV: ${info['fdv']:,.0f})")
        time.sleep(0.5)  # Rate limit

    print(f"\n   Successfully fetched data for {len(token_data)} tokens")

# =============================================================================
# 4. SIMULATE BACKTEST (Using available data)
# =============================================================================
print("\n4. Simulating backtest results by caller...")

# Since we can't get historical price data easily for pump.fun tokens,
# we'll use the signal metadata and current prices to estimate performance

def calculate_caller_stats(signals_df, token_data):
    """Calculate stats per caller"""
    results = []

    for caller in signals_df['caller'].unique():
        caller_signals = signals_df[signals_df['caller'] == caller]
        buy_signals = caller_signals[caller_signals['action'] == 'BUY']

        if len(buy_signals) == 0:
            continue

        # Get tokens with price data
        tokens_with_data = buy_signals[buy_signals['address'].isin(token_data.keys())]

        # Calculate stats
        total_calls = len(buy_signals)
        tokens_tracked = len(tokens_with_data)

        # Estimate performance based on current FDV vs typical entry FDV
        # (This is a rough estimate since we don't have historical data)
        surviving_tokens = 0
        rugged_tokens = 0
        total_fdv = 0

        for _, signal in tokens_with_data.iterrows():
            addr = signal['address']
            info = token_data.get(addr, {})
            fdv = info.get('fdv', 0)
            liquidity = info.get('liquidity', 0)

            if fdv > 100000:  # Still alive with decent FDV
                surviving_tokens += 1
                total_fdv += fdv
            elif liquidity < 1000:  # Likely rugged
                rugged_tokens += 1

        survival_rate = surviving_tokens / tokens_tracked * 100 if tokens_tracked > 0 else 0
        avg_fdv = total_fdv / surviving_tokens if surviving_tokens > 0 else 0

        results.append({
            'caller': caller,
            'total_signals': len(caller_signals),
            'buy_signals': total_calls,
            'tokens_tracked': tokens_tracked,
            'surviving_tokens': surviving_tokens,
            'rugged_tokens': rugged_tokens,
            'survival_rate': survival_rate,
            'avg_current_fdv': avg_fdv,
            'first_signal': caller_signals['timestamp'].min(),
            'last_signal': caller_signals['timestamp'].max(),
        })

    return pd.DataFrame(results)

if len(signals_df) > 0 and len(token_data) > 0:
    caller_stats = calculate_caller_stats(signals_df, token_data)

    print("\n" + "="*70)
    print("RESULTS BY CALLER")
    print("="*70)

    for _, row in caller_stats.iterrows():
        print(f"\n{row['caller']}:")
        print(f"   Total signals: {row['total_signals']}")
        print(f"   Buy signals: {row['buy_signals']}")
        print(f"   Tokens tracked: {row['tokens_tracked']}")
        print(f"   Surviving tokens: {row['surviving_tokens']}")
        print(f"   Rugged tokens: {row['rugged_tokens']}")
        print(f"   Survival rate: {row['survival_rate']:.1f}%")
        print(f"   Avg current FDV: ${row['avg_current_fdv']:,.0f}")
        print(f"   Active: {str(row['first_signal'])[:10]} to {str(row['last_signal'])[:10]}")

    # Save results
    caller_stats.to_csv('results/shocked_trading_caller_stats.csv', index=False)
    print(f"\n   Results saved to results/shocked_trading_caller_stats.csv")

# =============================================================================
# 5. EXPORT SIGNALS FOR ANALYSIS
# =============================================================================
print("\n5. Exporting signals...")

if len(signals_df) > 0:
    # Add token info to signals
    signals_df['token_name'] = signals_df['address'].apply(
        lambda x: token_data.get(x, {}).get('name', 'Unknown')
    )
    signals_df['token_symbol'] = signals_df['address'].apply(
        lambda x: token_data.get(x, {}).get('symbol', 'UNK')
    )
    signals_df['current_fdv'] = signals_df['address'].apply(
        lambda x: token_data.get(x, {}).get('fdv', 0)
    )

    # Save signals
    os.makedirs('results', exist_ok=True)
    signals_df.to_csv('results/shocked_trading_signals.csv', index=False)
    print(f"   Saved {len(signals_df)} signals to results/shocked_trading_signals.csv")

print("\n" + "="*70)
print("BACKTEST COMPLETE")
print("="*70)

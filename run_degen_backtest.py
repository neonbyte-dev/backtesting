"""
Pastel Degen Channel Backtest - Segmented by Caller
Only picks up contract addresses, ignores all other messages
"""
import clickhouse_connect
import pandas as pd
import numpy as np
import re
import requests
import time
import os
from datetime import datetime

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
print("PASTEL DEGEN CHANNEL BACKTEST - BY CALLER")
print("="*70)

# =============================================================================
# 1. FETCH ALL MESSAGES FROM DEGEN CHANNEL
# =============================================================================
print("\n1. Fetching messages from Pastel degen channel...")

query = """
SELECT
    user_name,
    raw,
    created_at
FROM messages
WHERE chat_name = 'Pastel'
  AND sub_chat_name = '❗｜degen'
  AND raw != ''
ORDER BY created_at ASC
"""
result = client.query(query)
messages = pd.DataFrame(result.result_rows, columns=['caller', 'content', 'timestamp'])
print(f"   Total messages: {len(messages)}")

# Show callers
print("\n   Messages by caller:")
for caller, count in messages['caller'].value_counts().items():
    print(f"      - {caller}: {count}")

# =============================================================================
# 2. EXTRACT CONTRACT ADDRESSES ONLY
# =============================================================================
print("\n2. Extracting contract addresses...")

# Solana address pattern (base58, 32-44 chars, often ends with 'pump')
solana_patterns = [
    r'([1-9A-HJ-NP-Za-km-z]{32,44}pump)',  # pump.fun tokens
    r'([1-9A-HJ-NP-Za-km-z]{40,44})',      # standard solana addresses
]

def extract_addresses(content):
    """Extract all Solana contract addresses from message"""
    addresses = []
    for pattern in solana_patterns:
        matches = re.findall(pattern, content)
        addresses.extend(matches)
    # Dedupe and filter
    addresses = list(set(addresses))
    # Filter out likely transaction hashes (too long) and invalid addresses
    addresses = [a for a in addresses if 32 <= len(a) <= 50]
    return addresses

# Extract addresses from each message
signals = []
for _, row in messages.iterrows():
    addresses = extract_addresses(row['content'])
    for addr in addresses:
        signals.append({
            'caller': row['caller'],
            'timestamp': row['timestamp'],
            'address': addr,
            'content': row['content'][:200]
        })

signals_df = pd.DataFrame(signals)
print(f"   Found {len(signals_df)} contract address signals")

if len(signals_df) > 0:
    print("\n   Signals by caller:")
    caller_counts = signals_df['caller'].value_counts()
    for caller, count in caller_counts.items():
        print(f"      - {caller}: {count} calls")

    # Get unique addresses per caller
    print("\n   Unique tokens by caller:")
    for caller in signals_df['caller'].unique():
        unique = signals_df[signals_df['caller'] == caller]['address'].nunique()
        print(f"      - {caller}: {unique} unique tokens")

# =============================================================================
# 3. FETCH TOKEN DATA FROM DEXSCREENER
# =============================================================================
print("\n3. Fetching current token data from DexScreener...")

def get_token_info(address):
    """Get token info from DexScreener"""
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('pairs') and len(data['pairs']) > 0:
                pair = data['pairs'][0]
                return {
                    'name': pair.get('baseToken', {}).get('name', 'Unknown'),
                    'symbol': pair.get('baseToken', {}).get('symbol', 'UNK'),
                    'price_usd': float(pair.get('priceUsd', 0) or 0),
                    'fdv': float(pair.get('fdv', 0) or 0),
                    'market_cap': float(pair.get('marketCap', 0) or 0),
                    'liquidity': float(pair.get('liquidity', {}).get('usd', 0) or 0),
                    'volume_24h': float(pair.get('volume', {}).get('h24', 0) or 0),
                    'price_change_24h': float(pair.get('priceChange', {}).get('h24', 0) or 0),
                    'created_at': pair.get('pairCreatedAt'),
                    'chain': pair.get('chainId', 'unknown'),
                }
        return None
    except Exception as e:
        return None

# Get unique addresses
if len(signals_df) > 0:
    unique_addresses = signals_df['address'].unique()
    print(f"   Fetching data for {len(unique_addresses)} unique tokens...")

    token_data = {}
    for i, addr in enumerate(unique_addresses):
        if i >= 100:  # Limit API calls
            print(f"   (Limited to first 100 tokens due to API rate limits)")
            break

        info = get_token_info(addr)
        if info:
            token_data[addr] = info
            status = "ALIVE" if info['liquidity'] > 1000 else "DEAD"
            print(f"   [{i+1}/{min(100, len(unique_addresses))}] {info['symbol']}: ${info['price_usd']:.8f} | FDV: ${info['fdv']:,.0f} | {status}")
        else:
            token_data[addr] = {'status': 'NOT_FOUND', 'symbol': 'UNKNOWN'}

        time.sleep(0.3)  # Rate limit

    print(f"\n   Successfully fetched data for {sum(1 for v in token_data.values() if v.get('fdv', 0) > 0)} tokens")

# =============================================================================
# 4. CALCULATE CALLER PERFORMANCE
# =============================================================================
print("\n4. Calculating performance by caller...")

def calculate_caller_performance(signals_df, token_data):
    """Calculate performance metrics per caller"""
    results = []

    for caller in signals_df['caller'].unique():
        caller_signals = signals_df[signals_df['caller'] == caller]
        unique_tokens = caller_signals['address'].unique()

        total_calls = len(unique_tokens)
        tokens_alive = 0
        tokens_dead = 0
        tokens_not_found = 0

        alive_fdvs = []
        alive_tokens = []

        for addr in unique_tokens:
            info = token_data.get(addr, {})
            if info.get('status') == 'NOT_FOUND':
                tokens_not_found += 1
            elif info.get('liquidity', 0) > 1000 and info.get('fdv', 0) > 10000:
                tokens_alive += 1
                alive_fdvs.append(info['fdv'])
                alive_tokens.append({
                    'symbol': info['symbol'],
                    'fdv': info['fdv'],
                    'address': addr
                })
            else:
                tokens_dead += 1

        survival_rate = tokens_alive / (tokens_alive + tokens_dead) * 100 if (tokens_alive + tokens_dead) > 0 else 0
        avg_fdv = np.mean(alive_fdvs) if alive_fdvs else 0
        max_fdv = max(alive_fdvs) if alive_fdvs else 0

        # Get date range
        first_call = caller_signals['timestamp'].min()
        last_call = caller_signals['timestamp'].max()

        results.append({
            'caller': caller,
            'total_calls': total_calls,
            'tokens_alive': tokens_alive,
            'tokens_dead': tokens_dead,
            'tokens_not_found': tokens_not_found,
            'survival_rate': survival_rate,
            'avg_alive_fdv': avg_fdv,
            'max_fdv': max_fdv,
            'first_call': first_call,
            'last_call': last_call,
            'top_tokens': sorted(alive_tokens, key=lambda x: x['fdv'], reverse=True)[:5]
        })

    return pd.DataFrame(results)

if len(signals_df) > 0 and len(token_data) > 0:
    caller_performance = calculate_caller_performance(signals_df, token_data)

    print("\n" + "="*70)
    print("RESULTS BY CALLER")
    print("="*70)

    # Sort by survival rate
    caller_performance = caller_performance.sort_values('survival_rate', ascending=False)

    for _, row in caller_performance.iterrows():
        print(f"\n{'='*50}")
        print(f"CALLER: {row['caller']}")
        print("="*50)
        print(f"   Total unique calls: {row['total_calls']}")
        print(f"   Tokens still alive: {row['tokens_alive']}")
        print(f"   Tokens dead/rugged: {row['tokens_dead']}")
        print(f"   Tokens not found:   {row['tokens_not_found']}")
        print(f"   SURVIVAL RATE:      {row['survival_rate']:.1f}%")
        print(f"   Avg FDV (alive):    ${row['avg_alive_fdv']:,.0f}")
        print(f"   Max FDV:            ${row['max_fdv']:,.0f}")
        print(f"   Active period:      {str(row['first_call'])[:10]} to {str(row['last_call'])[:10]}")

        if row['top_tokens']:
            print(f"\n   Top surviving tokens:")
            for token in row['top_tokens']:
                print(f"      - {token['symbol']}: ${token['fdv']:,.0f}")

    # Save results
    os.makedirs('results', exist_ok=True)
    caller_performance.drop('top_tokens', axis=1).to_csv('results/degen_caller_performance.csv', index=False)
    print(f"\n   Results saved to results/degen_caller_performance.csv")

    # Save all signals with token info
    signals_df['token_symbol'] = signals_df['address'].apply(
        lambda x: token_data.get(x, {}).get('symbol', 'UNKNOWN')
    )
    signals_df['current_fdv'] = signals_df['address'].apply(
        lambda x: token_data.get(x, {}).get('fdv', 0)
    )
    signals_df['liquidity'] = signals_df['address'].apply(
        lambda x: token_data.get(x, {}).get('liquidity', 0)
    )
    signals_df['status'] = signals_df.apply(
        lambda x: 'ALIVE' if x['liquidity'] > 1000 and x['current_fdv'] > 10000 else 'DEAD',
        axis=1
    )

    signals_df.to_csv('results/degen_all_signals.csv', index=False)
    print(f"   All signals saved to results/degen_all_signals.csv")

print("\n" + "="*70)
print("BACKTEST COMPLETE")
print("="*70)

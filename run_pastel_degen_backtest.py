"""
Pastel Degen Channel Backtest - Segmented by Caller
Strategy: Buy at Rick bot's FDV, exit at 3x or hold to 0
"""
import clickhouse_connect
import pandas as pd
import numpy as np
import re
import requests
import time
import os
from datetime import datetime, timedelta

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
print("PASTEL DEGEN BACKTEST - BY CALLER")
print("Strategy: Buy at Rick bot FDV → Exit at 3x or 0")
print("="*70)

# =============================================================================
# 1. FETCH ALL MESSAGES
# =============================================================================
print("\n1. Fetching messages from Pastel degen channel...")

query = """
SELECT
    user_name,
    raw,
    created_at,
    message_id
FROM messages
WHERE chat_name = 'Pastel'
  AND sub_chat_name = '❗｜degen'
  AND raw != ''
ORDER BY created_at ASC
"""
result = client.query(query)
messages = pd.DataFrame(result.result_rows, columns=['caller', 'content', 'timestamp', 'message_id'])
print(f"   Total messages: {len(messages)}")

# =============================================================================
# 2. PARSE RICK BOT MESSAGES AND ATTRIBUTE TO CALLERS
# =============================================================================
print("\n2. Parsing Rick bot alerts and attributing to callers...")

def parse_rick_message(content):
    """Extract token info from Rick bot message"""
    info = {}

    # Token name and ticker - e.g., "Farmer Ben [976.3K/30.9K%] - BEN/WETH"
    name_match = re.search(r'^([^\[]+)\s*\[', content)
    ticker_match = re.search(r'-\s*(\w+)/(?:SOL|WETH|ETH|SUI)', content)

    if name_match:
        info['name'] = name_match.group(1).strip()
    if ticker_match:
        info['ticker'] = ticker_match.group(1)

    # FDV (market cap) - e.g., "FDV: $976.3K" or "FDV: 976.3K"
    fdv_match = re.search(r'FDV:\s*\$?([\d.]+)([KMB])?', content)
    if fdv_match:
        fdv_val = float(fdv_match.group(1))
        multiplier = {'K': 1000, 'M': 1000000, 'B': 1000000000}.get(fdv_match.group(2), 1)
        info['entry_fdv'] = fdv_val * multiplier

    # Contract address - Solana or ETH
    addr_match = re.search(r'([1-9A-HJ-NP-Za-km-z]{32,44}(?:pump)?)', content)
    eth_match = re.search(r'(0x[a-fA-F0-9]{40})', content)

    if addr_match:
        info['address'] = addr_match.group(1)
        info['chain'] = 'solana'
    elif eth_match:
        info['address'] = eth_match.group(1)
        info['chain'] = 'ethereum'

    # ATH if available - e.g., "ATH: $4.7M"
    ath_match = re.search(r'ATH:\s*\$?([\d.]+)([KMB])?', content)
    if ath_match:
        ath_val = float(ath_match.group(1))
        multiplier = {'K': 1000, 'M': 1000000, 'B': 1000000000}.get(ath_match.group(2), 1)
        info['ath'] = ath_val * multiplier

    return info

def find_caller_for_rick_message(rick_time, messages_df):
    """Find the caller who posted just before Rick bot"""
    # Look for messages in the 5 seconds before Rick's message
    time_window = timedelta(seconds=5)
    before_msgs = messages_df[
        (messages_df['timestamp'] < rick_time) &
        (messages_df['timestamp'] > rick_time - time_window) &
        (~messages_df['caller'].str.contains('Rick|bot', case=False, na=False))
    ]

    if len(before_msgs) > 0:
        # Get the most recent caller
        caller_msg = before_msgs.iloc[-1]
        return caller_msg['caller'], caller_msg['content']
    return None, None

# Parse all Rick bot messages
rick_messages = messages[messages['caller'].str.contains('Rick', case=False, na=False)]
print(f"   Rick bot messages: {len(rick_messages)}")

calls = []
for _, rick_row in rick_messages.iterrows():
    rick_info = parse_rick_message(rick_row['content'])

    if not rick_info.get('address') or not rick_info.get('entry_fdv'):
        continue

    caller, caller_content = find_caller_for_rick_message(rick_row['timestamp'], messages)

    if caller:
        calls.append({
            'caller': caller,
            'caller_content': caller_content[:100] if caller_content else '',
            'timestamp': rick_row['timestamp'],
            'token_name': rick_info.get('name', 'Unknown'),
            'ticker': rick_info.get('ticker', 'UNK'),
            'address': rick_info['address'],
            'chain': rick_info.get('chain', 'unknown'),
            'entry_fdv': rick_info['entry_fdv'],
            'ath_at_call': rick_info.get('ath', rick_info['entry_fdv']),
        })

calls_df = pd.DataFrame(calls)
print(f"   Attributed calls: {len(calls_df)}")

# Normalize caller names
def normalize_caller(name):
    """Consolidate different username variations"""
    name_lower = name.lower()
    if 'cooker' in name_lower:
        return 'Cooker'
    elif 'pharoh' in name_lower or 'pharo' in name_lower:
        return 'Pharoh'
    elif 'potter' in name_lower:
        return 'Potter'
    elif 'wheat' in name_lower:
        return 'wheat'
    elif 'melon' in name_lower:
        return 'melon'
    elif 'ton the neko' in name_lower:
        return 'ton the neko'
    elif 'atomic' in name_lower:
        return 'atomic'
    elif 'beep' in name_lower:
        return 'beep'
    elif 'grimm' in name_lower:
        return 'Grimm'
    elif 'chary' in name_lower:
        return 'Chary1'
    elif 'shawns' in name_lower:
        return 'shawns'
    elif 'wolfsrain' in name_lower:
        return 'WolfsRain'
    elif 'alter' in name_lower:
        return 'Altersaber'
    else:
        return name

calls_df['caller_normalized'] = calls_df['caller'].apply(normalize_caller)

print(f"\n   Calls by caller:")
for caller, count in calls_df['caller_normalized'].value_counts().head(15).items():
    print(f"      - {caller}: {count}")

# =============================================================================
# 3. GET CURRENT TOKEN DATA (for performance calculation)
# =============================================================================
print("\n3. Fetching current token data...")

def get_token_info(address, chain='solana'):
    """Get current token info from DexScreener"""
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('pairs') and len(data['pairs']) > 0:
                pair = data['pairs'][0]
                return {
                    'current_fdv': float(pair.get('fdv', 0) or 0),
                    'current_price': float(pair.get('priceUsd', 0) or 0),
                    'liquidity': float(pair.get('liquidity', {}).get('usd', 0) or 0),
                    'volume_24h': float(pair.get('volume', {}).get('h24', 0) or 0),
                }
        return {'current_fdv': 0, 'current_price': 0, 'liquidity': 0, 'volume_24h': 0}
    except:
        return {'current_fdv': 0, 'current_price': 0, 'liquidity': 0, 'volume_24h': 0}

# Get unique addresses
unique_addresses = calls_df['address'].unique()
print(f"   Fetching data for {len(unique_addresses)} unique tokens...")

token_current_data = {}
for i, addr in enumerate(unique_addresses):
    if i >= 200:  # Limit API calls
        print(f"   (Limited to 200 tokens)")
        break

    info = get_token_info(addr)
    token_current_data[addr] = info

    if i % 20 == 0:
        print(f"   Progress: {i}/{min(200, len(unique_addresses))}")
    time.sleep(0.25)

# Add current data to calls
calls_df['current_fdv'] = calls_df['address'].apply(lambda x: token_current_data.get(x, {}).get('current_fdv', 0))
calls_df['liquidity'] = calls_df['address'].apply(lambda x: token_current_data.get(x, {}).get('liquidity', 0))

# =============================================================================
# 4. CALCULATE PERFORMANCE - 3x TP or 0 Strategy
# =============================================================================
print("\n4. Calculating performance (3x TP or 0 strategy)...")

def calculate_trade_result(row):
    """
    Strategy: Buy at entry_fdv, exit at 3x or hold to 0
    If current FDV >= 3x entry → WIN (3x return = +200%)
    If current FDV > 0 but < 3x → HOLDING (use current multiple)
    If current FDV ~= 0 or no liquidity → LOSS (-100%)
    """
    entry_fdv = row['entry_fdv']
    current_fdv = row['current_fdv']
    liquidity = row['liquidity']
    ath = row.get('ath_at_call', entry_fdv)

    # Check if token is dead (no liquidity or extremely low FDV)
    if liquidity < 100 or current_fdv < 1000:
        return {
            'result': 'RUGGED',
            'return_pct': -100,
            'exit_multiple': 0,
            'hit_3x': False,
            'max_multiple': ath / entry_fdv if entry_fdv > 0 else 0
        }

    current_multiple = current_fdv / entry_fdv if entry_fdv > 0 else 0
    max_multiple = max(ath / entry_fdv, current_multiple) if entry_fdv > 0 else 0

    # Check if it ever hit 3x (use ATH as proxy)
    if max_multiple >= 3:
        return {
            'result': 'HIT_3X',
            'return_pct': 200,  # 3x = +200%
            'exit_multiple': 3,
            'hit_3x': True,
            'max_multiple': max_multiple
        }
    else:
        # Still holding, use current multiple
        return {
            'result': 'HOLDING',
            'return_pct': (current_multiple - 1) * 100,
            'exit_multiple': current_multiple,
            'hit_3x': False,
            'max_multiple': max_multiple
        }

# Apply strategy
results = calls_df.apply(calculate_trade_result, axis=1, result_type='expand')
calls_df = pd.concat([calls_df, results], axis=1)

# =============================================================================
# 5. AGGREGATE BY CALLER
# =============================================================================
print("\n5. Aggregating results by caller...")

def calc_caller_stats(group):
    total_calls = len(group)
    hit_3x = (group['result'] == 'HIT_3X').sum()
    rugged = (group['result'] == 'RUGGED').sum()
    holding = (group['result'] == 'HOLDING').sum()

    # Win rate (hit 3x)
    win_rate = hit_3x / total_calls * 100 if total_calls > 0 else 0

    # Expected value per trade (assuming equal sizing)
    # +200% for 3x wins, -100% for rugs, current return for holding
    total_return = group['return_pct'].sum()
    avg_return = total_return / total_calls if total_calls > 0 else 0

    # Best performer
    best_idx = group['max_multiple'].idxmax() if len(group) > 0 else None
    best_token = group.loc[best_idx, 'ticker'] if best_idx else 'N/A'
    best_multiple = group['max_multiple'].max() if len(group) > 0 else 0

    return pd.Series({
        'total_calls': total_calls,
        'hit_3x': hit_3x,
        'rugged': rugged,
        'holding': holding,
        'win_rate': win_rate,
        'avg_return_pct': avg_return,
        'total_return_pct': total_return,
        'best_token': best_token,
        'best_multiple': best_multiple,
        'first_call': group['timestamp'].min(),
        'last_call': group['timestamp'].max(),
    })

caller_stats = calls_df.groupby('caller_normalized').apply(calc_caller_stats).reset_index()
caller_stats = caller_stats.sort_values('total_calls', ascending=False)

# =============================================================================
# 6. PRINT RESULTS
# =============================================================================
print("\n" + "="*70)
print("RESULTS BY CALLER (3x TP or 0 Strategy)")
print("="*70)

print("\n" + "-"*70)
print(f"{'Caller':<20} {'Calls':>6} {'3x Wins':>8} {'Rugged':>8} {'Win%':>7} {'Avg Ret':>10} {'Best':>8}")
print("-"*70)

for _, row in caller_stats.iterrows():
    if row['total_calls'] >= 3:  # Only show callers with 3+ calls
        print(f"{row['caller_normalized']:<20} {row['total_calls']:>6} {row['hit_3x']:>8} {row['rugged']:>8} {row['win_rate']:>6.1f}% {row['avg_return_pct']:>9.1f}% {row['best_multiple']:>7.1f}x")

print("-"*70)

# Overall stats
print(f"\n{'TOTAL':<20} {caller_stats['total_calls'].sum():>6} {caller_stats['hit_3x'].sum():>8} {caller_stats['rugged'].sum():>8}")

# Top performers
print("\n" + "="*70)
print("TOP CALLERS BY WIN RATE (min 5 calls)")
print("="*70)

qualified = caller_stats[caller_stats['total_calls'] >= 5].sort_values('win_rate', ascending=False)
for _, row in qualified.head(10).iterrows():
    print(f"\n{row['caller_normalized']}:")
    print(f"   Calls: {row['total_calls']} | 3x Wins: {row['hit_3x']} | Rugged: {row['rugged']}")
    print(f"   Win Rate: {row['win_rate']:.1f}% | Avg Return: {row['avg_return_pct']:.1f}%")
    print(f"   Best Token: {row['best_token']} ({row['best_multiple']:.1f}x)")
    print(f"   Active: {str(row['first_call'])[:10]} to {str(row['last_call'])[:10]}")

# =============================================================================
# 7. SAVE RESULTS
# =============================================================================
print("\n7. Saving results...")

os.makedirs('results', exist_ok=True)
caller_stats.to_csv('results/pastel_degen_caller_stats.csv', index=False)
calls_df.to_csv('results/pastel_degen_all_calls.csv', index=False)

print(f"   Saved caller stats to results/pastel_degen_caller_stats.csv")
print(f"   Saved all calls to results/pastel_degen_all_calls.csv")

print("\n" + "="*70)
print("BACKTEST COMPLETE")
print("="*70)

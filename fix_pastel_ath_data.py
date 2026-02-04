"""
Fix Pastel Degen ATH data using CoinGecko for large-cap tokens
"""
import pandas as pd
import requests
import time
import re

print("="*70)
print("FIXING ATH DATA FOR LARGE-CAP TOKENS")
print("="*70)

# Load current data
df = pd.read_csv("/Users/chrisl/Claude Code/trader strategy bot /results/pastel_degen_all_calls.csv")
print(f"\nLoaded {len(df)} calls")

# Find large-cap tokens that need fixing (>$10M entry, marked as RUGGED or low multiple)
needs_fixing = df[
    (df['entry_fdv'] > 10_000_000) &
    ((df['result'] == 'RUGGED') | (df['max_multiple'] < 2))
].copy()
print(f"Tokens needing ATH lookup: {len(needs_fixing)}")

# Manual corrections for known tokens (verified data)
# These are tokens we KNOW the ATH for, to avoid API calls
MANUAL_ATH = {
    '6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN': {  # TRUMP
        'name': 'TRUMP',
        'ath_fdv': 73_430_000_000,  # $73.43B (from CoinGecko)
        'current_fdv': 4_200_000_000,
        'coingecko_id': 'official-trump'
    },
    # MELANIA - need to find the contract address
}

# CoinGecko ID mappings for tokens we can look up
# Format: contract_address -> coingecko_id
COINGECKO_IDS = {
    '6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN': 'official-trump',
    # Add more as needed
}

def search_coingecko(token_name):
    """Search CoinGecko for a token by name"""
    try:
        # Clean up token name for search
        search_name = re.sub(r'[^\w\s]', '', token_name).strip()
        url = f"https://api.coingecko.com/api/v3/search?query={search_name}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            coins = data.get('coins', [])
            if coins:
                return coins[0].get('id')
    except Exception as e:
        print(f"  Search error: {e}")
    return None

def get_coingecko_ath(coin_id):
    """Get ATH data from CoinGecko"""
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            md = data.get('market_data', {})
            ath = md.get('ath', {}).get('usd')
            supply = md.get('total_supply') or md.get('circulating_supply')
            current_price = md.get('current_price', {}).get('usd')

            if ath and supply:
                return {
                    'ath_price': ath,
                    'supply': supply,
                    'ath_fdv': ath * supply,
                    'current_price': current_price,
                    'current_fdv': current_price * supply if current_price else None
                }
        elif resp.status_code == 429:
            print("  Rate limited, waiting 60s...")
            time.sleep(60)
            return get_coingecko_ath(coin_id)  # Retry
    except Exception as e:
        print(f"  API error: {e}")
    return None

# Process each large-cap token
print("\n" + "-"*70)
print("Processing large-cap tokens...")
print("-"*70)

corrections = []
processed = set()

for idx, row in needs_fixing.iterrows():
    addr = row['address']
    name = row['token_name']
    entry_fdv = row['entry_fdv']

    # Skip if already processed (same address)
    if addr in processed:
        continue
    processed.add(addr)

    print(f"\n{name} (${entry_fdv/1e6:.1f}M entry)")

    # Check manual corrections first
    if addr in MANUAL_ATH:
        manual = MANUAL_ATH[addr]
        ath_fdv = manual['ath_fdv']
        max_mult = ath_fdv / entry_fdv
        print(f"  ✓ Manual correction: ATH ${ath_fdv/1e9:.2f}B = {max_mult:.1f}x")
        corrections.append({
            'address': addr,
            'token_name': name,
            'ath_fdv': ath_fdv,
            'max_multiple': max_mult,
            'source': 'manual'
        })
        continue

    # Try CoinGecko lookup
    if addr in COINGECKO_IDS:
        coin_id = COINGECKO_IDS[addr]
    else:
        # Search by name
        print(f"  Searching CoinGecko for '{name}'...")
        coin_id = search_coingecko(name)
        time.sleep(1.5)  # Rate limit

    if coin_id:
        print(f"  Found CoinGecko ID: {coin_id}")
        ath_data = get_coingecko_ath(coin_id)
        time.sleep(1.5)  # Rate limit

        if ath_data:
            ath_fdv = ath_data['ath_fdv']
            max_mult = ath_fdv / entry_fdv
            print(f"  ✓ ATH FDV: ${ath_fdv/1e9:.2f}B = {max_mult:.1f}x")
            corrections.append({
                'address': addr,
                'token_name': name,
                'ath_fdv': ath_fdv,
                'current_fdv': ath_data.get('current_fdv'),
                'max_multiple': max_mult,
                'source': 'coingecko'
            })
        else:
            print(f"  ✗ Could not get ATH data")
    else:
        print(f"  ✗ Not found on CoinGecko")

# Apply corrections
print("\n" + "="*70)
print("APPLYING CORRECTIONS")
print("="*70)

corrections_df = pd.DataFrame(corrections)
print(f"\nTotal corrections: {len(corrections_df)}")

if len(corrections_df) > 0:
    print("\nCorrections to apply:")
    for _, corr in corrections_df.iterrows():
        print(f"  {corr['token_name']}: {corr['max_multiple']:.1f}x (was ~1x)")

    # Update main dataframe
    for _, corr in corrections_df.iterrows():
        mask = df['address'] == corr['address']
        df.loc[mask, 'max_multiple'] = corr['max_multiple']
        df.loc[mask, 'ath_fdv_corrected'] = corr['ath_fdv']
        if corr.get('current_fdv'):
            df.loc[mask, 'current_fdv'] = corr['current_fdv']

        # Update result based on new max multiple
        if corr['max_multiple'] >= 3:
            df.loc[mask, 'result'] = 'WIN (3x)'
            df.loc[mask, 'hit_3x'] = True
            df.loc[mask, 'return_pct'] = 200  # 3x = 200% gain
        elif corr['max_multiple'] >= 1:
            # Still alive but didn't hit 3x
            if corr.get('current_fdv') and corr['current_fdv'] > 0:
                entry = df.loc[mask, 'entry_fdv'].values[0]
                df.loc[mask, 'result'] = 'HOLDING'
                df.loc[mask, 'return_pct'] = ((corr['current_fdv'] / entry) - 1) * 100

# Save corrected data
df.to_csv("/Users/chrisl/Claude Code/trader strategy bot /results/pastel_degen_all_calls_corrected.csv", index=False)
print(f"\n✓ Saved corrected data to results/pastel_degen_all_calls_corrected.csv")

# Summary
print("\n" + "="*70)
print("SUMMARY OF CORRECTIONS")
print("="*70)

if len(corrections_df) > 0:
    print(f"\nTokens corrected: {len(corrections_df)}")
    print(f"\nTop corrected multiples:")
    for _, corr in corrections_df.nlargest(10, 'max_multiple').iterrows():
        print(f"  {corr['token_name']}: {corr['max_multiple']:.1f}x")

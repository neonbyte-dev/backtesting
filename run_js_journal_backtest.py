"""
JS Personal Journal Full Backtest (v3 - ATH Report)
=====================================================
Reports the ATH multiple for every token call JS made.

For each trade:
  Entry MC = Rick [bot] FDV at time of call, OR JS's stated entry
  ATH MC   = Rick [bot] ATH field, OR JS's mentioned peak, OR DexScreener ATH
  Multiple = ATH MC / Entry MC

Data: Clickhouse (crush_ats.messages) + Rick [bot] structured lookups + DexScreener
"""

import clickhouse_connect
import pandas as pd
import re
import requests
import time
import os

# =============================================================================
# CONFIG
# =============================================================================
CLICKHOUSE_HOST = 'ch.ops.xexlab.com'
CLICKHOUSE_PORT = 443
CLICKHOUSE_USER = 'dev_ado'
CLICKHOUSE_PASS = '5tTq7p6HBvCH5m4E'
CLICKHOUSE_DB = 'crush_ats'

DEXSCREENER_TOKEN_URL = 'https://api.dexscreener.com/latest/dex/tokens'
RATE_LIMIT = 0.4

RESULTS_DIR = 'results'
os.makedirs(RESULTS_DIR, exist_ok=True)


def parse_mc(mc_str):
    """Parse '8.3M', '572K', '29.7M', '1.2B' → float"""
    if not mc_str:
        return 0
    s = str(mc_str).replace('$', '').replace(',', '').strip()
    try:
        if s.upper().endswith('B'): return float(s[:-1]) * 1e9
        if s.upper().endswith('M'): return float(s[:-1]) * 1e6
        if s.upper().endswith('K'): return float(s[:-1]) * 1e3
        return float(s)
    except ValueError:
        return 0


# =============================================================================
# CURATED TRADE LIST (v3 — 38 trades)
# =============================================================================
# Every distinct buy signal from JS in the Shocked Trading JS Personal Journal.
# Compiled from manual reading of all 1,090 messages.
#
# entry_mc: market cap at JS's entry (from Rick bot FDV or JS stated)
# ath_mc:   all-time high MC after entry (from Rick ATH, JS messages, or known)
# ath_source: where the ATH data comes from

TRADES = [
    # --- Mar 2025: OG meme buys ---
    dict(date='2025-03-11', token='SPX6900', ticker='SPX', chain='ethereum', address=None,
         entry_mc=1_170_000_000, ath_mc=2_100_000_000, ath_source='CoinMarketCap: ATH $2.27 / ~$2.1B MC (Jul 28, 2025)',
         note="I've bought some SPX here (~$1.17B MC est.)", exited=False),
    dict(date='2025-03-11', token='Pepe', ticker='PEPE', chain='ethereum', address=None,
         entry_mc=None, ath_mc=None, ath_source='ATH $11B was Dec 2024 (before entry). Post-entry ATH unknown.',
         note="may grab some PEPE and MOG too", exited=False),
    dict(date='2025-03-11', token='Mog Coin', ticker='MOG', chain='ethereum', address=None,
         entry_mc=None, ath_mc=None, ath_source='ATH $1.5B was Dec 2024 (before entry). Post-entry ATH unknown.',
         note="may grab some PEPE and MOG too", exited=False),

    # --- Apr 2025 ---
    dict(date='2025-04-10', token='TITCOIN', ticker='TITCOIN', chain='solana', address=None,
         entry_mc=25_000_000, ath_mc=89_000_000, ath_source='CoinMarketCap/CoinGecko: ATH ~$89M',
         note="sized into TITCOIN at 20-30M", exited=False),
    dict(date='2025-04-14', token='Fartcoin', ticker='FARTCOIN', chain='solana', address=None,
         entry_mc=None, ath_mc=None, ath_source='',
         note="Re-entered FARTCOIN, think it's ready for 1B+", exited=True),

    # --- May 2025 ---
    dict(date='2025-05-02', token='Boop', ticker='BOOP', chain='solana', address=None,
         entry_mc=282_000_000, ath_mc=460_000_000, ath_source='CoinMarketCap: ATH ~$0.49 / ~$460M MC (May 2, 2025). Entry ~$0.30',
         note="bought some BOOP @ .3~", exited=True),
    dict(date='2025-05-09', token='Fartcoin (re-enter)', ticker='FARTCOIN2', chain='solana', address=None,
         entry_mc=1_200_000_000, ath_mc=1_200_000_000, ath_source='Overall ATH $2.5B was Jan 2025. Post-entry never reclaimed $1.2B.',
         note="large spot position in FARTCOIN @ 1.2B, target 2B+ and new ATHs", exited=True),

    # --- Jun 2025 ---
    dict(date='2025-06-17', token='Cupsey', ticker='CUPSEY', chain='solana',
         address='5PsnNwPmMtsGZgG6ZqMoDJJi28BR5xpAotXHHiQhpump',
         entry_mc=4_900_000, ath_mc=20_500_000, ath_source='Rick bot (ATH $20.5M)',
         note="$CUPSEY is a great front run", exited=True),
    dict(date='2025-06-28', token='GET RICH QUICK', ticker='RICH', chain='solana',
         address='5oUzkFsCFMJJ23Z6Ghev5m7FjE6TtrqZJXUS7V5Smoon',
         entry_mc=4_500_000, ath_mc=15_000_000, ath_source='JS said "15M ATH" on Jun 30',
         note="$RICH is a very free bid on any dips", exited=False),
    dict(date='2025-06-29', token='Startup', ticker='STARTUP', chain='solana',
         address='97PVGU2DzFqsAWaYU17ZBqGvQFmkqtdMywYBNPAfy8vy',
         entry_mc=None, ath_mc=49_600_000, ath_source='Rick bot ATH $49.6M (Jul 6); JS: "tapping ATHs @ 43M"',
         note="$STARTUP is the next liquid 10-20x+", exited=False),

    # --- Sep 2025 ---
    dict(date='2025-09-02', token='Collector Crypt CARDS', ticker='CARDS', chain='solana',
         address='CARDSccUMFKoPRZxt5vt3ksUbxEFEcnZ3H2pd3dKxYjp',
         entry_mc=115_000_000, ath_mc=350_000_000, ath_source='JS: "Holy shit 350M" on Sep 3',
         note="Sized some into CARDS @ 110M-120M~", exited=False),
    dict(date='2025-09-12', token='Pepe (long)', ticker='PEPE_LONG', chain='ethereum', address=None,
         entry_mc=None, ath_mc=None, ath_source='',
         note="Went long on PEPE here @ 0.010644", exited=False),
    dict(date='2025-09-14', token='Bagwork', ticker='BAGWORK', chain='solana', address=None,
         entry_mc=23_000_000, ath_mc=40_000_000, ath_source='CoinGecko: ATH ~$33-48M (Sep 2025). Using ~$40M midpoint.',
         note="sized in with about a 23M~ average", exited=False),
    dict(date='2025-09-14', token='streamdotfun', ticker='STREAM', chain='solana',
         address='2EYvskXTncMS11vejJcWHh8fPaCFy6bzDcVnmofEpump',
         entry_mc=1_500_000, ath_mc=9_000_000, ath_source='Rick bot: FDV $1.5M → $9M [4d]',
         note="bought some STREAM as an infra play", exited=False),
    dict(date='2025-09-17', token='Aster', ticker='ASTER', chain='bnb', address=None,
         entry_mc=300_000_000, ath_mc=3_500_000_000, ath_source='CoinMarketCap: ATH $2.42 / ~$3.5B MC (Sep 24, 2025). Trimmed early.',
         note="MC is 300M, FDV 1.1B. Trimmed $750K initials", exited=True),
    dict(date='2025-09-18', token='SUN', ticker='SUN', chain='tron', address=None,
         entry_mc=None, ath_mc=None, ath_source='',
         note="bought some SUN @ .026, betting on crime", exited=False),
    dict(date='2025-09-26', token='XPL', ticker='XPL', chain='unknown', address=None,
         entry_mc=None, ath_mc=None, ath_source='',
         note="liking what I'm seeing $XPL", exited=True),

    # --- Oct 2025 ---
    dict(date='2025-10-02', token='LaunchCoin', ticker='LAUNCHCOIN', chain='solana', address=None,
         entry_mc=110_000_000, ath_mc=110_000_000, ath_source='Overall ATH $350M was May 2025 (before entry). Token died/rebranded.',
         note="$500k initial with 110M~ avg", exited=True),
    dict(date='2025-10-05', token='4 (Believe eco)', ticker='4', chain='solana', address=None,
         entry_mc=150_000_000, ath_mc=None, ath_source='',
         note="rebought a large position in 4", exited=True),
    dict(date='2025-10-09', token='8', ticker='8', chain='solana',
         address='8ZEfp4PkEMoGFgphvxKJrDySfS3T73DBfxKCdAsPpump',
         entry_mc=7_000_000, ath_mc=None, ath_source='',
         note="Gambling some 8 here at 7M, aiming for 2-3x", exited=True),
    dict(date='2025-10-13', token='BNBet', ticker='BNBET', chain='bnb',
         address='0xCfafECD0b8E866A0626166667Bb652beC9D14444',
         entry_mc=4_300_000, ath_mc=6_800_000, ath_source='Rick bot: FDV $6.7M → $6.8M',
         note="I just top blasted this and it instantly 2x'd", exited=True),
    dict(date='2025-10-16', token='LAB', ticker='LAB', chain='bnb',
         address='0x7ec43Cf65F1663F820427C62A5780b8f2E25593A',
         entry_mc=152_000_000, ath_mc=218_000_000, ath_source='Rick bot: FDV $217M → ATH $218M. JS bought 30% dip → ~$152M',
         note="Started taking a position on this 30% dip", exited=True),
    dict(date='2025-10-25', token='Virtual Protocol', ticker='VIRTUAL', chain='base', address=None,
         entry_mc=None, ath_mc=None, ath_source='',
         note="longing VIRTUAL @ 1.0404 (perp)", exited=True),
    dict(date='2025-10-25', token='AIXBT', ticker='AIXBT', chain='base', address=None,
         entry_mc=None, ath_mc=None, ath_source='',
         note="Longed AIXBT at 0.069048 (perp)", exited=True),
    dict(date='2025-10-25', token='standwithcrypto', ticker='SWC', chain='base',
         address='0xf34B779C350A39E15DB4CD9754364b9f846fF088',
         entry_mc=1_250_000, ath_mc=1_600_000, ath_source='Rick bot: FDV $1.4M → ATH $1.6M (Oct 25, 2025)',
         note="aped this at 1-1.5M, GIGGLE type narrative", exited=True),
    dict(date='2025-10-26', token='Paluhaan', ticker='PALU', chain='bnb', address=None,
         entry_mc=30_000_000, ath_mc=None, ath_source='',
         note="bought semi-decent amount of PALU @ 30M", exited=False),
    dict(date='2025-10-29', token='1x_tech', ticker='1XTECH', chain='solana',
         address='8fdBKZq7wo9fJbsZEZhq6omCgvKzLt97HY9XaGgqpump',
         entry_mc=2_100_000, ath_mc=None, ath_source='',
         note="Gambled on this coin @ 2.1M avg", exited=True),

    # --- Nov 2025 ---
    dict(date='2025-11-12', token='Oobit', ticker='OOB', chain='solana',
         address='oobQ3oX6ubRYMNMahG7VSCe8Z73uaQbAWFn6f22XTgo',
         entry_mc=355_000_000, ath_mc=426_000_000, ath_source='Rick bot: FDV $355M → ATH $426M',
         note="I aped", exited=True),

    # --- Jan 2026 ---
    dict(date='2026-01-10', token='rainbowfish', ticker='FISH', chain='solana',
         address='CmgJ1PobhUqB7MEa8qDkiG2TUpMTskWj8d9JeZWSpump',
         entry_mc=6_800_000, ath_mc=13_000_000, ath_source='Rick bot: FDV $8.3M → ATH $13M',
         note="buying FISH today (avg entry 6.8M)", exited=False),
    dict(date='2026-01-16', token='GAS', ticker='GAS', chain='solana', address=None,
         entry_mc=20_000_000, ath_mc=50_000_000, ath_source='CoinGecko: ATH ~$44-60M (Jan 15, 2026). JS: "got rekt" later.',
         note="$200k twap into GAS near 20M~", exited=False),
    dict(date='2026-01-26', token='CLAWD', ticker='CLAWD', chain='solana', address=None,
         entry_mc=10_000_000, ath_mc=16_000_000, ath_source='CoinGecko: ATH ~$16M (Jan 25, 2026). Scam token, collapsed.',
         note="Bought a bunch of CLAWD from 8-12M", exited=True),
    dict(date='2026-01-26', token='ShrimpCoin', ticker='SHRIMP', chain='solana', address=None,
         entry_mc=1_500_000, ath_mc=None, ath_source='',
         note="bought a bunch of ShrimpCoin at 1.5M", exited=False),

    # --- Feb 2026 ---
    dict(date='2026-02-01', token='Flufy', ticker='FLUFY', chain='solana',
         address='43uGwcykUgmtQYrgsSDk7VkFhgN3kH9aThYeyWnBpump',
         entry_mc=1_200_000, ath_mc=1_200_000, ath_source='Rick bot: FDV $1.2M → $1.2M [1s] (just launched)',
         note="Aped this. Giga gamble, trim on the way up", exited=False),
    dict(date='2026-02-02', token='Buttcoin', ticker='BUTTCOIN', chain='solana',
         address='Cm6fNnMk7NfzStP9CZpsQA2v3jjzbcYGAxdJySmHpump',
         entry_mc=20_000_000, ath_mc=25_800_000, ath_source='Rick bot: FDV $21M → ATH $25.8M',
         note="Sized a bit of Butt Coin @ 20M", exited=False),
    dict(date='2026-02-02', token='Goyim', ticker='GOYIM', chain='solana',
         address='9S8edqWxoWz5LYLnxWUmWBJnePg35WfdYQp7HQkUpump',
         entry_mc=1_300_000, ath_mc=2_700_000, ath_source='Rick bot FDV $1.3M, ATH $1.7M; JS: "Hit 2.7M"',
         note="tried a bit, purely a gamble", exited=True),
    dict(date='2026-02-02', token='BANKR', ticker='BANKR', chain='solana', address=None,
         entry_mc=60_000_000, ath_mc=62_000_000, ath_source='Overall ATH $100M+ (Jul 2025, before entry). Post-entry ~$62M.',
         note="BANKR seems cheap here. Sized some @ 60M~", exited=True),
    dict(date='2026-02-02', token='MysticDAO', ticker='MYSTIC', chain='solana',
         address='mysticrSzUfD2pz4RayXF5oEHGfNNAFsSY3z5hTQZSN',
         entry_mc=27_500_000, ath_mc=55_800_000, ath_source='Rick bot: FDV $35.2M → ATH $55.8M. JS entry 25-30M~',
         note="Bought a bit of this at 25-30M~", exited=False),
    dict(date='2026-02-02', token='GOY', ticker='GOY', chain='solana',
         address='FYtP5AiiB4eUjVA88EeZS73PDpi7RPLusdqtXizYpump',
         entry_mc=1_400_000, ath_mc=1_600_000, ath_source='Rick bot: FDV $1.4M → ATH $1.6M',
         note="buying the original GOY", exited=False),
    dict(date='2026-02-03', token='BLM (Block Lives Matter)', ticker='BLM', chain='solana',
         address='6QBjp4h115hvHsWjisRCRKrfECGKFMdSkx1giYCjpump',
         entry_mc=6_100_000, ath_mc=7_000_000, ath_source='JS: "$55k worth at 6.1M AVG", "7M from 1M share"',
         note="Rebought a lot, really good people pushing it", exited=False),
]

# =============================================================================
# 1. CONNECT & VERIFY
# =============================================================================
print("=" * 90)
print("JS PERSONAL JOURNAL — ATH BACKTEST REPORT")
print("=" * 90)

print(f"\n[1/3] Connecting to Clickhouse...")
client = clickhouse_connect.get_client(
    host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT,
    username=CLICKHOUSE_USER, password=CLICKHOUSE_PASS,
    database=CLICKHOUSE_DB, secure=True
)
result = client.query("""
    SELECT count(*), min(created_at), max(created_at)
    FROM messages WHERE chat_name = 'Shocked Trading'
    AND sub_chat_name LIKE '%js-personal-journal%' AND raw != ''
""")
row = result.result_rows[0]
print(f"   Channel messages: {row[0]}  |  {row[1]} → {row[2]}")
print(f"   Curated trades: {len(TRADES)}")

# =============================================================================
# 2. ENRICH WITH DEXSCREENER ATH DATA (for tokens with addresses)
# =============================================================================
print(f"\n[2/3] Fetching DexScreener data for tokens with contract addresses...")


def dex_fetch(address):
    """Fetch from DexScreener token endpoint."""
    try:
        r = requests.get(f"{DEXSCREENER_TOKEN_URL}/{address}", timeout=15)
        if r.status_code == 429:
            time.sleep(5)
            r = requests.get(f"{DEXSCREENER_TOKEN_URL}/{address}", timeout=15)
        if r.status_code == 200:
            pairs = r.json().get('pairs', [])
            if pairs:
                pair = max(pairs, key=lambda p: float(p.get('liquidity', {}).get('usd', 0) or 0))
                return {
                    'name': pair.get('baseToken', {}).get('name', ''),
                    'symbol': pair.get('baseToken', {}).get('symbol', ''),
                    'fdv': float(pair.get('fdv', 0) or 0),
                    'liquidity': float(pair.get('liquidity', {}).get('usd', 0) or 0),
                }
        return None
    except:
        return None


# Only fetch for tokens that have addresses (to verify they still exist)
for i, t in enumerate(TRADES):
    if t.get('address'):
        data = dex_fetch(t['address'])
        if data:
            t['_dex_name'] = data['name']
            t['_dex_fdv'] = data['fdv']
            t['_dex_liq'] = data['liquidity']
            sym = data['symbol']
            fdv = f"${data['fdv']:>12,.0f}" if data['fdv'] else "dead"
            print(f"   {t['ticker']:15s} | {sym:10s} | Now: {fdv} | Liq: ${data['liquidity']:,.0f}")
        else:
            t['_dex_name'] = ''
            t['_dex_fdv'] = 0
            t['_dex_liq'] = 0
            print(f"   {t['ticker']:15s} | NOT FOUND")
        time.sleep(RATE_LIMIT)

# =============================================================================
# 3. REPORT
# =============================================================================
print(f"\n[3/3] Generating ATH report...\n")

print("=" * 90)
print("JS PERSONAL JOURNAL — ATH MULTIPLES REPORT")
print(f"Period: Feb 2025 → Feb 2026  |  Total Calls: {len(TRADES)}")
print("=" * 90)

# Separate calculable vs not
calculable = [t for t in TRADES if t['entry_mc'] and t['entry_mc'] > 0
              and t['ath_mc'] and t['ath_mc'] > 0]
no_entry = [t for t in TRADES if not t['entry_mc'] or t['entry_mc'] == 0]
no_ath = [t for t in TRADES if t['entry_mc'] and t['entry_mc'] > 0
          and (not t['ath_mc'] or t['ath_mc'] == 0)]

print(f"\n  Trades with BOTH entry MC & ATH MC: {len(calculable)}")
print(f"  Trades missing entry MC:            {len(no_entry)}")
print(f"  Trades with entry but no ATH:       {len(no_ath)}")

# Calculate multiples
for t in calculable:
    t['ath_multiple'] = t['ath_mc'] / t['entry_mc']

# Sort by multiple descending
calculable.sort(key=lambda t: t['ath_multiple'], reverse=True)

# Print the main table
print(f"\n  {'─'*88}")
print(f"  {'DATE':12s}{'TOKEN':18s}{'ENTRY MC':>14s}{'ATH MC':>14s}{'MULTIPLE':>10s}  ATH SOURCE")
print(f"  {'─'*88}")

for t in calculable:
    date = t['date']
    token = t['ticker'][:16]
    entry = f"${t['entry_mc']:>11,.0f}"
    ath = f"${t['ath_mc']:>11,.0f}"
    mult = f"{t['ath_multiple']:>8.2f}x"
    src = t['ath_source'][:40] if t['ath_source'] else ''
    print(f"  {date:12s}{token:18s}{entry:>14s}{ath:>14s}{mult:>10s}  {src}")

# Summary stats
if calculable:
    multiples = [t['ath_multiple'] for t in calculable]
    print(f"\n  {'─'*88}")
    print(f"\n  SUMMARY ({len(calculable)} trades with full data):")
    print(f"    Median ATH multiple:  {sorted(multiples)[len(multiples)//2]:.2f}x")
    print(f"    Mean ATH multiple:    {sum(multiples)/len(multiples):.2f}x")
    print(f"    Best:                 {max(multiples):.2f}x")
    print(f"    Worst:                {min(multiples):.2f}x")

    above_2x = [m for m in multiples if m >= 2.0]
    above_3x = [m for m in multiples if m >= 3.0]
    above_5x = [m for m in multiples if m >= 5.0]
    print(f"    ≥2x from entry:       {len(above_2x)} of {len(multiples)} ({len(above_2x)/len(multiples)*100:.0f}%)")
    print(f"    ≥3x from entry:       {len(above_3x)} of {len(multiples)} ({len(above_3x)/len(multiples)*100:.0f}%)")
    print(f"    ≥5x from entry:       {len(above_5x)} of {len(multiples)} ({len(above_5x)/len(multiples)*100:.0f}%)")

    # MC-weighted average
    total_mc = sum(t['entry_mc'] for t in calculable)
    weighted = sum(t['ath_multiple'] * t['entry_mc'] for t in calculable) / total_mc
    print(f"    MC-weighted avg:      {weighted:.2f}x (larger positions count more)")

    # Win/loss
    winners = [t for t in calculable if t['ath_multiple'] >= 1.5]
    breakeven = [t for t in calculable if 1.0 <= t['ath_multiple'] < 1.5]
    print(f"\n    ≥1.5x (clear win):    {len(winners)} trades")
    print(f"    1.0-1.5x (marginal):  {len(breakeven)} trades")

# Print trades with entry but no ATH
if no_ath:
    print(f"\n  {'─'*88}")
    print(f"  TRADES WITH ENTRY MC BUT NO ATH DATA ({len(no_ath)}):")
    print(f"  {'─'*88}")
    for t in no_ath:
        entry = f"${t['entry_mc']:>11,.0f}"
        exited = " (exited)" if t.get('exited') else ""
        print(f"  {t['date']:12s}{t['ticker']:18s}{entry:>14s}  {t['note'][:50]}{exited}")

# Print trades with no entry MC
if no_entry:
    print(f"\n  {'─'*88}")
    print(f"  TRADES WITHOUT ENTRY MC ({len(no_entry)}):")
    print(f"  {'─'*88}")
    for t in no_entry:
        print(f"  {t['date']:12s}{t['ticker']:18s}  {t['note'][:60]}")

# Export CSV
rows = []
for t in TRADES:
    rows.append({
        'signal_date': t['date'],
        'token': t['token'],
        'ticker': t['ticker'],
        'chain': t['chain'],
        'address': t.get('address', ''),
        'entry_mc': t['entry_mc'],
        'ath_mc': t['ath_mc'],
        'ath_multiple': t.get('ath_multiple', ''),
        'ath_source': t['ath_source'],
        'exited': t.get('exited', False),
        'note': t['note'],
    })

df = pd.DataFrame(rows)
path = os.path.join(RESULTS_DIR, 'js_journal_backtest.csv')
df.to_csv(path, index=False)
print(f"\n  Exported to {path}")

print("\n" + "=" * 90)
print("REPORT COMPLETE")
print("=" * 90)

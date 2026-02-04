# JS Personal Journal (Shocked Trading) — ATH Backtest Report

**Generated:** February 4, 2026
**Data Period:** February 20, 2025 → February 3, 2026 (≈12 months)
**Data Source:** Clickhouse (`crush_ats.messages`) — Shocked Trading → js-personal-journal
**Methodology:** Entry MC from JS messages + Rick bot FDV → ATH MC from Rick bot, JS messages, CoinMarketCap, CoinGecko
**Caller:** JS (all name variants consolidated: JS, JS SHCK Owner, JS SHCK, JS (LOCKED IN), JS (LOCKED IN) SHCK Owner)

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total Messages | 1,090 |
| Total Trade Calls | **39** |
| With Full Data (Entry + ATH) | 25 |
| Median ATH Multiple | **1.63x** |
| Mean ATH Multiple | **2.41x** |
| MC-Weighted Mean | **2.25x** |
| Best Trade | ASTER (11.67x) |
| ≥2x Trades | 9 of 25 (36%) |
| ≥3x Trades | 6 of 25 (24%) |
| Clear Wins (≥1.5x) | 15 of 25 (60%) |
| Flat/Loss (≤1.0x) | 3 of 25 (12%) |

**Key Takeaway:** JS's trade calls show a 60% hit rate for clear wins (≥1.5x to ATH) and 36% hit rate for doubles. The standout feature is ASTER at 11.67x, which single-handedly pulls the mean and MC-weighted averages well above the median. Without ASTER, the mean drops to 1.99x — still profitable but more moderate.

---

## ATH Multiples by Trade

![[js_ath_multiples.png]]

The chart above shows all 25 trades with calculable ATH multiples, sorted from lowest to highest. Green bars are big winners (≥3x), blue bars are clear wins (1.5-3x), amber bars are marginal wins (1.0-1.5x), and red bars are flat/losses (1.0x).

---

## Outcome Distribution & Data Coverage

![[js_outcome_breakdown.png]]

**Left panel:** Of the 25 calculable trades, 6 hit ≥3x, 3 more hit 2-3x, and 6 more hit 1.5-2x — totaling 15 clear winners out of 25. Ten trades were marginal (1-1.5x) and 3 were flat/losses (1.0x — token peaked at or before entry).

**Right panel:** Of 39 total trade calls, 25 have both entry MC and ATH MC data. Five trades have a known entry but no ATH data available. Nine trades are missing entry MC entirely (mostly established tokens like PEPE, MOG, or perps trades without clear MC references).

---

## Entry MC vs ATH MC

![[js_entry_vs_ath.png]]

This log-scale scatter plot shows entry market cap (x-axis) against ATH market cap (y-axis). Points above the diagonal 1x line represent profitable trades. The further above, the higher the multiple. ASTER stands out in the top-right with a $300M entry reaching $3.5B ATH. STREAM stands out for its distance from the 1x line — a $1.5M entry reaching $9M.

---

## Monthly Trade Frequency

![[js_monthly_frequency.png]]

JS's trading activity was not evenly distributed. Two peak months stand out:
- **September 2025** (7 trades) — the most active month, featuring ASTER, CARDS, STREAM, and BAGWORK
- **October 2025** (10 trades) — the highest volume month with many smaller bets (BNBET, LAB, SWC, 1XTECH, etc.)

No trades were recorded in July, August, or December 2025.

---

## Entry Market Cap Distribution

![[js_entry_mc_distribution.png]]

JS trades across the full market cap spectrum. The largest bucket is $5-25M (9 trades), typical of mid-cap meme/altcoin plays. But he also takes significant positions in $100-500M tokens (8 trades including CARDS, ASTER, OOB, LAB) and >$500M tokens (SPX at $1.17B, FARTCOIN at $1.2B).

This is a notably different profile from pure degen callers who mostly play sub-$5M tokens.

---

## Chain Distribution

![[js_chain_distribution.png]]

Solana dominates with 23 of 39 trades (59%). Ethereum and BNB Chain each account for a significant minority. Base chain appears in October 2025 (VIRTUAL, AIXBT, SWC perps plays). One trade on Tron (SUN).

---

## Full Trade Log — All 39 Calls

### Trades with Both Entry MC & ATH MC (25 trades)

| # | Date | Token | Chain | Entry MC | ATH MC | Multiple | ATH Source |
|---|------|-------|-------|----------|--------|----------|------------|
| 1 | Sep 17, 2025 | **ASTER** | BNB | $300M | $3.5B | **11.67x** | CoinMarketCap: ATH Sep 24, 2025. Trimmed early. |
| 2 | Sep 14, 2025 | **STREAM** | Solana | $1.5M | $9M | **6.00x** | Rick bot: FDV $1.5M → $9M [4d] |
| 3 | Jun 17, 2025 | **CUPSEY** | Solana | $4.9M | $20.5M | **4.18x** | Rick bot ATH $20.5M |
| 4 | Apr 10, 2025 | **TITCOIN** | Solana | $25M | $89M | **3.56x** | CoinMarketCap/CoinGecko: ATH ~$89M |
| 5 | Jun 28, 2025 | **RICH** | Solana | $4.5M | $15M | **3.33x** | JS said "15M ATH" on Jun 30 |
| 6 | Sep 2, 2025 | **CARDS** | Solana | $115M | $350M | **3.04x** | JS: "Holy shit 350M" on Sep 3 |
| 7 | Jan 16, 2026 | **GAS** | Solana | $20M | $50M | **2.50x** | CoinGecko: ATH ~$44-60M (Jan 15, 2026). JS: "got rekt" later. |
| 8 | Feb 2, 2026 | **GOYIM** | Solana | $1.3M | $2.7M | **2.08x** | Rick bot FDV $1.3M; JS: "Hit 2.7M" |
| 9 | Feb 2, 2026 | **MYSTIC** | Solana | $27.5M | $55.8M | **2.03x** | Rick bot: FDV $35.2M → ATH $55.8M. JS entry 25-30M~ |
| 10 | Jan 10, 2026 | FISH | Solana | $6.8M | $13M | 1.91x | Rick bot: FDV $8.3M → ATH $13M |
| 11 | Mar 11, 2025 | SPX | Ethereum | $1.17B | $2.1B | 1.79x | CoinMarketCap: ATH $2.27 / ~$2.1B MC (Jul 28, 2025) |
| 12 | Sep 14, 2025 | BAGWORK | Solana | $23M | $40M | 1.74x | CoinGecko: ATH ~$33-48M (Sep 2025) |
| 13 | May 2, 2025 | BOOP | Solana | $282M | $460M | 1.63x | CoinMarketCap: ATH ~$0.49 / ~$460M MC (May 2, 2025) |
| 14 | Jan 26, 2026 | CLAWD | Solana | $10M | $16M | 1.60x | CoinGecko: ATH ~$16M (Jan 25, 2026). Scam token, collapsed. |
| 15 | Oct 13, 2025 | BNBET | BNB | $4.3M | $6.8M | 1.58x | Rick bot: FDV $6.7M → $6.8M |
| 16 | Oct 16, 2025 | LAB | BNB | $152M | $218M | 1.43x | Rick bot: FDV $217M → ATH $218M. JS bought 30% dip. |
| 17 | Feb 2, 2026 | BUTTCOIN | Solana | $20M | $25.8M | 1.29x | Rick bot: FDV $21M → ATH $25.8M |
| 18 | Oct 25, 2025 | SWC | Base | $1.25M | $1.6M | 1.28x | Rick bot: FDV $1.4M → ATH $1.6M |
| 19 | Nov 12, 2025 | OOB | Solana | $355M | $426M | 1.20x | Rick bot: FDV $355M → ATH $426M |
| 20 | Feb 3, 2026 | BLM | Solana | $6.1M | $7M | 1.15x | JS: "$55k worth at 6.1M AVG", "7M from 1M share" |
| 21 | Feb 2, 2026 | GOY | Solana | $1.4M | $1.6M | 1.14x | Rick bot: FDV $1.4M → ATH $1.6M |
| 22 | Feb 2, 2026 | BANKR | Solana | $60M | $62M | 1.03x | Overall ATH $100M+ was Jul 2025 (before entry). Post-entry ~$62M. |
| 23 | May 9, 2025 | FARTCOIN (re) | Solana | $1.2B | $1.2B | 1.00x | Overall ATH $2.5B was Jan 2025. Post-entry never reclaimed $1.2B. |
| 24 | Oct 2, 2025 | LAUNCHCOIN | Solana | $110M | $110M | 1.00x | Overall ATH $350M was May 2025 (before entry). Token died/rebranded. |
| 25 | Feb 1, 2026 | FLUFY | Solana | $1.2M | $1.2M | 1.00x | Rick bot: FDV $1.2M → $1.2M [1s]. Just launched, no run yet. |

### Trades with Entry MC but No ATH Data (5 trades)

| # | Date | Token | Chain | Entry MC | Notes |
|---|------|-------|-------|----------|-------|
| 26 | Oct 5, 2025 | 4 (Believe eco) | Solana | $150M | "rebought a large position in 4" (exited) |
| 27 | Oct 9, 2025 | 8 | Solana | $7M | "Gambling some 8 here at 7M, aiming for 2-3x" (exited) |
| 28 | Oct 26, 2025 | PALU | BNB | $30M | "bought semi-decent amount of PALU @ 30M" |
| 29 | Oct 29, 2025 | 1XTECH | Solana | $2.1M | "Gambled on this coin @ 2.1M avg" (exited) |
| 30 | Jan 26, 2026 | SHRIMP | Solana | $1.5M | "bought a bunch of ShrimpCoin at 1.5M" |

### Trades without Entry MC (9 trades)

| # | Date | Token | Chain | Notes |
|---|------|-------|-------|-------|
| 31 | Mar 11, 2025 | PEPE | Ethereum | "may grab some PEPE and MOG too" — no entry MC stated |
| 32 | Mar 11, 2025 | MOG | Ethereum | "may grab some PEPE and MOG too" — no entry MC stated |
| 33 | Apr 14, 2025 | FARTCOIN | Solana | "Re-entered FARTCOIN, think it's ready for 1B+" — no specific MC |
| 34 | Jun 29, 2025 | STARTUP | Solana | "$STARTUP is the next liquid 10-20x+" — Rick bot ATH $49.6M later |
| 35 | Sep 12, 2025 | PEPE (long) | Ethereum | "Went long on PEPE here @ 0.010644" — perps, no MC stated |
| 36 | Sep 18, 2025 | SUN | Tron | "bought some SUN @ .026, betting on crime" |
| 37 | Sep 26, 2025 | XPL | Unknown | "liking what I'm seeing $XPL" (exited) |
| 38 | Oct 25, 2025 | VIRTUAL | Base | "longing VIRTUAL @ 1.0404 (perps)" (exited) |
| 39 | Oct 25, 2025 | AIXBT | Base | "Longed AIXBT at 0.069048 (perps)" (exited) |

---

## Summary Statistics (25 Trades with Full Data)

| Statistic | Value |
|-----------|-------|
| Median ATH Multiple | 1.63x |
| Mean ATH Multiple | 2.41x |
| MC-Weighted Average | 2.25x |
| Best Trade | ASTER at 11.67x |
| Worst Trade | FARTCOIN/LAUNCHCOIN/FLUFY at 1.00x |
| ≥5x from entry | 2 of 25 (8%) |
| ≥3x from entry | 6 of 25 (24%) |
| ≥2x from entry | 9 of 25 (36%) |
| ≥1.5x (clear win) | 15 of 25 (60%) |
| 1.0-1.5x (marginal) | 7 of 25 (28%) |
| ≤1.0x (flat/loss) | 3 of 25 (12%) |

### Without ASTER (Outlier Sensitivity)

Removing the ASTER outlier (11.67x):

| Statistic | With ASTER | Without ASTER |
|-----------|-----------|---------------|
| Mean | 2.41x | 1.99x |
| MC-Weighted Avg | 2.25x | 1.38x |
| ≥3x count | 6 | 5 |

The MC-weighted average drops significantly without ASTER because it was both a large position ($300M entry) and the highest multiple. This shows concentration risk — one trade disproportionately drives the overall result.

---

## Notable Patterns

### 1. Big Winners Were Early-Stage or TGE Entries
The top 3 multiples (ASTER 11.67x, STREAM 6.00x, CUPSEY 4.18x) all had entry MCs under $5M or caught a token near TGE. ASTER entered at $300M MC on the day of its token generation event (Sep 17) and ran to $3.5B within a week. The pattern: the biggest wins come from getting in early, not from buying established tokens on dips.

### 2. Large-Cap Entries Produce Smaller Multiples
Trades with entry MC >$100M (CARDS, OOB, LAB, BOOP, SPX, FARTCOIN, LAUNCHCOIN) averaged just 1.65x to ATH. The two entries above $1B (SPX at $1.17B, FARTCOIN at $1.2B) returned only 1.79x and 1.00x respectively. Larger positions are harder to get multiples on because the upside ceiling is lower at scale.

### 3. "ATH Before Entry" Trades Are the Biggest Risk
Three trades (FARTCOIN re-entry, LAUNCHCOIN, and arguably BANKR) entered AFTER the token's ATH had already been set. These returned 1.00-1.03x at best — effectively break-even or losses once slippage and fees are considered. This "buying the dip that keeps dipping" pattern is the main source of losses.

### 4. Feb 2026 Was High Volume, Low Quality
Seven trades in Feb 2026 (FLUFY, BUTTCOIN, GOYIM, BANKR, MYSTIC, GOY, BLM) — the highest density — but most showed low ATH multiples (1.0-1.3x). MYSTIC at 2.03x was the exception. Many of these are recent and may still be developing.

---

## Data Sources & Methodology

### Entry Market Cap
1. **Rick bot FDV** — When Rick bot's first structured lookup for a token is timestamped near JS's call, the FDV field is used as entry MC
2. **JS's own messages** — JS frequently states his entry price or MC (e.g., "sized into TITCOIN at 20-30M")
3. **Estimated from price** — For established tokens (SPX, BOOP), entry MC was estimated from entry price × known circulating supply

### ATH Market Cap
1. **Rick bot ATH field** — The structured format `FDV: $X ➡︎ ATH: $Y` provides ATH at time of query
2. **JS's messages** — JS sometimes mentions ATH levels (e.g., "Holy shit 350M" for CARDS)
3. **CoinMarketCap / CoinGecko** — For tokens with public ATH data (ASTER, TITCOIN, SPX, etc.)
4. **Post-entry ATH only** — When a token's overall ATH predates JS's entry, the post-entry peak is used

### Limitations
- **ATH ≠ Realized P&L** — This report shows theoretical maximum returns. JS's actual returns depend on when he sold.
- **14 trades missing data** — Nine trades lack entry MC (mostly established tokens or perps). Five trades lack ATH data.
- **ATH estimates** — For some tokens (BAGWORK, GAS), web sources report varying ATH figures. Midpoints were used.
- **No position sizing data** — JS sometimes mentions dollar amounts ("$500k initial", "$200k twap", "$55k worth") but not consistently enough to calculate portfolio-level returns.

---

## Data File

Full trade data exported to: `results/js_journal_backtest.csv`

---

*Report generated from manual curation of 1,090 messages across both js-personal-journal sub-channels.*
*Entry = JS's stated entry MC or first Rick bot FDV.*
*ATH = Highest known market cap after entry from Rick bot, JS messages, or public price data.*

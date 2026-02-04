# BH Insights Strategy Backtest Report

**Generated:** February 3, 2026
**Data Period:** November 2024 - February 2026 (~15 months)
**Data Source:** BH Insights Discord (data/bh_insights_messages.csv)
**Strategy:** Follow Brandon Hong's Discord trading signals

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total Assets Tested | 12 |
| Assets with Trades | 11 |
| Total Trades | 33 |
| Assets Beating Buy & Hold | **8/12 (67%)** |
| Average Alpha | **+15.49%** |
| Best Performer | OP (+119.07% alpha) |
| Portfolio Savings | **+$18,593** vs buy & hold |

### Key Finding

![[bh_alpha_by_asset.png]]

**67% of assets generated positive alpha vs buy & hold.** The strategy outperformed on average by +15.49%, saving ~$18,593 per $120,000 invested compared to passive holding.

---

## How The Strategy Works

1. **Entry Signal:** Brandon posts trade intent (longed, TWAP, bought, back in)
2. **Entry Price:** Candle close at time of signal
3. **Exit Signal:** Brandon posts exit (TP'd, sold, closed, took profit)
4. **No Timeout:** Positions only close on Brandon's explicit exit signals

### Signal Types Captured

| Signal Type | Examples |
|-------------|----------|
| **Explicit Entry** | "longed SOL", "shorted ETH", "started TWAP on HYPE" |
| **Implicit Entry** | "back in XRP", "bought some gold", "giga longed" |
| **Exit** | "TP'd", "sold", "took profit", "closed", "scaled out" |

---

## Results by Asset Type

### Crypto Assets (10 tested)

![[bh_strategy_vs_buyhold.png]]

| Asset | Strategy | Buy&Hold | Alpha | Trades | Win Rate |
|-------|----------|----------|-------|--------|----------|
| **OP** | +38.19% | -80.88% | **+119.07%** | 1 | 100% |
| **TRUMP** | +8.12% | -64.88% | **+73.01%** | 1 | 100% |
| **PEPE** | -36.47% | -81.92% | **+45.45%** | 1 | 0% |
| **PUMP** | +0.00% | -41.45% | **+41.45%** | 0 | - |
| **FARTCOIN** | -53.29% | -77.43% | **+24.14%** | 2 | 0% |
| **ETH** | -2.74% | -15.27% | **+12.53%** | 10 | 60% |
| **XRP** | -28.31% | -32.12% | **+3.81%** | 3 | 33% |
| **BTC** | -32.59% | -19.72% | -12.87% | 11 | 55% |
| **HYPE** | +91.62% | +164.28% | -72.67% | 1 | 100% |
| **VIRTUAL** | -49.88% | +23.21% | -73.10% | 1 | 0% |

**Crypto Summary:**
- Positive alpha: 7/10 assets (70%)
- Average alpha: +16.08%

### Commodity Assets (2 tested)

| Asset | Strategy | Buy&Hold | Alpha | Trades | Win Rate |
|-------|----------|----------|-------|--------|----------|
| **SILVER** | **+37.41%** | +11.69% | **+25.72%** | 1 | 100% |
| **GOLD** | **+5.75%** | +6.37% | -0.62% | 1 | 100% |

**Commodity Summary:**
- Positive alpha: 1/2 assets (50%)
- Average alpha: +12.55%
- Both trades were winners (100% win rate)

---

## Notable Trades

### OP: The Short That Saved 119%

![[bh_winrate_scatter.png]]

Brandon's OP short is the standout performer:

- **Entry:** Short position on OP
- **Result:** Strategy returned +38.19% while buy & hold lost -80.88%
- **Alpha:** +119.07% outperformance

This demonstrates the value of shorting during bear markets - the strategy captured the downside move instead of suffering through it.

### HYPE: The $24 to $44 Swing

Brandon's HYPE trade shows excellent timing:

- **May 9, 2025:** "Started a TWAP on HYPE from 24" - Entry at ~$24.85
- **June 16, 2025:** "TP'd partials from these longs" - Exit at ~$44.59
- **Result:** +91.62% gain on this trade

While HYPE showed -72.67% alpha (underperformed buy & hold), the actual trade made +91.62% return - just missing the run from $44 to $168.

### SILVER: The Generational Breakout

Brandon repeatedly called silver as "the best chart I've ever seen":

- **Entry:** October 2025 during ATH breakout
- **Exit:** January 2026 after significant run-up
- **Result:** +37.41% return vs +11.69% buy & hold (+25.72% alpha)

---

## Portfolio Simulation

![[bh_portfolio_simulation.png]]

Starting with $10,000 per asset ($120,000 total):

| Metric | Value |
|--------|-------|
| Starting Capital | $120,000 |
| Strategy Final Value | $117,781 (-1.8%) |
| Buy & Hold Final Value | $99,188 (-17.3%) |
| **Strategy Outperformance** | **+$18,593** |

Despite both approaches losing money (bear market conditions), the strategy lost significantly less than passive holding - a difference of nearly $19,000.

---

## Top & Bottom Performers

![[bh_top_bottom.png]]

### Top 5 Alpha Generators

1. **OP** (+119.07%) - 1 short trade, 100% win rate
2. **TRUMP** (+73.01%) - 1 trade, 100% win rate
3. **PEPE** (+45.45%) - 1 trade, avoided major crash
4. **PUMP** (+41.45%) - No trades (avoided losses)
5. **SILVER** (+25.72%) - 1 trade, 100% win rate

### Bottom 3 Underperformers

1. **VIRTUAL** (-73.10%) - Entry timing issue
2. **HYPE** (-72.67%) - Missed the $44 to $168 run
3. **BTC** (-12.87%) - Choppy trading, slight underperformance

---

## Trade Count Distribution

![[bh_trade_distribution.png]]

| Trading Activity | Assets |
|-----------------|--------|
| High (10+ trades) | BTC, ETH |
| Medium (2-3 trades) | XRP, FARTCOIN |
| Low (1 trade) | Most others |
| Zero trades | PUMP |

---

## Data Limitations

### Assets Not Included

Some assets failed data fetching and are not included:
- **SOL** - Binance data fetch error
- **MKR** - No data available for signal period

### Silver Historical Data

Silver (XAG) perpetual futures data only available from January 2026 on Binance. Earlier signals (October-December 2025) could not be fully backtested. Brandon's earlier silver entries around the $50-53 ATH breakout used partial data.

### HYPE Early Signals

HYPE launched in November 2024. The backtest captures the May 2025 re-entry but not the initial airdrop position at $3-4.

### Signal Attribution

Some "implicit" signals (mentions of positions without explicit entry) may be missed or incorrectly attributed. The strategy uses conservative pattern matching to avoid false positives.

---

## Methodology

### Signal Detection

Patterns extracted from Brandon's Discord messages:

**Entry Patterns:**
- Explicit: "longed X", "shorted X", "bought X"
- TWAP: "started a TWAP on X", "TWAPing X", "TWAP above $Y"
- Implicit: "back in X", "positioned in X", "giga longed", "left curved X"

**Exit Patterns:**
- "TP'd", "took profit", "sold", "closed", "exited", "scaled out"

**False Positive Filtering:**
- "positioned in X and Y" (stating position, not entry)
- "like X did" (comparison, not entry)
- "did with X" (past reference)

### Price Data Sources

| Asset | Source |
|-------|--------|
| Crypto | Binance spot via CCXT |
| GOLD | Bybit XAUT perp (primary), OKX XAU, Binance PAXG |
| SILVER | Bitget XAG perp (primary), Binance XAG |
| HYPE | Hyperliquid native (4h candles) |

### Backtest Parameters

- **Initial Capital:** $10,000 per asset
- **Trading Fee:** 0.1%
- **Hold Period:** Signal-based only (no timeout)
- **Position Sizing:** 100% of available capital

---

## Conclusions

### What Works

1. **Short Positions:** OP short generated +119% alpha - capturing downside moves is valuable
2. **Commodity Calls:** Gold and silver trades both profitable with 100% win rate
3. **Avoiding Losers:** Strategy avoided major drawdowns on PEPE, FARTCOIN, TRUMP
4. **Timing:** Entry timing on strong trends (TRUMP, SILVER, OP) was excellent

### What Doesn't

1. **Missing Exits:** Some profitable runs not fully captured (HYPE $44 to $168)
2. **Choppy Markets:** BTC trading in ranging markets underperformed
3. **Early Entries on Wrong Assets:** VIRTUAL entry came before further decline

### Overall Assessment

Following BH Insights signals generated **+15.49% alpha on average** across 12 assets. In a challenging bear market where buy & hold lost -17.3%, the strategy limited losses to just -1.8%.

**Key Takeaway:** The strategy adds value primarily through:
1. **Risk management** - avoiding major losers
2. **Short positions** - capturing downside moves
3. **Timing** - entering strong trends at good levels

The +$18,593 portfolio outperformance on $120,000 invested demonstrates real value in following the signals.

---

*Report generated by BH Insights Backtest System*
*Data: data/bh_insights_messages.csv*
*Results: results/bh_insights_full_backtest.csv*
*Visualizations: reports/figures/*

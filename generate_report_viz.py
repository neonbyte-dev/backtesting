"""
Generate visualizations for the trading strategy report
"""
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

# Set style
plt.style.use('dark_background')
plt.rcParams['figure.figsize'] = (12, 6)
plt.rcParams['font.size'] = 11

# Create reports/figures directory if needed
os.makedirs('reports/figures', exist_ok=True)

# =============================================================================
# 1. STRATEGY COMPARISON - Final Optimized Strategies
# =============================================================================
print("Generating strategy comparison chart...")

strategies_df = pd.read_csv('results/final_strategy_comparison.csv')
strategies_df = strategies_df.sort_values('Return %', ascending=True)

fig, ax = plt.subplots(figsize=(12, 7))

colors = ['#ff6b6b' if r < 0 else '#4ecdc4' for r in strategies_df['Return %']]
bars = ax.barh(strategies_df['Strategy'], strategies_df['Return %'], color=colors, edgecolor='white', linewidth=0.5)

# Add value labels
for bar, val in zip(bars, strategies_df['Return %']):
    x_pos = val + 0.3 if val >= 0 else val - 0.3
    ha = 'left' if val >= 0 else 'right'
    ax.text(x_pos, bar.get_y() + bar.get_height()/2, f'{val:.1f}%',
            va='center', ha=ha, fontsize=10, fontweight='bold')

ax.axvline(x=0, color='white', linewidth=1, linestyle='--', alpha=0.5)
ax.set_xlabel('Return (%)', fontsize=12)
ax.set_title('Strategy Performance Comparison (90-Day Backtest)', fontsize=14, fontweight='bold', pad=20)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

plt.tight_layout()
plt.savefig('reports/figures/strategy_comparison.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print("  ✓ Saved strategy_comparison.png")

# =============================================================================
# 2. BH INSIGHTS MULTI-ASSET PERFORMANCE
# =============================================================================
print("Generating BH Insights asset performance chart...")

bh_df = pd.read_csv('results/bh_insights_full_backtest.csv')
bh_df = bh_df.sort_values('Alpha_Pct', ascending=True)

fig, ax = plt.subplots(figsize=(14, 8))

x = np.arange(len(bh_df))
width = 0.35

bars1 = ax.bar(x - width/2, bh_df['Strategy_Return_Pct'], width, label='Strategy Return',
               color='#4ecdc4', edgecolor='white', linewidth=0.5)
bars2 = ax.bar(x + width/2, bh_df['BuyHold_Return_Pct'], width, label='Buy & Hold',
               color='#ff6b6b', edgecolor='white', linewidth=0.5, alpha=0.7)

ax.axhline(y=0, color='white', linewidth=1, linestyle='--', alpha=0.5)
ax.set_ylabel('Return (%)', fontsize=12)
ax.set_xlabel('Asset', fontsize=12)
ax.set_title('BH Insights Strategy vs Buy & Hold by Asset', fontsize=14, fontweight='bold', pad=20)
ax.set_xticks(x)
ax.set_xticklabels(bh_df['Asset'], rotation=45, ha='right')
ax.legend(loc='upper left')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

plt.tight_layout()
plt.savefig('reports/figures/bh_insights_performance.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print("  ✓ Saved bh_insights_performance.png")

# =============================================================================
# 3. ALPHA GENERATION CHART
# =============================================================================
print("Generating alpha chart...")

fig, ax = plt.subplots(figsize=(14, 6))

colors = ['#ff6b6b' if a < 0 else '#4ecdc4' for a in bh_df['Alpha_Pct']]
bars = ax.bar(bh_df['Asset'], bh_df['Alpha_Pct'], color=colors, edgecolor='white', linewidth=0.5)

ax.axhline(y=0, color='white', linewidth=1, linestyle='--', alpha=0.5)
ax.set_ylabel('Alpha (%)', fontsize=12)
ax.set_xlabel('Asset', fontsize=12)
ax.set_title('Alpha Generated (Strategy Return - Buy & Hold)', fontsize=14, fontweight='bold', pad=20)
ax.set_xticklabels(bh_df['Asset'], rotation=45, ha='right')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

# Add value annotations for extreme values
for bar, val, asset in zip(bars, bh_df['Alpha_Pct'], bh_df['Asset']):
    if abs(val) > 50:
        y_pos = val + 5 if val > 0 else val - 5
        ax.text(bar.get_x() + bar.get_width()/2, y_pos, f'{val:.0f}%',
                ha='center', va='bottom' if val > 0 else 'top', fontsize=9, fontweight='bold')

plt.tight_layout()
plt.savefig('reports/figures/alpha_by_asset.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print("  ✓ Saved alpha_by_asset.png")

# =============================================================================
# 4. OI STRATEGY COMPARISON
# =============================================================================
print("Generating OI strategy comparison chart...")

oi_df = pd.read_csv('results/oi_funding_comparison.csv')
oi_df = oi_df.sort_values('return_pct', ascending=True)

fig, ax = plt.subplots(figsize=(12, 6))

colors = ['#ff6b6b' if r < 0 else '#4ecdc4' for r in oi_df['return_pct']]
bars = ax.barh(oi_df['strategy'], oi_df['return_pct'], color=colors, edgecolor='white', linewidth=0.5)

# Add trade count and win rate annotations
for i, (bar, trades, wr) in enumerate(zip(bars, oi_df['trades'], oi_df['win_rate'])):
    val = bar.get_width()
    if trades > 0:
        label = f'{val:.1f}% | {int(trades)} trades | {wr:.0f}% WR'
    else:
        label = f'{val:.1f}%'
    x_pos = val + 0.2 if val >= 0 else val - 0.2
    ha = 'left' if val >= 0 else 'right'
    ax.text(x_pos, bar.get_y() + bar.get_height()/2, label,
            va='center', ha=ha, fontsize=9)

ax.axvline(x=0, color='white', linewidth=1, linestyle='--', alpha=0.5)
ax.set_xlabel('Return (%)', fontsize=12)
ax.set_title('Open Interest & Funding Rate Strategy Comparison', fontsize=14, fontweight='bold', pad=20)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

plt.tight_layout()
plt.savefig('reports/figures/oi_funding_comparison.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print("  ✓ Saved oi_funding_comparison.png")

# =============================================================================
# 5. CME SUNDAY GAP ANALYSIS
# =============================================================================
print("Generating CME Sunday gap analysis chart...")

cme_df = pd.read_csv('results/cme_sunday_results.csv')

# Filter to just the key strategies for comparison
key_strategies = ['CME Both (24h hold)', 'CME Short Only (24h)', 'CME Both (2% SL, 4% TP)']
cme_filtered = cme_df[cme_df['Strategy'].isin(key_strategies)]

# Pivot for grouped bar chart
fig, ax = plt.subplots(figsize=(12, 6))

assets = cme_filtered['Asset'].unique()
strategies = key_strategies
x = np.arange(len(assets))
width = 0.25

colors = ['#4ecdc4', '#ff6b6b', '#ffd93d']
for i, strat in enumerate(strategies):
    data = cme_filtered[cme_filtered['Strategy'] == strat]['Total Return %'].values
    ax.bar(x + i*width - width, data, width, label=strat.replace('CME ', ''),
           color=colors[i], edgecolor='white', linewidth=0.5)

# Add buy & hold reference line
bh_returns = cme_filtered[cme_filtered['Strategy'] == 'CME Both (24h hold)']['Buy & Hold %'].values
for i, (pos, val) in enumerate(zip(x, bh_returns)):
    ax.scatter(pos, val, color='white', s=100, marker='_', linewidths=3, zorder=5)

ax.axhline(y=0, color='white', linewidth=1, linestyle='--', alpha=0.5)
ax.set_ylabel('Return (%)', fontsize=12)
ax.set_xlabel('Asset', fontsize=12)
ax.set_title('CME Sunday Gap Trading Strategies by Asset', fontsize=14, fontweight='bold', pad=20)
ax.set_xticks(x)
ax.set_xticklabels(assets)
ax.legend(loc='upper right', title='Strategy')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

# Add note about white markers
ax.text(0.02, 0.02, '— = Buy & Hold baseline', transform=ax.transAxes, fontsize=9, color='white', alpha=0.7)

plt.tight_layout()
plt.savefig('reports/figures/cme_sunday_analysis.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print("  ✓ Saved cme_sunday_analysis.png")

# =============================================================================
# 6. WIN RATE VS RETURN SCATTER
# =============================================================================
print("Generating win rate vs return scatter plot...")

# Combine data from multiple sources
scatter_data = []

# From final strategy comparison
for _, row in strategies_df.iterrows():
    if row['Trades'] > 0:
        scatter_data.append({
            'Strategy': row['Strategy'][:20] + '...' if len(row['Strategy']) > 20 else row['Strategy'],
            'Return': row['Return %'],
            'Win Rate': row['Win Rate %'],
            'Trades': row['Trades'],
            'Source': 'OI Strategies'
        })

# From BH Insights (only assets with trades)
for _, row in bh_df.iterrows():
    if row['Total_Trades'] > 0:
        scatter_data.append({
            'Strategy': row['Asset'],
            'Return': row['Strategy_Return_Pct'],
            'Win Rate': row['Win_Rate_Pct'],
            'Trades': row['Total_Trades'],
            'Source': 'BH Insights'
        })

scatter_df = pd.DataFrame(scatter_data)

fig, ax = plt.subplots(figsize=(12, 8))

sources = scatter_df['Source'].unique()
colors = {'OI Strategies': '#4ecdc4', 'BH Insights': '#ffd93d'}

for source in sources:
    data = scatter_df[scatter_df['Source'] == source]
    sizes = data['Trades'] * 15 + 50
    ax.scatter(data['Win Rate'], data['Return'], s=sizes, c=colors[source],
               label=source, alpha=0.7, edgecolor='white', linewidth=0.5)

# Add quadrant lines
ax.axhline(y=0, color='white', linewidth=1, linestyle='--', alpha=0.3)
ax.axvline(x=50, color='white', linewidth=1, linestyle='--', alpha=0.3)

# Add quadrant labels
ax.text(75, 80, 'IDEAL\nHigh Win Rate\nPositive Return', ha='center', va='center',
        fontsize=10, alpha=0.5, color='#4ecdc4')
ax.text(25, -40, 'WORST\nLow Win Rate\nNegative Return', ha='center', va='center',
        fontsize=10, alpha=0.5, color='#ff6b6b')

ax.set_xlabel('Win Rate (%)', fontsize=12)
ax.set_ylabel('Return (%)', fontsize=12)
ax.set_title('Win Rate vs Return (bubble size = trade count)', fontsize=14, fontweight='bold', pad=20)
ax.legend(loc='upper left')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

plt.tight_layout()
plt.savefig('reports/figures/winrate_vs_return.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print("  ✓ Saved winrate_vs_return.png")

# =============================================================================
# 7. SUMMARY STATS TABLE AS IMAGE
# =============================================================================
print("Generating summary stats image...")

fig, ax = plt.subplots(figsize=(10, 4))
ax.axis('off')

# Calculate summary stats
stats = {
    'Metric': [
        'Total Strategies Tested',
        'Best Strategy (90d)',
        'Best Return',
        'Best Win Rate (>5 trades)',
        'Most Alpha Generated',
        'BH Insights Assets Beating Market'
    ],
    'Value': [
        '15+',
        'OPTIMIZED (OI:-0.2, PT:1.5)',
        '+6.96%',
        'OPTIMIZED - 75%',
        'ZEC (+106.74%)',
        '18 of 22 (82%)'
    ]
}

table = ax.table(
    cellText=list(zip(stats['Metric'], stats['Value'])),
    colLabels=['Metric', 'Value'],
    loc='center',
    cellLoc='left',
    colWidths=[0.6, 0.4]
)
table.auto_set_font_size(False)
table.set_fontsize(11)
table.scale(1.2, 1.8)

# Style the table
for (row, col), cell in table.get_celld().items():
    cell.set_edgecolor('#333')
    if row == 0:
        cell.set_facecolor('#2d3436')
        cell.set_text_props(weight='bold', color='white')
    else:
        cell.set_facecolor('#1a1a2e')
        cell.set_text_props(color='white')

plt.title('Strategy Backtest Summary', fontsize=14, fontweight='bold', pad=10, color='white')
plt.savefig('reports/figures/summary_stats.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print("  ✓ Saved summary_stats.png")

print("\n✅ All visualizations generated successfully!")
print("   Output directory: reports/figures/")

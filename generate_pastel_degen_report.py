"""
Generate Pastel Degen Report with Visualizations
"""
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

# Set style
plt.style.use('dark_background')
plt.rcParams['figure.figsize'] = (12, 6)
plt.rcParams['font.size'] = 11

os.makedirs('reports/figures', exist_ok=True)

print("Loading data...")
caller_stats = pd.read_csv('results/pastel_degen_caller_stats.csv')
all_calls = pd.read_csv('results/pastel_degen_all_calls.csv')

# Filter to callers with 5+ calls
qualified = caller_stats[caller_stats['total_calls'] >= 5].copy()
qualified = qualified.sort_values('total_calls', ascending=False)

print(f"Loaded {len(caller_stats)} callers, {len(qualified)} with 5+ calls")

# =============================================================================
# 1. CALLS BY CALLER (Bar Chart)
# =============================================================================
print("Generating calls by caller chart...")

fig, ax = plt.subplots(figsize=(12, 6))

colors = ['#4ecdc4' if row['win_rate'] > 0 else '#ff6b6b' for _, row in qualified.iterrows()]
bars = ax.bar(qualified['caller_normalized'], qualified['total_calls'], color=colors,
              edgecolor='white', linewidth=0.5)

ax.set_xlabel('Caller', fontsize=12)
ax.set_ylabel('Number of Calls', fontsize=12)
ax.set_title('Pastel Degen: Total Calls by Caller\n(Green = has 3x winners, Red = no winners)',
             fontsize=14, fontweight='bold', pad=20)
plt.xticks(rotation=45, ha='right')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

plt.tight_layout()
plt.savefig('reports/figures/pastel_calls_by_caller.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print("  ✓ Saved pastel_calls_by_caller.png")

# =============================================================================
# 2. WIN RATE VS RUG RATE (Stacked Bar)
# =============================================================================
print("Generating win/rug rate chart...")

fig, ax = plt.subplots(figsize=(14, 6))

x = np.arange(len(qualified))
width = 0.6

# Calculate percentages
qualified['hit_3x_pct'] = qualified['hit_3x'] / qualified['total_calls'] * 100
qualified['rugged_pct'] = qualified['rugged'] / qualified['total_calls'] * 100
qualified['holding_pct'] = 100 - qualified['hit_3x_pct'] - qualified['rugged_pct']

# Stacked bar
ax.bar(x, qualified['hit_3x_pct'], width, label='Hit 3x (WIN)', color='#4ecdc4', edgecolor='white')
ax.bar(x, qualified['holding_pct'], width, bottom=qualified['hit_3x_pct'],
       label='Still Holding', color='#ffd93d', edgecolor='white')
ax.bar(x, qualified['rugged_pct'], width,
       bottom=qualified['hit_3x_pct'] + qualified['holding_pct'],
       label='Rugged (LOSS)', color='#ff6b6b', edgecolor='white')

ax.set_xlabel('Caller', fontsize=12)
ax.set_ylabel('Percentage of Calls', fontsize=12)
ax.set_title('Call Outcomes by Caller\n(3x TP or Hold to 0 Strategy)', fontsize=14, fontweight='bold', pad=20)
ax.set_xticks(x)
ax.set_xticklabels(qualified['caller_normalized'], rotation=45, ha='right')
ax.legend(loc='upper right')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

plt.tight_layout()
plt.savefig('reports/figures/pastel_outcome_distribution.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print("  ✓ Saved pastel_outcome_distribution.png")

# =============================================================================
# 3. AVG RETURN BY CALLER
# =============================================================================
print("Generating average return chart...")

fig, ax = plt.subplots(figsize=(12, 6))

colors = ['#4ecdc4' if r > -50 else '#ff6b6b' for r in qualified['avg_return_pct']]
bars = ax.bar(qualified['caller_normalized'], qualified['avg_return_pct'], color=colors,
              edgecolor='white', linewidth=0.5)

ax.axhline(y=0, color='white', linewidth=1, linestyle='--', alpha=0.5)
ax.axhline(y=-100, color='#ff6b6b', linewidth=1, linestyle='--', alpha=0.3)

ax.set_xlabel('Caller', fontsize=12)
ax.set_ylabel('Average Return per Call (%)', fontsize=12)
ax.set_title('Average Return by Caller\n(Negative = losing money overall)', fontsize=14, fontweight='bold', pad=20)
plt.xticks(rotation=45, ha='right')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

# Add value labels
for bar, val in zip(bars, qualified['avg_return_pct']):
    y_pos = bar.get_height() - 5 if bar.get_height() < 0 else bar.get_height() + 2
    ax.text(bar.get_x() + bar.get_width()/2, y_pos, f'{val:.0f}%',
            ha='center', va='top' if val < 0 else 'bottom', fontsize=9, fontweight='bold')

plt.tight_layout()
plt.savefig('reports/figures/pastel_avg_return.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print("  ✓ Saved pastel_avg_return.png")

# =============================================================================
# 4. BEST PERFORMERS (Scatter: Calls vs Win Rate)
# =============================================================================
print("Generating scatter plot...")

fig, ax = plt.subplots(figsize=(10, 8))

# Size by total calls, color by avg return
sizes = qualified['total_calls'] * 2 + 50
colors_val = qualified['avg_return_pct']

scatter = ax.scatter(qualified['total_calls'], qualified['win_rate'],
                     s=sizes, c=colors_val, cmap='RdYlGn',
                     alpha=0.7, edgecolors='white', linewidth=1,
                     vmin=-100, vmax=0)

# Add labels
for _, row in qualified.iterrows():
    ax.annotate(row['caller_normalized'],
                (row['total_calls'], row['win_rate']),
                xytext=(5, 5), textcoords='offset points', fontsize=9)

ax.set_xlabel('Total Calls', fontsize=12)
ax.set_ylabel('Win Rate (Hit 3x) %', fontsize=12)
ax.set_title('Caller Performance: Calls vs Win Rate\n(Color = avg return, Size = call volume)',
             fontsize=14, fontweight='bold', pad=20)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

# Colorbar
cbar = plt.colorbar(scatter, ax=ax)
cbar.set_label('Avg Return %')

plt.tight_layout()
plt.savefig('reports/figures/pastel_caller_scatter.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print("  ✓ Saved pastel_caller_scatter.png")

# =============================================================================
# 5. TOKEN OUTCOME PIE CHART
# =============================================================================
print("Generating overall outcomes pie...")

fig, ax = plt.subplots(figsize=(8, 8))

total_3x = caller_stats['hit_3x'].sum()
total_rugged = caller_stats['rugged'].sum()
total_holding = caller_stats['total_calls'].sum() - total_3x - total_rugged

labels = ['Hit 3x (WIN)', 'Rugged (LOSS)', 'Still Holding']
sizes = [total_3x, total_rugged, total_holding]
colors = ['#4ecdc4', '#ff6b6b', '#ffd93d']
explode = (0.05, 0, 0)

wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors, explode=explode,
                                   autopct='%1.1f%%', startangle=90,
                                   textprops={'color': 'white', 'fontsize': 12})

ax.set_title(f'Overall Token Outcomes\n(Total: {sum(sizes)} calls)',
             fontsize=14, fontweight='bold', pad=20)

plt.tight_layout()
plt.savefig('reports/figures/pastel_outcomes_pie.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print("  ✓ Saved pastel_outcomes_pie.png")

# =============================================================================
# 6. BEST MAX MULTIPLES
# =============================================================================
print("Generating best performers chart...")

# Get top tokens by max multiple
top_tokens = all_calls.nlargest(15, 'max_multiple')[['ticker', 'caller_normalized', 'max_multiple', 'entry_fdv', 'result']]

fig, ax = plt.subplots(figsize=(12, 6))

colors = ['#4ecdc4' if r == 'HIT_3X' else '#ffd93d' if r == 'HOLDING' else '#ff6b6b'
          for r in top_tokens['result']]

bars = ax.barh(range(len(top_tokens)), top_tokens['max_multiple'], color=colors,
               edgecolor='white', linewidth=0.5)

ax.set_yticks(range(len(top_tokens)))
ax.set_yticklabels([f"{row['ticker']} ({row['caller_normalized']})" for _, row in top_tokens.iterrows()])
ax.set_xlabel('Max Multiple from Entry', fontsize=12)
ax.set_title('Top 15 Best Performing Calls (Max Multiple Achieved)',
             fontsize=14, fontweight='bold', pad=20)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

# Add value labels
for bar, val in zip(bars, top_tokens['max_multiple']):
    ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2, f'{val:.1f}x',
            va='center', fontsize=10, fontweight='bold')

plt.tight_layout()
plt.savefig('reports/figures/pastel_top_performers.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print("  ✓ Saved pastel_top_performers.png")

print("\n✅ All visualizations generated!")
print(f"   Output: reports/figures/")

# Print summary for report
print("\n" + "="*60)
print("SUMMARY STATS FOR REPORT")
print("="*60)
print(f"Total calls analyzed: {caller_stats['total_calls'].sum()}")
print(f"Unique callers: {len(caller_stats)}")
print(f"Callers with 5+ calls: {len(qualified)}")
print(f"Total 3x wins: {caller_stats['hit_3x'].sum()}")
print(f"Total rugged: {caller_stats['rugged'].sum()}")
print(f"Overall rug rate: {caller_stats['rugged'].sum() / caller_stats['total_calls'].sum() * 100:.1f}%")
print(f"Overall win rate: {caller_stats['hit_3x'].sum() / caller_stats['total_calls'].sum() * 100:.1f}%")

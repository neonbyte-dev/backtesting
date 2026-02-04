"""
Generate visualizations for max mcap analysis
"""
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

plt.style.use('dark_background')
plt.rcParams['figure.figsize'] = (12, 6)
os.makedirs('reports/figures', exist_ok=True)

# Load data
calls_df = pd.read_csv('results/pastel_degen_max_analysis.csv')
caller_stats = pd.read_csv('results/pastel_degen_caller_max_stats.csv')

qualified = caller_stats[caller_stats['calls'] >= 5].sort_values('calls', ascending=False)

print("Generating max mcap visualizations...")

# =============================================================================
# 1. MAX MULTIPLE DISTRIBUTION
# =============================================================================
fig, ax = plt.subplots(figsize=(12, 6))

# Create bins
bins = [0, 2, 3, 5, 10, 20, 50, 100, 500]
labels = ['<2x', '2-3x', '3-5x', '5-10x', '10-20x', '20-50x', '50-100x', '100x+']
calls_df['mult_bin'] = pd.cut(calls_df['max_multiple'], bins=bins, labels=labels)

counts = calls_df['mult_bin'].value_counts().reindex(labels)
colors = plt.cm.RdYlGn(np.linspace(0.2, 0.9, len(labels)))

bars = ax.bar(labels, counts, color=colors, edgecolor='white', linewidth=0.5)

ax.set_xlabel('Max Multiple Achieved', fontsize=12)
ax.set_ylabel('Number of Calls', fontsize=12)
ax.set_title('Distribution of Max Multiples (ATH from Rick Bot Data)\n31.7% hit 3x+, but most died before you could exit',
             fontsize=14, fontweight='bold', pad=20)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

# Add value labels
for bar, val in zip(bars, counts):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5, f'{val}',
            ha='center', fontsize=10, fontweight='bold')

plt.tight_layout()
plt.savefig('reports/figures/pastel_max_distribution.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print("  ✓ Saved pastel_max_distribution.png")

# =============================================================================
# 2. AVG MAX MULTIPLE BY CALLER
# =============================================================================
fig, ax = plt.subplots(figsize=(12, 6))

# Sort by avg max
qualified_sorted = qualified.sort_values('avg_max', ascending=True)

colors = plt.cm.RdYlGn(np.linspace(0.2, 0.9, len(qualified_sorted)))
bars = ax.barh(qualified_sorted['caller_normalized'], qualified_sorted['avg_max'],
               color=colors, edgecolor='white', linewidth=0.5)

ax.axvline(x=3, color='#ffd93d', linewidth=2, linestyle='--', label='3x (break-even)')
ax.axvline(x=5, color='#4ecdc4', linewidth=2, linestyle='--', label='5x')

ax.set_xlabel('Average Max Multiple', fontsize=12)
ax.set_title('Average Max Multiple by Caller\n(Higher = tokens pumped more before dying)',
             fontsize=14, fontweight='bold', pad=20)
ax.legend(loc='lower right')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

# Add value labels
for bar, val in zip(bars, qualified_sorted['avg_max']):
    ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height()/2, f'{val:.1f}x',
            va='center', fontsize=10, fontweight='bold')

plt.tight_layout()
plt.savefig('reports/figures/pastel_caller_avg_max.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print("  ✓ Saved pastel_caller_avg_max.png")

# =============================================================================
# 3. PERCENTAGE HITTING THRESHOLDS BY CALLER
# =============================================================================
fig, ax = plt.subplots(figsize=(14, 6))

x = np.arange(len(qualified))
width = 0.2

ax.bar(x - 1.5*width, qualified['pct_10x'], width, label='≥10x', color='#4ecdc4', edgecolor='white')
ax.bar(x - 0.5*width, qualified['pct_5x'], width, label='≥5x', color='#45b7d1', edgecolor='white')
ax.bar(x + 0.5*width, qualified['pct_3x'], width, label='≥3x', color='#ffd93d', edgecolor='white')

ax.set_ylabel('% of Calls Hitting Target', fontsize=12)
ax.set_xlabel('Caller', fontsize=12)
ax.set_title('Percentage of Calls Reaching Max Multiple Thresholds\n(Based on ATH, not captured profit)',
             fontsize=14, fontweight='bold', pad=20)
ax.set_xticks(x)
ax.set_xticklabels(qualified['caller_normalized'], rotation=45, ha='right')
ax.legend(loc='upper right')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

plt.tight_layout()
plt.savefig('reports/figures/pastel_threshold_pct.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print("  ✓ Saved pastel_threshold_pct.png")

# =============================================================================
# 4. ATH vs REALITY COMPARISON
# =============================================================================
fig, ax = plt.subplots(figsize=(10, 6))

# Compare: What tokens achieved (ATH) vs What you captured (3x strategy result)
categories = ['Hit 3x\n(ATH)', 'Captured 3x\n(Strategy)', 'Hit 5x\n(ATH)', 'Hit 10x\n(ATH)']
values = [31.7, 0.9, 21.0, 7.9]  # From our analysis
colors = ['#4ecdc4', '#ff6b6b', '#45b7d1', '#9b59b6']

bars = ax.bar(categories, values, color=colors, edgecolor='white', linewidth=1)

ax.set_ylabel('% of Calls', fontsize=12)
ax.set_title('The Timing Gap: ATH Potential vs Captured Gains\n(31.7% hit 3x, but only 0.9% were captured)',
             fontsize=14, fontweight='bold', pad=20)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

# Add value labels
for bar, val in zip(bars, values):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, f'{val:.1f}%',
            ha='center', fontsize=12, fontweight='bold')

# Add annotation
ax.annotate('97% of potential\ngains lost to\ntiming issues',
            xy=(1, 0.9), xytext=(1.5, 15),
            arrowprops=dict(arrowstyle='->', color='white'),
            fontsize=11, ha='center')

plt.tight_layout()
plt.savefig('reports/figures/pastel_ath_vs_captured.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print("  ✓ Saved pastel_ath_vs_captured.png")

# =============================================================================
# 5. TOP CALLERS COMPARISON
# =============================================================================
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

# Left: Best max multiples
top_by_best = qualified.nlargest(8, 'best')
ax1.barh(top_by_best['caller_normalized'], top_by_best['best'],
         color='#4ecdc4', edgecolor='white', linewidth=0.5)
ax1.set_xlabel('Best Single Call (Max Multiple)')
ax1.set_title('Best Single Call per Caller', fontweight='bold')
ax1.spines['top'].set_visible(False)
ax1.spines['right'].set_visible(False)

for i, (_, row) in enumerate(top_by_best.iterrows()):
    ax1.text(row['best'] + 5, i, f"{row['best']:.0f}x ({row['best_token']})",
             va='center', fontsize=9)

# Right: Calls hitting 5x+
top_by_5x = qualified.nlargest(8, 'cnt_5x')
ax2.barh(top_by_5x['caller_normalized'], top_by_5x['cnt_5x'],
         color='#ffd93d', edgecolor='white', linewidth=0.5)
ax2.set_xlabel('Number of Calls Hitting 5x+')
ax2.set_title('Most Calls Reaching 5x+', fontweight='bold')
ax2.spines['top'].set_visible(False)
ax2.spines['right'].set_visible(False)

plt.tight_layout()
plt.savefig('reports/figures/pastel_top_callers.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print("  ✓ Saved pastel_top_callers.png")

print("\n✅ All visualizations generated!")

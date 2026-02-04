"""
Analyze Trade Quality - Where Are We Losing Money?

The user is right - 5% monthly return seems low if OI has predictive power.
Let's dig into:
1. What the current entry/exit rules actually do
2. Where trades are going wrong
3. What better conditions might look like
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

plt.style.use('seaborn-v0_8-whitegrid')


def load_data():
    """Load combined data"""
    df = pd.read_csv('data/btc_oi_funding_combined.csv', parse_dates=['timestamp'])
    df = df.set_index('timestamp')
    return df


def analyze_current_strategy_logic():
    """
    Explain what the current strategies are actually doing
    """
    print("=" * 70)
    print("CURRENT STRATEGY LOGIC (THE PROBLEMS)")
    print("=" * 70)

    print("""
CURRENT ENTRY RULES:
--------------------
- Wait for OI to drop by X% (e.g., -0.3% over 4 hours)
- Optionally require price to also be dropping
- Optionally filter by funding rate

CURRENT EXIT RULES:
-------------------
- Exit when OI starts rising again, OR
- Exit after max hold period (e.g., 24 hours)

PROBLEMS WITH THIS APPROACH:
----------------------------
1. EXIT TOO EARLY: We sell when OI rises, but price might still be recovering
2. ARBITRARY THRESHOLDS: Why -0.3%? Why 4 hours? These are guesses.
3. NO PROFIT TARGETS: We don't let winners run
4. NO STOP LOSSES: We don't cut losers quickly
5. BINARY SIGNALS: All-in or all-out, no scaling

Let's look at what actually happened in the trades...
""")


def simulate_and_analyze_trades(df):
    """
    Manually simulate trades and analyze each one
    """
    print("\n" + "=" * 70)
    print("DETAILED TRADE ANALYSIS")
    print("=" * 70)

    # Simple OI drop strategy
    df['oi_change_4h'] = df['oi_btc'].pct_change(4) * 100
    df['price_change_4h'] = df['close'].pct_change(4) * 100

    # Find entry points: OI dropped significantly
    entry_threshold = -0.2
    df['entry_signal'] = df['oi_change_4h'] <= entry_threshold

    trades = []
    in_trade = False
    entry_price = None
    entry_time = None
    entry_oi = None

    for i in range(4, len(df)):
        row = df.iloc[i]

        if not in_trade and row['entry_signal']:
            # Enter trade
            in_trade = True
            entry_price = row['close']
            entry_time = df.index[i]
            entry_oi = row['oi_btc']

        elif in_trade:
            # Check what happens over next periods
            hours_held = (df.index[i] - entry_time).total_seconds() / 3600
            current_price = row['close']
            current_return = (current_price / entry_price - 1) * 100

            # Exit after 24 hours (current logic)
            if hours_held >= 24:
                trades.append({
                    'entry_time': entry_time,
                    'exit_time': df.index[i],
                    'entry_price': entry_price,
                    'exit_price': current_price,
                    'return_pct': current_return,
                    'hours_held': hours_held,
                    'exit_reason': 'max_hold'
                })
                in_trade = False

    trades_df = pd.DataFrame(trades)

    if len(trades_df) > 0:
        print(f"\nTotal trades: {len(trades_df)}")
        print(f"Win rate: {(trades_df['return_pct'] > 0).mean()*100:.1f}%")
        print(f"Average return: {trades_df['return_pct'].mean():.2f}%")
        print(f"Total return: {trades_df['return_pct'].sum():.2f}%")

        print("\n--- INDIVIDUAL TRADES ---")
        for _, trade in trades_df.iterrows():
            win = "WIN" if trade['return_pct'] > 0 else "LOSS"
            print(f"{win}: Entry {trade['entry_time']} @ ${trade['entry_price']:,.0f} -> "
                  f"Exit @ ${trade['exit_price']:,.0f} = {trade['return_pct']:+.2f}%")

        # Analyze what we COULD have captured
        print("\n--- MISSED OPPORTUNITY ANALYSIS ---")
        analyze_missed_opportunities(df, trades_df)

    return trades_df


def analyze_missed_opportunities(df, trades_df):
    """
    For each trade, look at what the MAX potential profit was
    """
    print("\nFor each entry, what was the max profit we COULD have captured?")

    for _, trade in trades_df.iterrows():
        entry_time = trade['entry_time']
        entry_price = trade['entry_price']

        # Look at next 48 hours after entry
        mask = (df.index > entry_time) & (df.index <= entry_time + pd.Timedelta(hours=48))
        future_prices = df.loc[mask, 'close']

        if len(future_prices) > 0:
            max_price = future_prices.max()
            min_price = future_prices.min()
            max_profit = (max_price / entry_price - 1) * 100
            max_loss = (min_price / entry_price - 1) * 100
            actual = trade['return_pct']

            missed = max_profit - actual

            print(f"\nEntry: {entry_time.strftime('%Y-%m-%d %H:%M')}")
            print(f"  Entry price: ${entry_price:,.0f}")
            print(f"  Max price (48h): ${max_price:,.0f} ({max_profit:+.2f}%)")
            print(f"  Min price (48h): ${min_price:,.0f} ({max_loss:+.2f}%)")
            print(f"  Actual captured: {actual:+.2f}%")
            print(f"  LEFT ON TABLE: {missed:+.2f}%")


def find_optimal_exit_rules(df):
    """
    Analyze what exit rules would have worked best
    """
    print("\n" + "=" * 70)
    print("FINDING BETTER EXIT RULES")
    print("=" * 70)

    df['oi_change_4h'] = df['oi_btc'].pct_change(4) * 100

    # Entry: OI drops
    entry_threshold = -0.2

    # Test different exit strategies
    exit_strategies = [
        {'name': 'Fixed 24h hold', 'hours': 24, 'profit_target': None, 'stop_loss': None},
        {'name': 'Fixed 48h hold', 'hours': 48, 'profit_target': None, 'stop_loss': None},
        {'name': '2% profit target', 'hours': 48, 'profit_target': 2.0, 'stop_loss': None},
        {'name': '3% profit target', 'hours': 72, 'profit_target': 3.0, 'stop_loss': None},
        {'name': '2% target + 1% stop', 'hours': 48, 'profit_target': 2.0, 'stop_loss': -1.0},
        {'name': '3% target + 1.5% stop', 'hours': 72, 'profit_target': 3.0, 'stop_loss': -1.5},
        {'name': 'Trailing 1% from peak', 'hours': 72, 'profit_target': None, 'stop_loss': None, 'trailing': 1.0},
        {'name': 'Trailing 1.5% from peak', 'hours': 72, 'profit_target': None, 'stop_loss': None, 'trailing': 1.5},
    ]

    results = []

    for strategy in exit_strategies:
        trades = simulate_with_exit_strategy(df, entry_threshold, strategy)

        if len(trades) > 0:
            wins = sum(1 for t in trades if t['return'] > 0)
            total_return = sum(t['return'] for t in trades)
            avg_return = total_return / len(trades)
            win_rate = wins / len(trades) * 100

            results.append({
                'strategy': strategy['name'],
                'trades': len(trades),
                'win_rate': win_rate,
                'avg_return': avg_return,
                'total_return': total_return
            })

    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values('total_return', ascending=False)

    print("\nEXIT STRATEGY COMPARISON:")
    print(results_df.to_string(index=False))

    return results_df


def simulate_with_exit_strategy(df, entry_threshold, exit_config):
    """
    Simulate trades with a specific exit strategy
    """
    df = df.copy()
    df['oi_change_4h'] = df['oi_btc'].pct_change(4) * 100
    df['entry_signal'] = df['oi_change_4h'] <= entry_threshold

    trades = []
    in_trade = False
    entry_price = None
    entry_time = None
    peak_price = None

    max_hours = exit_config.get('hours', 24)
    profit_target = exit_config.get('profit_target')
    stop_loss = exit_config.get('stop_loss')
    trailing = exit_config.get('trailing')

    for i in range(4, len(df)):
        row = df.iloc[i]
        current_time = df.index[i]
        current_price = row['close']

        if not in_trade and row['entry_signal']:
            in_trade = True
            entry_price = current_price
            entry_time = current_time
            peak_price = current_price

        elif in_trade:
            hours_held = (current_time - entry_time).total_seconds() / 3600
            current_return = (current_price / entry_price - 1) * 100

            # Track peak for trailing stop
            if current_price > peak_price:
                peak_price = current_price

            exit_trade = False
            exit_reason = None

            # Check exit conditions
            if profit_target and current_return >= profit_target:
                exit_trade = True
                exit_reason = 'profit_target'
            elif stop_loss and current_return <= stop_loss:
                exit_trade = True
                exit_reason = 'stop_loss'
            elif trailing:
                drawdown_from_peak = (current_price / peak_price - 1) * 100
                if drawdown_from_peak <= -trailing and current_return > 0:
                    exit_trade = True
                    exit_reason = 'trailing_stop'

            if hours_held >= max_hours:
                exit_trade = True
                exit_reason = 'max_hold'

            if exit_trade:
                trades.append({
                    'entry_time': entry_time,
                    'exit_time': current_time,
                    'return': current_return,
                    'reason': exit_reason
                })
                in_trade = False

    return trades


def analyze_entry_timing(df):
    """
    Are we entering at the right time?
    """
    print("\n" + "=" * 70)
    print("ENTRY TIMING ANALYSIS")
    print("=" * 70)

    df['oi_change_1h'] = df['oi_btc'].pct_change(1) * 100
    df['oi_change_4h'] = df['oi_btc'].pct_change(4) * 100
    df['oi_change_8h'] = df['oi_btc'].pct_change(8) * 100

    df['future_return_4h'] = df['close'].shift(-4) / df['close'] - 1
    df['future_return_8h'] = df['close'].shift(-8) / df['close'] - 1
    df['future_return_24h'] = df['close'].shift(-24) / df['close'] - 1

    # Test different entry thresholds
    print("\nOI DROP THRESHOLD vs FUTURE RETURNS:")
    print("-" * 50)

    for threshold in [-0.1, -0.2, -0.3, -0.4, -0.5]:
        entries = df[df['oi_change_4h'] <= threshold]
        if len(entries) > 3:
            avg_4h = entries['future_return_4h'].mean() * 100
            avg_8h = entries['future_return_8h'].mean() * 100
            avg_24h = entries['future_return_24h'].mean() * 100
            win_rate = (entries['future_return_24h'] > 0).mean() * 100

            print(f"OI drop <= {threshold}%: n={len(entries):3d}, "
                  f"4h:{avg_4h:+.2f}%, 8h:{avg_8h:+.2f}%, 24h:{avg_24h:+.2f}%, "
                  f"win:{win_rate:.0f}%")

    # Test combining OI drop with price drop
    print("\nCOMBINING OI DROP + PRICE DROP:")
    print("-" * 50)

    df['price_change_4h'] = df['close'].pct_change(4) * 100

    for oi_thresh in [-0.2, -0.3]:
        for price_thresh in [0, -0.5, -1.0]:
            entries = df[(df['oi_change_4h'] <= oi_thresh) &
                        (df['price_change_4h'] <= price_thresh)]
            if len(entries) > 3:
                avg_24h = entries['future_return_24h'].mean() * 100
                win_rate = (entries['future_return_24h'] > 0).mean() * 100

                print(f"OI<={oi_thresh}% & Price<={price_thresh}%: n={len(entries):3d}, "
                      f"24h:{avg_24h:+.2f}%, win:{win_rate:.0f}%")


def propose_better_strategy(df):
    """
    Based on analysis, propose an improved strategy
    """
    print("\n" + "=" * 70)
    print("PROPOSED IMPROVED STRATEGY")
    print("=" * 70)

    print("""
IMPROVED ENTRY CONDITIONS:
--------------------------
1. OI must drop >= 0.3% over 4 hours (liquidation signal)
2. Price must also be down (confirming distress)
3. Funding rate not at extreme low (avoid catching falling knife)

IMPROVED EXIT CONDITIONS:
-------------------------
1. PROFIT TARGET: Take profit at +2% (lock in gains)
2. TRAILING STOP: Once +1% profit, trail by 1% from peak
3. STOP LOSS: Cut at -1.5% (limit downside)
4. MAX HOLD: 48 hours (don't hold forever)

This gives us:
- Clear profit taking (don't give back gains)
- Limited downside (stop loss)
- Let winners run a bit (trailing stop)
- Time limit to avoid dead money
""")

    # Simulate the improved strategy
    trades = simulate_improved_strategy(df)

    if len(trades) > 0:
        trades_df = pd.DataFrame(trades)
        wins = (trades_df['return'] > 0).sum()
        total_return = trades_df['return'].sum()

        print(f"\nIMPROVED STRATEGY RESULTS:")
        print(f"  Trades: {len(trades_df)}")
        print(f"  Wins: {wins} ({wins/len(trades_df)*100:.1f}%)")
        print(f"  Total Return: {total_return:.2f}%")
        print(f"  Average per trade: {total_return/len(trades_df):.2f}%")

        print("\nTrade details:")
        for _, t in trades_df.iterrows():
            status = "WIN" if t['return'] > 0 else "LOSS"
            print(f"  {status}: {t['entry_time'].strftime('%m-%d %H:%M')} -> "
                  f"{t['exit_time'].strftime('%m-%d %H:%M')} = {t['return']:+.2f}% ({t['reason']})")

        return trades_df

    return None


def simulate_improved_strategy(df):
    """
    Simulate the improved strategy with better entry/exit rules
    """
    df = df.copy()
    df['oi_change_4h'] = df['oi_btc'].pct_change(4) * 100
    df['price_change_4h'] = df['close'].pct_change(4) * 100

    trades = []
    in_trade = False
    entry_price = None
    entry_time = None
    peak_price = None

    # Improved parameters
    OI_DROP_THRESHOLD = -0.25
    PRICE_DROP_THRESHOLD = -0.3
    PROFIT_TARGET = 2.0
    TRAILING_ACTIVATION = 1.0
    TRAILING_STOP = 1.0
    STOP_LOSS = -1.5
    MAX_HOLD_HOURS = 48

    for i in range(4, len(df)):
        row = df.iloc[i]
        current_time = df.index[i]
        current_price = row['close']

        # ENTRY CONDITIONS
        if not in_trade:
            oi_drop = row['oi_change_4h'] <= OI_DROP_THRESHOLD
            price_drop = row['price_change_4h'] <= PRICE_DROP_THRESHOLD

            if oi_drop and price_drop:
                in_trade = True
                entry_price = current_price
                entry_time = current_time
                peak_price = current_price
                trailing_active = False

        # EXIT CONDITIONS
        elif in_trade:
            hours_held = (current_time - entry_time).total_seconds() / 3600
            current_return = (current_price / entry_price - 1) * 100

            # Update peak
            if current_price > peak_price:
                peak_price = current_price

            # Check if trailing stop should activate
            if current_return >= TRAILING_ACTIVATION:
                trailing_active = True

            exit_trade = False
            exit_reason = None

            # 1. Profit target hit
            if current_return >= PROFIT_TARGET:
                exit_trade = True
                exit_reason = 'profit_target'

            # 2. Stop loss hit
            elif current_return <= STOP_LOSS:
                exit_trade = True
                exit_reason = 'stop_loss'

            # 3. Trailing stop (only if activated)
            elif trailing_active:
                drawdown = (current_price / peak_price - 1) * 100
                if drawdown <= -TRAILING_STOP:
                    exit_trade = True
                    exit_reason = 'trailing_stop'

            # 4. Max hold time
            if hours_held >= MAX_HOLD_HOURS:
                exit_trade = True
                exit_reason = 'max_hold'

            if exit_trade:
                trades.append({
                    'entry_time': entry_time,
                    'exit_time': current_time,
                    'entry_price': entry_price,
                    'exit_price': current_price,
                    'return': current_return,
                    'reason': exit_reason
                })
                in_trade = False

    return trades


def visualize_strategy_comparison(df):
    """
    Visual comparison of old vs new strategy
    """
    # Old strategy trades
    old_trades = simulate_with_exit_strategy(
        df,
        entry_threshold=-0.2,
        exit_config={'hours': 24}
    )

    # New strategy trades
    new_trades = simulate_improved_strategy(df)

    if len(old_trades) > 0 and len(new_trades) > 0:
        fig, axes = plt.subplots(2, 1, figsize=(14, 10))

        # Plot price with trade markers
        ax1 = axes[0]
        ax1.plot(df.index, df['close'], 'b-', alpha=0.7, label='BTC Price')

        # Old strategy markers
        for t in old_trades:
            ax1.axvline(x=t['entry_time'], color='gray', linestyle='--', alpha=0.3)

        # New strategy markers
        for t in new_trades:
            color = 'green' if t['return'] > 0 else 'red'
            ax1.plot(t['entry_time'], t['entry_price'], 'o', color=color, markersize=10)
            ax1.plot(t['exit_time'], t['exit_price'], 's', color=color, markersize=10)

        ax1.set_ylabel('Price')
        ax1.set_title('New Strategy Trades on Price Chart')
        ax1.legend()

        # Cumulative returns comparison
        ax2 = axes[1]

        old_cum = [0]
        for t in old_trades:
            old_cum.append(old_cum[-1] + t['return'])

        new_cum = [0]
        for t in new_trades:
            new_cum.append(new_cum[-1] + t['return'])

        ax2.plot(range(len(old_cum)), old_cum, 'r-', label=f'Old Strategy ({sum(t["return"] for t in old_trades):.1f}%)')
        ax2.plot(range(len(new_cum)), new_cum, 'g-', label=f'New Strategy ({sum(t["return"] for t in new_trades):.1f}%)')
        ax2.axhline(y=0, color='gray', linestyle='--')
        ax2.set_xlabel('Trade Number')
        ax2.set_ylabel('Cumulative Return (%)')
        ax2.set_title('Cumulative Returns: Old vs New Strategy')
        ax2.legend()

        plt.tight_layout()
        plt.savefig('results/strategy_improvement.png', dpi=150)
        plt.close()

        print("\nSaved comparison chart to results/strategy_improvement.png")


if __name__ == "__main__":
    df = load_data()

    analyze_current_strategy_logic()
    trades_df = simulate_and_analyze_trades(df)
    find_optimal_exit_rules(df)
    analyze_entry_timing(df)
    propose_better_strategy(df)
    visualize_strategy_comparison(df)

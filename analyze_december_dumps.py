"""
Detailed Analysis of December 10 AM Dumps

Shows every day in December with:
- 9:30 AM open price
- Prices during 10:00-10:59 AM
- Maximum dump % from 9:30 AM open
"""

import sys
sys.path.append('src')

import pandas as pd
from utils.data_fetcher import DataFetcher


def main():
    print("\n" + "="*80)
    print("📊 DECEMBER 2025: DETAILED DUMP ANALYSIS")
    print("="*80 + "\n")

    # Fetch data
    fetcher = DataFetcher()
    data = fetcher.fetch_ohlcv('BTC/USDT', '15m', days_back=33)
    dec_data = data[(data.index >= '2025-12-01') & (data.index < '2026-01-01')].copy()

    print(f"Period: {dec_data.index[0]} to {dec_data.index[-1]}")
    print(f"Total candles: {len(dec_data)}\n")

    # Add hour/minute columns
    dec_data['hour'] = dec_data.index.hour
    dec_data['minute'] = dec_data.index.minute
    dec_data['date'] = dec_data.index.date

    # Get all unique dates
    dates = sorted(dec_data['date'].unique())

    print("="*80)
    print("DAILY BREAKDOWN: 9:30 AM OPEN → 10 AM HOUR PRICES")
    print("="*80 + "\n")

    dump_days = []

    for date in dates:
        day_data = dec_data[dec_data['date'] == date]

        # Find 9:30 AM candle
        am_930 = day_data[(day_data['hour'] == 9) & (day_data['minute'] == 30)]

        # Find 10 AM hour candles (10:00, 10:15, 10:30, 10:45)
        am_10_hour = day_data[(day_data['hour'] == 10)]

        if len(am_930) == 0 or len(am_10_hour) == 0:
            continue

        open_930 = am_930['open'].iloc[0]

        # Get all prices during 10 AM hour
        prices_10am = []
        for idx, row in am_10_hour.iterrows():
            prices_10am.append({
                'time': idx.strftime('%H:%M'),
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close']
            })

        # Find minimum price during 10 AM hour (biggest dump)
        min_price = am_10_hour['low'].min()
        dump_pct = ((min_price - open_930) / open_930) * 100

        # Store days with dumps
        if dump_pct <= -0.5:  # Any dump >= 0.5%
            dump_days.append({
                'date': date,
                'open_930': open_930,
                'min_10am': min_price,
                'dump_pct': dump_pct,
                'prices': prices_10am
            })

        # Print daily summary
        print(f"📅 {date.strftime('%Y-%m-%d (%A)')}")
        print(f"   9:30 AM open: ${open_930:,.2f}")

        if len(prices_10am) > 0:
            print(f"   10 AM hour:")
            for p in prices_10am:
                dump_at_low = ((p['low'] - open_930) / open_930) * 100
                print(f"      {p['time']}: ${p['low']:,.2f} → {dump_at_low:+.2f}%")
            print(f"   Maximum dump: {dump_pct:.2f}%")

            if dump_pct <= -0.75:
                print(f"   ✅ DUMP >= 0.75% ✅")
            elif dump_pct <= -0.5:
                print(f"   ⚠️  Small dump (0.5-0.75%)")
        else:
            print(f"   ❌ No 10 AM data")

        print()

    # Summary
    print("="*80)
    print("📈 DUMP SUMMARY")
    print("="*80 + "\n")

    dumps_075 = [d for d in dump_days if d['dump_pct'] <= -0.75]
    dumps_050 = [d for d in dump_days if -0.75 < d['dump_pct'] <= -0.5]
    dumps_100 = [d for d in dump_days if d['dump_pct'] <= -1.0]
    dumps_150 = [d for d in dump_days if d['dump_pct'] <= -1.5]
    dumps_200 = [d for d in dump_days if d['dump_pct'] <= -2.0]
    dumps_250 = [d for d in dump_days if d['dump_pct'] <= -2.5]

    print(f"Total trading days analyzed: {len(dates)}")
    print(f"\nDumps by threshold:")
    print(f"  >= 0.50%: {len(dump_days)} days")
    print(f"  >= 0.75%: {len(dumps_075)} days")
    print(f"  >= 1.00%: {len(dumps_100)} days")
    print(f"  >= 1.50%: {len(dumps_150)} days")
    print(f"  >= 2.00%: {len(dumps_200)} days")
    print(f"  >= 2.50%: {len(dumps_250)} days")

    if len(dumps_075) > 0:
        print(f"\n" + "="*80)
        print(f"DAYS WITH >= 0.75% DUMP:")
        print("="*80 + "\n")

        for d in dumps_075:
            print(f"{d['date'].strftime('%Y-%m-%d (%A)')}")
            print(f"  9:30 AM: ${d['open_930']:,.2f}")
            print(f"  10 AM low: ${d['min_10am']:,.2f}")
            print(f"  Dump: {d['dump_pct']:.2f}%\n")

    # Reality check
    print("="*80)
    print("🎯 REALITY CHECK")
    print("="*80 + "\n")

    if len(dumps_075) <= 3:
        print(f"✅ YES - December only had {len(dumps_075)} days with >= 0.75% dumps at 10 AM")
        print("\nThis means:")
        print("  - The '10 AM dump' pattern is NOT common in December 2025")
        print("  - This is a LOW-FREQUENCY pattern")
        print(f"  - Only {len(dumps_075)}/{len(dates)} trading days ({len(dumps_075)/len(dates)*100:.1f}%) showed this pattern")
    else:
        print(f"There were {len(dumps_075)} days with >= 0.75% dumps")

    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()

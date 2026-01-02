# 🔬 Cryptocurrency Backtesting Lab

**Test your trading ideas before risking real money.**

This is a backtesting system where you can:
1. Come up with a trading strategy idea
2. Test it on historical price data
3. See if it would have made or lost money

---

## 🧠 What is Backtesting?

**Backtesting = simulating trades on historical data**

Imagine you have a time machine. You could go back to January 1st with $10,000 and test your strategy:
- "Buy when price crosses above 20-day average"
- "Sell when RSI goes above 70"
- "Buy when spot/perp diverge by 2%"

Backtesting does exactly that - but with code instead of a time machine.

**⚠️ Important Reality Check:**
- Past performance ≠ future results
- Backtests are overly optimistic (no slippage, perfect fills, hindsight bias)
- BUT: If a strategy loses money in backtest, it will **definitely** lose money in real trading

Backtesting helps you eliminate bad ideas quickly.

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd /Users/chrisl/backtesting

# Activate virtual environment
source venv/bin/activate

# Install required libraries
pip install -r requirements.txt
```

### 2. Run the Example

```bash
python run_backtest.py
```

This will:
- Download 90 days of BTC/USDT hourly data from Binance
- Test a simple moving average crossover strategy
- Show you results with charts
- Save chart to `results/` folder

### 3. Check the Results

Look at:
- **Console output**: Trade-by-trade log, final metrics
- **Chart**: `results/BTC_USDT_1h_90d.png`
  - Top: Portfolio value over time
  - Middle: Price with buy/sell markers
  - Bottom: Drawdown (how much you lost from peak)

---

## 📁 Project Structure

```
backtesting/
├── run_backtest.py              # Main script - run this to test strategies
├── requirements.txt             # Python dependencies
│
├── src/
│   ├── backtester.py            # Core engine - simulates trades
│   ├── strategies/
│   │   └── moving_average_cross.py    # Example strategy (MA crossover)
│   └── utils/
│       ├── data_fetcher.py      # Downloads historical data from Binance
│       └── visualizer.py        # Creates charts
│
├── data/                        # Cached price data (CSV files)
└── results/                     # Generated charts (PNG files)
```

---

## 🎯 How to Test Your Own Ideas

### Method 1: Modify Parameters (Easiest)

Open `run_backtest.py` and change:

```python
# Test different cryptocurrencies
SYMBOL = 'ETH/USDT'      # Try ETH, SOL, BNB, etc.

# Test different timeframes
TIMEFRAME = '15m'        # Options: 1m, 5m, 15m, 1h, 4h, 1d

# Test different history lengths
DAYS_BACK = 180          # More data = more reliable results

# Test different strategy parameters
strategy = MovingAverageCrossStrategy(
    fast_period=10,      # Try 10, 20, 30, 50
    slow_period=30       # Try 30, 50, 100, 200
)
```

Then run: `python run_backtest.py`

### Method 2: Write Your Own Strategy (More Advanced)

Create a new file: `src/strategies/your_idea.py`

```python
class YourStrategy:
    def __init__(self, param1, param2):
        self.param1 = param1
        self.param2 = param2

    def generate_signals(self, data):
        """
        Args:
            data: DataFrame with columns: open, high, low, close, volume

        Returns:
            DataFrame with 'signal' column: 'BUY', 'SELL', or 'HOLD'
        """
        df = data.copy()
        df['signal'] = 'HOLD'

        # YOUR LOGIC HERE
        # Example: Buy when price drops 5% from recent high
        df['recent_high'] = df['close'].rolling(20).max()
        df['drop_pct'] = (df['close'] - df['recent_high']) / df['recent_high'] * 100

        df.loc[df['drop_pct'] < -5, 'signal'] = 'BUY'
        df.loc[df['drop_pct'] > -1, 'signal'] = 'SELL'

        return df[['signal']]
```

Then in `run_backtest.py`:

```python
from strategies.your_idea import YourStrategy
strategy = YourStrategy(param1=10, param2=20)
```

---

## 📊 Understanding the Results

### Key Metrics Explained

**Total Return %**
- How much money did you make/lose?
- Example: +25% means $10,000 → $12,500

**Buy & Hold Return %**
- What if you just bought at the start and held?
- Compare this to your strategy - are you beating simple buy & hold?

**Win Rate**
- What % of trades were profitable?
- 60% win rate = 6 out of 10 trades made money
- ⚠️ High win rate doesn't mean profitable! (could have small wins, big losses)

**Max Drawdown**
- Largest peak-to-valley loss
- Example: -15% means at worst, you were down 15% from your highest point
- This is your pain tolerance - can you stomach a -30% drawdown?

**Total Trades**
- How often does the strategy trade?
- Too many trades = high fees eat your profit
- Too few trades = not enough data to judge effectiveness

---

## 💡 Strategy Ideas to Test

Here are some ideas you can implement:

1. **RSI Oversold/Overbought**
   - Buy when RSI < 30 (oversold)
   - Sell when RSI > 70 (overbought)

2. **Bollinger Band Bounce**
   - Buy when price touches lower band
   - Sell when price touches upper band

3. **Volume Spike Breakout**
   - Buy when volume > 2x average AND price breaks resistance
   - Sell when volume dies down

4. **Spot-Perp Divergence** (requires fetching both spot and futures data)
   - Buy spot when perp premium > 2%
   - Sell when premium < 0.5%

5. **News-Based** (would need external data)
   - Buy on certain events
   - Sell after X hours

6. **Your Own Hunch**
   - "I notice price tends to X when Y happens"
   - Test it!

---

## 🛠️ Common Tasks

### Change to Different Coin

```python
# In run_backtest.py
SYMBOL = 'ETH/USDT'  # Anything Binance supports
```

### Test Longer History

```python
DAYS_BACK = 365  # Test a full year
```

**Note:** Binance limits historical data. For 1-minute candles, you can only go back ~30 days. For daily candles, you can go back years.

### Adjust Starting Capital

```python
# In run_backtest.py
backtester = Backtester(
    initial_capital=50000,  # Start with $50k instead of $10k
    fee_percent=0.1
)
```

### Change Trading Fees

```python
fee_percent=0.075  # VIP fee tier
fee_percent=0.5    # Simulate higher DEX fees
```

---

## 🧪 Data Sources

**Where does data come from?**
- Binance public API (no account needed)
- Free, historical OHLCV (Open, High, Low, Close, Volume) candles
- Same data that professional traders use

**What timeframes are available?**
- 1m, 3m, 5m, 15m, 30m (minutes)
- 1h, 2h, 4h, 6h, 8h, 12h (hours)
- 1d, 3d (days)
- 1w (week)
- 1M (month)

**Data limitations:**
- Binance limits to 1000 candles per request (the fetcher handles this automatically)
- Shorter timeframes = less history available
- Data starts from when Binance listed that coin

---

## 🔍 Reading the Code

**Start here to understand the system:**

1. **`run_backtest.py`** - The main script, see the big picture
2. **`src/backtester.py`** - The engine, understand how trades are simulated
3. **`src/strategies/moving_average_cross.py`** - Example strategy, see the pattern
4. **`src/utils/data_fetcher.py`** - How data is downloaded
5. **`src/utils/visualizer.py`** - How charts are made

---

## ⚠️ Important Notes

### This is NOT Ready for Live Trading

This backtester is simplified and missing:
- **Slippage**: Real orders don't fill at exact prices
- **Market impact**: Your orders move the price
- **Partial fills**: Orders don't always fill completely
- **Liquidity**: Can't always buy/sell when you want
- **Funding rates**: Futures have ongoing costs
- **Server delays**: Real trading has latency
- **Emotional factors**: Backtests don't feel fear/greed

**Real trading results will be worse than backtest results.**

### Avoiding Common Mistakes

❌ **Don't overfit**
- Testing 100 parameter combinations until one works = finding noise, not signal
- That "perfect" setting will fail on new data

❌ **Don't ignore fees**
- 0.1% per trade = 0.2% round trip
- Trading 50 times = 10% of capital lost to fees
- High-frequency strategies die from fees

❌ **Don't cherry-pick time periods**
- "My strategy made 200% in May 2021!" (bull market)
- Test across bull, bear, and sideways markets

✅ **Do keep it simple**
- Simple strategies are more robust
- Complex strategies usually overfit

✅ **Do test on unseen data**
- Optimize on 2023 data
- Validate on 2024 data
- If it works on both = more confidence

✅ **Do understand WHY it works**
- "It works because..." vs "I don't know but numbers look good"
- If you can't explain why, it's probably random luck

---

## 🎓 Learning Path

1. **Run the example** - See how everything connects
2. **Modify parameters** - Change periods, symbols, timeframes
3. **Read the code** - Understand how the backtester works
4. **Implement simple strategy** - Try RSI or Bollinger Bands
5. **Compare strategies** - Which performs better?
6. **Understand the limitations** - Why backtest ≠ reality

---

## 📚 Next Steps

Once you're comfortable:

- Add more technical indicators (pandas-ta library)
- Implement position sizing (risk % of portfolio)
- Add stop-loss and take-profit logic
- Test multiple timeframes simultaneously
- Compare multiple strategies side-by-side
- Add Monte Carlo simulation (random walk forward)

---

## 🤝 Working Together

**When you have a trading idea:**

1. Describe it to me in plain English
2. I'll implement it as a strategy
3. We'll run a backtest
4. We'll analyze if it has merit

**Example:**
> "I think buying when BTC drops 10% from its 30-day high works well. Sell when it recovers to 5% below the high."

I'll turn that into code, test it, and show you the results.

---

## 📝 Notes

- This backtester uses **all capital per trade** (100% in or out)
- Could be extended to: partial positions, dollar-cost averaging, rebalancing
- Currently only tests **long** positions (buy low, sell high)
- Could be extended to: short selling, futures, options

**The goal: Learn what works, what doesn't, and why.**

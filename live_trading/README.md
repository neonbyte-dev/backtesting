# Overnight Recovery Trading Bot

Automated trading bot implementing the optimized overnight recovery strategy (+17.95% in December 2025).

**⚠️ IMPORTANT: This bot trades real money. Start with testnet and small amounts.**

---

## Quick Start

### 1. Install Dependencies

```bash
cd live_trading
pip install -r requirements.txt
```

### 2. Setup Credentials

Copy the template and add your credentials:

```bash
cp .env.template .env
chmod 600 .env  # Secure the file
```

Edit `.env` and add:
- HyperLiquid API key and secret
- Telegram bot token and chat ID

### 3. Configure Strategy

Edit `config.json`:
- Set `"testnet": true` for testing (fake money)
- Set `"enable_trading": true` when ready to trade

### 4. Test Components

Test each component individually:

```bash
# Test exchange connection
python src/exchange.py

# Test Telegram notifications
python src/notifier.py

# Test strategy logic
python src/strategy.py
```

### 5. Run Bot

```bash
python bot.py
```

The bot will:
- Check conditions every 5 minutes
- Buy at 3 PM EST if price < $90K
- Sell when trailing stop (1%) hit
- Send Telegram alerts on all actions

---

## Setup Guide

### HyperLiquid API Setup

1. Go to https://app.hyperliquid.xyz/API
2. Create a new API key
3. **IMPORTANT**: Select "Trading" permissions ONLY (no withdrawal)
4. Copy the key and secret to `.env` file

For testnet:
1. Go to https://app.hyperliquid-testnet.xyz
2. Request testnet funds (free)
3. Create API key following same steps

### Telegram Bot Setup

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow instructions
3. Copy the bot token to `.env`
4. To get your chat ID:
   - Message [@userinfobot](https://t.me/userinfobot)
   - Copy your ID to `.env`

Test the connection:
```bash
python src/notifier.py
```

You should receive a test message in Telegram.

---

## Configuration

Edit `config.json` to customize behavior:

### Strategy Settings

```json
{
  "strategy": {
    "entry_hour": 15,              // 3 PM EST
    "max_entry_price_usd": 90000,  // Don't buy above $90K
    "trailing_stop_pct": 1.0,      // Exit if drops 1% from peak
    "timezone": "America/New_York"
  }
}
```

**These are optimized values from backtesting. Only change if you understand the impact.**

### Risk Settings

```json
{
  "risk": {
    "max_daily_loss_pct": 5.0,        // Stop if down 5% in one day
    "max_consecutive_losses": 3,      // Stop after 3 losses in a row
    "position_size_pct": 100          // Use 100% of capital per trade
  }
}
```

**Circuit breakers protect against catastrophic losses. Don't disable them.**

### Bot Settings

```json
{
  "bot": {
    "loop_interval_seconds": 300,      // Check every 5 minutes
    "heartbeat_interval_hours": 1,     // Send heartbeat every hour
    "enable_trading": false            // Set true to enable real trades
  }
}
```

**Set `enable_trading: false` while testing to avoid accidental trades.**

---

## Testing Strategy (Follow This!)

### Week 1: Local Development ✅ (COMPLETE)
All components are built and ready.

### Week 2: Testnet Validation

**Goal**: Prove the bot works without risking real money.

1. Set in `config.json`:
   ```json
   {
     "exchange": { "testnet": true },
     "bot": { "enable_trading": true }
   }
   ```

2. Run bot for 7-10 days:
   ```bash
   python bot.py
   ```

3. Monitor:
   - Does it enter at 3 PM EST?
   - Does it exit at correct trailing stop?
   - Do Telegram alerts arrive?
   - Does state persist across restarts?

4. Success criteria:
   - ✅ 7+ days uptime
   - ✅ All trades match strategy rules
   - ✅ No crashes
   - ✅ Alerts working

### Week 3: Small Capital ($1,000)

**Goal**: Validate with real money (small amount).

1. Set in `config.json`:
   ```json
   {
     "exchange": { "testnet": false },
     "bot": { "enable_trading": true }
   }
   ```

2. Fund HyperLiquid account with **$1,000**

3. Run for 10+ trades

4. Verify:
   - Actual returns match backtest expectations (~18%/month)
   - Slippage is acceptable (< 0.1% per trade)
   - No critical errors

### Week 4: Scale to $100K

**CRITICAL: Scale gradually!**

- Week 4.1: $1K → $10K (monitor 5 trades)
- Week 4.2: $10K → $50K (monitor 5 trades)
- Week 4.3: $50K → $100K (monitor carefully)

**Why gradual scaling?**
If something breaks, you lose $5K not $100K.

---

## Monitoring

### Daily Routine

1. Check 9 AM summary message (Telegram)
2. Verify heartbeat messages arrive hourly
3. Glance at trade alerts (if any)

### What to Watch For

**Good signals**:
- 💚 Heartbeat messages arrive every hour
- Trades execute at correct times (3 PM entry)
- Win rate around 70-75%
- Returns around +15-18%/month

**Warning signs**:
- ⚠️ Missing heartbeats (bot may have crashed)
- Trades at wrong times
- Win rate below 50%
- Circuit breakers triggering frequently

### Logs

Bot writes detailed logs to `logs/trades_YYYY-MM-DD.log`:

```bash
# View today's log
tail -f logs/trades_$(date +%Y-%m-%d).log

# Search for errors
grep ERROR logs/*.log
```

---

## Emergency Procedures

### Stop the Bot Immediately

**Method 1: STOP file**
```bash
cd live_trading
touch STOP
```
Bot will detect this and shut down safely.

**Method 2: Keyboard interrupt**
Press `Ctrl+C` in the terminal.

### Force Close Position

If you need to manually exit a position:

1. Go to https://app.hyperliquid.xyz
2. Close position manually
3. Update `state/state.json`:
   ```json
   {
     "in_position": false,
     ...
   }
   ```

### Bot Crashed - What to Do

1. **Check position**: Go to HyperLiquid, see if you're in a trade
2. **Review logs**: Check `logs/` for error messages
3. **Restart bot**: `python bot.py`
4. **Verify state**: Bot should resume from where it left off

The bot saves state after every action, so it will remember:
- Are we in a position?
- What was entry price?
- What's the peak price?

---

## File Structure

```
live_trading/
├── bot.py                    # START HERE - Main entry point
├── config.json               # Strategy configuration
├── .env                      # API credentials (SECRET - never commit)
├── requirements.txt          # Python dependencies
├── README.md                 # This file
│
├── src/
│   ├── exchange.py           # HyperLiquid API client
│   ├── strategy.py           # Strategy logic (buy/sell decisions)
│   ├── notifier.py           # Telegram alerts
│   ├── state_manager.py      # Position state persistence
│   └── risk_manager.py       # Circuit breakers
│
├── logs/
│   └── trades_YYYY-MM-DD.log # Daily trade logs
│
└── state/
    ├── state.json            # Current position state
    └── state_backup.json     # Backup (in case of corruption)
```

---

## Troubleshooting

### "ERROR: HYPERLIQUID_API_KEY not found"

Your `.env` file is missing or not loaded.

**Fix**:
```bash
cp .env.template .env
# Edit .env and add your credentials
```

### "Telegram message failed to send"

Your Telegram credentials are incorrect.

**Fix**:
1. Verify bot token from [@BotFather](https://t.me/BotFather)
2. Verify chat ID from [@userinfobot](https://t.me/userinfobot)
3. Test: `python src/notifier.py`

### "Circuit breaker triggered: Daily loss -5%"

The bot detected excessive losses and paused trading.

**What to do**:
1. Review trades in logs
2. Check if market conditions changed
3. Decide: Resume tomorrow or investigate further

### Bot keeps crashing

Check the error logs:
```bash
grep ERROR logs/*.log
```

Common causes:
- Network issues (HyperLiquid API down)
- Invalid API credentials
- System resources (out of memory)

---

## Safety Checklist

Before going live with real money:

- [ ] Tested on testnet for 7+ days
- [ ] Telegram alerts working
- [ ] Verified trades execute at correct times
- [ ] State persists across restarts
- [ ] Circuit breakers tested (set low limits and trigger them)
- [ ] Started with small capital ($1K)
- [ ] Monitored for 10+ trades
- [ ] Performance matches backtest expectations
- [ ] Scaled gradually to final amount

**DO NOT skip these steps with $100K on the line!**

---

## Risk Warnings

⚠️ **Past Performance Disclaimer**
This strategy was optimized on December 2025 data. Future performance may differ.

⚠️ **Market Regime Dependency**
Strategy works best in ranging markets. May underperform in strong trends.

⚠️ **24/7 Operation**
Bot holds positions overnight, exposed to gap risk and crypto volatility.

⚠️ **No Guarantees**
Automated trading carries risk of total capital loss. Never trade more than you can afford to lose.

---

## Support

If you encounter issues:

1. Check logs: `logs/trades_*.log`
2. Review this README
3. Test individual components: `python src/exchange.py`, etc.
4. Check state file: `cat state/state.json`

---

## Next Steps

1. ✅ Read this entire README
2. ✅ Setup credentials (.env file)
3. ✅ Test on testnet (Week 2)
4. ✅ Small capital test (Week 3)
5. ✅ Scale gradually (Week 4)
6. ✅ Monitor daily

**Good luck and trade safely!** 🚀

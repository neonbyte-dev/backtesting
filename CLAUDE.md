# Project: Trader Strategy Bot

## Master Credentials

**IMPORTANT:** When you need to log into any service (Clickhouse, APIs, etc.), check the master credentials file:

```
/Users/chrisl/Claude Code/master-credentials.env
```

This file contains all API keys, database credentials, and service logins.

## Key Services

- **Clickhouse Database**: `ch.ops.xexlab.com` - Contains Discord messages, trading signals
- **Hyperliquid**: Trading API for live bot
- **Telegram**: Bot notifications

## Data Sources

- BH Insights messages are stored in Clickhouse database `crush_ats`
- CSV export at `data/bh_insights_messages.csv` may be incomplete - always verify against Clickhouse

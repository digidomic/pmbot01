# PM Bot - Polymarket Copy Trading Bot

🤖 **PM Bot** is an automated trading bot for Polymarket with multiple strategies:
- **Copy Trading**: Monitor and copy trades from target users
- **Bitcoin Arbitrage**: Detect BTC price movements and trade prediction markets

## 🆕 Architecture v2.0 - Separated Dashboard + Bot

The bot now supports a **separated architecture** where:
- **Dashboard** runs on your local machine or main server
- **Bot** (Scraper + Trader) runs on a VPS with proxy support
- **Database** can be shared via PostgreSQL (recommended) or SQLite

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Dashboard     │────▶│   PostgreSQL    │◀────│  Bot (VPS)      │
│  (Local/Main)   │     │   Database      │     │  (With Proxy)   │
│   Port 8080     │     │   Port 5432     │     │   Polymarket    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                                                  ┌─────────┐
                                                  │  Proxy  │
                                                  │ Server  │
                                                  └─────────┘
```

## 🚀 Features

- **Real-time Trade Monitoring**: Automatically detects new trades from target users
- **Smart Scaling**: Copy trades with configurable percentage scaling and max amount limits
- **Bitcoin Arbitrage**: WebSocket-powered BTC price monitoring with momentum detection
- **Web Dashboard**: Live monitoring with trade history, statistics, and configuration
- **Proxy Support**: Route all external API calls through a proxy (for VPS deployments)
- **Separated Architecture**: Run bot and dashboard on different machines
- **Latency Tracking**: Measure and display trade execution latency
- **24/7 Stability**: Robust error handling and graceful recovery
- **Modular Architecture**: Separate components for easy maintenance

## 🏗️ Project Structure

```
pmbot01/
├── scraper/              # Polymarket Activity Scraping
│   └── polymarket_scraper.py   # With proxy support
├── trader/               # CLOB Client Integration
├── strategies/           # Trading strategies
├── dashboard/            # Web-UI (Flask + SocketIO)
├── config/               # Settings management
│   ├── settings.py       # Main config
│   ├── proxy_config.py   # NEW: Proxy configuration
│   └── network_config.py # NEW: Network/database config
├── database/             # SQLite/PostgreSQL support
├── run_bot_only.py       # NEW: Start bot only (with proxy)
├── run_dashboard_only.py # NEW: Start dashboard only
├── main.py               # Legacy: Combined mode
├── docker-compose.yml    # Docker deployment
├── .env.example          # Configuration template
└── README.md             # This file
```

## 📋 Requirements

- Python 3.8+
- Polymarket API credentials
- Linux/macOS/Windows (tested on Linux)
- For separated architecture: PostgreSQL (optional, SQLite works locally)

## ⚡ Quick Start

### Option 1: All-in-One (Simple)

Run everything on one machine:

```bash
git clone https://github.com/digidomic/pmbot01.git
cd pmbot01
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
python main.py
```

### Option 2: Separated Architecture (Recommended)

Run bot on VPS with proxy, dashboard locally:

#### Step 1: Setup Database (on main server)

```bash
# Using Docker Compose
docker-compose up -d db
```

Or use a managed PostgreSQL service.

#### Step 2: Configure Environment

```bash
cp .env.example .env
```

**On VPS (Bot only):**
```env
DB_TYPE=postgresql
DB_HOST=your-db-server-ip
DB_PORT=5432
DB_NAME=pmbot
DB_USER=pmbot
DB_PASSWORD=your_secure_password

USE_PROXY=true
PROXY_HOST=es.proxy.iproyal.com
PROXY_PORT=12321
PROXY_USERNAME=your_proxy_user
PROXY_PASSWORD=your_proxy_pass

POLYMARKET_API_KEY=your_key
POLYMARKET_SECRET=your_secret
POLYMARKET_PASSPHRASE=your_passphrase
```

**On Local (Dashboard only):**
```env
DB_TYPE=postgresql
DB_HOST=your-db-server-ip
DB_PORT=5432
DB_NAME=pmbot
DB_USER=pmbot
DB_PASSWORD=your_secure_password

DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8080
```

#### Step 3: Start Services

**On VPS (Bot):**
```bash
python run_bot_only.py
# Or with Docker:
docker-compose up -d bot
```

**On Local (Dashboard):**
```bash
python run_dashboard_only.py
# Or with Docker:
docker-compose up -d dashboard
```

## 🐳 Docker Deployment

### Full Stack (Recommended)

```bash
# 1. Configure
cp .env.example .env
# Edit .env with your credentials

# 2. Start all services
docker-compose up -d

# 3. View logs
docker-compose logs -f bot
docker-compose logs -f dashboard

# 4. Stop
docker-compose down
```

### Legacy Mode (Single Container)

```bash
docker-compose --profile legacy up -d pmbot
```

### Separate Services

```bash
# Database only
docker-compose up -d db

# Bot only (with proxy)
docker-compose up -d bot

# Dashboard only
docker-compose up -d dashboard
```

## 🔧 Configuration

### Environment Variables (.env)

#### Proxy Settings (for VPS)

```env
# Enable proxy for external API calls
USE_PROXY=true
PROXY_HOST=es.proxy.iproyal.com
PROXY_PORT=12321
PROXY_USERNAME=your_proxy_username
PROXY_PASSWORD=your_proxy_password
```

#### Database Settings

```env
# SQLite (local, simple)
DB_TYPE=sqlite
DATABASE_PATH=database/trades.db

# PostgreSQL (network, recommended for separated architecture)
DB_TYPE=postgresql
DB_HOST=localhost      # Or remote DB server IP
DB_PORT=5432
DB_NAME=pmbot
DB_USER=pmbot
DB_PASSWORD=your_secure_password
```

#### Trading Settings

```env
# Polymarket API Credentials
POLYMARKET_API_KEY=your_api_key_here
POLYMARKET_SECRET=your_secret_here
POLYMARKET_PASSPHRASE=your_passphrase_here

# Target User to Copy
TARGET_USER_URL=https://polymarket.com/profile/@0x8dxd
TARGET_USERNAME=0x8dxd

# Trading Settings
MAX_TRADE_AMOUNT_USDC=50
TRADE_PERCENTAGE=10
MAX_TRADES_TO_TRACK=20
DRY_RUN=true          # Set to false for live trading

# Dashboard
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8080
```

### Trading Logic

- **Amount Calculation**: `min(original_amount * (percentage / 100), max_amount)`
- **Minimum Trade**: 1 USDC
- **Latency**: Time between target trade detection and copy execution

## 🎛️ Dashboard Features

- **Live Statistics**: Total trades, volume, P&L, average latency
- **Trade History**: Filterable view of target and copied trades
- **Real-time Updates**: WebSocket-powered live updates
- **Settings Panel**: Configure trading parameters on-the-fly
- **Bot Control**: Start/stop bot from dashboard
- **Profile Management**: Switch between target users

## 🛠️ Running Modes

```bash
# Combined mode (legacy)
python main.py

# Bot only (for VPS with proxy)
python run_bot_only.py

# Dashboard only (stateless)
python run_dashboard_only.py

# Copy Trading explicitly
python main.py --strategy=copy

# Bitcoin Arbitrage Strategy
python main.py --strategy=bitcoin_arbitrage

# Custom dashboard port
python run_dashboard_only.py
# Or set DASHBOARD_PORT in .env
```

## 🎯 Trading Strategies

### 1. Copy Trading (Default)

Monitors a target user's trades and copies them with configurable scaling.

**Usage**:
```bash
python run_bot_only.py  # Default strategy
```

**Features**:
- Real-time monitoring of target user activity
- Configurable trade scaling (percentage + max amount)
- Automatic market validation
- Latency tracking
- Proxy support for VPS deployments

### 2. Bitcoin Arbitrage Strategy

Monitors BTC price movements via Coinbase WebSocket and trades Bitcoin prediction markets on Polymarket.

**Usage**:
```bash
python main.py --strategy=bitcoin_arbitrage
```

**Features**:
- Real-time BTC price feed from Coinbase
- Momentum-based signal generation
- Dynamic threshold adjustment based on volatility
- Position management with profit targets and stop-loss
- Automatic market discovery on Polymarket

## 🌐 Network Architecture Guide

### Scenario 1: Local Development

```
Local Machine:
├── Bot (with or without proxy)
├── Dashboard
└── SQLite Database
```

**Setup:**
```env
DB_TYPE=sqlite
USE_PROXY=false  # or true if you want to test proxy
```

### Scenario 2: VPS with Proxy (Production)

```
VPS (with Proxy):
├── Bot (uses proxy for Polymarket)
└── PostgreSQL Database

Your Computer:
└── Dashboard (connects to VPS database)
```

**Setup:**

On VPS:
```env
DB_TYPE=postgresql
DB_HOST=localhost
USE_PROXY=true
PROXY_HOST=es.proxy.iproyal.com
# ... other proxy settings
```

On your computer:
```env
DB_TYPE=postgresql
DB_HOST=vps-ip-address
# ... database credentials
```

### Scenario 3: Cloud Database (e.g., Supabase, AWS RDS)

```
Cloud Database (PostgreSQL)
     ▲
     │
┌────┴────┐        ┌─────────────┐
│   Bot   │        │  Dashboard  │
│  (VPS)  │        │  (Local)    │
└────┬────┘        └─────────────┘
     │
  (Proxy)
```

## 🔒 Security Notes

- Never commit `.env` file (it's in `.gitignore`)
- API credentials are sensitive - store securely
- Use strong passwords for PostgreSQL
- Restrict database access with firewall rules
- Use proxy for additional IP anonymity (if needed)
- Bot runs with full trading permissions

### Database Security

```bash
# If self-hosting PostgreSQL, restrict access:
# pg_hba.conf
hostssl pmbot pmbot 0.0.0.0/0 scram-sha-256

# Or restrict to specific IPs:
hostssl pmbot pmbot your-vps-ip/32 scram-sha-256
hostssl pmbot pmbot your-local-ip/32 scram-sha-256
```

## 📊 Monitoring

- **Logs**: Check `pmbot.log` or `docker-compose logs`
- **Dashboard**: Real-time monitoring via web interface
- **Database**: Query directly for custom reports

### Health Checks

```bash
# Check bot is running
docker-compose ps

# Check database connection
docker-compose exec bot python -c "from database.db import get_db; print(get_db().check_connection())"

# View recent logs
docker-compose logs --tail 100 -f bot
```

## ⚠️ Risk Warning

Trading on Polymarket involves significant financial risk. This bot copies trades automatically without human intervention. Use with caution and only risk what you can afford to lose.

## 🆘 Troubleshooting

### Common Issues

**Database Connection Failed**
```
# Check PostgreSQL is running
docker-compose ps db
docker-compose logs db

# Verify credentials in .env
cat .env | grep DB_
```

**Proxy Connection Failed**
```
# Test proxy connectivity
curl -x http://user:pass@host:port https://clob.polymarket.com

# Check proxy config in .env
cat .env | grep PROXY
```

**CLOB Client Initialization Failed**
- Check API credentials in `.env`
- Verify network connectivity to Polymarket
- If using proxy, ensure proxy allows Polymarket traffic

**No Trades Detected**
- Confirm target username is correct
- Check Polymarket profile visibility
- Review logs for scraping errors
- Check if proxy is blocking requests

**Dashboard Not Loading**
- Check port availability
- Verify Flask installation
- Check firewall settings
- Confirm database connection

### Debug Mode

```bash
LOG_LEVEL=DEBUG python run_bot_only.py
LOG_LEVEL=DEBUG python run_dashboard_only.py
```

## 🔌 API Reference

### REST Endpoints

- `GET /api/stats` - Get trading statistics
- `GET /api/trades` - Get trade history
- `GET /api/config` - Get current configuration
- `POST /api/config` - Update configuration
- `GET /api/bot/state` - Get bot state (running/paused)
- `POST /api/bot/state` - Toggle bot state

### WebSocket Events

- `new_trade` - New trade detected/executed
- `stats_update` - Statistics updated
- `config_update` - Configuration changed
- `bot_state_update` - Bot state changed

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📝 License

MIT License - see LICENSE file for details

---

**Built with ❤️ for the Polymarket community**

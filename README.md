# PM Bot - Polymarket Copy Trading Bot

🤖 **PM Bot** is an automated copy trading bot for Polymarket that monitors a target user's trades and executes scaled copies in real-time.

## 🚀 Features

- **Real-time Trade Monitoring**: Automatically detects new trades from target users
- **Smart Scaling**: Copy trades with configurable percentage scaling and max amount limits
- **Web Dashboard**: Live monitoring with trade history, statistics, and configuration
- **Latency Tracking**: Measure and display trade execution latency
- **24/7 Stability**: Robust error handling and graceful recovery
- **Modular Architecture**: Separate components for easy maintenance

## 🏗️ Architecture

```
pmbot01/
├── scraper/          # Polymarket Activity Scraping
├── trader/           # CLOB Client Integration
├── dashboard/        # Web-UI (Flask/FastAPI + simple HTML/JS)
├── config/           # Settings management
├── database/         # SQLite für Trade-History
├── main.py           # Entry point
├── requirements.txt
├── .env.example
└── README.md
```

## 📋 Requirements

- Python 3.8+
- Polymarket API credentials
- Linux/macOS/Windows (tested on Linux)

## ⚡ Quick Start

1. **Clone & Setup**:
   ```bash
   git clone https://github.com/digidomic/pmbot01.git
   cd pmbot01
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Credentials**:
   ```bash
   cp .env.example .env
   # Edit .env with your Polymarket credentials
   ```

4. **Run the Bot**:
   ```bash
   python main.py
   ```

5. **Access Dashboard**:
   Open http://localhost:8080 in your browser

## 🐳 Docker Deployment

For easier deployment, use Docker Compose:

1. **Configure Credentials**:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

2. **Start with Docker Compose**:
   ```bash
   docker-compose up -d
   ```

3. **View Logs**:
   ```bash
   docker-compose logs -f
   ```

4. **Stop**:
   ```bash
   docker-compose down
   ```

The dashboard will be available on port 8080.

## 🔧 Configuration

### Environment Variables (.env)

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

# Dashboard
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8080

# Database
DATABASE_PATH=database/trades.db

# Logging
LOG_LEVEL=INFO

# Polling Interval (seconds)
POLL_INTERVAL=30
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

## 🛠️ Development

### Running Modes

```bash
# Full bot (trading + dashboard)
python main.py

# Dashboard only
python main.py --dashboard-only

# Trading only
python main.py --trade-only

# Custom dashboard port
python main.py --port 3000
```

### Components

- **`scraper/`**: Polymarket profile scraping (fallback to web scraping)
- **`trader/`**: CLOB client integration for order execution
- **`dashboard/`**: Flask web app with SocketIO
- **`database/`**: SQLite wrapper for trade persistence
- **`config/`**: Configuration management

## 🔒 Security Notes

- Never commit `.env` file (it's in `.gitignore`)
- API credentials are sensitive - store securely
- Bot runs with full trading permissions

## 📊 Monitoring

- **Logs**: Check `pmbot.log` for detailed operation logs
- **Dashboard**: Real-time monitoring via web interface
- **Database**: Trade history in `database/trades.db`

## ⚠️ Risk Warning

Trading on Polymarket involves significant financial risk. This bot copies trades automatically without human intervention. Use with caution and only risk what you can afford to lose.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📝 License

MIT License - see LICENSE file for details

## 🌐 Network Access

By default, the dashboard binds to `0.0.0.0` which makes it accessible from any device on your network:

- **Local access**: http://localhost:8080
- **Network access**: http://YOUR_IP:8080 (e.g., http://192.168.1.100:8080)

### Security Warning ⚠️

- `0.0.0.0` binds to **ALL network interfaces** - any device on your network can access the dashboard
- Only use this in a **trusted network** (home LAN, secure office network)
- **Do NOT expose directly to the internet** without additional protection

### For Production Use

If you need external access, use a **reverse proxy** with authentication:
- **nginx** with basic auth or OAuth
- **Traefik** with middleware auth
- **Cloudflare Tunnel** for secure remote access

### Firewall / Port Forwarding

If accessing from another device doesn't work:
1. **Check firewall**: Allow port 8080/tcp on your host
   ```bash
   # Ubuntu/Debian with ufw
   sudo ufw allow 8080/tcp
   
   # Or with iptables
   sudo iptables -A INPUT -p tcp --dport 8080 -j ACCEPT
   ```
2. **Router port forwarding**: Forward external port 8080 to your machine's internal IP (only if needed)

## 🆘 Troubleshooting

### Common Issues

**CLOB Client Initialization Failed**
- Check API credentials in `.env`
- Verify network connectivity to Polymarket

**No Trades Detected**
- Confirm target username is correct
- Check Polymarket profile visibility
- Review logs for scraping errors

**Dashboard Not Loading**
- Check port availability
- Verify Flask installation
- Check firewall settings

### Debug Mode

```bash
LOG_LEVEL=DEBUG python main.py
```

## 🔄 API Reference

### REST Endpoints

- `GET /api/stats` - Get trading statistics
- `GET /api/trades` - Get trade history
- `GET /api/config` - Get current configuration
- `POST /api/config` - Update configuration

### WebSocket Events

- `new_trade` - New trade detected/executed
- `stats_update` - Statistics updated
- `config_update` - Configuration changed

---

**Built with ❤️ for the Polymarket community**


# Enhanced AI-Powered Crypto Trading Bot

An advanced cryptocurrency trading bot with machine learning capabilities that analyzes 400+ Binance coins and provides AI-powered trading signals through a Telegram interface.

## 🌟 Key Features

* **AI-Powered Analysis**: Uses XGBoost machine learning model with 8 technical indicators for accurate signal prediction
* **Real-time Market Scanning**: Continuously monitors all 400+ Binance USDT trading pairs every 3 minutes
* **Telegram Integration**: Interactive bot interface for receiving signals and market insights
* **Advanced Technical Indicators**: RSI, MACD, CCI, Bollinger Bands, and custom volatility metrics
* **Automated Notifications**: Real-time alerts when significant market changes occur
* **Price Predictions**: AI-generated forecasts for multiple timeframes (7 days to 1 year)
* **Rate Limiting**: Intelligent API usage management to prevent bans
* **Batch Processing**: Efficient handling of large coin datasets with concurrency controls

## 🚀 Technologies Used

* **Python 3.8+** - Core programming language
* **XGBoost** - Machine learning model for signal prediction
* **Telegram Bot API** - User interface and notifications
* **Binance API** - Market data and trading pair information
* **Pandas & NumPy** - Data processing and analysis
* **Technical Analysis (TA)** - Library for technical indicators
* **AsyncIO** - Asynchronous operations for performance
* **SQLite** - Local database for signal storage

## 🤖 AI/ML Components

The bot uses an enhanced XGBoost classifier trained on multiple technical indicators:

* **RSI (Relative Strength Index)** - Momentum indicator
* **MACD (Moving Average Convergence Divergence)** - Trend following indicator
* **CCI (Commodity Channel Index)** - Oscillator for price trends
* **Bollinger Bands** - Volatility bands around moving average
* **Price Change Metrics** - Custom indicators for trend analysis
* **Volume Analysis** - Trading volume patterns

The model is trained on historical data from top cryptocurrencies (BTC, ETH, BNB, etc.) and provides confidence scores for each prediction.

## 📱 Telegram Integration

Users interact with the bot through Telegram commands:

* `/ai_signal BTC` - Get advanced AI signal with confidence score
* `/price_prediction BTC` - AI-powered price forecasts for multiple timeframes
* `/top_signals` - View best BUY/SELL opportunities by volume
* `/all_signals` - See all current market signals
* `/start_scanner` - Begin continuous market analysis
* `/subscribe` - Enable real-time signal change notifications

## 📊 Real-time Market Analysis

The bot continuously scans all Binance USDT pairs every 3 minutes, analyzing:

* Price movements and trends
* Trading volume patterns
* Technical indicator signals
* Market volatility metrics

When significant changes occur, users receive instant notifications with actionable insights.

## 🛠️ Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/crypto-trading-bot.git
cd crypto-trading-bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your Telegram bot token in environment variables:
```bash
export TELEGRAM_BOT_TOKEN="your_telegram_bot_token_here"
```

4. Run the bot:
```bash
python bot.py
```

## 📈 Usage

After starting the bot, interact with it through Telegram:

1. Start a conversation with your bot
2. Use `/start` to see available commands
3. Try `/ai_signal BTC` to get an AI-powered signal for Bitcoin
4. Use `/start_scanner` to begin continuous market analysis
5. Subscribe to notifications with `/subscribe`

## 🏗️ Project Structure

```
├── bot.py                  # Main Telegram bot implementation
├── enhanced_ai_logic.py     # AI/ML signal prediction engine
├── batch_processor.py      # Batch processing for multiple coins
├── coin_discovery.py       # Binance coin discovery service
├── rate_limiter.py         # API rate limiting controls
├── config.py               # Configuration management
├── signal_database.py      # Signal storage and retrieval
├── enhanced_background_scanner.py  # Continuous scanning engine
└── requirements.txt        # Python dependencies
```

## 🔒 Security Features

* Input validation for all user commands
* Rate limiting to prevent API abuse
* Secure environment variable management
* Error handling with generic messages to prevent information leakage

## 📈 Performance Metrics

* Full market scan every 3 minutes
* Processes 400+ coins per cycle
* 99%+ uptime with automatic error recovery
* Advanced ML model with 8 technical indicators
* Rate-limited for optimal performance

## 📝 Disclaimer

This bot is for educational and informational purposes only. Cryptocurrency trading involves substantial risk and is not suitable for all investors. Past performance is not indicative of future results. Do not make investment decisions based solely on this bot's predictions. Always do your own research and consider your risk tolerance.

## 📞 Contact

For questions or support, please open an issue on this repository.

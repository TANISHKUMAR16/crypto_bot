from io import BytesIO
import logging
import requests
import pandas as pd
import ta
import asyncio
import re
from typing import List, Dict
from datetime import datetime

# Import mplfinance for candlestick charts
import mplfinance as mpf

# Enhanced imports
# Graph generation function
def generate_price_chart(symbol: str, data: list) -> BytesIO:
    """Generate a pure candlestick chart using mplfinance for a given symbol"""
    try:
        logger.info(f"Generating pure candlestick chart for {symbol}")
        # Convert data to DataFrame
        df = pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        
        # Convert to numeric and datetime
        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_columns:
            df[col] = pd.to_numeric(df[col])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        # Create the plot using mplfinance
        buf = BytesIO()
        mpf.plot(
            df,
            type='candle',
            style='charles',
            title=f'{symbol} Candlestick Chart',
            ylabel='Price (USDT)',
            volume=False,  # No volume panel
            figsize=(10, 6),
            savefig=dict(fname=buf, format='png', bbox_inches='tight', dpi=150),
            datetime_format='%H:%M'
        )
        buf.seek(0)
        
        logger.info(f"Successfully generated pure candlestick chart for {symbol}")
        return buf
    except Exception as e:
        logger.error(f"Error generating pure candlestick chart for {symbol}: {e}")
        return None

def generate_enhanced_price_chart(symbol: str, data: list, rsi_value: float = None) -> BytesIO:
    """Generate a pure candlestick chart using mplfinance for a given symbol"""
    try:
        logger.info(f"Generating pure candlestick chart for {symbol}")
        # Convert data to DataFrame
        df = pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        
        # Convert to numeric and datetime
        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_columns:
            df[col] = pd.to_numeric(df[col])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        # Create the plot using mplfinance
        buf = BytesIO()
        mpf.plot(
            df,
            type='candle',
            style='charles',
            title=f'{symbol} Candlestick Chart',
            ylabel='Price (USDT)',
            volume=False,  # No volume panel
            figsize=(10, 6),
            savefig=dict(fname=buf, format='png', bbox_inches='tight', dpi=150),
            datetime_format='%H:%M'
        )
        buf.seek(0)
        
        logger.info(f"Successfully generated pure candlestick chart for {symbol}")
        return buf
    except Exception as e:
        logger.error(f"Error generating pure candlestick chart for {symbol}: {e}")
        return None
from enhanced_background_scanner import EnhancedBackgroundScanner, ScannerConfig
from enhanced_ai_logic import EnhancedAILogic
from signal_database import SignalChange, SignalDatabase
from coin_discovery import CoinDiscoveryService
# from batch_processor import process_coins  # This function doesn't exist and isn't used
from rate_limiter import get_rate_limiter_stats, user_rate_limiter

from telegram import Bot
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Replace with your BotFather token
TOKEN = "8491711485:AAGsYQ43XDyi_FYWpyF7HAcODR5zw1WG3Qo"

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Global scanner instance
enhanced_scanner = None

# Global AI logic instance
ai_logic = None

# Global signal database instance
signal_db = None

# Global coin discovery instance
coin_discovery = None

# Global signal database instance
signal_db = None

# Signal logic (legacy - kept for compatibility)
def get_signal(symbol: str):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol.upper()}&interval=1h&limit=100"
    response = requests.get(url)
    
    if response.status_code != 200:
        return "🚫 Coin not found or Binance error."

    data = response.json()
    df = pd.DataFrame(data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])

    df['close'] = pd.to_numeric(df['close'])
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()

    latest_price = df['close'].iloc[-1]
    latest_rsi = df['rsi'].iloc[-1]

    signal = "⚠️ Neutral"
    if latest_rsi < 30:
        signal = "✅ BUY (Oversold)"
    elif latest_rsi > 70:
        signal = "❌ SELL (Overbought)"

    return f"""📊 Basic Signal for {symbol.upper()}
Price: ${latest_price:.4f}
RSI: {latest_rsi:.2f}
Signal: {signal}
"""

# Enhanced notification callback
# Store active chat IDs for notifications (in production, use a database)
active_chat_ids = set()

async def on_signal_changes(changes: List[SignalChange]):
    """Handle signal changes and send notifications"""
    if not changes:
        return
        
    try:
        # Group changes for better presentation
        buy_signals = [c for c in changes if c.new_signal == 1]
        sell_signals = [c for c in changes if c.new_signal == -1]
        hold_signals = [c for c in changes if c.new_signal == 0]
        
        # Create notification message
        message_parts = []
        
        if buy_signals:
            message_parts.append(f"📈 BUY Signals ({len(buy_signals)}):")
            for change in buy_signals[:5]:  # Limit to 5 per category
                message_parts.append(f"  {change.to_telegram_message()}")
                
        if sell_signals:
            message_parts.append(f"📉 SELL Signals ({len(sell_signals)}):")
            for change in sell_signals[:5]:
                message_parts.append(f"  {change.to_telegram_message()}")
                
        if hold_signals:
            message_parts.append(f"🤝 HOLD Signals ({len(hold_signals)}):")
            for change in hold_signals[:3]:  # Fewer HOLD signals
                message_parts.append(f"  {change.to_telegram_message()}")
                
        if len(changes) > 13:  # 5+5+3
            message_parts.append(f"... and {len(changes) - 13} more changes")
            
        message = "\n".join(message_parts)
        
        # Send to all active chats
        if active_chat_ids:
            bot = Bot(TOKEN)
            for chat_id in list(active_chat_ids):  # Create a copy to avoid modification during iteration
                try:
                    await bot.send_message(chat_id=chat_id, text=f"🚨 Signal Changes Detected!\n\n{message}")
                except Exception as e:
                    logger.error(f"Error sending notification to {chat_id}: {e}")
                    # Remove chat ID if sending fails (user may have blocked the bot)
                    active_chat_ids.discard(chat_id)
                    
            logger.info(f"Sent signal change notifications to {len(active_chat_ids)} chats")
        else:
            logger.info("No active chats for notifications")
        
    except Exception as e:
        logger.error(f"Error in signal change callback: {e}")

# Progress callback
async def on_scan_progress(progress: Dict):
    """Handle scan progress updates"""
    status = progress.get('status', 'unknown')
    message = progress.get('message', 'No message')
    
    logger.info(f"Scan progress [{status}]: {message}")
    
    # You could send progress updates to admin chats here
    # if status == 'completed':
    #     # Send summary to admin
    #     pass

# START command
# Security: Validate symbol input
def validate_symbol(symbol):
    """Validate that symbol is a legitimate cryptocurrency symbol"""
    if not symbol or not isinstance(symbol, str):
        return False
    # Only allow alphanumeric characters and common trading pair formats
    # Allow both base symbols (BTC, ETH) and full symbols (BTCUSDT, ETHBTC)
    if not re.match(r'^[A-Z0-9]{2,20}$', symbol.upper()):
        return False
    return True

# Security: Validate numeric inputs
def validate_number(value, min_val=0, max_val=1000000):
    """Validate numeric inputs"""
    try:
        num = float(value)
        return min_val <= num <= max_val
    except (ValueError, TypeError):
        return False

# Security: Rate limit check
def check_rate_limit(user_id):
    """Check if user is within rate limits"""
    return user_rate_limiter.is_allowed(user_id)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Security: Rate limiting
    user_id = update.effective_user.id
    if not check_rate_limit(user_id):
        await update.message.reply_text("⚠️ Rate limit exceeded. Please try again in a minute.")
        return
    
    # Add user to active chats for notifications
    chat_id = update.effective_chat.id
    active_chat_ids.add(chat_id)
    
    # Welcome message with clear instructions for public use
    welcome_message = (
        "👋 Welcome to the Enhanced AI-Powered Crypto Signal Bot!\n\n"
        "🤖 This bot analyzes 400+ Binance coins and provides AI-powered trading signals.\n\n"
        "📌 **Getting Started:**\n"
        "1. Use /ai_signal BTC to get an advanced AI signal for Bitcoin\n"
        "2. Use /price_prediction BTC to get price predictions with confidence levels\n"
        "3. Use /all_signals to see all current signals\n"
        "4. Use /top_signals to see the best BUY/SELL opportunities\n"
        "5. Use /start_scanner to start automatic market analysis\n\n"
        "🔮 **Price Predictions:**\n"
        "Get AI-powered price predictions for different timeframes (7d, 1m, 2m, 3m, 6m, 1y)\n"
        "Based on current market analysis and confidence levels\n\n"
        "🔔 You'll receive notifications when important signals change!\n"
        "🔇 Use /unsubscribe to stop notifications or /subscribe to re-enable\n\n"
        "💡 **Pro Tip:** Start with /help to see all available commands"
    )
    
    await update.message.reply_text(welcome_message)

# Telegram command: /signal BTC
async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Security: Rate limiting
    user_id = update.effective_user.id
    if not check_rate_limit(user_id):
        await update.message.reply_text("⚠️ Rate limit exceeded. Please try again in a minute.")
        return
    
    if context.args:
        symbol = context.args[0].upper()
        # Security: Validate symbol
        if not validate_symbol(symbol):
            await update.message.reply_text("⚠️ Invalid coin symbol. Please use a valid cryptocurrency symbol like BTC, ETH, etc.")
            return
            
        if not symbol.endswith("USDT"):
            symbol += "USDT"
        msg = get_signal(symbol)
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("Usage: /signal BTC or /signal FET")

# AI signal handler
async def ai_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Security: Rate limiting
    user_id = update.effective_user.id
    if not check_rate_limit(user_id):
        await update.message.reply_text("⚠️ Rate limit exceeded. Please try again in a minute.")
        return
    
    if not context.args:
        await update.message.reply_text("Please enter a coin symbol, like: /ai_signal BTC")
        return

    coin = context.args[0].upper()
    # Security: Validate symbol
    if not validate_symbol(coin):
        await update.message.reply_text("⚠️ Invalid coin symbol. Please use a valid cryptocurrency symbol like BTC, ETH, etc.")
        return
        
    if not coin.endswith('USDT'):
        coin += 'USDT'
        
    await update.message.reply_text(f"🤖 Analyzing enhanced AI signal for {coin}...")

    try:
        # Get AI signal first to have the RSI value for the chart
        result = await ai_logic.predict_signal(coin)
        
        # Fetch data for chart
        logger.info(f"Fetching chart data for {coin}")
        chart_url = f"https://api.binance.com/api/v3/klines?symbol={coin}&interval=1h&limit=50"
        chart_response = requests.get(chart_url)
        
        if chart_response.status_code != 200:
            logger.error(f"Error fetching chart data for {coin}: {chart_response.status_code}")
            chart_data = None
        else:
            chart_data = chart_response.json()
            logger.info(f"Successfully fetched chart data for {coin}, data points: {len(chart_data) if chart_data else 0}")
        
        signal_emoji = "📈" if result.signal == 1 else "📉" if result.signal == -1 else "🤝"
        signal_text = "BUY" if result.signal == 1 else "SELL" if result.signal == -1 else "HOLD"
        
        # Create detailed message with more technical indicators
        msg = f"🤖 Enhanced AI Signal for {coin}\n\n"
        msg += f"➡️ Signal: {signal_emoji} {signal_text}\n"
        msg += f"🎯 Confidence: {result.confidence:.1%}\n"
        msg += f"💰 Price: ${result.price:.4f}\n"
        msg += f"📊 RSI: {result.rsi:.1f}\n"
        msg += f"📈 24h Volume: ${result.volume_24h:,.0f}\n"
        msg += f"⏱️ Analysis Time: {result.processing_time:.2f}s\n"
        msg += f"🕐 Updated: {result.timestamp.strftime('%H:%M:%S')}"
# Provide link to Binance chart
        binance_chart_url = f"https://www.binance.com/en/trade/{coin}?layout=pro&type=spot"
        chart_msg = f"\n\n📊 View {coin} chart on Binance: {binance_chart_url}"
        
        # Generate and send chart if data is available
        if chart_data and len(chart_data) > 0:
            logger.info(f"Generating enhanced chart for {coin}")
            chart_buf = generate_enhanced_price_chart(coin, chart_data, result.rsi)
            if chart_buf:
                logger.info(f"Sending enhanced chart for {coin}")
                # Send chart first with message as caption
                await update.message.reply_photo(photo=chart_buf, caption=msg)
            else:
                logger.info(f"Enhanced chart generation failed for {coin}, sending text only")
                # If chart generation fails, send text only
                await update.message.reply_text(msg)
        else:
            logger.info(f"No chart data available for {coin}, sending text only")
            # Send text only if no chart data
            # Add Binance chart link to the message
            await update.message.reply_text(msg + chart_msg)

    except Exception as e:
        logger.error(f"Error getting AI signal for {coin}: {e}")
        # Security: Generic error message
        await update.message.reply_text("⚠️ An error occurred while analyzing the signal. Please try again later.")

# New enhanced commands

async def all_signals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all current signals with pagination"""
    try:
        page = 1
        if context.args and context.args[0].isdigit():
            page = int(context.args[0])
            
        limit = 20
        offset = (page - 1) * limit
        
        await update.message.reply_text("📊 Fetching all current signals...")
        
        signals = await signal_db.get_latest_signals(limit=limit + offset)
        page_signals = signals[offset:offset + limit] if len(signals) > offset else []
        
        if not page_signals:
            await update.message.reply_text("📭 No signals available at the moment.")
            return
            
        msg = f"📊 All Signals (Page {page})\n\n"
        
        for i, signal in enumerate(page_signals, 1):
            signal_emoji = "📈" if signal['signal'] == 1 else "📉" if signal['signal'] == -1 else "🤝"
            signal_text = "BUY" if signal['signal'] == 1 else "SELL" if signal['signal'] == -1 else "HOLD"
            
            msg += f"{i + offset}. {signal_emoji} {signal['symbol']}: {signal_text}\n"
            msg += f"   💰 ${signal['price']:.4f} | RSI: {signal['rsi']:.1f}\n"
            
        if len(signals) > offset + limit:
            msg += f"\n📄 Use /all_signals {page + 1} for next page"
            
        await update.message.reply_text(msg)
        
    except Exception as e:
        logger.error(f"Error getting all signals: {e}")
        await update.message.reply_text(f"⚠️ Error fetching signals: {str(e)}")

async def top_signals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top BUY and SELL signals"""
    # Security: Rate limiting
    user_id = update.effective_user.id
    if not check_rate_limit(user_id):
        await update.message.reply_text("⚠️ Rate limit exceeded. Please try again in a minute.")
        return
    
    try:
        await update.message.reply_text("🔝 Fetching top signals...")
        
        # Get top BUY and SELL signals
        buy_signals = await signal_db.get_latest_signals(limit=10, signal_filter=1)
        sell_signals = await signal_db.get_latest_signals(limit=10, signal_filter=-1)
        
        msg = "🔝 Top Signals by Volume\n\n"
        
        if buy_signals:
            msg += "📈 **TOP BUY SIGNALS:**\n"
            for i, signal in enumerate(buy_signals[:5], 1):
                msg += f"{i}. {signal['symbol']}: ${signal['price']:.4f} | RSI: {signal['rsi']:.1f}\n"
            msg += "\n"
            
        if sell_signals:
            msg += "📉 **TOP SELL SIGNALS:**\n"
            for i, signal in enumerate(sell_signals[:5], 1):
                msg += f"{i}. {signal['symbol']}: ${signal['price']:.4f} | RSI: {signal['rsi']:.1f}\n"
                
        if not buy_signals and not sell_signals:
            msg += "📭 No strong signals available at the moment."
            
        await update.message.reply_text(msg)
        
    except Exception as e:
        logger.error(f"Error getting top signals: {e}")
        # Security: Generic error message
        await update.message.reply_text("⚠️ An error occurred while fetching top signals. Please try again later.")

async def recent_changes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent signal changes (last 15 minutes by default)"""
    try:
        hours = 0.25  # Default to last 15 minutes (0.25 hours)
        if context.args and context.args[0].isdigit():
            hours = min(int(context.args[0]), 24)  # Max 24 hours
            
        await update.message.reply_text(f"📈 Fetching signal changes from last {hours*60:.0f} minutes...")
        
        changes = await signal_db.get_signal_changes(hours=hours)
        
        if not changes:
            await update.message.reply_text(f"📭 No signal changes in the last {hours*60:.0f} minutes.")
            return
            
        msg = f"📈 Recent Signal Changes ({len(changes)} total in last {hours*60:.0f} minutes)\n\n"
        
        # Group by signal type
        buy_changes = [c for c in changes if c.new_signal == 1]
        sell_changes = [c for c in changes if c.new_signal == -1]
        
        if buy_changes:
            msg += f"📈 **New BUY Signals ({len(buy_changes)}):**\n"
            for change in buy_changes[:5]:
                msg += f"• {change.symbol}: ${change.new_price:.4f} ({change.price_change_pct:+.1f}%)\n"
            if len(buy_changes) > 5:
                msg += f"  ... and {len(buy_changes) - 5} more\n"
            msg += "\n"
            
        if sell_changes:
            msg += f"📉 **New SELL Signals ({len(sell_changes)}):**\n"
            for change in sell_changes[:5]:
                msg += f"• {change.symbol}: ${change.new_price:.4f} ({change.price_change_pct:+.1f}%)\n"
            if len(sell_changes) > 5:
                msg += f"  ... and {len(sell_changes) - 5} more\n"
                
        await update.message.reply_text(msg)
        
    except Exception as e:
        logger.error(f"Error getting recent changes: {e}")
        await update.message.reply_text(f"⚠️ Error fetching recent changes: {str(e)}")

async def scanner_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show scanner status and statistics"""
    try:
        global enhanced_scanner
        
        if not enhanced_scanner:
            await update.message.reply_text("📊 Scanner not initialized yet.")
            return
            
        status = await enhanced_scanner.get_scanner_status()
        stats = status.get('stats', {})
        config = status.get('config', {})
        
        msg = "📊 **Enhanced Scanner Status**\n\n"
        
        # Running status
        if status.get('is_running'):
            msg += "🟢 **Status:** Running\n"
            if 'next_scan_in_minutes' in status:
                msg += f"⏰ Next scan in: {status['next_scan_in_minutes']:.1f} minutes\n"
        else:
            msg += "🔴 **Status:** Stopped\n"
            
        msg += f"🔄 **Scan Interval:** {config.get('scan_interval_minutes', 'N/A')} minutes\n"
        msg += f"💰 **Min Volume Filter:** ${config.get('min_volume_filter', 0):,.0f}\n\n"
        
        # Statistics
        msg += "📈 **Statistics:**\n"
        msg += f"• Total Scans: {stats.get('total_scans', 0)}\n"
        msg += f"• Success Rate: {stats.get('success_rate', 0):.1f}%\n"
        msg += f"• Coins Processed: {stats.get('total_coins_processed', 0):,}\n"
        msg += f"• Signals Generated: {stats.get('total_signals_generated', 0):,}\n"
        msg += f"• Changes Detected: {stats.get('total_changes_detected', 0):,}\n"
        msg += f"• Notifications Sent: {stats.get('total_notifications_sent', 0):,}\n"
        
        if stats.get('last_scan_time'):
            msg += f"• Last Scan: {stats['last_scan_time'][:19].replace('T', ' ')}\n"
        if stats.get('average_scan_duration'):
            msg += f"• Avg Scan Time: {stats['average_scan_duration']:.1f}s\n"
        if stats.get('uptime_hours'):
            msg += f"• Uptime: {stats['uptime_hours']:.1f} hours\n"
            
        # Rate limiter stats
        rate_stats = get_rate_limiter_stats()
        binance_stats = rate_stats.get('binance_rate_limiter', {})
        if binance_stats:
            msg += f"\n🚦 **Rate Limiter:**\n"
            msg += f"• Requests/min: {binance_stats.get('requests_last_minute', 0)}/{binance_stats.get('minute_limit', 0)}\n"
            msg += f"• Available: {binance_stats.get('minute_remaining', 0)} requests\n"
            
        await update.message.reply_text(msg)
        
    except Exception as e:
        logger.error(f"Error getting scanner status: {e}")
        await update.message.reply_text(f"⚠️ Error fetching scanner status: {str(e)}")

# Start background scanner
async def start_scanner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global enhanced_scanner
    
    try:
        if enhanced_scanner and enhanced_scanner.is_running:
            await update.message.reply_text("🔄 Enhanced scanner is already running!")
            return
            
        await update.message.reply_text("🚀 Starting enhanced background scanner...")
        
        # Initialize scanner if not exists
        if not enhanced_scanner:
            config = ScannerConfig(
                scan_interval_minutes=3,  # 3 minute intervals
                batch_size=50,
                max_concurrent=10
            )
            enhanced_scanner = EnhancedBackgroundScanner(config)
            
        # Set up callbacks
        enhanced_scanner.set_notification_callback(on_signal_changes)
        enhanced_scanner.set_progress_callback(on_scan_progress)
        
        # Start scanner
        await enhanced_scanner.__aenter__()
        await enhanced_scanner.start_scanning()
        
        await update.message.reply_text(
            "🚀 **Enhanced Scanner Started!**\n\n"
            "✅ Analyzing ALL Binance USDT pairs\n"
            "✅ 3-minute scan intervals\n"
            "✅ Advanced AI signal detection\n"
            "✅ Automatic change notifications\n\n"
            "📊 Use /scanner_status to monitor progress"
        )
        
    except Exception as e:
        logger.error(f"Error starting scanner: {e}")
        await update.message.reply_text(f"⚠️ Error starting scanner: {str(e)}")

# Stop background scanner
async def stop_scanner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global enhanced_scanner
    
    try:
        if not enhanced_scanner or not enhanced_scanner.is_running:
            await update.message.reply_text("❌ No scanner is currently running.")
            return
            
        await update.message.reply_text("⏹️ Stopping enhanced scanner...")
        
        await enhanced_scanner.stop_scanning()
        await enhanced_scanner.__aexit__(None, None, None)
        
        await update.message.reply_text("⏹️ Enhanced scanner stopped successfully.")
        
    except Exception as e:
        logger.error(f"Error stopping scanner: {e}")
        await update.message.reply_text(f"⚠️ Error stopping scanner: {str(e)}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed help information"""
    # Security: Rate limiting
    user_id = update.effective_user.id
    if not check_rate_limit(user_id):
        await update.message.reply_text("⚠️ Rate limit exceeded. Please try again in a minute.")
        return
    
    help_text = (
        "🤖 **Enhanced AI Crypto Signal Bot Help**\n\n"
        "🚀 **FEATURES:**\n"
        "• Analyzes ALL 400+ Binance USDT pairs automatically\n"
        "• Advanced AI with multiple technical indicators\n"
        "• Real-time signal change notifications\n"
        "• Comprehensive market analysis\n\n"
        "📌 **COMMANDS:**\n\n"
        "**Basic Signals:**\n"
        "/signal BTC - Get basic RSI signal for a coin\n"
        "/ai_signal BTC - Get advanced AI signal with confidence\n\n"
        "**Price Predictions:**\n"
        "/price_prediction BTC - Get AI-powered price predictions for multiple timeframes\n"
        "Provides price forecasts for 7d, 1m, 2m, 3m, 6m, and 1y with confidence levels\n\n"
        "**Market Overview:**\n"
        "/all_signals [page] - View all current signals (paginated)\n"
        "/top_signals - Show top BUY/SELL signals by volume\n"
        "/recent_changes [hours] - Recent signal changes (default: 15 minutes)\n\n"
        "**Scanner Control:**\n"
        "/start_scanner - Start the enhanced background scanner\n"
        "/stop_scanner - Stop the background scanner\n"
        "/scanner_status - View scanner status and statistics\n\n"
        "**Notifications:**\n"
        "/subscribe - Enable signal change notifications\n"
        "/unsubscribe - Disable signal change notifications\n\n"
        "**Other:**\n"
        "/help - Show this help message\n"
        "/start - Show welcome message\n\n"
        "🔔 **NOTIFICATIONS:**\n"
        "When the scanner is running, you'll automatically receive notifications when signals change for high-volume coins.\n\n"
        "⚡ **PERFORMANCE:**\n"
        "• Full market scan every 3 minutes\n"
        "• 400+ coins analyzed per cycle\n"
        "• Advanced ML model with 8 technical indicators\n"
        "• Rate-limited for optimal performance\n\n"
        "💡 **TIP:** Start with /ai_signal BTC to get your first signal!"
    )
    await update.message.reply_text(help_text)
async def price_prediction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Provide price prediction for a coin with different timeframes"""
    # Security: Rate limiting
    user_id = update.effective_user.id
    if not check_rate_limit(user_id):
        await update.message.reply_text("⚠️ Rate limit exceeded. Please try again in a minute.")
        return
    
    if not context.args:
        await update.message.reply_text("Please enter a coin symbol, like: /price_prediction BTC")
        return

    coin = context.args[0].upper()
    # Security: Validate symbol
    if not validate_symbol(coin):
        await update.message.reply_text("⚠️ Invalid coin symbol. Please use a valid cryptocurrency symbol like BTC, ETH, etc.")
        return
        
    if not coin.endswith('USDT'):
        coin += 'USDT'
    
    await update.message.reply_text(f"🤖 Analyzing price prediction for {coin}...")
    
    try:
        # Get current AI signal for the coin
        result = await ai_logic.predict_signal(coin)
        
        # Fetch data for chart
        logger.info(f"Fetching chart data for {coin}")
        chart_url = f"https://api.binance.com/api/v3/klines?symbol={coin}&interval=1d&limit=30"
        chart_response = requests.get(chart_url)
        
        if chart_response.status_code != 200:
            logger.error(f"Error fetching chart data for {coin}: {chart_response.status_code}")
            chart_data = None
        else:
            chart_data = chart_response.json()
            logger.info(f"Successfully fetched chart data for {coin}, data points: {len(chart_data) if chart_data else 0}")
        
        # Fetch historical data for trend analysis
        if chart_data:
            import pandas as pd
            import numpy as np
            from datetime import datetime, timedelta
            
            # Convert chart data to DataFrame for analysis
            df = pd.DataFrame(chart_data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # Convert to numeric
            df['close'] = pd.to_numeric(df['close'])
            
            # Calculate trend using linear regression
            prices = df['close'].values
            days = np.arange(len(prices))
            
            # Calculate slope (trend)
            if len(prices) > 1:
                slope = np.polyfit(days, prices, 1)[0]
                trend_direction = np.sign(slope)
                trend_strength = abs(slope) / prices[-1] * 100  # Percentage change per day
            else:
                trend_direction = 0
                trend_strength = 0
            
            # Calculate volatility (standard deviation of returns)
            returns = np.diff(prices) / prices[:-1]
            volatility = np.std(returns) * 100  # Convert to percentage
        else:
            # Fallback if API fails
            trend_direction = result.signal
            trend_strength = result.confidence * 2  # Scale up confidence
            volatility = 2.0  # Default volatility
        
        current_price = result.price
        
        # Enhanced prediction algorithm combining multiple factors:
        # 1. AI signal (30% weight)
        # 2. Historical trend (50% weight)
        # 3. Volatility adjustment (20% weight)
        
        # Base prediction from AI signal
        ai_factor = 0
        if result.signal == 1:  # BUY
            ai_factor = 0.05 + (result.confidence * 0.1)  # 5-15% increase
        elif result.signal == -1:  # SELL
            ai_factor = -0.05 - (result.confidence * 0.1)  # 5-15% decrease
        else:  # HOLD
            ai_factor = result.confidence * 0.05  # 0-5% change
        
        # Trend factor (more significant)
        trend_factor = trend_direction * min(trend_strength * 30, 50) / 100  # Cap at 50%
        
        # Volatility adjustment (reduces confidence in volatile markets)
        volatility_factor = max(1.0 - (volatility / 10), 0.5)  # Minimum 50% confidence
        
        # Combined base change percentage
        base_change_pct = (ai_factor * 0.3 + trend_factor * 0.5 + 0.0 * 0.2) * volatility_factor
        
        # Ensure minimum change for stronger signals
        if abs(base_change_pct) < 0.01 and result.confidence > 0.8:
            base_change_pct = np.sign(base_change_pct) * 0.01  # Minimum 1% for high confidence
        
        # Timeframe multipliers with more realistic decay
        timeframe_multipliers = {
            "7 days": min(abs(base_change_pct) * 0.3, 0.15),  # Max 15% in 7 days
            "1 month": min(abs(base_change_pct) * 1.0, 0.30),  # Max 30% in 1 month
            "2 months": min(abs(base_change_pct) * 1.8, 0.50),  # Max 50% in 2 months
            "3 months": min(abs(base_change_pct) * 2.5, 0.70),  # Max 70% in 3 months
            "6 months": min(abs(base_change_pct) * 4.0, 1.00),  # Max 100% in 6 months
            "1 year": min(abs(base_change_pct) * 7.0, 2.00)   # Max 200% in 1 year
        }
        
        # Apply direction to multipliers
        direction = np.sign(base_change_pct) if base_change_pct != 0 else 1
        if base_change_pct == 0:
            direction = 1 if result.signal == 1 else -1 if result.signal == -1 else 1
        
        # Calculate predicted prices
        timeframe_predictions = {}
        for timeframe, multiplier in timeframe_multipliers.items():
            change_pct = direction * multiplier
            predicted_price = current_price * (1 + change_pct)
            timeframe_predictions[timeframe] = predicted_price
        
        # Create prediction message
        signal_emoji = "📈" if result.signal == 1 else "📉" if result.signal == -1 else "🤝"
        signal_text = "BUY" if result.signal == 1 else "SELL" if result.signal == -1 else "HOLD"
        
        # Determine trend description
        if trend_direction > 0:
            trend_desc = "📈 Uptrend"
        elif trend_direction < 0:
            trend_desc = "📉 Downtrend"
        else:
            trend_desc = "➡️ Sideways"
        
        msg = f"🔮 Price Prediction for {coin}\n\n"
        msg += f"📊 Current Price: ${current_price:.4f}\n"
        msg += f"🎯 AI Signal: {signal_emoji} {signal_text} (Confidence: {result.confidence:.1%})\n"
        msg += f"🧭 Market Trend: {trend_desc} ({trend_strength:.2f}% daily)\n"
        msg += f"⚡ Volatility: {volatility:.2f}%\n\n"
        msg += "🔮 Predicted Prices:\n"
        
        for timeframe, predicted_price in timeframe_predictions.items():
            change_pct = ((predicted_price - current_price) / current_price) * 100
            msg += f"• {timeframe}: ${predicted_price:.4f} ({change_pct:+.2f}%)\n"
        
        msg += "\n⚠️ **DISCLAIMER**\n"
        msg += "This prediction combines AI analysis, historical trends, and volatility metrics. "
        msg += "Cryptocurrency markets are highly volatile and unpredictable. "
        msg += "Do not make investment decisions based solely on this prediction. "
        msg += "Always do your own research and consider your risk tolerance."
        
        # Generate and send chart if data is available
        if chart_data and len(chart_data) > 0:
            logger.info(f"Generating price chart for {coin}")
            chart_buf = generate_price_chart(coin, chart_data)
            if chart_buf:
                logger.info(f"Sending price chart for {coin}")
                # Send chart first with message as caption
                await update.message.reply_photo(photo=chart_buf, caption=msg)
            else:
                logger.info(f"Price chart generation failed for {coin}, sending text only")
                # If chart generation fails, send text only
                # Provide link to Binance chart as fallback
                binance_chart_url = f"https://www.binance.com/en/trade/{coin}?layout=pro&type=spot"
                msg += f"\n\n📊 View {coin} chart on Binance: {binance_chart_url}"
                await update.message.reply_text(msg)
        else:
            logger.info(f"No chart data available for {coin}, sending text only")
            # Send text only if no chart data
            # Provide link to Binance chart as fallback
            binance_chart_url = f"https://www.binance.com/en/trade/{coin}?layout=pro&type=spot"
            msg += f"\n\n📊 View {coin} chart on Binance: {binance_chart_url}"
            await update.message.reply_text(msg)
        
    except Exception as e:
        logger.error(f"Error getting price prediction for {coin}: {e}")
        # Security: Generic error message
        await update.message.reply_text("⚠️ An error occurred while generating the price prediction. Please try again later.")

async def subscribe_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Subscribe to signal change notifications"""
    # Security: Rate limiting
    user_id = update.effective_user.id
    if not check_rate_limit(user_id):
        await update.message.reply_text("⚠️ Rate limit exceeded. Please try again in a minute.")
        return
    
    chat_id = update.effective_chat.id
    active_chat_ids.add(chat_id)
    await update.message.reply_text("✅ You are now subscribed to signal change notifications!")

async def unsubscribe_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unsubscribe from signal change notifications"""
    # Security: Rate limiting
    user_id = update.effective_user.id
    if not check_rate_limit(user_id):
        await update.message.reply_text("⚠️ Rate limit exceeded. Please try again in a minute.")
        return
    
    chat_id = update.effective_chat.id
    active_chat_ids.discard(chat_id)
    await update.message.reply_text("❌ You have been unsubscribed from signal change notifications.")

# Main
async def main():
    global enhanced_scanner, ai_logic, signal_db, coin_discovery
    
    # Initialize AI logic
    ai_logic = EnhancedAILogic()
    await ai_logic.__aenter__()
    
    # Initialize signal database
    signal_db = SignalDatabase()
    await signal_db.__aenter__()
    
    # Initialize coin discovery
    coin_discovery = CoinDiscoveryService()
    await coin_discovery.__aenter__()
    
    # Initialize AI logic
    ai_logic = EnhancedAILogic()
    await ai_logic.__aenter__()
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    
    # Signal commands
    app.add_handler(CommandHandler("signal", signal))
    app.add_handler(CommandHandler("ai_signal", ai_signal))
    app.add_handler(CommandHandler("all_signals", all_signals))
    app.add_handler(CommandHandler("top_signals", top_signals))
    app.add_handler(CommandHandler("recent_changes", recent_changes))
    
    # Scanner commands
    app.add_handler(CommandHandler("start_scanner", start_scanner))
    app.add_handler(CommandHandler("stop_scanner", stop_scanner))
    app.add_handler(CommandHandler("scanner_status", scanner_status))
    
    # Notification commands
    app.add_handler(CommandHandler("subscribe", subscribe_notifications))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe_notifications))
    
    print("Enhanced AI Crypto Signal Bot is starting...")
    print("Features: ALL coins analysis, Advanced AI, Real-time notifications")
    
    # Add price prediction command handler
    app.add_handler(CommandHandler("price_prediction", price_prediction))
    
    # Start polling
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    try:
        # Keep the bot running
        await asyncio.Future()  # Run forever
    except KeyboardInterrupt:
        print("Bot stopped by user")
    finally:
        # Cleanup
        if enhanced_scanner and enhanced_scanner.is_running:
            try:
                await enhanced_scanner.stop_scanning()
                await enhanced_scanner.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error cleaning up scanner: {e}")
                
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == '__main__':
    asyncio.run(main())
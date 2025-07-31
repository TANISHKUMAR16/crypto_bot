import asyncio
import aiohttp
import pandas as pd
import numpy as np
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import joblib
import os

from ta.momentum import RSIIndicator
from ta.trend import MACD, CCIIndicator
from ta.volatility import BollingerBands
from xgboost import XGBClassifier
from sklearn.preprocessing import StandardScaler

from rate_limiter import rate_limited_request

logger = logging.getLogger(__name__)

@dataclass
class SignalResult:
    """Result of AI signal analysis"""
    symbol: str
    signal: int  # -1=SELL, 0=HOLD, 1=BUY
    confidence: float
    price: float
    rsi: float
    volume_24h: float
    timestamp: datetime
    processing_time: float
    
    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'signal': self.signal,
            'confidence': self.confidence,
            'price': self.price,
            'rsi': self.rsi,
            'volume_24h': self.volume_24h,
            'timestamp': self.timestamp.isoformat(),
            'processing_time': self.processing_time
        }
    
    def to_telegram_message(self) -> str:
        signal_emoji = "📈" if self.signal == 1 else "📉" if self.signal == -1 else "🤝"
        signal_text = "BUY" if self.signal == 1 else "SELL" if self.signal == -1 else "HOLD"
        return f"{signal_emoji} {self.symbol}: {signal_text} | ${self.price:.4f} | RSI: {self.rsi:.1f}"

class EnhancedAILogic:
    """
    Enhanced AI logic using Binance API for data fetching
    Optimized for batch processing of multiple coins
    """
    
    def __init__(self):
        self.base_url = "https://api.binance.com/api/v3"
        self.session: Optional[aiohttp.ClientSession] = None
        self.model: Optional[XGBClassifier] = None
        self.scaler: Optional[StandardScaler] = None
        self.model_path = "enhanced_model.pkl"
        self.scaler_path = "enhanced_scaler.pkl"
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        await self._load_or_create_model()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make a rate-limited request to Binance API"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        url = f"{self.base_url}{endpoint}"
        
        async def _request():
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 429:
                    raise Exception("Rate limit exceeded")
                else:
                    raise Exception(f"API error: {response.status} for {url}")
                    
        return await rate_limited_request(_request, endpoint=endpoint)
        
    async def fetch_klines_data(self, symbol: str, interval: str = "1h", limit: int = 200) -> pd.DataFrame:
        """
        Fetch klines (candlestick) data from Binance
        """
        try:
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }
            
            data = await self._make_request("/klines", params)
            
            if not data:
                raise ValueError(f"No data received for {symbol}")
                
            # Convert to DataFrame
            df = pd.DataFrame(data, columns=[
                'timestamp', 'Open', 'High', 'Low', 'Close', 'Volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # Convert data types
            numeric_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col])
                
            # Convert timestamp
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Keep only OHLCV data
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
            
            logger.debug(f"Fetched {len(df)} rows for {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            raise
            
    def add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add technical indicators to the dataframe
        """
        try:
            df_copy = df.copy()
            
            # RSI
            df_copy['rsi'] = RSIIndicator(df_copy['Close'], window=14).rsi()
            
            # MACD
            macd = MACD(df_copy['Close'])
            df_copy['macd'] = macd.macd_diff()
            
            # CCI
            df_copy['cci'] = CCIIndicator(df_copy['High'], df_copy['Low'], df_copy['Close']).cci()
            
            # Bollinger Bands
            bb = BollingerBands(df_copy['Close'])
            df_copy['bb_bbm'] = bb.bollinger_mavg()
            df_copy['bb_bbh'] = bb.bollinger_hband()
            df_copy['bb_bbl'] = bb.bollinger_lband()
            
            # Additional indicators
            df_copy['price_change'] = df_copy['Close'].pct_change()
            df_copy['volume_sma'] = df_copy['Volume'].rolling(window=20).mean()
            df_copy['high_low_pct'] = (df_copy['High'] - df_copy['Low']) / df_copy['Close']
            
            # Drop rows with NaN values
            df_clean = df_copy.dropna()
            
            if len(df_clean) < 30:
                raise ValueError("Insufficient data after adding indicators")
                
            return df_clean
            
        except Exception as e:
            logger.error(f"Error adding indicators: {e}")
            raise
            
    def create_labels(self, df: pd.DataFrame, threshold: float = 0.015) -> pd.DataFrame:
        """
        Create labels for supervised learning with improved stability
        """
        try:
            df_copy = df.copy()
            
            # Look ahead multiple periods for more stable labels
            df_copy['future_close_3'] = df_copy['Close'].shift(-3)   # Short term (3 periods)
            df_copy['future_close_10'] = df_copy['Close'].shift(-10)  # Medium term (10 periods)
            df_copy['future_close_20'] = df_copy['Close'].shift(-20)  # Long term (20 periods)
            
            # Calculate price changes for different time horizons
            price_change_3 = (df_copy['future_close_3'] - df_copy['Close']) / df_copy['Close']
            price_change_10 = (df_copy['future_close_10'] - df_copy['Close']) / df_copy['Close']
            price_change_20 = (df_copy['future_close_20'] - df_copy['Close']) / df_copy['Close']
            
            # Combine multiple time horizons for more stable labels
            # Weighted average: 50% short term, 30% medium term, 20% long term
            combined_change = (price_change_3 * 0.5 + price_change_10 * 0.3 + price_change_20 * 0.2)
            
            # Create signals with improved thresholds for stability
            # 0 = SELL, 1 = HOLD, 2 = BUY (XGBoost expects labels starting from 0)
            df_copy['signal'] = np.where(combined_change > 0.015, 2,      # 1.5% gain threshold for BUY
                                       np.where(combined_change < -0.015, 0, 1))  # 1.5% loss threshold for SELL
            
            # Drop rows with NaN
            df_labeled = df_copy.dropna()
            
            return df_labeled
            
        except Exception as e:
            logger.error(f"Error creating labels: {e}")
            raise
            
    async def _load_or_create_model(self):
        """Load existing model or create new one"""
        try:
            if os.path.exists(self.model_path) and os.path.exists(self.scaler_path):
                self.model = joblib.load(self.model_path)
                self.scaler = joblib.load(self.scaler_path)
                logger.info("Loaded existing model and scaler")
            else:
                logger.info("Model files not found, will train when needed")
                
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            self.model = None
            self.scaler = None
            
    async def train_model(self, training_symbols: List[str] = None) -> bool:
        """
        Train the ML model using data from multiple symbols
        """
        try:
            if not training_symbols:
                # Use popular coins for training
                training_symbols = [
                    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT',
                    'XRPUSDT', 'DOTUSDT', 'DOGEUSDT', 'AVAXUSDT', 'LINKUSDT'
                ]
                
            logger.info(f"Training model with {len(training_symbols)} symbols")
            
            all_features = []
            all_labels = []
            
            # Collect training data from multiple symbols
            for symbol in training_symbols:
                try:
                    df = await self.fetch_klines_data(symbol, limit=500)
                    df_indicators = self.add_technical_indicators(df)
                    df_labeled = self.create_labels(df_indicators)
                    
                    if len(df_labeled) > 50:  # Minimum data requirement
                        features = ['rsi', 'macd', 'cci', 'bb_bbm', 'bb_bbh', 'bb_bbl', 
                                  'price_change', 'high_low_pct']
                        
                        X = df_labeled[features].values
                        y = df_labeled['signal'].values
                        
                        all_features.append(X)
                        all_labels.append(y)
                        
                except Exception as e:
                    logger.warning(f"Failed to get training data for {symbol}: {e}")
                    continue
                    
            if not all_features:
                raise ValueError("No training data collected")
                
            # Combine all training data
            X_combined = np.vstack(all_features)
            y_combined = np.hstack(all_labels)
            
            logger.info(f"Training with {len(X_combined)} samples")
            
            # Check class distribution
            unique, counts = np.unique(y_combined, return_counts=True)
            logger.info(f"Class distribution: {dict(zip(unique, counts))}")
            
            # Scale features
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X_combined)
            
            # Train model with parameters optimized for higher confidence and stability
            self.model = XGBClassifier(
                n_estimators=700,        # More trees for better performance and stability
                max_depth=12,            # Deeper trees for complex patterns
                learning_rate=0.02,      # Lower learning rate for better generalization
                subsample=0.9,           # Slightly lower subsample for better generalization
                colsample_bytree=0.85,   # Slightly lower column sampling for better generalization
                min_child_weight=3,      # Higher minimum sum for more robust predictions
                gamma=0.3,               # Higher gamma for more conservative splits
                reg_alpha=0.3,           # Higher L1 regularization for sparsity
                reg_lambda=2.0,          # Higher L2 regularization for smoothness
                use_label_encoder=False,
                eval_metric='mlogloss',
                random_state=42
            )
            
            self.model.fit(X_scaled, y_combined)
            
            # Save model
            joblib.dump(self.model, self.model_path)
            joblib.dump(self.scaler, self.scaler_path)
            
            logger.info("Model training completed and saved")
            return True
            
        except Exception as e:
            logger.error(f"Error training model: {e}")
            return False
            
    async def predict_signal(self, symbol: str) -> SignalResult:
        """
        Predict signal for a single symbol
        """
        start_time = datetime.now()
        
        try:
            # Fetch and process data
            df = await self.fetch_klines_data(symbol)
            df_indicators = self.add_technical_indicators(df)
            
            if len(df_indicators) == 0:
                raise ValueError("No data available after processing")
                
            # Ensure model is available
            if self.model is None or self.scaler is None:
                logger.info("Model not available, training...")
                success = await self.train_model()
                if not success:
                    logger.warning("Model training failed, using fallback prediction")
                    # Return fallback result instead of raising error
                    processing_time = (datetime.now() - start_time).total_seconds()
                    return SignalResult(
                        symbol=symbol,
                        signal=0,  # HOLD
                        confidence=0.33,
                        price=float(df_indicators.iloc[-1]['Close']),
                        rsi=float(df_indicators.iloc[-1]['rsi']),
                        volume_24h=0.0,
                        timestamp=datetime.now(),
                        processing_time=processing_time
                    )
                    
            # Prepare features
            features = ['rsi', 'macd', 'cci', 'bb_bbm', 'bb_bbh', 'bb_bbl', 
                       'price_change', 'high_low_pct']
            
            # Get latest data point
            latest_data = df_indicators.iloc[-1]
            X = latest_data[features].values.reshape(1, -1)
            
            # Make prediction
            X_scaled = self.scaler.transform(X)
            prediction = self.model.predict(X_scaled)[0]
            
            # Get prediction probabilities for confidence
            probabilities = self.model.predict_proba(X_scaled)[0]
            confidence = float(np.max(probabilities))
            
            # Convert prediction back to original signal values
            # 0 -> SELL (-1), 1 -> HOLD (0), 2 -> BUY (1)
            signal_mapping = {0: -1, 1: 0, 2: 1}
            prediction = signal_mapping.get(prediction, 0)  # Default to HOLD if unknown
            
            # Get additional metrics
            rsi_value = float(latest_data['rsi'])
            price = float(latest_data['Close'])
            
            # Get 24h volume from ticker API instead of klines
            try:
                ticker_data = await self._make_request("/ticker/24hr", {"symbol": symbol})
                volume_24h = float(ticker_data.get('volume', 0))
            except:
                # Fallback to klines volume calculation
                volume_24h = float(df['Volume'].iloc[-24:].sum()) if len(df) >= 24 else float(df['Volume'].sum())
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            result = SignalResult(
                symbol=symbol,
                signal=int(prediction),
                confidence=confidence,
                price=price,
                rsi=rsi_value,
                volume_24h=volume_24h,
                timestamp=datetime.now(),
                processing_time=processing_time
            )
            
            logger.debug(f"Prediction for {symbol}: {prediction} (confidence: {confidence:.3f})")
            return result
            
        except Exception as e:
            logger.error(f"Error predicting signal for {symbol}: {e}")
            # Return neutral signal with current price if possible
            try:
                df = await self.fetch_klines_data(symbol, limit=1)
                price = float(df['Close'].iloc[-1])
                
                # Try to get volume from ticker
                try:
                    ticker_data = await self._make_request("/ticker/24hr", {"symbol": symbol})
                    volume_24h = float(ticker_data.get('volume', 0))
                except:
                    volume_24h = 0.0
            except:
                price = 0.0
                volume_24h = 0.0
                
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return SignalResult(
                symbol=symbol,
                signal=0,
                confidence=0.33,
                price=price,
                rsi=50.0,
                volume_24h=volume_24h,
                timestamp=datetime.now(),
                processing_time=processing_time
            )
            
    async def batch_predict_signals(self, symbols: List[str]) -> Dict[str, SignalResult]:
        """
        Predict signals for multiple symbols in parallel
        """
        logger.info(f"Batch predicting signals for {len(symbols)} symbols")
        
        # Create tasks for parallel processing
        tasks = [self.predict_signal(symbol) for symbol in symbols]
        
        # Execute with some concurrency control
        semaphore = asyncio.Semaphore(10)  # Limit concurrent predictions
        
        async def predict_with_semaphore(symbol):
            async with semaphore:
                return await self.predict_signal(symbol)
                
        tasks = [predict_with_semaphore(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        signal_results = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.error(f"Error predicting {symbol}: {result}")
                # Create default result
                signal_results[symbol] = SignalResult(
                    symbol=symbol,
                    signal=0,
                    confidence=0.33,
                    price=0.0,
                    rsi=50.0,
                    volume_24h=0.0,
                    timestamp=datetime.now(),
                    processing_time=0.0
                )
            else:
                signal_results[symbol] = result
                
        logger.info(f"Completed batch prediction for {len(signal_results)} symbols")
        return signal_results
        
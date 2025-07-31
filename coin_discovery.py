import asyncio
import aiohttp
import logging
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

from rate_limiter import rate_limited_request

logger = logging.getLogger(__name__)

@dataclass
class CoinInfo:
    """Information about a trading pair"""
    symbol: str
    base_asset: str
    quote_asset: str
    status: str
    is_spot_trading_allowed: bool
    is_margin_trading_allowed: bool
    permissions: List[str]
    filters: Dict
    volume_24h: Optional[float] = None
    price_change_24h: Optional[float] = None
    last_updated: Optional[datetime] = None

class CoinDiscoveryService:
    """
    Service for discovering and managing all available Binance trading pairs
    """
    
    def __init__(self):
        self.base_url = "https://api.binance.com/api/v3"
        self.session: Optional[aiohttp.ClientSession] = None
        self.cached_coins: Dict[str, CoinInfo] = {}
        self.cache_expiry: Optional[datetime] = None
        self.cache_duration = timedelta(hours=1)  # Cache for 1 hour
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
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
                    raise Exception(f"API error: {response.status}")
                    
        return await rate_limited_request(_request, endpoint=endpoint)
        
    async def fetch_exchange_info(self) -> Dict:
        """
        Fetch exchange information from Binance
        Contains all trading pairs and their details
        """
        try:
            logger.info("Fetching exchange information from Binance...")
            data = await self._make_request("/exchangeInfo")
            logger.info(f"Fetched exchange info with {len(data.get('symbols', []))} symbols")
            return data
        except Exception as e:
            logger.error(f"Error fetching exchange info: {e}")
            raise
            
    async def fetch_24hr_ticker(self) -> List[Dict]:
        """
        Fetch 24hr ticker statistics for all symbols
        """
        try:
            logger.info("Fetching 24hr ticker data...")
            data = await self._make_request("/ticker/24hr")
            logger.info(f"Fetched 24hr ticker for {len(data)} symbols")
            return data
        except Exception as e:
            logger.error(f"Error fetching 24hr ticker: {e}")
            raise
            
    def _parse_symbol_info(self, symbol_data: Dict) -> CoinInfo:
        """Parse symbol information from exchange info"""
        return CoinInfo(
            symbol=symbol_data['symbol'],
            base_asset=symbol_data['baseAsset'],
            quote_asset=symbol_data['quoteAsset'],
            status=symbol_data['status'],
            is_spot_trading_allowed=symbol_data.get('isSpotTradingAllowed', False),
            is_margin_trading_allowed=symbol_data.get('isMarginTradingAllowed', False),
            permissions=symbol_data.get('permissions', []),
            filters={f['filterType']: f for f in symbol_data.get('filters', [])}
        )
        
    def _add_ticker_data(self, coin_info: CoinInfo, ticker_data: Dict) -> CoinInfo:
        """Add 24hr ticker data to coin info"""
        coin_info.volume_24h = float(ticker_data.get('volume', 0))
        coin_info.price_change_24h = float(ticker_data.get('priceChangePercent', 0))
        coin_info.last_updated = datetime.now()
        return coin_info
        
    async def get_all_coins(self, force_refresh: bool = False) -> Dict[str, CoinInfo]:
        """
        Get all available coins with their information
        Uses caching to avoid frequent API calls
        """
        # Check cache validity
        if (not force_refresh and 
            self.cached_coins and 
            self.cache_expiry and 
            datetime.now() < self.cache_expiry):
            logger.info(f"Using cached coin data ({len(self.cached_coins)} coins)")
            return self.cached_coins
            
        try:
            # Fetch exchange info and ticker data concurrently
            exchange_info_task = self.fetch_exchange_info()
            ticker_data_task = self.fetch_24hr_ticker()
            
            exchange_info, ticker_data = await asyncio.gather(
                exchange_info_task, ticker_data_task
            )
            
            # Create ticker lookup for faster access
            ticker_lookup = {item['symbol']: item for item in ticker_data}
            
            # Process all symbols
            coins = {}
            for symbol_data in exchange_info.get('symbols', []):
                coin_info = self._parse_symbol_info(symbol_data)
                
                # Add ticker data if available
                if coin_info.symbol in ticker_lookup:
                    coin_info = self._add_ticker_data(coin_info, ticker_lookup[coin_info.symbol])
                    
                coins[coin_info.symbol] = coin_info
                
            # Update cache
            self.cached_coins = coins
            self.cache_expiry = datetime.now() + self.cache_duration
            
            logger.info(f"Successfully fetched {len(coins)} coins")
            return coins
            
        except Exception as e:
            logger.error(f"Error getting all coins: {e}")
            # Return cached data if available
            if self.cached_coins:
                logger.warning("Returning cached data due to error")
                return self.cached_coins
            raise
            
    async def get_usdt_pairs(self, min_volume: float = 0, active_only: bool = True) -> List[CoinInfo]:
        """
        Get all USDT trading pairs with optional filtering
        """
        all_coins = await self.get_all_coins()
        
        usdt_pairs = []
        for coin_info in all_coins.values():
            # Filter for USDT pairs
            if coin_info.quote_asset != 'USDT':
                continue
                
            # Filter for active trading
            if active_only and coin_info.status != 'TRADING':
                continue
                
            # Filter for spot trading permission (but allow empty permissions for backward compatibility)
            if coin_info.permissions and 'SPOT' not in coin_info.permissions:
                continue
                
            # Filter by minimum volume
            if min_volume > 0 and (coin_info.volume_24h or 0) < min_volume:
                continue
                
            usdt_pairs.append(coin_info)
            
        # Sort by 24h volume (descending)
        usdt_pairs.sort(key=lambda x: x.volume_24h or 0, reverse=True)
        
        logger.info(f"Found {len(usdt_pairs)} USDT pairs (min_volume: {min_volume})")
        return usdt_pairs
        
    async def get_top_coins(self, limit: int = 100, quote_asset: str = 'USDT') -> List[CoinInfo]:
        """
        Get top coins by 24h volume
        """
        if quote_asset == 'USDT':
            coins = await self.get_usdt_pairs()
        else:
            all_coins = await self.get_all_coins()
            coins = [coin for coin in all_coins.values() 
                    if coin.quote_asset == quote_asset and coin.status == 'TRADING']
            coins.sort(key=lambda x: x.volume_24h or 0, reverse=True)
            
        return coins[:limit]
        
    async def get_coin_symbols(self, quote_asset: str = 'USDT', active_only: bool = True) -> List[str]:
        """
        Get list of coin symbols for a specific quote asset
        """
        if quote_asset == 'USDT':
            coins = await self.get_usdt_pairs(active_only=active_only)
        else:
            all_coins = await self.get_all_coins()
            coins = [coin for coin in all_coins.values() 
                    if coin.quote_asset == quote_asset]
            if active_only:
                coins = [coin for coin in coins if coin.status == 'TRADING']
                
        return [coin.symbol for coin in coins]
        
    def filter_by_volume(self, coins: List[CoinInfo], min_volume: float) -> List[CoinInfo]:
        """Filter coins by minimum 24h volume"""
        return [coin for coin in coins if (coin.volume_24h or 0) >= min_volume]
        
    def filter_by_price_change(self, coins: List[CoinInfo], 
                              min_change: float = None, 
                              max_change: float = None) -> List[CoinInfo]:
        """Filter coins by 24h price change percentage"""
        filtered = coins
        
        if min_change is not None:
            filtered = [coin for coin in filtered 
                       if (coin.price_change_24h or 0) >= min_change]
                       
        if max_change is not None:
            filtered = [coin for coin in filtered 
                       if (coin.price_change_24h or 0) <= max_change]
                       
        return filtered
        
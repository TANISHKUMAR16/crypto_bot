import asyncio
import logging
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import time
from collections import defaultdict

from coin_discovery import CoinDiscoveryService, CoinInfo
from enhanced_ai_logic import EnhancedAILogic, SignalResult
from rate_limiter import get_rate_limiter_stats
from config import config

logger = logging.getLogger(__name__)

@dataclass
class BatchConfig:
    """Configuration for batch processing"""
    batch_size: int = 50              # Coins per batch
    max_concurrent: int = 10          # Max concurrent requests
    delay_between_batches: float = 2.0  # Seconds between batches
    max_processing_time: float = 300.0  # Max 5 minutes per full scan
    retry_failed: bool = True         # Retry failed coins
    min_volume_filter: float = None   # Will use config.scanner.min_volume_filter
    
    def __post_init__(self):
        if self.min_volume_filter is None:
            self.min_volume_filter = config.scanner.min_volume_filter
    
@dataclass
class BatchStats:
    """Statistics for batch processing"""
    total_coins: int = 0
    processed_coins: int = 0
    successful_coins: int = 0
    failed_coins: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    processing_time: float = 0.0
    average_time_per_coin: float = 0.0
    batches_processed: int = 0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
            
    @property
    def success_rate(self) -> float:
        if self.processed_coins == 0:
            return 0.0
        return (self.successful_coins / self.processed_coins) * 100
        
    @property
    def is_complete(self) -> bool:
        return self.processed_coins >= self.total_coins
        
    def to_dict(self) -> Dict:
        return {
            'total_coins': self.total_coins,
            'processed_coins': self.processed_coins,
            'successful_coins': self.successful_coins,
            'failed_coins': self.failed_coins,
            'success_rate': self.success_rate,
            'processing_time': self.processing_time,
            'average_time_per_coin': self.average_time_per_coin,
            'batches_processed': self.batches_processed,
            'is_complete': self.is_complete,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None
        }

class BatchProcessor:
    """
    Manages batch processing of multiple coins for AI signal analysis
    Handles rate limiting, error recovery, and performance monitoring
    """
    
    def __init__(self, config: BatchConfig = None):
        self.config = config or BatchConfig()
        self.coin_discovery = CoinDiscoveryService()
        self.ai_logic = EnhancedAILogic()
        self.stats = BatchStats()
        self.is_running = False
        self.should_stop = False
        self._progress_callback: Optional[Callable] = None
        
    async def __aenter__(self):
        await self.coin_discovery.__aenter__()
        await self.ai_logic.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.coin_discovery.__aexit__(exc_type, exc_val, exc_tb)
        await self.ai_logic.__aexit__(exc_type, exc_val, exc_tb)
        
    def set_progress_callback(self, callback: Callable[[BatchStats], None]):
        """Set callback function to receive progress updates"""
        self._progress_callback = callback
        
    def _update_progress(self):
        """Update progress and call callback if set"""
        if self._progress_callback:
            try:
                self._progress_callback(self.stats)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")
                
    async def get_coins_to_process(self) -> List[CoinInfo]:
        """
        Get list of coins to process based on configuration
        """
        try:
            logger.info("Discovering coins to process...")
            
            # Get USDT pairs with volume filter
            coins = await self.coin_discovery.get_usdt_pairs(
                min_volume=self.config.min_volume_filter,
                active_only=True
            )
            
            logger.info(f"Found {len(coins)} coins meeting criteria")
            return coins
            
        except Exception as e:
            logger.error(f"Error getting coins to process: {e}")
            return []
            
    async def process_batch(self, coins: List[CoinInfo]) -> Dict[str, SignalResult]:
        """
        Process a batch of coins
        """
        batch_start = time.time()
        symbols = [coin.symbol for coin in coins]
        
        logger.info(f"Processing batch of {len(symbols)} coins")
        
        try:
            # Process batch with AI logic
            results = await self.ai_logic.batch_predict_signals(symbols)
            
            # Update statistics
            batch_time = time.time() - batch_start
            successful = sum(1 for r in results.values() if r.signal != 0 or r.confidence > 0.4)
            
            self.stats.processed_coins += len(results)
            self.stats.successful_coins += successful
            self.stats.failed_coins += len(symbols) - len(results)
            self.stats.batches_processed += 1
            
            logger.info(f"Batch completed in {batch_time:.2f}s, {successful}/{len(results)} successful")
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing batch: {e}")
            self.stats.failed_coins += len(symbols)
            self.stats.errors.append(f"Batch error: {str(e)}")
            return {}
            
    async def process_all_coins(self) -> Dict[str, SignalResult]:
        """
        Process all available coins in batches
        """
        if self.is_running:
            raise RuntimeError("Batch processor is already running")
            
        self.is_running = True
        self.should_stop = False
        
        # Initialize statistics
        self.stats = BatchStats()
        self.stats.start_time = datetime.now()
        
        all_results = {}
        
        try:
            # Get coins to process
            coins = await self.get_coins_to_process()
            if not coins:
                logger.warning("No coins found to process")
                return all_results
                
            self.stats.total_coins = len(coins)
            logger.info(f"Starting batch processing of {len(coins)} coins")
            
            # Split into batches
            batches = [coins[i:i + self.config.batch_size] 
                      for i in range(0, len(coins), self.config.batch_size)]
            
            logger.info(f"Created {len(batches)} batches of max {self.config.batch_size} coins each")
            
            # Process batches
            for batch_idx, batch_coins in enumerate(batches):
                if self.should_stop:
                    logger.info("Batch processing stopped by request")
                    break
                    
                # Check timeout
                elapsed = (datetime.now() - self.stats.start_time).total_seconds()
                if elapsed > self.config.max_processing_time:
                    logger.warning(f"Max processing time ({self.config.max_processing_time}s) exceeded")
                    break
                    
                logger.info(f"Processing batch {batch_idx + 1}/{len(batches)}")
                
                # Process batch
                batch_results = await self.process_batch(batch_coins)
                all_results.update(batch_results)
                
                # Update progress
                self._update_progress()
                
                # Delay between batches (except last one)
                if batch_idx < len(batches) - 1 and self.config.delay_between_batches > 0:
                    await asyncio.sleep(self.config.delay_between_batches)
                    
            # Retry failed coins if enabled
            if self.config.retry_failed and self.stats.failed_coins > 0:
                await self._retry_failed_coins(coins, all_results)
                
        except Exception as e:
            logger.error(f"Error in batch processing: {e}")
            self.stats.errors.append(f"Processing error: {str(e)}")
            
        finally:
            # Finalize statistics
            self.stats.end_time = datetime.now()
            self.stats.processing_time = (self.stats.end_time - self.stats.start_time).total_seconds()
            
            if self.stats.processed_coins > 0:
                self.stats.average_time_per_coin = self.stats.processing_time / self.stats.processed_coins
                
            self.is_running = False
            
            logger.info(f"Batch processing completed: {self.stats.successful_coins}/{self.stats.total_coins} "
                       f"successful in {self.stats.processing_time:.2f}s")
            
            # Final progress update
            self._update_progress()
            
        return all_results
        
    async def _retry_failed_coins(self, original_coins: List[CoinInfo], 
                                 current_results: Dict[str, SignalResult]):
        """
        Retry processing coins that failed in the initial run
        """
        processed_symbols = set(current_results.keys())
        failed_coins = [coin for coin in original_coins if coin.symbol not in processed_symbols]
        
        if not failed_coins:
            return
            
        logger.info(f"Retrying {len(failed_coins)} failed coins")
        
        # Process failed coins in smaller batches
        retry_batch_size = min(10, self.config.batch_size // 2)
        retry_batches = [failed_coins[i:i + retry_batch_size] 
                        for i in range(0, len(failed_coins), retry_batch_size)]
        
        for batch in retry_batches:
            if self.should_stop:
                break
                
            try:
                batch_results = await self.process_batch(batch)
                current_results.update(batch_results)
                await asyncio.sleep(1.0)  # Shorter delay for retries
                
            except Exception as e:
                logger.error(f"Error in retry batch: {e}")
                
    def stop_processing(self):
        """
        Signal the processor to stop after current batch
        """
        logger.info("Stop signal received")
        self.should_stop = True
        
    async def get_processing_status(self) -> Dict:
        """
        Get current processing status
        """
        rate_stats = get_rate_limiter_stats()
        
        return {
            'is_running': self.is_running,
            'should_stop': self.should_stop,
            'stats': self.stats.to_dict(),
            'rate_limiter': rate_stats,
            'config': {
                'batch_size': self.config.batch_size,
                'max_concurrent': self.config.max_concurrent,
                'min_volume_filter': self.config.min_volume_filter
            }
        }
        
    async def process_specific_coins(self, symbols: List[str]) -> Dict[str, SignalResult]:
        """
        Process specific coins (for testing or manual requests)
        """
        logger.info(f"Processing specific coins: {symbols}")
        
        try:
            # Create fake coin info objects
            coins = [CoinInfo(
                symbol=symbol,
                base_asset=symbol.replace('USDT', ''),
                quote_asset='USDT',
                status='TRADING',
                is_spot_trading_allowed=True,
                is_margin_trading_allowed=False,
                permissions=['SPOT'],
                filters={}
            ) for symbol in symbols]
            
            return await self.process_batch(coins)
            
        except Exception as e:
            logger.error(f"Error processing specific coins: {e}")
            return {}

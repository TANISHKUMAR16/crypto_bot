import asyncio
import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass

from batch_processor import BatchProcessor, BatchConfig
from signal_database import SignalDatabase, SignalChange
from enhanced_ai_logic import SignalResult
from coin_discovery import CoinDiscoveryService
from config import config

logger = logging.getLogger(__name__)

@dataclass
class ScannerConfig:
    """Configuration for the enhanced background scanner"""
    scan_interval_minutes: int = 3        # How often to scan all coins
    min_volume_filter: float = None      # Will use config.scanner.min_volume_filter
    batch_size: int = 50                  # Coins per batch
    max_concurrent: int = 10              # Max concurrent requests
    notification_threshold: float = 0.02  # Min price change for notifications
    max_notifications_per_cycle: int = 20 # Max notifications per scan
    enable_auto_cleanup: bool = True      # Auto cleanup old data
    cleanup_days: int = 7                 # Days to keep data
    
    def __post_init__(self):
        if self.min_volume_filter is None:
            self.min_volume_filter = config.scanner.min_volume_filter
    
@dataclass
class ScannerStats:
    """Statistics for the scanner"""
    total_scans: int = 0
    successful_scans: int = 0
    failed_scans: int = 0
    total_coins_processed: int = 0
    total_signals_generated: int = 0
    total_changes_detected: int = 0
    total_notifications_sent: int = 0
    last_scan_time: Optional[datetime] = None
    last_scan_duration: float = 0.0
    average_scan_duration: float = 0.0
    uptime_start: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            'total_scans': self.total_scans,
            'successful_scans': self.successful_scans,
            'failed_scans': self.failed_scans,
            'success_rate': (self.successful_scans / max(1, self.total_scans)) * 100,
            'total_coins_processed': self.total_coins_processed,
            'total_signals_generated': self.total_signals_generated,
            'total_changes_detected': self.total_changes_detected,
            'total_notifications_sent': self.total_notifications_sent,
            'last_scan_time': self.last_scan_time.isoformat() if self.last_scan_time else None,
            'last_scan_duration': self.last_scan_duration,
            'average_scan_duration': self.average_scan_duration,
            'uptime_hours': self._get_uptime_hours()
        }
        
    def _get_uptime_hours(self) -> float:
        if not self.uptime_start:
            return 0.0
        return (datetime.now() - self.uptime_start).total_seconds() / 3600

class EnhancedBackgroundScanner:
    """
    Enhanced background scanner that processes all Binance coins
    Integrates with all the new components for comprehensive analysis
    """
    
    def __init__(self, config: ScannerConfig = None):
        self.config = config or ScannerConfig()
        self.stats = ScannerStats()
        self.is_running = False
        self.should_stop = False
        self.scanner_task: Optional[asyncio.Task] = None
        
        # Components
        self.batch_processor: Optional[BatchProcessor] = None
        self.signal_db: Optional[SignalDatabase] = None
        self.coin_discovery: Optional[CoinDiscoveryService] = None
        
        # Callbacks
        self._notification_callback: Optional[Callable] = None
        self._progress_callback: Optional[Callable] = None
        
        # State tracking
        self.last_cleanup_time: Optional[datetime] = None
        
    async def __aenter__(self):
        await self._initialize_components()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._cleanup_components()
        
    async def _initialize_components(self):
        """Initialize all required components"""
        try:
            # Create batch processor with our config
            batch_config = BatchConfig(
                batch_size=self.config.batch_size,
                max_concurrent=self.config.max_concurrent,
                min_volume_filter=self.config.min_volume_filter
            )
            
            self.batch_processor = BatchProcessor(batch_config)
            await self.batch_processor.__aenter__()
            
            # Initialize database
            self.signal_db = SignalDatabase()
            await self.signal_db.__aenter__()
            
            # Initialize coin discovery
            self.coin_discovery = CoinDiscoveryService()
            await self.coin_discovery.__aenter__()
            
            logger.info("Enhanced background scanner components initialized")
            
        except Exception as e:
            logger.error(f"Error initializing scanner components: {e}")
            raise
            
    async def _cleanup_components(self):
        """Cleanup all components"""
        try:
            if self.batch_processor:
                await self.batch_processor.__aexit__(None, None, None)
                
            if self.signal_db:
                await self.signal_db.__aexit__(None, None, None)
                
            if self.coin_discovery:
                await self.coin_discovery.__aexit__(None, None, None)
                
            logger.info("Scanner components cleaned up")
            
        except Exception as e:
            logger.error(f"Error cleaning up components: {e}")
            
    def set_notification_callback(self, callback: Callable[[List[SignalChange]], None]):
        """Set callback for signal change notifications"""
        self._notification_callback = callback
        
    def set_progress_callback(self, callback: Callable[[Dict], None]):
        """Set callback for progress updates"""
        self._progress_callback = callback
        
    async def start_scanning(self):
        """Start the background scanning process"""
        if self.is_running:
            raise RuntimeError("Scanner is already running")
            
        self.is_running = True
        self.should_stop = False
        self.stats.uptime_start = datetime.now()
        
        logger.info(f"Starting enhanced background scanner (interval: {self.config.scan_interval_minutes} minutes)")
        
        # Start the scanning task
        self.scanner_task = asyncio.create_task(self._scanning_loop())
        
    async def stop_scanning(self):
        """Stop the background scanning process"""
        if not self.is_running:
            return
            
        logger.info("Stopping enhanced background scanner...")
        self.should_stop = True
        
        if self.scanner_task:
            self.scanner_task.cancel()
            try:
                await self.scanner_task
            except asyncio.CancelledError:
                pass
                
        # Stop batch processor if running
        if self.batch_processor:
            self.batch_processor.stop_processing()
            
        self.is_running = False
        logger.info("Enhanced background scanner stopped")
        
    async def _scanning_loop(self):
        """Main scanning loop"""
        try:
            while self.is_running and not self.should_stop:
                try:
                    await self._perform_scan()
                    
                    # Wait for next scan interval
                    if not self.should_stop:
                        await asyncio.sleep(self.config.scan_interval_minutes * 60)
                        
                except Exception as e:
                    logger.error(f"Error in scanning loop: {e}")
                    self.stats.failed_scans += 1
                    
                    # Wait a bit before retrying
                    if not self.should_stop:
                        await asyncio.sleep(60)  # Wait 1 minute on error
                        
        except asyncio.CancelledError:
            logger.info("Scanning loop cancelled")
            
    async def _perform_scan(self):
        """Perform a single scan of all coins"""
        scan_start = datetime.now()
        
        try:
            logger.info("Starting comprehensive coin scan...")
            
            # Update progress
            if self._progress_callback:
                await self._progress_callback({
                    'status': 'starting',
                    'message': 'Starting coin scan...'
                })
            
            # Process all coins
            results = await self.batch_processor.process_all_coins()
            
            if not results:
                logger.warning("No results from batch processing")
                self.stats.failed_scans += 1
                return
                
            # Store results and detect changes
            changes = await self.signal_db.update_latest_signals(results)
            stored_count = len(results)
            
            # Filter significant changes
            significant_changes = self._filter_significant_changes(changes)
            
            # Send notifications
            notifications_sent = 0
            if significant_changes and self._notification_callback:
                try:
                    await self._notification_callback(significant_changes)
                    notifications_sent = len(significant_changes)
                    
                    # Mark as notified
                    symbols = [change.symbol for change in significant_changes]
                    await self.signal_db.mark_changes_notified(symbols)
                    
                except Exception as e:
                    logger.error(f"Error sending notifications: {e}")
                    
            # Update statistics
            scan_duration = (datetime.now() - scan_start).total_seconds()
            self._update_scan_stats(len(results), stored_count, len(changes), 
                                  notifications_sent, scan_duration, True)
            
            # Perform cleanup if needed
            await self._perform_cleanup_if_needed()
            
            # Update progress
            if self._progress_callback:
                await self._progress_callback({
                    'status': 'completed',
                    'message': f'Scan completed: {len(results)} coins, {len(changes)} changes',
                    'results_count': len(results),
                    'changes_count': len(changes),
                    'notifications_sent': notifications_sent,
                    'duration': scan_duration
                })
            
            logger.info(f"Scan completed: {len(results)} coins processed, "
                       f"{len(changes)} changes detected, {notifications_sent} notifications sent "
                       f"in {scan_duration:.2f}s")
                       
        except Exception as e:
            logger.error(f"Error performing scan: {e}")
            scan_duration = (datetime.now() - scan_start).total_seconds()
            self._update_scan_stats(0, 0, 0, 0, scan_duration, False)
            
            if self._progress_callback:
                await self._progress_callback({
                    'status': 'error',
                    'message': f'Scan failed: {str(e)}',
                    'error': str(e)
                })
                
    def _filter_significant_changes(self, changes: List[SignalChange]) -> List[SignalChange]:
        """Filter changes that are significant enough for notifications"""
        if not changes:
            return []
            
        significant = []
        
        for change in changes:
            # Always include signal changes
            if change.old_signal != change.new_signal:
                # Additional filters for noise reduction
                if (abs(change.price_change_pct) >= self.config.notification_threshold * 100 or
                    change.volume_24h >= self.config.min_volume_filter):
                    significant.append(change)
                    
        # Limit number of notifications per cycle
        if len(significant) > self.config.max_notifications_per_cycle:
            # Sort by volume and take top ones
            significant.sort(key=lambda x: x.volume_24h, reverse=True)
            significant = significant[:self.config.max_notifications_per_cycle]
            
        return significant
        
    def _update_scan_stats(self, coins_processed: int, signals_stored: int, 
                          changes_detected: int, notifications_sent: int,
                          duration: float, success: bool):
        """Update scanning statistics"""
        self.stats.total_scans += 1
        
        if success:
            self.stats.successful_scans += 1
        else:
            self.stats.failed_scans += 1
            
        self.stats.total_coins_processed += coins_processed
        self.stats.total_signals_generated += signals_stored
        self.stats.total_changes_detected += changes_detected
        self.stats.total_notifications_sent += notifications_sent
        self.stats.last_scan_time = datetime.now()
        self.stats.last_scan_duration = duration
        
        # Update average duration
        if self.stats.successful_scans > 0:
            total_duration = (self.stats.average_scan_duration * (self.stats.successful_scans - 1) + 
                            duration)
            self.stats.average_scan_duration = total_duration / self.stats.successful_scans
            
    async def _perform_cleanup_if_needed(self):
        """Perform database cleanup if needed"""
        if not self.config.enable_auto_cleanup:
            return
            
        now = datetime.now()
        
        # Check if cleanup is needed (once per day)
        if (self.last_cleanup_time is None or 
            (now - self.last_cleanup_time).total_seconds() > 86400):  # 24 hours
            
            try:
                logger.info("Performing database cleanup...")
                deleted_count = await self.signal_db.cleanup_old_data(self.config.cleanup_days)
                logger.info(f"Cleaned up {deleted_count} old records")
                self.last_cleanup_time = now
                
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
                
    async def get_scanner_status(self) -> Dict:
        """Get comprehensive scanner status"""
        status = {
            'is_running': self.is_running,
            'should_stop': self.should_stop,
            'config': {
                'scan_interval_minutes': self.config.scan_interval_minutes,
                'min_volume_filter': self.config.min_volume_filter,
                'batch_size': self.config.batch_size,
                'max_concurrent': self.config.max_concurrent
            },
            'stats': self.stats.to_dict()
        }
        
        # Add component status
        if self.batch_processor:
            batch_status = await self.batch_processor.get_processing_status()
            status['batch_processor'] = batch_status
            
        if self.signal_db:
            db_stats = await self.signal_db.get_database_stats()
            status['database'] = db_stats
            
        # Add next scan time
        if self.is_running and self.stats.last_scan_time:
            next_scan = (self.stats.last_scan_time + 
                        timedelta(minutes=self.config.scan_interval_minutes))
            remaining_minutes = (next_scan - datetime.now()).total_seconds() / 60
            status['next_scan_in_minutes'] = max(0, remaining_minutes)
            
        return status
        
    async def force_scan(self) -> Dict:
        """Force an immediate scan (for testing/manual trigger)"""
        if not self.is_running:
            raise RuntimeError("Scanner is not running")
            
        logger.info("Forcing immediate scan...")
        await self._perform_scan()
        
        return await self.get_scanner_status()
        
    async def get_recent_signals(self, limit: int = 50, signal_filter: int = None) -> List[Dict]:
        """Get recent signals from database"""
        if not self.signal_db:
            return []
            
        return await self.signal_db.get_latest_signals(limit=limit, signal_filter=signal_filter)
        
    async def get_recent_changes(self, hours: int = 24) -> List[SignalChange]:
        """Get recent signal changes"""
        if not self.signal_db:
            return []
            
        return await self.signal_db.get_signal_changes(hours=hours)

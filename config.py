import os
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class BotConfig:
    """Main bot configuration"""
    telegram_token: str
    log_level: str = "INFO"
    database_path: str = "signals.db"
    
@dataclass
class ScannerConfig:
    """Scanner configuration"""
    scan_interval_minutes: int = 3
    min_volume_filter: float = 100000
    batch_size: int = 50
    max_concurrent: int = 10
    notification_threshold: float = 0.02
    max_notifications_per_cycle: int = 20
    enable_auto_cleanup: bool = True
    cleanup_days: int = 7
    
@dataclass
class RateLimitConfig:
    """Rate limiting configuration"""
    requests_per_minute: int = 1200
    requests_per_second: int = 20
    burst_limit: int = 50
    backoff_factor: float = 2.0
    max_retries: int = 3
    
@dataclass
class AIConfig:
    """AI model configuration"""
    model_path: str = "enhanced_model.pkl"
    scaler_path: str = "enhanced_scaler.pkl"
    training_symbols: list = None
    retrain_interval_hours: int = 24
    confidence_threshold: float = 0.6
    
    def __post_init__(self):
        if self.training_symbols is None:
            self.training_symbols = [
                'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT',
                'XRPUSDT', 'DOTUSDT', 'DOGEUSDT', 'AVAXUSDT', 'LINKUSDT',
                'MATICUSDT', 'LTCUSDT', 'UNIUSDT', 'ATOMUSDT', 'FILUSDT'
            ]

@dataclass
class DatabaseConfig:
    """Database configuration"""
    path: str = "signals.db"
    backup_enabled: bool = True
    backup_interval_hours: int = 6
    max_backups: int = 10
    connection_timeout: int = 30

class Config:
    """Main configuration manager"""
    
    def __init__(self):
        self.bot = self._load_bot_config()
        self.scanner = self._load_scanner_config()
        self.rate_limit = self._load_rate_limit_config()
        self.ai = self._load_ai_config()
        self.database = self._load_database_config()
        
    def _load_bot_config(self) -> BotConfig:
        """Load bot configuration from environment variables"""
        token = os.getenv('TELEGRAM_BOT_TOKEN', '8491711485:AAGsYQ43XDyi_FYWpyF7HAcODR5zw1WG3Qo')
        
        return BotConfig(
            telegram_token=token,
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            database_path=os.getenv('DATABASE_PATH', 'signals.db')
        )
        
    def _load_scanner_config(self) -> ScannerConfig:
        """Load scanner configuration"""
        return ScannerConfig(
            scan_interval_minutes=int(os.getenv('SCAN_INTERVAL_MINUTES', '3')),
            min_volume_filter=float(os.getenv('MIN_VOLUME_FILTER', '100000')),  # Reduced from 500k to 100k
            batch_size=int(os.getenv('BATCH_SIZE', '50')),
            max_concurrent=int(os.getenv('MAX_CONCURRENT', '10')),
            notification_threshold=float(os.getenv('NOTIFICATION_THRESHOLD', '0.02')),
            max_notifications_per_cycle=int(os.getenv('MAX_NOTIFICATIONS_PER_CYCLE', '20')),
            enable_auto_cleanup=os.getenv('ENABLE_AUTO_CLEANUP', 'true').lower() == 'true',
            cleanup_days=int(os.getenv('CLEANUP_DAYS', '7'))
        )
        
    def _load_rate_limit_config(self) -> RateLimitConfig:
        """Load rate limiting configuration"""
        return RateLimitConfig(
            requests_per_minute=int(os.getenv('REQUESTS_PER_MINUTE', '1200')),
            requests_per_second=int(os.getenv('REQUESTS_PER_SECOND', '20')),
            burst_limit=int(os.getenv('BURST_LIMIT', '50')),
            backoff_factor=float(os.getenv('BACKOFF_FACTOR', '2.0')),
            max_retries=int(os.getenv('MAX_RETRIES', '3'))
        )
        
    def _load_ai_config(self) -> AIConfig:
        """Load AI configuration"""
        training_symbols_str = os.getenv('TRAINING_SYMBOLS', '')
        training_symbols = None
        if training_symbols_str:
            training_symbols = [s.strip() for s in training_symbols_str.split(',')]
            
        return AIConfig(
            model_path=os.getenv('MODEL_PATH', 'enhanced_model.pkl'),
            scaler_path=os.getenv('SCALER_PATH', 'enhanced_scaler.pkl'),
            training_symbols=training_symbols,
            retrain_interval_hours=int(os.getenv('RETRAIN_INTERVAL_HOURS', '24')),
            confidence_threshold=float(os.getenv('CONFIDENCE_THRESHOLD', '0.6'))
        )
        
    def _load_database_config(self) -> DatabaseConfig:
        """Load database configuration"""
        return DatabaseConfig(
            path=os.getenv('DATABASE_PATH', 'signals.db'),
            backup_enabled=os.getenv('BACKUP_ENABLED', 'true').lower() == 'true',
            backup_interval_hours=int(os.getenv('BACKUP_INTERVAL_HOURS', '6')),
            max_backups=int(os.getenv('MAX_BACKUPS', '10')),
            connection_timeout=int(os.getenv('CONNECTION_TIMEOUT', '30'))
        )
        
    def setup_logging(self):
        """Setup logging based on configuration"""
        log_level = getattr(logging, self.bot.log_level.upper(), logging.INFO)
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('bot.log', encoding='utf-8')
            ]
        )
        
        # Set specific loggers
        logging.getLogger('aiohttp').setLevel(logging.WARNING)
        logging.getLogger('telegram').setLevel(logging.WARNING)
        
        logger.info(f"Logging configured at {self.bot.log_level} level")
        
    def validate_config(self) -> bool:
        """Validate configuration settings"""
        errors = []
        
        # Validate bot config
        if not self.bot.telegram_token:
            errors.append("Telegram bot token is required")
            
        # Validate scanner config
        if self.scanner.scan_interval_minutes < 1:
            errors.append("Scan interval must be at least 1 minute")
            
        if self.scanner.batch_size < 1:
            errors.append("Batch size must be at least 1")
            
        if self.scanner.max_concurrent < 1:
            errors.append("Max concurrent must be at least 1")
            
        # Validate rate limits
        if self.rate_limit.requests_per_minute < 1:
            errors.append("Requests per minute must be at least 1")
            
        # Validate AI config
        if self.ai.confidence_threshold < 0 or self.ai.confidence_threshold > 1:
            errors.append("Confidence threshold must be between 0 and 1")
            
        if errors:
            for error in errors:
                logger.error(f"Configuration error: {error}")
            return False
            
        logger.info("Configuration validation passed")
        return True
        
    def get_summary(self) -> dict:
        """Get configuration summary"""
        return {
            'bot': {
                'log_level': self.bot.log_level,
                'database_path': self.bot.database_path
            },
            'scanner': {
                'scan_interval_minutes': self.scanner.scan_interval_minutes,
                'min_volume_filter': self.scanner.min_volume_filter,
                'batch_size': self.scanner.batch_size,
                'max_concurrent': self.scanner.max_concurrent,
                'auto_cleanup': self.scanner.enable_auto_cleanup
            },
            'rate_limit': {
                'requests_per_minute': self.rate_limit.requests_per_minute,
                'requests_per_second': self.rate_limit.requests_per_second,
                'max_retries': self.rate_limit.max_retries
            },
            'ai': {
                'model_path': self.ai.model_path,
                'training_symbols_count': len(self.ai.training_symbols),
                'confidence_threshold': self.ai.confidence_threshold
            }
        }

# Global configuration instance
config = Config()

# Environment setup helper
def setup_environment():
    """Setup environment variables for development"""
    env_vars = {
        'TELEGRAM_BOT_TOKEN': '8491711485:AAGsYQ43XDyi_FYWpyF7HAcODR5zw1WG3Qo',
        'LOG_LEVEL': 'INFO',
        'SCAN_INTERVAL_MINUTES': '3',
        'MIN_VOLUME_FILTER': '100000',
        'BATCH_SIZE': '50',
        'MAX_CONCURRENT': '10',
        'REQUESTS_PER_MINUTE': '1200',
        'REQUESTS_PER_SECOND': '20',
        'CONFIDENCE_THRESHOLD': '0.6',
        'ENABLE_AUTO_CLEANUP': 'true',
        'CLEANUP_DAYS': '7'
    }
    
    for key, value in env_vars.items():
        if key not in os.environ:
            os.environ[key] = value
            
    logger.info("Environment variables configured")

# Production configuration helper
def get_production_config() -> Config:
    """Get production-optimized configuration"""
    # Set production environment variables
    production_env = {
        'LOG_LEVEL': 'WARNING',
        'SCAN_INTERVAL_MINUTES': '2',  # Faster scanning
        'MIN_VOLUME_FILTER': '1000000',  # Higher volume filter
        'BATCH_SIZE': '75',  # Larger batches
        'MAX_CONCURRENT': '15',  # More concurrent requests
        'REQUESTS_PER_MINUTE': '1100',  # Conservative rate limit
        'CLEANUP_DAYS': '5',  # Shorter retention
        'BACKUP_ENABLED': 'true',
        'BACKUP_INTERVAL_HOURS': '4'
    }
    
    for key, value in production_env.items():
        os.environ[key] = value
        
    return Config()

# Development configuration helper
def get_development_config() -> Config:
    """Get development-optimized configuration"""
    development_env = {
        'LOG_LEVEL': 'DEBUG',
        'SCAN_INTERVAL_MINUTES': '5',  # Slower for testing
        'MIN_VOLUME_FILTER': '100000',  # Lower volume filter
        'BATCH_SIZE': '20',  # Smaller batches
        'MAX_CONCURRENT': '5',  # Fewer concurrent requests
        'REQUESTS_PER_MINUTE': '600',  # Conservative rate limit
        'CLEANUP_DAYS': '3',  # Shorter retention for testing
        'BACKUP_ENABLED': 'false'
    }
    
    for key, value in development_env.items():
        os.environ[key] = value
        
    return Config()

if __name__ == "__main__":
    # Test configuration
    setup_environment()
    test_config = Config()
    
    print("Configuration Summary:")
    print("=" * 50)
    
    summary = test_config.get_summary()
    for section, settings in summary.items():
        print(f"\n{section.upper()}:")
        for key, value in settings.items():
            print(f"  {key}: {value}")
            
    print(f"\nValidation: {'✅ PASSED' if test_config.validate_config() else '❌ FAILED'}")
import asyncio
import aiosqlite
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import json
import os

from enhanced_ai_logic import SignalResult

logger = logging.getLogger(__name__)

@dataclass
class SignalChange:
    """Represents a change in signal for a coin"""
    symbol: str
    old_signal: int
    new_signal: int
    old_price: float
    new_price: float
    price_change_pct: float
    timestamp: datetime
    volume_24h: float
    rsi: float
    
    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'old_signal': self.old_signal,
            'new_signal': self.new_signal,
            'old_price': self.old_price,
            'new_price': self.new_price,
            'price_change_pct': self.price_change_pct,
            'timestamp': self.timestamp.isoformat(),
            'volume_24h': self.volume_24h,
            'rsi': self.rsi
        }
    
    def to_telegram_message(self) -> str:
        old_emoji = "📈" if self.old_signal == 1 else "📉" if self.old_signal == -1 else "🤝"
        new_emoji = "📈" if self.new_signal == 1 else "📉" if self.new_signal == -1 else "🤝"
        old_text = "BUY" if self.old_signal == 1 else "SELL" if self.old_signal == -1 else "HOLD"
        new_text = "BUY" if self.new_signal == 1 else "SELL" if self.new_signal == -1 else "HOLD"
        
        return (f"🚨 {self.symbol}: {old_emoji}{old_text} → {new_emoji}{new_text}\n"
                f"💰 ${self.new_price:.4f} ({self.price_change_pct:+.2f}%)\n"
                f"📊 RSI: {self.rsi:.1f}")

class SignalDatabase:
    """
    Database manager for storing and retrieving signal data
    Uses SQLite with async support for high performance
    """
    
    def __init__(self, db_path: str = "signals.db"):
        self.db_path = db_path
        self.connection: Optional[aiosqlite.Connection] = None
        
    async def __aenter__(self):
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        
    async def connect(self):
        """Connect to the database and create tables if needed"""
        try:
            self.connection = await aiosqlite.connect(self.db_path)
            await self._create_tables()
            logger.info(f"Connected to database: {self.db_path}")
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            raise
            
    async def close(self):
        """Close database connection"""
        if self.connection:
            await self.connection.close()
            self.connection = None
            
    async def _create_tables(self):
        """Create database tables if they don't exist"""
        try:
            # Signals table - stores all signal results
            await self.connection.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    signal INTEGER NOT NULL,
                    confidence REAL NOT NULL,
                    price REAL NOT NULL,
                    rsi REAL NOT NULL,
                    volume_24h REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    processing_time REAL NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Signal changes table - tracks when signals change
            await self.connection.execute("""
                CREATE TABLE IF NOT EXISTS signal_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    old_signal INTEGER NOT NULL,
                    new_signal INTEGER NOT NULL,
                    old_price REAL NOT NULL,
                    new_price REAL NOT NULL,
                    price_change_pct REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    volume_24h REAL NOT NULL,
                    rsi REAL NOT NULL,
                    notified BOOLEAN DEFAULT FALSE,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Latest signals view - for quick access to current signals
            await self.connection.execute("""
                CREATE TABLE IF NOT EXISTS latest_signals (
                    symbol TEXT PRIMARY KEY,
                    signal INTEGER NOT NULL,
                    confidence REAL NOT NULL,
                    price REAL NOT NULL,
                    rsi REAL NOT NULL,
                    volume_24h REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    processing_time REAL NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for better performance
            await self.connection.execute("CREATE INDEX IF NOT EXISTS idx_signals_symbol_timestamp ON signals(symbol, timestamp)")
            await self.connection.execute("CREATE INDEX IF NOT EXISTS idx_signal_changes_timestamp ON signal_changes(timestamp)")
            await self.connection.execute("CREATE INDEX IF NOT EXISTS idx_signal_changes_notified ON signal_changes(notified)")
            
            await self.connection.commit()
            logger.info("Database tables created/verified")
            
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            raise
            
    async def store_signal(self, result: SignalResult) -> bool:
        """
        Store a signal result in the database
        """
        try:
            if not self.connection:
                await self.connect()
                
            # Insert into signals table
            await self.connection.execute("""
                INSERT INTO signals (symbol, signal, confidence, price, rsi, volume_24h, timestamp, processing_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.symbol,
                result.signal,
                result.confidence,
                result.price,
                result.rsi,
                result.volume_24h,
                result.timestamp.isoformat(),
                result.processing_time
            ))
            
            await self.connection.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error storing signal for {result.symbol}: {e}")
            return False
            
    async def store_signals_batch(self, results: Dict[str, SignalResult]) -> int:
        """
        Store multiple signal results efficiently
        """
        try:
            if not self.connection:
                await self.connect()
                
            # Prepare data for batch insert
            signal_data = []
            for result in results.values():
                signal_data.append((
                    result.symbol,
                    result.signal,
                    result.confidence,
                    result.price,
                    result.rsi,
                    result.volume_24h,
                    result.timestamp.isoformat(),
                    result.processing_time
                ))
                
            # Batch insert
            await self.connection.executemany("""
                INSERT INTO signals (symbol, signal, confidence, price, rsi, volume_24h, timestamp, processing_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, signal_data)
            
            await self.connection.commit()
            logger.info(f"Stored {len(signal_data)} signals in batch")
            return len(signal_data)
            
        except Exception as e:
            logger.error(f"Error storing signal batch: {e}")
            return 0
            
    async def update_latest_signals(self, results: Dict[str, SignalResult]) -> List[SignalChange]:
        """
        Update latest signals and detect changes
        Returns list of signal changes
        """
        try:
            if not self.connection:
                await self.connect()
                
            changes = []
            
            for result in results.values():
                # Get previous signal
                cursor = await self.connection.execute("""
                    SELECT signal, price FROM latest_signals WHERE symbol = ?
                """, (result.symbol,))
                
                previous = await cursor.fetchone()
                
                if previous:
                    old_signal, old_price = previous
                    
                    # Check if signal changed
                    if old_signal != result.signal:
                        price_change_pct = ((result.price - old_price) / old_price) * 100
                        
                        change = SignalChange(
                            symbol=result.symbol,
                            old_signal=old_signal,
                            new_signal=result.signal,
                            old_price=old_price,
                            new_price=result.price,
                            price_change_pct=price_change_pct,
                            timestamp=result.timestamp,
                            volume_24h=result.volume_24h,
                            rsi=result.rsi
                        )
                        
                        changes.append(change)
                        
                        # Store the change
                        await self.connection.execute("""
                            INSERT INTO signal_changes 
                            (symbol, old_signal, new_signal, old_price, new_price, 
                             price_change_pct, timestamp, volume_24h, rsi)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            change.symbol,
                            change.old_signal,
                            change.new_signal,
                            change.old_price,
                            change.new_price,
                            change.price_change_pct,
                            change.timestamp.isoformat(),
                            change.volume_24h,
                            change.rsi
                        ))
                
                # Update or insert latest signal
                await self.connection.execute("""
                    INSERT OR REPLACE INTO latest_signals 
                    (symbol, signal, confidence, price, rsi, volume_24h, timestamp, processing_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result.symbol,
                    result.signal,
                    result.confidence,
                    result.price,
                    result.rsi,
                    result.volume_24h,
                    result.timestamp.isoformat(),
                    result.processing_time
                ))
                
            await self.connection.commit()
            
            if changes:
                logger.info(f"Detected {len(changes)} signal changes")
                
            return changes
            
        except Exception as e:
            logger.error(f"Error updating latest signals: {e}")
            return []
            
    async def get_latest_signals(self, limit: int = 100, signal_filter: int = None) -> List[Dict]:
        """
        Get latest signals with optional filtering
        """
        try:
            if not self.connection:
                await self.connect()
                
            query = "SELECT * FROM latest_signals"
            params = []
            
            if signal_filter is not None:
                query += " WHERE signal = ?"
                params.append(signal_filter)
                
            query += " ORDER BY volume_24h DESC LIMIT ?"
            params.append(limit)
            
            cursor = await self.connection.execute(query, params)
            rows = await cursor.fetchall()
            
            # Convert to dictionaries
            columns = [description[0] for description in cursor.description]
            results = [dict(zip(columns, row)) for row in rows]
            
            return results
            
        except Exception as e:
            logger.error(f"Error getting latest signals: {e}")
            return []
            
    async def get_signal_changes(self, hours: int = 24, notified_only: bool = False) -> List[SignalChange]:
        """
        Get recent signal changes
        """
        try:
            if not self.connection:
                await self.connect()
                
            since = datetime.now() - timedelta(hours=hours)
            
            query = """
                SELECT symbol, old_signal, new_signal, old_price, new_price, 
                       price_change_pct, timestamp, volume_24h, rsi
                FROM signal_changes 
                WHERE timestamp >= ?
            """
            params = [since.isoformat()]
            
            if notified_only:
                query += " AND notified = FALSE"
                
            query += " ORDER BY timestamp DESC"
            
            cursor = await self.connection.execute(query, params)
            rows = await cursor.fetchall()
            
            changes = []
            for row in rows:
                changes.append(SignalChange(
                    symbol=row[0],
                    old_signal=row[1],
                    new_signal=row[2],
                    old_price=row[3],
                    new_price=row[4],
                    price_change_pct=row[5],
                    timestamp=datetime.fromisoformat(row[6]),
                    volume_24h=row[7],
                    rsi=row[8]
                ))
                
            return changes
            
        except Exception as e:
            logger.error(f"Error getting signal changes: {e}")
            return []
            
    async def mark_changes_notified(self, symbols: List[str]) -> bool:
        """
        Mark signal changes as notified
        """
        try:
            if not self.connection:
                await self.connect()
                
            placeholders = ','.join(['?' for _ in symbols])
            await self.connection.execute(f"""
                UPDATE signal_changes 
                SET notified = TRUE 
                WHERE symbol IN ({placeholders}) AND notified = FALSE
            """, symbols)
            
            await self.connection.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error marking changes as notified: {e}")
            return False
            
    async def get_signal_history(self, symbol: str, hours: int = 24) -> List[Dict]:
        """
        Get signal history for a specific symbol
        """
        try:
            if not self.connection:
                await self.connect()
                
            since = datetime.now() - timedelta(hours=hours)
            
            cursor = await self.connection.execute("""
                SELECT * FROM signals 
                WHERE symbol = ? AND timestamp >= ?
                ORDER BY timestamp DESC
            """, (symbol, since.isoformat()))
            
            rows = await cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            
            return [dict(zip(columns, row)) for row in rows]
            
        except Exception as e:
            logger.error(f"Error getting signal history for {symbol}: {e}")
            return []
            
    async def cleanup_old_data(self, days: int = 7) -> int:
        """
        Clean up old signal data to manage database size
        """
        try:
            if not self.connection:
                await self.connect()
                
            cutoff = datetime.now() - timedelta(days=days)
            
            # Delete old signals
            cursor = await self.connection.execute("""
                DELETE FROM signals WHERE timestamp < ?
            """, (cutoff.isoformat(),))
            
            deleted_signals = cursor.rowcount
            
            # Delete old signal changes (keep longer for analysis)
            cutoff_changes = datetime.now() - timedelta(days=days * 2)
            cursor = await self.connection.execute("""
                DELETE FROM signal_changes WHERE timestamp < ?
            """, (cutoff_changes.isoformat(),))
            
            deleted_changes = cursor.rowcount
            
            await self.connection.commit()
            
            total_deleted = deleted_signals + deleted_changes
            logger.info(f"Cleaned up {total_deleted} old records ({deleted_signals} signals, {deleted_changes} changes)")
            
            return total_deleted
            
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
            return 0
            
    async def get_database_stats(self) -> Dict:
        """
        Get database statistics
        """
        try:
            if not self.connection:
                await self.connect()
                
            stats = {}
            
            # Count records in each table
            for table in ['signals', 'signal_changes', 'latest_signals']:
                cursor = await self.connection.execute(f"SELECT COUNT(*) FROM {table}")
                count = await cursor.fetchone()
                stats[f"{table}_count"] = count[0] if count else 0
                
            # Get database file size
            if os.path.exists(self.db_path):
                stats['db_size_mb'] = os.path.getsize(self.db_path) / (1024 * 1024)
            else:
                stats['db_size_mb'] = 0
                
            # Get latest update time
            cursor = await self.connection.execute("""
                SELECT MAX(updated_at) FROM latest_signals
            """)
            latest_update = await cursor.fetchone()
            stats['latest_update'] = latest_update[0] if latest_update and latest_update[0] else None
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}

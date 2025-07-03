"""
Database connection manager for PostgreSQL and SQLite
Handles connection pooling, migrations, and database operations
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any, List, Union
from contextlib import asynccontextmanager
import json
from datetime import datetime

# Database imports
try:
    import asyncpg
    import psycopg2
    from psycopg2.extras import RealDictCursor
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    asyncpg = None
    psycopg2 = None

import sqlite3
import aiosqlite

from config import config

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Database manager supporting both PostgreSQL and SQLite"""
    
    def __init__(self):
        self.db_type = config.DATABASE_TYPE.lower()
        self.pool: Optional[Union[asyncpg.Pool, aiosqlite.Connection]] = None
        self.connection_string = self._build_connection_string()
        
    def _build_connection_string(self) -> str:
        """Build database connection string"""
        if self.db_type == 'postgresql':
            # Try Railway auto-generated URL first
            if config.DATABASE_URL:
                return config.DATABASE_URL
            elif hasattr(config, 'RAILWAY_POSTGRES_URL') and config.RAILWAY_POSTGRES_URL:
                return config.RAILWAY_POSTGRES_URL
            else:
                # Build from individual components
                return (
                    f"postgresql://{config.POSTGRES_USER}:{config.POSTGRES_PASSWORD}"
                    f"@{config.POSTGRES_HOST}:{config.POSTGRES_PORT}/{config.POSTGRES_DB}"
                )
        else:
            # Fallback to DATABASE_PATH if SQLITE_DATABASE_PATH not set
            if hasattr(config, 'SQLITE_DATABASE_PATH') and config.SQLITE_DATABASE_PATH:
                return config.SQLITE_DATABASE_PATH
            return os.path.join(os.path.dirname(__file__), config.DATABASE_PATH)
    
    async def initialize(self):
        """Initialize database connection pool"""
        try:
            if self.db_type == 'postgresql':
                if not POSTGRES_AVAILABLE:
                    raise ImportError("PostgreSQL dependencies not installed. Run: pip install asyncpg psycopg2-binary")
                
                logger.info("Initializing PostgreSQL connection pool...")
                self.pool = await asyncpg.create_pool(
                    self.connection_string,
                    min_size=1,
                    max_size=config.DATABASE_POOL_SIZE,
                    max_queries=50000,
                    max_inactive_connection_lifetime=300,
                    timeout=config.DATABASE_CONNECTION_TIMEOUT,
                    command_timeout=60,
                    server_settings={
                        'jit': 'off'  # Disable JIT for better performance on small queries
                    }
                )
                logger.info("PostgreSQL connection pool initialized successfully")
                
            else:
                logger.info("Initializing SQLite connection...")
                self.pool = await aiosqlite.connect(
                    self.connection_string,
                    timeout=config.DATABASE_CONNECTION_TIMEOUT
                )
                # Enable WAL mode for better concurrency
                await self.pool.execute("PRAGMA journal_mode=WAL")
                await self.pool.execute("PRAGMA synchronous=NORMAL")
                await self.pool.execute("PRAGMA cache_size=10000")
                await self.pool.execute("PRAGMA temp_store=memory")
                logger.info("SQLite connection initialized successfully")
            
            # Run migrations
            if config.AUTO_MIGRATE_ON_START:
                await self.run_migrations()
                
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def close(self):
        """Close database connections"""
        try:
            if self.pool:
                if self.db_type == 'postgresql':
                    await self.pool.close()
                else:
                    await self.pool.close()
                logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error closing database connections: {e}")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection context manager"""
        if self.db_type == 'postgresql':
            async with self.pool.acquire() as connection:
                yield connection
        else:
            yield self.pool
    
    async def execute_query(self, query: str, params: tuple = None, fetch: str = None) -> Optional[Union[List[Dict], Dict, Any]]:
        """Execute database query with error handling"""
        try:
            async with self.get_connection() as conn:
                if self.db_type == 'postgresql':
                    if fetch == 'all':
                        result = await conn.fetch(query, *(params or ()))
                        return [dict(row) for row in result]
                    elif fetch == 'one':
                        result = await conn.fetchrow(query, *(params or ()))
                        return dict(result) if result else None
                    else:
                        return await conn.execute(query, *(params or ()))
                else:
                    # SQLite
                    if fetch == 'all':
                        async with conn.execute(query, params or ()) as cursor:
                            rows = await cursor.fetchall()
                            columns = [description[0] for description in cursor.description]
                            return [dict(zip(columns, row)) for row in rows]
                    elif fetch == 'one':
                        async with conn.execute(query, params or ()) as cursor:
                            row = await cursor.fetchone()
                            if row:
                                columns = [description[0] for description in cursor.description]
                                return dict(zip(columns, row))
                            return None
                    else:
                        await conn.execute(query, params or ())
                        await conn.commit()
                        return None
                        
        except Exception as e:
            logger.error(f"Database query error: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            raise
    
    async def execute_transaction(self, queries: List[tuple]) -> bool:
        """Execute multiple queries in a transaction"""
        try:
            async with self.get_connection() as conn:
                if self.db_type == 'postgresql':
                    async with conn.transaction():
                        for query, params in queries:
                            await conn.execute(query, *(params or ()))
                else:
                    # SQLite
                    for query, params in queries:
                        await conn.execute(query, params or ())
                    await conn.commit()
                return True
        except Exception as e:
            logger.error(f"Transaction error: {e}")
            return False
    
    async def run_migrations(self):
        """Run database migrations"""
        try:
            logger.info("Running database migrations...")
            
            # Create migrations table
            if self.db_type == 'postgresql':
                await self.execute_query("""
                    CREATE TABLE IF NOT EXISTS migrations (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) UNIQUE NOT NULL,
                        executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            else:
                await self.execute_query("""
                    CREATE TABLE IF NOT EXISTS migrations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            
            # Get executed migrations
            executed_migrations = await self.execute_query(
                "SELECT name FROM migrations ORDER BY id",
                fetch='all'
            )
            executed_names = {m['name'] for m in (executed_migrations or [])}
            
            # Run pending migrations
            migrations = self._get_migrations()
            for migration_name, migration_sql in migrations:
                if migration_name not in executed_names:
                    logger.info(f"Running migration: {migration_name}")
                    
                    # Execute migration in transaction
                    queries = [
                        (migration_sql, None),
                        ("INSERT INTO migrations (name) VALUES (?)" if self.db_type == 'sqlite' 
                         else "INSERT INTO migrations (name) VALUES ($1)", (migration_name,))
                    ]
                    
                    success = await self.execute_transaction(queries)
                    if success:
                        logger.info(f"Migration {migration_name} completed successfully")
                    else:
                        raise Exception(f"Migration {migration_name} failed")
            
            logger.info("All migrations completed successfully")
            
        except Exception as e:
            logger.error(f"Migration error: {e}")
            raise
    
    def _get_migrations(self) -> List[tuple]:
        """Get list of migrations to run"""
        if self.db_type == 'postgresql':
            return [
                ('001_create_users_table', """
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username VARCHAR(255),
                        first_name VARCHAR(255),
                        current_flow VARCHAR(50) DEFAULT 'welcome',
                        registration_status VARCHAR(50) DEFAULT 'not_started',
                        deposit_confirmed BOOLEAN DEFAULT FALSE,
                        uid VARCHAR(255),
                        verification_status VARCHAR(50) DEFAULT 'pending',
                        verification_method VARCHAR(50) DEFAULT 'none',
                        verified_by VARCHAR(255),
                        verification_date TIMESTAMP,
                        screenshot_file_id VARCHAR(255),
                        join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        follow_up_day INTEGER DEFAULT 0,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """),
                ('002_create_user_interactions_table', """
                    CREATE TABLE IF NOT EXISTS user_interactions (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        interaction_type VARCHAR(100) NOT NULL,
                        interaction_data TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                    )
                """),
                ('003_create_verification_queue_table', """
                    CREATE TABLE IF NOT EXISTS verification_queue (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        uid VARCHAR(255),
                        screenshot_file_id VARCHAR(255),
                        auto_verified BOOLEAN DEFAULT FALSE,
                        admin_reviewed BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        reviewed_at TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                    )
                """),
                ('004_create_indexes', """
                    CREATE INDEX IF NOT EXISTS idx_users_user_id ON users (user_id);
                    CREATE INDEX IF NOT EXISTS idx_users_verification_status ON users (verification_status);
                    CREATE INDEX IF NOT EXISTS idx_users_last_interaction ON users (last_interaction);
                    CREATE INDEX IF NOT EXISTS idx_user_interactions_user_id ON user_interactions (user_id);
                    CREATE INDEX IF NOT EXISTS idx_user_interactions_timestamp ON user_interactions (timestamp);
                    CREATE INDEX IF NOT EXISTS idx_verification_queue_user_id ON verification_queue (user_id);
                    CREATE INDEX IF NOT EXISTS idx_verification_queue_admin_reviewed ON verification_queue (admin_reviewed);
                """),
                ('005_create_error_logs_table', """
                    CREATE TABLE IF NOT EXISTS error_logs (
                        id SERIAL PRIMARY KEY,
                        error_type VARCHAR(255),
                        error_message TEXT,
                        stack_trace TEXT,
                        context VARCHAR(255),
                        user_id BIGINT,
                        extra_data JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """),
                ('006_create_bot_metrics_table', """
                    CREATE TABLE IF NOT EXISTS bot_metrics (
                        id SERIAL PRIMARY KEY,
                        metric_name VARCHAR(100) NOT NULL,
                        metric_value NUMERIC,
                        metric_data JSONB,
                        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            ]
        else:
            # SQLite migrations
            return [
                ('001_create_users_table', """
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        current_flow TEXT DEFAULT 'welcome',
                        registration_status TEXT DEFAULT 'not_started',
                        deposit_confirmed BOOLEAN DEFAULT FALSE,
                        uid TEXT,
                        verification_status TEXT DEFAULT 'pending',
                        verification_method TEXT DEFAULT 'none',
                        verified_by TEXT,
                        verification_date TIMESTAMP,
                        screenshot_file_id TEXT,
                        join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        follow_up_day INTEGER DEFAULT 0,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """),
                ('002_create_user_interactions_table', """
                    CREATE TABLE IF NOT EXISTS user_interactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        interaction_type TEXT NOT NULL,
                        interaction_data TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                """),
                ('003_create_verification_queue_table', """
                    CREATE TABLE IF NOT EXISTS verification_queue (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        uid TEXT,
                        screenshot_file_id TEXT,
                        auto_verified BOOLEAN DEFAULT FALSE,
                        admin_reviewed BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        reviewed_at TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                """),
                ('004_create_indexes', """
                    CREATE INDEX IF NOT EXISTS idx_users_user_id ON users (user_id);
                    CREATE INDEX IF NOT EXISTS idx_users_verification_status ON users (verification_status);
                    CREATE INDEX IF NOT EXISTS idx_users_last_interaction ON users (last_interaction);
                    CREATE INDEX IF NOT EXISTS idx_user_interactions_user_id ON user_interactions (user_id);
                    CREATE INDEX IF NOT EXISTS idx_user_interactions_timestamp ON user_interactions (timestamp);
                    CREATE INDEX IF NOT EXISTS idx_verification_queue_user_id ON verification_queue (user_id);
                    CREATE INDEX IF NOT EXISTS idx_verification_queue_admin_reviewed ON verification_queue (admin_reviewed);
                """),
                ('005_create_error_logs_table', """
                    CREATE TABLE IF NOT EXISTS error_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        error_type TEXT,
                        error_message TEXT,
                        stack_trace TEXT,
                        context TEXT,
                        user_id INTEGER,
                        extra_data TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """),
                ('006_create_bot_metrics_table', """
                    CREATE TABLE IF NOT EXISTS bot_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        metric_name TEXT NOT NULL,
                        metric_value REAL,
                        metric_data TEXT,
                        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            ]
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform database health check"""
        try:
            start_time = datetime.now()
            
            # Simple query to test connection
            result = await self.execute_query("SELECT 1 as test", fetch='one')
            
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds() * 1000
            
            return {
                'status': 'healthy',
                'database_type': self.db_type,
                'response_time_ms': round(response_time, 2),
                'connection_string': self.connection_string.split('@')[0] + '@***' if '@' in self.connection_string else 'local',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'database_type': self.db_type,
                'timestamp': datetime.now().isoformat()
            }

# Global database manager instance
db_manager = DatabaseManager()

# Convenience functions for backward compatibility
async def get_user_data(user_id: int) -> Optional[Dict]:
    """Get user data by user ID"""
    return await db_manager.execute_query(
        "SELECT * FROM users WHERE user_id = $1" if db_manager.db_type == 'postgresql' else "SELECT * FROM users WHERE user_id = ?",
        (user_id,),
        fetch='one'
    )

async def update_user_data(user_id: int, **kwargs) -> bool:
    """Update user data"""
    if not kwargs:
        return False
    
    kwargs['updated_at'] = datetime.now()
    
    set_clause = ', '.join([f"{key} = ${i+2}" if db_manager.db_type == 'postgresql' else f"{key} = ?" 
                           for i, key in enumerate(kwargs.keys())])
    
    if db_manager.db_type == 'postgresql':
        query = f"UPDATE users SET {set_clause} WHERE user_id = $1"
        params = (user_id, *kwargs.values())
    else:
        query = f"UPDATE users SET {set_clause} WHERE user_id = ?"
        params = (*kwargs.values(), user_id)
    
    try:
        await db_manager.execute_query(query, params)
        return True
    except Exception as e:
        logger.error(f"Error updating user data: {e}")
        return False

async def create_user(user_id: int, username: str, first_name: str) -> bool:
    """Create or update user"""
    try:
        if db_manager.db_type == 'postgresql':
            query = """
                INSERT INTO users (user_id, username, first_name, join_date, last_interaction)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_interaction = EXCLUDED.last_interaction,
                    updated_at = CURRENT_TIMESTAMP
            """
        else:
            query = """
                INSERT OR REPLACE INTO users (user_id, username, first_name, join_date, last_interaction)
                VALUES (?, ?, ?, ?, ?)
            """
        
        now = datetime.now()
        await db_manager.execute_query(query, (user_id, username, first_name, now, now))
        return True
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return False

async def log_interaction(user_id: int, interaction_type: str, interaction_data: str = "") -> bool:
    """Log user interaction"""
    try:
        query = "INSERT INTO user_interactions (user_id, interaction_type, interaction_data) VALUES ($1, $2, $3)" if db_manager.db_type == 'postgresql' else "INSERT INTO user_interactions (user_id, interaction_type, interaction_data) VALUES (?, ?, ?)"
        await db_manager.execute_query(query, (user_id, interaction_type, interaction_data))
        return True
    except Exception as e:
        logger.error(f"Error logging interaction: {e}")
        return False

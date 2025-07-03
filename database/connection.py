"""
Database connection manager for PostgreSQL and SQLite
Handles connection pooling, migrations, and database operations for OPTRIXTRADES bot
"""

import os
import asyncio
import logging
import sqlite3
from typing import Optional, Dict, Any, List, Union
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

# Database imports
try:
    import asyncpg
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    asyncpg = None

try:
    import aiosqlite
    SQLITE_AVAILABLE = True
except ImportError:
    SQLITE_AVAILABLE = False
    aiosqlite = None

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages database connections and operations for both PostgreSQL and SQLite"""
    
    def __init__(self):
        self.pool = None
        self.db_type = os.getenv('DATABASE_TYPE', 'sqlite').lower()
        self.database_url = os.getenv('DATABASE_URL', '')
        self.sqlite_path = os.getenv('SQLITE_DATABASE_PATH', 'trading_bot.db')
        self.is_initialized = False
        
    async def initialize(self):
        """Initialize database connection"""
        try:
            if self.db_type == 'postgresql' and POSTGRES_AVAILABLE and self.database_url:
                await self._init_postgresql()
            elif SQLITE_AVAILABLE:
                await self._init_sqlite()
            else:
                raise RuntimeError("No suitable database backend available")
            
            await self._create_tables()
            self.is_initialized = True
            logger.info(f"Database initialized successfully ({self.db_type})")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    async def _init_postgresql(self):
        """Initialize PostgreSQL connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=1,
                max_size=int(os.getenv('DATABASE_POOL_SIZE', '10')),
                command_timeout=int(os.getenv('DATABASE_CONNECTION_TIMEOUT', '30')),
                max_inactive_connection_lifetime=300,
                server_settings={
                    'jit': 'off',  # Disable JIT for better performance on small queries
                    'statement_timeout': '30000'  # 30 second statement timeout
                }
            )
            logger.info("PostgreSQL connection pool created")
        except Exception as e:
            logger.error(f"PostgreSQL connection failed: {e}")
            raise
    
    async def _init_sqlite(self):
        """Initialize SQLite connection"""
        try:
            # Create database file if it doesn't exist
            if not os.path.exists(self.sqlite_path):
                conn = sqlite3.connect(self.sqlite_path)
                conn.close()
            
            # Initialize aiosqlite connection pool
            self.pool = await aiosqlite.connect(self.sqlite_path)
            # Enable WAL mode for better concurrency
            await self.pool.execute("PRAGMA journal_mode=WAL")
            await self.pool.execute("PRAGMA synchronous=NORMAL")
            await self.pool.execute("PRAGMA cache_size=10000")
            await self.pool.execute("PRAGMA temp_store=MEMORY")
            
            logger.info(f"SQLite database ready: {self.sqlite_path}")
        except Exception as e:
            logger.error(f"SQLite initialization failed: {e}")
            raise
    
    async def _create_tables(self):
        """Create database tables with migrations"""
        try:
            # Create migrations table if not exists
            if self.db_type == 'postgresql':
                await self.pool.execute('''
                    CREATE TABLE IF NOT EXISTS migrations (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) UNIQUE NOT NULL,
                        executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
            else:
                await self.pool.execute('''
                    CREATE TABLE IF NOT EXISTS migrations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
            
            # Get executed migrations
            if self.db_type == 'postgresql':
                executed_migrations = await self.pool.fetch('SELECT name FROM migrations ORDER BY id')
                executed_names = {m['name'] for m in executed_migrations}
            else:
                cursor = await self.pool.execute('SELECT name FROM migrations ORDER BY id')
                executed_migrations = await cursor.fetchall()
                executed_names = {m[0] for m in executed_migrations}
            
            # Run pending migrations
            migrations = self._get_migrations()
            for migration_name, migration_sql in migrations:
                if migration_name not in executed_names:
                    logger.info(f"Running migration: {migration_name}")
                    
                    try:
                        # Start transaction
                        if self.db_type == 'postgresql':
                            async with self.pool.acquire() as conn:
                                async with conn.transaction():
                                    await conn.execute(migration_sql)
                                    await conn.execute(
                                        "INSERT INTO migrations (name) VALUES ($1)",
                                        migration_name
                                    )
                        else:
                            await self.pool.execute(migration_sql)
                            await self.pool.execute(
                                "INSERT INTO migrations (name) VALUES (?)",
                                (migration_name,)
                            )
                            await self.pool.commit()
                            
                        logger.info(f"Migration {migration_name} completed successfully")
                    except Exception as e:
                        logger.error(f"Migration {migration_name} failed: {e}")
                        raise
                        
            logger.info("Database tables initialized")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            raise
    
    def _get_migrations(self) -> List[tuple]:
        """Get list of migrations to run"""
        if self.db_type == 'postgresql':
            return [
                ('001_create_users_table', '''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        current_flow TEXT DEFAULT 'welcome',
                        registration_status TEXT DEFAULT 'not_started',
                        deposit_confirmed BOOLEAN DEFAULT FALSE,
                        uid TEXT,
                        join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        follow_up_day INTEGER DEFAULT 0,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                '''),
                ('002_create_user_interactions_table', '''
                    CREATE TABLE IF NOT EXISTS user_interactions (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT,
                        interaction_type TEXT,
                        interaction_data TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                '''),
                ('003_create_verification_requests_table', '''
                    CREATE TABLE IF NOT EXISTS verification_requests (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT,
                        uid TEXT,
                        screenshot_file_id TEXT,
                        status TEXT DEFAULT 'pending',
                        admin_notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        verified_at TIMESTAMP,
                        verified_by BIGINT,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                '''),
                ('004_create_indexes', '''
                    CREATE INDEX IF NOT EXISTS idx_users_user_id ON users (user_id);
                    CREATE INDEX IF NOT EXISTS idx_users_last_interaction ON users (last_interaction);
                    CREATE INDEX IF NOT EXISTS idx_user_interactions_user_id ON user_interactions (user_id);
                    CREATE INDEX IF NOT EXISTS idx_verification_requests_status ON verification_requests (status);
                ''')
            ]
        else:
            return [
                ('001_create_users_table', '''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        current_flow TEXT DEFAULT 'welcome',
                        registration_status TEXT DEFAULT 'not_started',
                        deposit_confirmed BOOLEAN DEFAULT FALSE,
                        uid TEXT,
                        join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        follow_up_day INTEGER DEFAULT 0,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                '''),
                ('002_create_user_interactions_table', '''
                    CREATE TABLE IF NOT EXISTS user_interactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        interaction_type TEXT,
                        interaction_data TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                '''),
                ('003_create_verification_requests_table', '''
                    CREATE TABLE IF NOT EXISTS verification_requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        uid TEXT,
                        screenshot_file_id TEXT,
                        status TEXT DEFAULT 'pending',
                        admin_notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        verified_at TIMESTAMP,
                        verified_by INTEGER,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                '''),
                ('004_create_indexes', '''
                    CREATE INDEX IF NOT EXISTS idx_users_user_id ON users (user_id);
                    CREATE INDEX IF NOT EXISTS idx_users_last_interaction ON users (last_interaction);
                    CREATE INDEX IF NOT EXISTS idx_user_interactions_user_id ON user_interactions (user_id);
                    CREATE INDEX IF NOT EXISTS idx_verification_requests_status ON verification_requests (status);
                ''')
            ]
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection context manager"""
        if self.db_type == 'postgresql':
            async with self.pool.acquire() as conn:
                yield conn
        else:
            # For SQLite, we use the same connection pool
            yield self.pool
    
    async def execute(self, query: str, *args, fetch: str = None):
        """Execute a query with optional fetch"""
        try:
            if self.db_type == 'postgresql':
                async with self.pool.acquire() as conn:
                    if fetch == 'all':
                        result = await conn.fetch(query, *args)
                        return [dict(row) for row in result]
                    elif fetch == 'one':
                        result = await conn.fetchrow(query, *args)
                        return dict(result) if result else None
                    else:
                        return await conn.execute(query, *args)
            else:
                if fetch == 'all':
                    cursor = await self.pool.execute(query, args)
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
                elif fetch == 'one':
                    cursor = await self.pool.execute(query, args)
                    row = await cursor.fetchone()
                    return dict(row) if row else None
                else:
                    await self.pool.execute(query, args)
                    await self.pool.commit()
                    return None
        except Exception as e:
            logger.error(f"Database query error: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Args: {args}")
            raise
    
    async def close(self):
        """Close database connections"""
        if self.pool:
            if self.db_type == 'postgresql':
                await self.pool.close()
            else:
                await self.pool.close()
            logger.info("Database connections closed")

# Global database manager instance
db_manager = DatabaseManager()

# Database operation functions
async def get_user_data(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user data from database"""
    try:
        if db_manager.db_type == 'postgresql':
            query = 'SELECT * FROM users WHERE user_id = $1'
        else:
            query = 'SELECT * FROM users WHERE user_id = ?'
        
        return await db_manager.execute(query, user_id, fetch='one')
    except Exception as e:
        logger.error(f"Error getting user data: {e}")
        return None

async def update_user_data(user_id: int, **kwargs) -> bool:
    """Update user data in database"""
    try:
        # Add updated_at timestamp
        kwargs['updated_at'] = datetime.now()
        
        if db_manager.db_type == 'postgresql':
            set_clause = ', '.join([f"{key} = ${i+2}" for i, key in enumerate(kwargs.keys())])
            query = f'UPDATE users SET {set_clause} WHERE user_id = $1'
            args = [user_id] + list(kwargs.values())
        else:
            set_clause = ', '.join([f"{key} = ?" for key in kwargs.keys()])
            query = f'UPDATE users SET {set_clause} WHERE user_id = ?'
            args = list(kwargs.values()) + [user_id]
        
        await db_manager.execute(query, *args)
        return True
    except Exception as e:
        logger.error(f"Error updating user data: {e}")
        return False

async def create_user(user_id: int, username: str, first_name: str) -> bool:
    """Create new user in database"""
    try:
        now = datetime.now()
        
        if db_manager.db_type == 'postgresql':
            query = '''
                INSERT INTO users (user_id, username, first_name, join_date, last_interaction, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_interaction = EXCLUDED.last_interaction,
                    updated_at = EXCLUDED.updated_at
            '''
        else:
            query = '''
                INSERT OR REPLACE INTO users (user_id, username, first_name, join_date, last_interaction, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            '''
        
        await db_manager.execute(query, user_id, username, first_name, now, now, now, now)
        return True
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return False

async def log_interaction(user_id: int, interaction_type: str, interaction_data: str = "") -> bool:
    """Log user interaction"""
    try:
        if db_manager.db_type == 'postgresql':
            query = 'INSERT INTO user_interactions (user_id, interaction_type, interaction_data) VALUES ($1, $2, $3)'
        else:
            query = 'INSERT INTO user_interactions (user_id, interaction_type, interaction_data) VALUES (?, ?, ?)'
        
        await db_manager.execute(query, user_id, interaction_type, interaction_data)
        return True
    except Exception as e:
        logger.error(f"Error logging interaction: {e}")
        return False

async def get_pending_verifications() -> List[Dict[str, Any]]:
    """Get pending verification requests"""
    try:
        if db_manager.db_type == 'postgresql':
            query = '''
                SELECT v.*, u.username, u.first_name 
                FROM verification_requests v
                JOIN users u ON v.user_id = u.user_id
                WHERE v.status = 'pending'
                ORDER BY v.created_at ASC
            '''
        else:
            query = '''
                SELECT v.*, u.username, u.first_name 
                FROM verification_requests v
                JOIN users u ON v.user_id = u.user_id
                WHERE v.status = 'pending'
                ORDER BY v.created_at ASC
            '''
        
        return await db_manager.execute(query, fetch='all')
    except Exception as e:
        logger.error(f"Error getting pending verifications: {e}")
        return []

# Convenience functions
async def initialize_db():
    """Initialize database - main entry point"""
    await db_manager.initialize()

async def cleanup_db():
    """Cleanup database connections"""
    await db_manager.close()

async def get_all_users() -> List[Dict[str, Any]]:
    """Get all users from database"""
    try:
        if db_manager.db_type == 'postgresql':
            query = 'SELECT * FROM users ORDER BY join_date DESC'
        else:
            query = 'SELECT * FROM users ORDER BY join_date DESC'
        
        return await db_manager.execute(query, fetch='all')
    except Exception as e:
        logger.error(f"Error getting all users: {e}")
        return []

async def delete_user(user_id: int) -> bool:
    """Delete user from database"""
    try:
        # First delete related records
        if db_manager.db_type == 'postgresql':
            await db_manager.execute('DELETE FROM user_interactions WHERE user_id = $1', user_id)
            await db_manager.execute('DELETE FROM verification_requests WHERE user_id = $1', user_id)
            await db_manager.execute('DELETE FROM users WHERE user_id = $1', user_id)
        else:
            await db_manager.execute('DELETE FROM user_interactions WHERE user_id = ?', user_id)
            await db_manager.execute('DELETE FROM verification_requests WHERE user_id = ?', user_id)
            await db_manager.execute('DELETE FROM users WHERE user_id = ?', user_id)
        
        return True
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        return False

async def health_check() -> Dict[str, Any]:
    """Perform database health check"""
    try:
        start_time = datetime.now()
        result = await db_manager.execute("SELECT 1 as test", fetch='one')
        end_time = datetime.now()
        
        return {
            'status': 'healthy',
            'response_time_ms': (end_time - start_time).total_seconds() * 1000,
            'database_type': db_manager.db_type,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'database_type': db_manager.db_type,
            'timestamp': datetime.now().isoformat()
        }
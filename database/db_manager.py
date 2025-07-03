import sqlite3
import psycopg2
import psycopg2.extras
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import sys
import os

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BotConfig

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Database abstraction layer supporting both SQLite and PostgreSQL"""
    
    def __init__(self):
        self.db_type = BotConfig.DATABASE_TYPE.lower()
        self.connection = None
        
    def get_connection(self):
        """Get database connection based on configuration"""
        if self.db_type == 'postgresql':
            return psycopg2.connect(
                host=BotConfig.POSTGRES_HOST,
                port=BotConfig.POSTGRES_PORT,
                database=BotConfig.POSTGRES_DB,
                user=BotConfig.POSTGRES_USER,
                password=BotConfig.POSTGRES_PASSWORD
            )
        else:
            return sqlite3.connect(BotConfig.SQLITE_DATABASE_PATH)
    
    def execute_query(self, query: str, params: tuple = None, fetch: bool = False) -> Optional[List[Dict]]:
        """Execute a database query"""
        try:
            conn = self.get_connection()
            
            if self.db_type == 'postgresql':
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            else:
                cursor = conn.cursor()
                cursor.row_factory = sqlite3.Row
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            if fetch:
                if self.db_type == 'postgresql':
                    result = [dict(row) for row in cursor.fetchall()]
                else:
                    result = [dict(row) for row in cursor.fetchall()]
                conn.close()
                return result
            else:
                conn.commit()
                conn.close()
                return None
                
        except Exception as e:
            logger.error(f"Database error: {e}")
            if conn:
                conn.close()
            raise e
    
    def init_database(self):
        """Initialize database with all required tables"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Adjust SQL syntax based on database type
            if self.db_type == 'postgresql':
                # PostgreSQL syntax
                tables = [
                    '''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username VARCHAR(255),
                        first_name VARCHAR(255),
                        uid VARCHAR(50),
                        deposit_screenshot VARCHAR(500),
                        verification_status VARCHAR(20) DEFAULT 'pending',
                        premium_access BOOLEAN DEFAULT FALSE,
                        group_access BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    ''',
                    '''
                    CREATE TABLE IF NOT EXISTS interactions (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT,
                        interaction_type VARCHAR(50),
                        interaction_data TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    ''',
                    '''
                    CREATE TABLE IF NOT EXISTS verification_requests (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT,
                        uid VARCHAR(50),
                        screenshot_file_id VARCHAR(500),
                        status VARCHAR(20) DEFAULT 'pending',
                        admin_response TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    ''',
                    '''
                    CREATE TABLE IF NOT EXISTS broadcast_messages (
                        id SERIAL PRIMARY KEY,
                        message_text TEXT,
                        total_users INTEGER,
                        sent_count INTEGER DEFAULT 0,
                        failed_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    ''',
                    '''
                    CREATE TABLE IF NOT EXISTS chat_history (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT,
                        message_type VARCHAR(20),
                        message_text TEXT,
                        message_data JSONB,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(user_id)
                    )
                    '''
                ]
            else:
                # SQLite syntax
                tables = [
                    '''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        uid TEXT,
                        deposit_screenshot TEXT,
                        verification_status TEXT DEFAULT 'pending',
                        premium_access INTEGER DEFAULT 0,
                        group_access INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    ''',
                    '''
                    CREATE TABLE IF NOT EXISTS interactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        interaction_type TEXT,
                        interaction_data TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    ''',
                    '''
                    CREATE TABLE IF NOT EXISTS verification_requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        uid TEXT,
                        screenshot_file_id TEXT,
                        status TEXT DEFAULT 'pending',
                        admin_response TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    ''',
                    '''
                    CREATE TABLE IF NOT EXISTS broadcast_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        message_text TEXT,
                        total_users INTEGER,
                        sent_count INTEGER DEFAULT 0,
                        failed_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    ''',
                    '''
                    CREATE TABLE IF NOT EXISTS chat_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        message_type TEXT,
                        message_text TEXT,
                        message_data TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(user_id)
                    )
                    '''
                ]
            
            for table_sql in tables:
                cursor.execute(table_sql)
            
            conn.commit()
            conn.close()
            logger.info(f"Database initialized successfully with {self.db_type}")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise e
    
    def log_chat_message(self, user_id: int, message_type: str, message_text: str, message_data: Dict = None):
        """Log chat message to history"""
        try:
            if self.db_type == 'postgresql':
                import json
                query = '''
                    INSERT INTO chat_history (user_id, message_type, message_text, message_data)
                    VALUES (%s, %s, %s, %s)
                '''
                params = (user_id, message_type, message_text, json.dumps(message_data) if message_data else None)
            else:
                import json
                query = '''
                    INSERT INTO chat_history (user_id, message_type, message_text, message_data)
                    VALUES (?, ?, ?, ?)
                '''
                params = (user_id, message_type, message_text, json.dumps(message_data) if message_data else None)
            
            self.execute_query(query, params)
            
        except Exception as e:
            logger.error(f"Failed to log chat message: {e}")
    
    def get_chat_history(self, user_id: int, limit: int = 50) -> List[Dict]:
        """Get chat history for a user"""
        try:
            if self.db_type == 'postgresql':
                query = '''
                    SELECT * FROM chat_history 
                    WHERE user_id = %s 
                    ORDER BY timestamp DESC 
                    LIMIT %s
                '''
            else:
                query = '''
                    SELECT * FROM chat_history 
                    WHERE user_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                '''
            
            return self.execute_query(query, (user_id, limit), fetch=True)
            
        except Exception as e:
            logger.error(f"Failed to get chat history: {e}")
            return []
    
    def get_all_chat_history(self, limit: int = 1000) -> List[Dict]:
        """Get all chat history across all users"""
        try:
            if self.db_type == 'postgresql':
                query = '''
                    SELECT ch.*, u.username, u.first_name 
                    FROM chat_history ch
                    LEFT JOIN users u ON ch.user_id = u.user_id
                    ORDER BY ch.timestamp DESC 
                    LIMIT %s
                '''
            else:
                query = '''
                    SELECT ch.*, u.username, u.first_name 
                    FROM chat_history ch
                    LEFT JOIN users u ON ch.user_id = u.user_id
                    ORDER BY ch.timestamp DESC 
                    LIMIT ?
                '''
            
            return self.execute_query(query, (limit,), fetch=True)
            
        except Exception as e:
            logger.error(f"Failed to get all chat history: {e}")
            return []
    
    def get_recent_activity(self, limit: int = 30) -> List[Dict]:
        """Get recent activity across all users"""
        try:
            if self.db_type == 'postgresql':
                query = '''
                    SELECT ch.*, u.username, u.first_name 
                    FROM chat_history ch
                    LEFT JOIN users u ON ch.user_id = u.user_id
                    ORDER BY ch.timestamp DESC 
                    LIMIT %s
                '''
            else:
                query = '''
                    SELECT ch.*, u.username, u.first_name 
                    FROM chat_history ch
                    LEFT JOIN users u ON ch.user_id = u.user_id
                    ORDER BY ch.timestamp DESC 
                    LIMIT ?
                '''
            
            return self.execute_query(query, (limit,), fetch=True)
            
        except Exception as e:
            logger.error(f"Failed to get recent activity: {e}")
            return []

# Global database manager instance
db_manager = DatabaseManager()

def get_chat_history(user_id, limit=50):
    """Get chat history for a specific user"""
    return db_manager.get_chat_history(user_id, limit)

def get_recent_activity(limit=30):
    """Get recent activity across all users"""
    return db_manager.get_recent_activity(limit)
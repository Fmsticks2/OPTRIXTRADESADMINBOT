"""Database utility functions for OPTRIXTRADES Telegram Bot"""

import logging
from typing import Dict, Any, List, Optional, Tuple, Union

from telegram_bot.utils.error_handler import ErrorLogger

logger = logging.getLogger(__name__)


async def execute_query(db_manager, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
    """Execute a database query with error handling.
    
    Args:
        db_manager: The database manager instance
        query: The SQL query to execute
        params: Query parameters (to prevent SQL injection)
        
    Returns:
        List of dictionaries containing the query results
        
    Raises:
        Exception: If the query execution fails
    """
    try:
        async with db_manager.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params or ())
                if query.strip().upper().startswith("SELECT"):
                    columns = [col[0] for col in cursor.description]
                    return [dict(zip(columns, row)) for row in await cursor.fetchall()]
                else:
                    return []
    except Exception as e:
        ErrorLogger.log_database_error(
            operation="execute_query",
            error=e,
            details={"query": query, "params": params}
        )
        raise


async def get_user_by_id(db_manager, user_id: int) -> Optional[Dict[str, Any]]:
    """Get user information by user ID.
    
    Args:
        db_manager: The database manager instance
        user_id: The Telegram user ID
        
    Returns:
        User information as a dictionary, or None if not found
    """
    try:
        query = "SELECT * FROM users WHERE user_id = %s"
        results = await execute_query(db_manager, query, (user_id,))
        return results[0] if results else None
    except Exception as e:
        ErrorLogger.log_database_error(
            operation="get_user_by_id",
            error=e,
            details={"user_id": user_id}
        )
        return None


async def get_user_verification_status(db_manager, user_id: int) -> Optional[str]:
    """Get user verification status.
    
    Args:
        db_manager: The database manager instance
        user_id: The Telegram user ID
        
    Returns:
        Verification status (verified, pending, rejected, None)
    """
    try:
        query = "SELECT verification_status FROM users WHERE user_id = %s"
        results = await execute_query(db_manager, query, (user_id,))
        return results[0]["verification_status"] if results else None
    except Exception as e:
        ErrorLogger.log_database_error(
            operation="get_user_verification_status",
            error=e,
            details={"user_id": user_id}
        )
        return None


async def update_user_verification_status(db_manager, user_id: int, status: str) -> bool:
    """Update user verification status.
    
    Args:
        db_manager: The database manager instance
        user_id: The Telegram user ID
        status: The new verification status
        
    Returns:
        True if successful, False otherwise
    """
    try:
        query = "UPDATE users SET verification_status = %s WHERE user_id = %s"
        await execute_query(db_manager, query, (status, user_id))
        return True
    except Exception as e:
        ErrorLogger.log_database_error(
            operation="update_user_verification_status",
            error=e,
            details={"user_id": user_id, "status": status}
        )
        return False


async def get_verification_queue(db_manager, limit: int = 10) -> List[Dict[str, Any]]:
    """Get the verification queue.
    
    Args:
        db_manager: The database manager instance
        limit: Maximum number of records to return
        
    Returns:
        List of users in the verification queue
    """
    try:
        query = """
        SELECT u.user_id, u.username, u.first_name, u.last_name, 
               v.submission_time, v.verification_photo_id
        FROM users u
        JOIN verification_requests v ON u.user_id = v.user_id
        WHERE u.verification_status = 'pending'
        ORDER BY v.submission_time ASC
        LIMIT %s
        """
        return await execute_query(db_manager, query, (limit,))
    except Exception as e:
        ErrorLogger.log_database_error(
            operation="get_verification_queue",
            error=e,
            details={"limit": limit}
        )
        return []


async def get_recent_activity(db_manager, limit: int = 20) -> List[Dict[str, Any]]:
    """Get recent user activity.
    
    Args:
        db_manager: The database manager instance
        limit: Maximum number of records to return
        
    Returns:
        List of recent activity records
    """
    try:
        query = """
        SELECT a.activity_id, a.user_id, u.username, a.activity_type, 
               a.activity_data, a.timestamp
        FROM user_activity a
        LEFT JOIN users u ON a.user_id = u.user_id
        ORDER BY a.timestamp DESC
        LIMIT %s
        """
        return await execute_query(db_manager, query, (limit,))
    except Exception as e:
        ErrorLogger.log_database_error(
            operation="get_recent_activity",
            error=e,
            details={"limit": limit}
        )
        return []


async def log_user_activity(db_manager, user_id: int, activity_type: str, activity_data: Dict[str, Any]) -> bool:
    """Log user activity.
    
    Args:
        db_manager: The database manager instance
        user_id: The Telegram user ID
        activity_type: Type of activity (command, verification, etc.)
        activity_data: Additional activity data
        
    Returns:
        True if successful, False otherwise
    """
    try:
        query = """
        INSERT INTO user_activity (user_id, activity_type, activity_data)
        VALUES (%s, %s, %s)
        """
        await execute_query(db_manager, query, (user_id, activity_type, str(activity_data)))
        return True
    except Exception as e:
        ErrorLogger.log_database_error(
            operation="log_user_activity",
            error=e,
            details={
                "user_id": user_id,
                "activity_type": activity_type,
                "activity_data": activity_data
            }
        )
        return False
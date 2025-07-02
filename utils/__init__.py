"""
Utilities package for OPTRIXTRADES bot
"""

from .error_handler import ErrorHandler, error_handler, safe_execute, safe_execute_async

__all__ = ['ErrorHandler', 'error_handler', 'safe_execute', 'safe_execute_async']

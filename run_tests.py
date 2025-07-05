#!/usr/bin/env python
"""Test runner for OPTRIXTRADES Telegram Bot"""

import unittest
import sys
import os
import logging
import argparse
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_results.log')
    ]
)

logger = logging.getLogger('test_runner')

def discover_and_run_tests(test_type=None, pattern=None, verbose=False):
    """Discover and run tests based on type and pattern"""
    start_time = datetime.now()
    logger.info(f"Starting test run at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Determine test directory and pattern
    test_dir = os.path.join(os.path.dirname(__file__), 'tests')
    
    if pattern is None:
        if test_type == 'unit':
            pattern = 'test_*.py'
        elif test_type == 'integration':
            pattern = 'integration_*.py'
        else:
            pattern = 'test_*.py'
    
    logger.info(f"Discovering tests in {test_dir} with pattern {pattern}")
    
    # Discover tests
    test_suite = unittest.defaultTestLoader.discover(test_dir, pattern=pattern)
    
    # Run tests
    test_runner = unittest.TextTestRunner(verbosity=2 if verbose else 1)
    result = test_runner.run(test_suite)
    
    # Log results
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    logger.info(f"Test run completed in {duration:.2f} seconds")
    logger.info(f"Tests run: {result.testsRun}")
    logger.info(f"Failures: {len(result.failures)}")
    logger.info(f"Errors: {len(result.errors)}")
    logger.info(f"Skipped: {len(result.skipped)}")
    
    # Return success status (True if no failures or errors)
    return len(result.failures) == 0 and len(result.errors) == 0

def main():
    """Main entry point for test runner"""
    parser = argparse.ArgumentParser(description='Run OPTRIXTRADES tests')
    parser.add_argument(
        '--type', 
        choices=['unit', 'integration', 'all'],
        default='all',
        help='Type of tests to run (default: all)'
    )
    parser.add_argument(
        '--pattern',
        help='Pattern for test discovery (e.g., "test_error_*.py")',
        default=None
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    success = discover_and_run_tests(
        test_type=args.type,
        pattern=args.pattern,
        verbose=args.verbose
    )
    
    # Exit with appropriate status code
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
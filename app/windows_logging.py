"""
Windows-compatible logging configuration for GentleΩ
Handles Unicode encoding issues and provides clean console output
"""

import logging
import sys
import os
from pathlib import Path

class WindowsSafeFormatter(logging.Formatter):
    """
    Custom formatter that replaces Unicode characters that cause issues in Windows console
    """
    
    # Unicode character replacements for Windows console compatibility
    UNICODE_REPLACEMENTS = {
        'Ω': 'Omega',  # Greek Omega
        '✅': '[OK]',   # Check mark
        '❌': '[ERROR]', # Cross mark
        '⚠️': '[WARN]',  # Warning
        '🚀': '[START]', # Rocket
        '🔗': '[CHAIN]', # Link
        '📊': '[METRICS]', # Chart
        '🔄': '[CYCLE]',  # Refresh
        '💡': '[INFO]',   # Bulb
        '🛑': '[STOP]',   # Stop sign
        '👋': '[BYE]',    # Wave
        '🎉': '[SUCCESS]', # Party
        '🔍': '[SEARCH]', # Magnifying glass
        '⏳': '[WAIT]',   # Hourglass
    }
    
    def format(self, record):
        """Format the log record with Unicode replacement"""
        # Get the original formatted message
        original_message = super().format(record)
        
        # Replace problematic Unicode characters
        safe_message = original_message
        for unicode_char, replacement in self.UNICODE_REPLACEMENTS.items():
            safe_message = safe_message.replace(unicode_char, replacement)
        
        return safe_message

def setup_windows_safe_logging(logger_name: str, log_level: int = logging.INFO) -> logging.Logger:
    """
    Set up Windows-safe logging configuration
    """
    # Create logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler with UTF-8 encoding
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # Set encoding explicitly for Windows
    if hasattr(console_handler.stream, 'reconfigure'):
        try:
            console_handler.stream.reconfigure(encoding='utf-8', errors='replace')
        except:
            pass  # Fallback if reconfigure fails
    
    # Create formatter
    formatter = WindowsSafeFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    # Create file handler for detailed logging (with Unicode support)
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    file_handler = logging.FileHandler(
        log_dir / f"{logger_name.lower()}.log", 
        encoding='utf-8',
        mode='a'
    )
    file_handler.setLevel(logging.DEBUG)
    
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    return logger

def configure_system_encoding():
    """
    Configure system-level encoding for Windows compatibility
    """
    # Set console encoding
    if sys.platform.startswith('win'):
        try:
            # Set console code page to UTF-8
            os.system('chcp 65001 > nul 2>&1')
            
            # Set environment variables for UTF-8
            os.environ['PYTHONIOENCODING'] = 'utf-8'
            os.environ['PYTHONUTF8'] = '1'
            
        except Exception:
            pass  # Silently fail if we can't set encoding
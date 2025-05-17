"""
CMD-Pilot - AI-powered command line assistant
"""

from .core.command_engine import CommandEngine
from .core.security import CommandValidator
from .core.error_handler import ErrorHandler
from .ui.main_window import ModernUI

__all__ = [
    'CommandEngine',
    'ModernUI',
    'CommandValidator',
    'ErrorHandler'
]

__version__ = '1.0.0'

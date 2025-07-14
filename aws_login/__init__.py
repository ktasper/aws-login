"""AWS Login Tool - ADFS authentication with YAML configuration"""

__version__ = "1.0.0"

from .config import Config
from .cli import main

__all__ = ['Config', 'main']
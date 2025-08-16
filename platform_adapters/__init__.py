"""
Platform adapters for various ATS systems
"""
from .base_adapter import BaseAdapter, AdapterResult
from .greenhouse import GreenhouseAdapter
from .lever import LeverAdapter
from .workable import WorkableAdapter
from .generic_ai import GenericAIAdapter
from .adapter_registry import AdapterRegistry

__all__ = [
    'BaseAdapter',
    'AdapterResult',
    'GreenhouseAdapter',
    'LeverAdapter',
    'WorkableAdapter',
    'GenericAIAdapter',
    'AdapterRegistry'
]

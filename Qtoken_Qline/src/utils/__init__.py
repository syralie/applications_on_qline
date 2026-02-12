"""
Utils package for the QToken protocol
"""

from .protocol_utils import (
    generate_presentation_points,
    xor_bits,
    is_port_in_use,
    # Integer-based bit operations
    list_to_int,
    str_to_int,
    int_to_str,
    int_to_list,
    xor_bits_int,
    hamming_distance_int,
    normalize_to_int,
    set_to_mask,
)
from .logging_config import setup_logging

__all__ = [
    'generate_presentation_points',
    'xor_bits',
    'is_port_in_use',
    'setup_logging',
    # Integer-based bit operations
    'list_to_int',
    'str_to_int',
    'int_to_str',
    'int_to_list',
    'xor_bits_int',
    'hamming_distance_int',
    'normalize_to_int',
    'set_to_mask',
]

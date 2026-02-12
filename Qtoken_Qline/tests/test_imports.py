#!/usr/bin/env python3
"""
Test script to verify all imports work correctly
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def test_imports():
    """Test all module imports"""
    print("Testing QToken protocol imports...")

    try:
        # Test configuration imports
        print("   Testing config imports...")
        from config.defaults import (
            ALICE_DEFAULT_X, ALICE_DEFAULT_Y,
            BOB_DEFAULT_T, BOB_DEFAULT_U,
            DEFAULT_BOB_PORT, DEFAULT_ALICE_AGENT_PORT, DEFAULT_BOB_AGENT_BASE_PORT
        )
        print("   Config imports successful")

        # Test utility imports
        print("   Testing utility imports...")
        from src.utils.logging_config import setup_logging
        from src.utils.protocol_utils import xor_bits, generate_presentation_points, verify_token
        from src.utils.participant import Participant
        print("   Utility imports successful")

        # Test main participant imports
        print("   Testing participant imports...")
        from src.alice.alice import Alice
        from src.bob.bob import Bob
        print("   Participant imports successful")

        # Test agent imports
        print("   Testing agent imports...")
        from src.agents.alice_agent import AliceAgent
        from src.agents.bob_agent import BobAgent
        print("   Agent imports successful")

        print("All imports successful!")
        return True

    except ImportError as e:
        print(f"Import error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

def test_default_values():
    """Test default values"""
    print("\nTesting default values...")

    from config.defaults import (
        ALICE_DEFAULT_X, ALICE_DEFAULT_Y,
        BOB_DEFAULT_T, BOB_DEFAULT_U
    )

    # Check that all default values have the same length
    values = [ALICE_DEFAULT_X, ALICE_DEFAULT_Y, BOB_DEFAULT_T, BOB_DEFAULT_U]
    lengths = [len(v) for v in values]

    if len(set(lengths)) == 1:
        print(f"   All default values have the same length: {lengths[0]} bits")
        print(f"   Values: x={ALICE_DEFAULT_X}, y={ALICE_DEFAULT_Y}, t={BOB_DEFAULT_T}, u={BOB_DEFAULT_U}")
    else:
        print(f"   Default values have different lengths: {lengths}")
        return False

    return True

def test_utility_functions():
    """Test utility functions"""
    print("\nTesting utility functions...")

    from src.utils.protocol_utils import xor_bits, generate_presentation_points

    # Test XOR function
    result = xor_bits("1010", "1100")
    expected = "0110"
    if result == expected:
        print("   XOR function works correctly")
    else:
        print(f"   XOR function failed: expected {expected}, got {result}")
        return False

    # Test presentation points generation
    points = generate_presentation_points(2)
    expected_count = 2**2  # 4 agents
    if len(points) == expected_count:
        print(f"   Presentation points generation works: {len(points)} agents")
    else:
        print(f"   Presentation points generation failed: expected {expected_count}, got {len(points)}")
        return False

    return True

def main():
    """Main test function"""
    print("==========================================")
    print("QTOKEN PROTOCOL IMPORT TESTS")
    print("==========================================")

    success = True

    # Test imports
    if not test_imports():
        success = False

    # Test default values
    if not test_default_values():
        success = False

    # Test utility functions
    if not test_utility_functions():
        success = False

    print("\n==========================================")
    if success:
        print("ALL TESTS PASSED!")
        print("   The QToken protocol is ready to use")
    else:
        print("SOME TESTS FAILED!")
        print("   Please check the errors above")
    print("==========================================")

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Alice launcher script
Automatically configures the path and launches Alice
"""

import sys
import os
import asyncio


def main():
    # Get project root directory
    project_root = os.path.dirname(os.path.abspath(__file__))

    # Add project root to path
    sys.path.insert(0, project_root)

    # Import and execute Alice
    from src.alice.alice import main as alice_main
    asyncio.run(alice_main())


if __name__ == "__main__":
    main()

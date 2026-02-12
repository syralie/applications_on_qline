#!/usr/bin/env python3
"""
Bob launcher script
Automatically configures the path and launches Bob
"""

import sys
import os
import asyncio


def main():
    # Get project root directory
    project_root = os.path.dirname(os.path.abspath(__file__))

    # Add project root to path
    sys.path.insert(0, project_root)

    # Import and execute Bob
    from src.bob.bob import main as bob_main
    asyncio.run(bob_main())


if __name__ == "__main__":
    main()

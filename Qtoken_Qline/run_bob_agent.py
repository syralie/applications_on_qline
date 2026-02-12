#!/usr/bin/env python3
"""
Bob agent launcher script
Automatically configures the path and launches Bob agent
"""

import sys
import os

def main():
    # Get project root directory
    project_root = os.path.dirname(os.path.abspath(__file__))

    # Add project root to path
    sys.path.insert(0, project_root)

    # Import and execute Bob agent
    from src.agents.bob_agent import main as agent_main
    agent_main()

if __name__ == "__main__":
    main()

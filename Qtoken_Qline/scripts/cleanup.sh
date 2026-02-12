#!/bin/bash

# Cleanup script for QToken protocol
# Kills all related Python processes

echo "Cleaning up QToken protocol processes..."

# Kill all Python processes related to the project
echo "   Killing Bob processes..."
pkill -f "python3.*bob.py"
pkill -f "python3.*run_bob.py"

echo "   Killing Alice processes..."
pkill -f "python3.*alice.py"
pkill -f "python3.*run_alice.py"

echo "   Killing Bob agent processes..."
pkill -f "python3.*bob_agent.py"
pkill -f "python3.*run_bob_agent.py"

echo "   Killing Alice agent processes..."
pkill -f "python3.*alice_agent.py"
pkill -f "python3.*run_alice_agent.py"

echo "   Killing any remaining Python processes from the project..."
pkill -f "qtoken"

echo "Cleanup completed"
echo "   All QToken protocol processes have been terminated"

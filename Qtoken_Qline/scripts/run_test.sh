#!/bin/bash

# Simple test launcher script
# Launches the main test script with default parameters

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Launching QToken protocol test..."
echo "Using default mode (M=2, default values)"
echo ""

# Launch the main test script
"$SCRIPT_DIR/test_protocol_no_hw.sh" 2 default

echo ""
echo "Test completed"

#!/bin/bash

# Script to automatically launch hw_sim + gc simulation
# Can be called standalone or from other scripts
# Based on README.md instructions

# Colors for messages
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments for standalone vs called mode
STANDALONE=true
OPEN_TERMINAL=true

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-terminal)
            OPEN_TERMINAL=false
            shift
            ;;
        --called)
            STANDALONE=false
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Base path
SIM_PATH="$HOME/VeriQloud/kiwi_hw_control/config/sim"

if [ "$STANDALONE" = true ]; then
    echo -e "${GREEN}=== Launching hw_sim + gc simulation ===${NC}"
fi

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo -e "${RED}Error: tmux is not installed. Please install it with:${NC}"
    echo "sudo apt-get install tmux"
    exit 1
fi

# Check if base directory exists
if [ ! -d "$SIM_PATH" ]; then
    echo -e "${RED}Error: Directory $SIM_PATH does not exist.${NC}"
    echo "Please ensure kiwi_hw_control is installed in the right place."
    exit 1
fi

# Check if binaries are available (only check critical ones)
BINARIES=("simulator" "gc_bob" "gc_alice")
for binary in "${BINARIES[@]}"; do
    if ! command -v "$binary" &> /dev/null; then
        echo -e "${YELLOW}Warning: $binary is not in PATH.${NC}"
        echo "Make sure binaries are copied to ~/bin and ~/bin is in PATH."
    fi
done

# Kill existing tmux sessions if they exist
if tmux has-session -t hw_simulation 2>/dev/null; then
    echo -e "${YELLOW}Existing tmux session detected. Stopping previous session...${NC}"
    tmux kill-session -t hw_simulation
fi

# Create new tmux session
echo -e "${GREEN}Creating tmux session 'hw_simulation'...${NC}"
tmux new-session -d -s hw_simulation -c "$SIM_PATH"

# Create 4 windows and launch commands
echo -e "${GREEN}Launching simulation processes...${NC}"

# Window 1: hw_sim bob
tmux rename-window -t hw_simulation:0 'hw_sim_bob'
tmux send-keys -t hw_simulation:0 "cd $SIM_PATH && simulator -c bob/sim.json" Enter

# Window 2: hw_sim alice
tmux new-window -t hw_simulation:1 -n 'hw_sim_alice' -c "$SIM_PATH"
tmux send-keys -t hw_simulation:1 "simulator -c alice/sim.json" Enter

# Window 3: gc_bob
tmux new-window -t hw_simulation:2 -n 'gc_bob' -c "$SIM_PATH"
tmux send-keys -t hw_simulation:2 "gc_bob -c bob/gc.json" Enter

# Window 4: gc_alice
tmux new-window -t hw_simulation:3 -n 'gc_alice' -c "$SIM_PATH"
tmux send-keys -t hw_simulation:3 "gc_alice -c alice/gc.json" Enter

# Note: Readers are now called directly from alice.py and bob.py when --sim=True
# No need to launch them separately here

echo -e "${GREEN}=== Simulation launched successfully! ===${NC}"
if [ "$STANDALONE" = true ]; then
    echo -e "${YELLOW}Processes running:${NC}"
    echo "  - 4 tmux windows: hw_sim (bob/alice) + gc (bob/alice)"
    echo "  - Readers will be called automatically by Bob and Alice"
    echo ""
    echo -e "${YELLOW}To see the tmux terminals:${NC}"
    echo "tmux attach-session -t hw_simulation"
    echo ""
    echo -e "${YELLOW}To navigate between tmux windows:${NC}"
    echo "Ctrl+b then window number (0-3)"
    echo ""
    echo -e "${YELLOW}To stop the simulation:${NC}"
    echo "tmux kill-session -t hw_simulation"
    echo ""
    echo -e "${GREEN}All processes are now running!${NC}"
fi

# Open gnome-terminal only if requested
if [ "$OPEN_TERMINAL" = true ]; then
    gnome-terminal --title="simulation" -- bash -c "tmux attach-session -t hw_simulation; exec bash"
fi

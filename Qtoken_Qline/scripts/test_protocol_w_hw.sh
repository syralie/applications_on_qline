#!/bin/bash

# QToken Protocol Test Script with Hardware Simulation
#
# This script:
# - Launches hardware simulation via scripts/launch_simulation.sh
# - Tests the full QToken protocol with hardware simulation
#
# Launch order:
# 1. Hardware simulation (hw_sim + gc_bob + gc_alice) in tmux
# 2. Bob main server (in background, output to terminal)
# 3. Alice main client (in separate gnome-terminal)
# 4. BobAgent processes (2^M agents, each in separate terminal)
# 5. AliceAgent processes (2^M agents, each in separate terminal)
#
# Features:
# - Automatic shutdown: When Bob/Alice stops, their agents follow automatically
# - Graceful cleanup: Ctrl+C triggers proper cleanup of all processes
# - Hardware simulation in tmux for easy monitoring
#
# Usage: ./test_protocol_w_hw.sh <M> [bit_size] [gamma_err]

# Get project root (script is in scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
export PYTHONPATH="$PROJECT_ROOT"

# Function to handle cleanup on script exit
cleanup() {
    echo ""
    echo "Received interrupt signal. Cleaning up..."

    # Kill Bob process if it's still running
    if [ ! -z "$BOB_PID" ] && kill -0 $BOB_PID 2>/dev/null; then
        echo "Killing Bob process (PID: $BOB_PID)..."
        kill -TERM $BOB_PID 2>/dev/null
        sleep 1
        # Force kill if still running
        if kill -0 $BOB_PID 2>/dev/null; then
            echo "Force killing Bob process..."
            kill -KILL $BOB_PID 2>/dev/null
        fi
    fi

    # Kill all Bob and Alice processes
    echo "Killing all Bob and Alice processes..."
    pkill -f "python3 run_bob.py" 2>/dev/null
    pkill -f "python3 run_alice.py" 2>/dev/null
    pkill -f "python3 run_bob_agent.py" 2>/dev/null
    pkill -f "python3 run_alice_agent.py" 2>/dev/null

    # Kill hardware simulation processes
    pkill -f "hw_sim" 2>/dev/null
    pkill -f "gc_bob" 2>/dev/null
    pkill -f "gc_alice" 2>/dev/null
    # Note: Readers are now part of alice.py and bob.py, no separate processes

    # Close tmux session
    if tmux has-session -t hw_simulation 2>/dev/null; then
        echo "Closing tmux session..."
        tmux kill-session -t hw_simulation 2>/dev/null
    fi

    # Clean up ready files
    rm -f /tmp/.bob_ready /tmp/.alice_ready

    echo "Cleanup completed"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Help function
show_usage() {
    echo "Usage: $0 <M> [bit_size] [gamma_err]"
    echo ""
    echo "Parameters:"
    echo "  M          : Number of bits to identify agents (2^M agents)"
    echo "  bit_size   : Size of the token in bits (default: 10)"
    echo "  gamma_err  : Error rate threshold for token verification (default: 0.11)"
    echo ""
    echo "Examples:"
    echo "  $0 2              # Full hw simulation with M=2 and default parameters"
    echo "  $0 2 10 0.11      # Full hw simulation with M=2, bit_size=10, gamma_err=0.11"
    echo "  $0 3 20 0.05      # Full hw simulation with M=3, bit_size=20, gamma_err=0.05"
    echo ""
    echo "Note:"
    echo "  - Launches tmux session with hw_sim, gc_bob, and gc_alice"
    echo "  - Readers are called automatically from alice.py and bob.py (--sim=True)"
    echo "  - Use 'tmux attach-session -t hw_simulation' to view simulation logs"
    exit 1
}

# Parse command line arguments
if [ $# -lt 1 ]; then
    show_usage
fi

# Fetch defaults from config/defaults.py unique source of truth
DEFAULT_M=$(python3 -c "from config.defaults import BENCHMARK_M_VALUE; print(BENCHMARK_M_VALUE)" 2>/dev/null || echo "1")
DEFAULT_BIT_SIZE=$(python3 -c "from config.defaults import ALICE_DEFAULT_BITLEN; print(ALICE_DEFAULT_BITLEN)" 2>/dev/null || echo "10")
DEFAULT_GAMMA_ERR=$(python3 -c "from config.defaults import QT1_GAMMA_ERR; print(QT1_GAMMA_ERR)" 2>/dev/null || echo "0.1")

M=""
BIT_SIZE=$DEFAULT_BIT_SIZE
GAMMA_ERR=$DEFAULT_GAMMA_ERR

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_usage
            ;;
        *)
            # First positional argument is M
            if [ -z "$M" ]; then
                if [[ $1 =~ ^[0-9]+$ ]]; then
                    M=$1
                    shift
                else
                    echo "M must be a number: $1"
                    show_usage
                fi
            # Second positional argument is bit_size
            elif [[ $1 =~ ^[0-9]+$ ]]; then
                BIT_SIZE=$1
                shift
                # Third positional argument is gamma_err
                if [[ $# -gt 0 && $1 =~ ^[0-9]*\.?[0-9]+$ ]]; then
                    GAMMA_ERR=$1
                    shift
                fi
            else
                echo "Unknown argument: $1"
                show_usage
            fi
            ;;
    esac
done

# Check if M was provided
if [ -z "$M" ]; then
    echo "M not provided, using default from config: $DEFAULT_M"
    M=$DEFAULT_M
fi

AGENTS_COUNT=$((2**M))
echo "Launching hardware simulation with M=$M (2^$M = $AGENTS_COUNT agents), bit_size=$BIT_SIZE, gamma_err=$GAMMA_ERR"

# Paths for different components
HW_SIM_SCRIPT="$SCRIPT_DIR/launch_simulation.sh"

# Launch hardware simulation using dedicated script
echo "Launching hardware simulation with tmux..."
if [ ! -f "$HW_SIM_SCRIPT" ]; then
    echo "Error: launch_simulation.sh not found at $HW_SIM_SCRIPT"
    exit 1
fi

# Call launch_simulation.sh in non-interactive mode
bash "$HW_SIM_SCRIPT" --called --no-terminal

if [ $? -ne 0 ]; then
    echo "Error: Failed to launch hardware simulation"
    exit 1
fi

echo "Hardware simulation launched successfully"

# Wait for hardware simulation to be ready
echo "Waiting for hardware simulation to be ready..."
sleep 5
echo "Hardware simulation should be ready"

# Function to launch Bob and Alice with results
launch_with_results() {
    echo ""
    echo "Launching Bob, Alice and their agents with hardware simulation..."

    # Clean up any previous ready files
    rm -f /tmp/.bob_ready /tmp/.alice_ready

    # 1. Launch Bob main server (reader_alice is called internally when --sim=True)
    echo "Starting Bob main server in background..."
    cd "$PROJECT_ROOT"
    python3 run_bob.py --M $M --port 65431 --sim=True --bit_size $BIT_SIZE &
    BOB_PID=$!
    echo "Bob main server started (PID: $BOB_PID)"

    # Small delay before launching Alice
    sleep 1

    # 2. Launch Alice main client (reader_bob is called internally when --sim=True)
    echo "Starting Alice main client..."
    gnome-terminal --title="Alice" -- bash -c "cd $PROJECT_ROOT; python3 run_alice.py --M $M --port 65431 --ag_port 65000 --sim=True --bit_size $BIT_SIZE; exec bash"

    # Wait for both Bob and Alice to finish reading data (they read in parallel)
    echo "Waiting for Bob and Alice to finish reading data from hw_sim..."
    timeout=300  # 5 minutes max
    elapsed=0
    bob_ready=false
    alice_ready=false

    while [ $elapsed -lt $timeout ]; do
        # Check if Bob is ready
        if [ -f /tmp/.bob_ready ] && [ "$bob_ready" = false ]; then
            echo "Bob has finished reading data"
            bob_ready=true
        fi

        # Check if Alice is ready
        if [ -f /tmp/.alice_ready ] && [ "$alice_ready" = false ]; then
            echo "Alice has finished reading data"
            alice_ready=true
        fi

        # Both are ready, we can continue
        if [ "$bob_ready" = true ] && [ "$alice_ready" = true ]; then
            break
        fi

        sleep 1
        elapsed=$((elapsed + 1))

        # Show progress every 10 seconds
        if [ $((elapsed % 10)) -eq 0 ]; then
            if [ "$bob_ready" = false ] && [ "$alice_ready" = false ]; then
                echo "Still waiting for Bob and Alice... ($elapsed seconds elapsed)"
            elif [ "$bob_ready" = false ]; then
                echo "Still waiting for Bob... ($elapsed seconds elapsed)"
            elif [ "$alice_ready" = false ]; then
                echo "Still waiting for Alice... ($elapsed seconds elapsed)"
            fi
        fi
    done

    # Check if we timed out
    if [ "$bob_ready" = false ] || [ "$alice_ready" = false ]; then
        if [ "$bob_ready" = false ] && [ "$alice_ready" = false ]; then
            echo "Timeout: Bob and Alice did not finish reading data after $timeout seconds"
        elif [ "$bob_ready" = false ]; then
            echo "Timeout: Bob did not finish reading data after $timeout seconds"
        else
            echo "Timeout: Alice did not finish reading data after $timeout seconds"
        fi
        cleanup
        exit 1
    fi

    echo "Both Bob and Alice have finished reading data"

    # Small additional delay to ensure servers are fully ready
    sleep 2

    # 3. Launch BobAgent processes (for M=$M, we have $AGENTS_COUNT agents)
    echo "Launching BobAgent processes..."
    for i in $(seq 0 $((AGENTS_COUNT - 1))); do
        # Convert to binary and format with M digits
        pid=$(printf "%0${M}d" $(echo "obase=2; $i" | bc))
        gnome-terminal --title="BobAgent-$pid" -- bash -c "cd $PROJECT_ROOT; python3 run_bob_agent.py --M $M --pid $pid --gamma-err $GAMMA_ERR; exec bash"
    done

    # Wait a bit for Bob agents to be ready
    sleep 2

    # 4. Launch AliceAgent processes
    echo "Launching AliceAgent processes..."
    for i in $(seq 0 $((AGENTS_COUNT - 1))); do
        # Convert to binary and format with M digits
        pid=$(printf "%0${M}d" $(echo "obase=2; $i" | bc))
        gnome-terminal --title="AliceAgent-$pid" -- bash -c "cd $PROJECT_ROOT; python3 run_alice_agent.py --M $M --pid $pid --al_port 65000; exec bash"
    done

    echo "Bob, Alice and all their agents launched with hardware simulation"
    echo ""
    echo "Launch order:"
    echo "   1. Bob main server (PID: $BOB_PID) - running in this terminal"
    echo "   2. Alice main client - running in separate terminal"
    echo "   3. BobAgent processes ($AGENTS_COUNT agents) - each in separate terminal"
    echo "   4. AliceAgent processes ($AGENTS_COUNT agents) - each in separate terminal"
    echo ""
    echo "Automatic shutdown:"
    echo "   - When Bob stops -> all BobAgents shutdown automatically"
    echo "   - When Alice stops -> all AliceAgents shutdown automatically"
    echo "   - No need to manually close agent terminals!"
    echo ""
    echo "Press Ctrl+C to stop Bob when done"

    # Keep the script running and show Bob's output
    echo "Monitoring Bob's output (press Ctrl+C to stop)..."
    wait $BOB_PID
}

# Call the function to launch with results
launch_with_results

# Open tmux session in a new terminal for easy access to simulation
echo ""
echo "Opening tmux session in a new terminal..."
gnome-terminal --title="hw_simulation" -- bash -c "tmux attach-session -t hw_simulation; exec bash"

# Function to close all created terminals
close_all_terminals() {
    echo ""
    echo "Closing all created terminals..."

    # Kill Bob process if it's still running
    if [ ! -z "$BOB_PID" ] && kill -0 $BOB_PID 2>/dev/null; then
        echo "Killing Bob process (PID: $BOB_PID)..."
        kill -TERM $BOB_PID 2>/dev/null
        sleep 1
        # Force kill if still running
        if kill -0 $BOB_PID 2>/dev/null; then
            echo "Force killing Bob process..."
            kill -KILL $BOB_PID 2>/dev/null
        fi
    fi

    # Kill all Bob and Alice processes
    echo "Killing all Bob and Alice processes..."
    pkill -f "python3 run_bob.py" 2>/dev/null
    pkill -f "python3 run_alice.py" 2>/dev/null
    pkill -f "python3 run_bob_agent.py" 2>/dev/null
    pkill -f "python3 run_alice_agent.py" 2>/dev/null

    # Close tmux session
    if tmux has-session -t hw_simulation 2>/dev/null; then
        echo "Closing tmux session 'hw_simulation'..."
        tmux kill-session -t hw_simulation
    fi

    # Close hardware simulation and GC processes (in case they're running outside tmux)
    echo "Killing hardware simulation processes..."
    pkill -f "hw_sim" 2>/dev/null
    pkill -f "gc_bob" 2>/dev/null
    pkill -f "gc_alice" 2>/dev/null
    # Note: Readers are now part of alice.py and bob.py, no separate processes

    echo "All terminals have been closed"
}

# Call the close function
close_all_terminals

#!/bin/bash

# Script to test the QToken protocol without hardware simulation
# Generates simulated data and launches all components manually

# Get project root (script is in scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
export PYTHONPATH="$PROJECT_ROOT"

# Help function
show_usage() {
    echo "Usage: $0 <M> [mode] [size] [log_level]"
    echo ""
    echo "Available modes:"
    echo "  default    - Use default values (x=1110010011, y=1001011010, t=1010110010, u=1100101011)"
    echo "  random     - Generate random values of specified size"
    echo "  manual     - Allow manual input of values"
    echo ""
    echo "Available log levels:"
    echo "  DEBUG      - Detailed debug information"
    echo "  INFO       - General information (default)"
    echo "  WARNING    - Warning messages only"
    echo "  ERROR      - Error messages only"
    echo ""
    echo "Examples:"
    echo "  $0 2                    # Test with M=2 and default values"
    echo "  $0 2 default            # Test with M=2 and default values"
    echo "  $0 2 default DEBUG      # Test with M=2, default values, and DEBUG logging"
    echo "  $0 2 random 10          # Test with M=2 and 10 random bits"
    echo "  $0 2 random 10 DEBUG    # Test with M=2, 10 random bits, and DEBUG logging"
    echo "  $0 2 manual 10          # Test with M=2 and manual input (10 bits)"
    echo "  $0 2 manual 10 DEBUG    # Test with M=2, manual input (10 bits), and DEBUG logging"
    echo ""
    echo "Note: SIZE parameter is only needed for 'random' and 'manual' modes"
    echo "M=2 -> 4 agents, M=3 -> 8 agents, M=4 -> 16 agents"
    exit 1
}

# Parameter validation
if [ $# -eq 0 ]; then
    show_usage
fi

M=$1
MODE=${2:-default}

# Smart parameter handling based on mode
case $MODE in
    "default")
        # For default mode: M, default, [log_level]
        LOG_LEVEL=${3:-INFO}
        SIZE=10  # Default values are always 10 bits
        ;;
    "random"|"manual")
        # For random/manual modes: M, mode, size, [log_level]
        SIZE=${3:-10}
        LOG_LEVEL=${4:-INFO}
        ;;
    *)
        echo "Mode '$MODE' not recognized"
        show_usage
        ;;
esac

echo "Testing QToken protocol with M=$M (2^$M = $((2**M)) agents)"
echo "Mode: $MODE"
echo "Size: $SIZE bits"
echo "Log level: $LOG_LEVEL"

# Function to generate random bits
generate_random_bits() {
    local size=$1
    local result=""
    for i in $(seq 1 $size); do
        result+=$((RANDOM % 2))
    done
    echo "$result"
}

# Function to validate sizes
validate_sizes() {
    local x_len=${#1}
    local y_len=${#2}
    local t_len=${#3}
    local u_len=${#4}

    if [ $x_len -ne $y_len ] || [ $t_len -ne $u_len ] || [ $x_len -ne $t_len ]; then
        echo "ERROR: Values do not have the same size!"
        echo "   x: $x_len bits, y: $y_len bits"
        echo "   t: $t_len bits, u: $u_len bits"
        echo "   All values must have the same size."
        exit 1
    fi
    echo "Size validation successful: all values have $x_len bits"
}

# Function to generate data according to mode
generate_data() {
    case $MODE in
        "default")
            echo "Using default values..."
            x=None
            y=None
            t=None
            u=None
            ;;
        "random")
            echo "Generating random values of $SIZE bits..."
            x=$(generate_random_bits $SIZE)
            y=$(generate_random_bits $SIZE)
            t=$(generate_random_bits $SIZE)
            u=$(generate_random_bits $SIZE)
            ;;
        "manual")
            echo "Manual value input..."
            echo "Please enter values of $SIZE bits:"
            read -p "x (token): " x
            read -p "y: " y
            read -p "t: " t
            read -p "u: " u
            ;;
        *)
            echo "Mode '$MODE' not recognized"
            show_usage
            ;;
    esac

    # Validate sizes
    validate_sizes "$x" "$y" "$t" "$u"

    echo "Generated values:"
    echo "   x (token): $x"
    echo "   y: $y"
    echo "   t: $t"
    echo "   u: $u"
    echo ""
}

# Function to launch Bob and his agents
launch_bob_and_agents() {
    echo "Launching Bob and his agents..."

    # 1. Launch Bob main server
    echo "   Launching Bob main server..."
    if [ -z "$t" ] || [ -z "$u" ] || [ "$t" = "None" ] || [ "$u" = "None" ]; then
        gnome-terminal --title="Bob-Main" -- bash -c "cd $PROJECT_ROOT; python3 run_bob.py --M $M --port 65431 --log-level $LOG_LEVEL; exec bash"
    else
        gnome-terminal --title="Bob-Main" -- bash -c "cd $PROJECT_ROOT; python3 run_bob.py --M $M --port 65431 --t '$t' --u '$u' --log-level $LOG_LEVEL; exec bash"
    fi

    # Wait for Bob to be ready
    sleep 2

    # 2. Launch Bob agents
    echo "   Launching Bob agents..."
    for i in $(seq 0 $((2**M - 1))); do
        # Convert to binary and format with M digits
        pid=$(printf "%0${M}d" $(echo "obase=2; $i" | bc))
        echo "     Agent Bob-$pid"
        gnome-terminal --title="BobAgent-$pid" -- bash -c "cd $PROJECT_ROOT; python3 run_bob_agent.py --M $M --pid $pid --log-level $LOG_LEVEL; exec bash"
    done

    echo "Bob and his agents launched"
    echo ""
}

# Function to launch Alice and her agents
launch_alice_and_agents() {
    echo "Launching Alice and her agents..."

    # Wait for Bob agents to be ready
    sleep 3

    # 1. Launch Alice main client
    echo "   Launching Alice main client..."
    if [ -z "$x" ] || [ -z "$y" ] || [ "$x" = "None" ] || [ "$y" = "None" ]; then
        gnome-terminal --title="Alice-Main" -- bash -c "cd $PROJECT_ROOT; python3 run_alice.py --M $M --port 65431 --ag_port 65000 --log-level $LOG_LEVEL; exec bash"
    else
        gnome-terminal --title="Alice-Main" -- bash -c "cd $PROJECT_ROOT; python3 run_alice.py --M $M --port 65431 --ag_port 65000 --x '$x' --y '$y' --log-level $LOG_LEVEL; exec bash"
    fi

    # Wait for Alice to be ready
    sleep 2

    # 2. Launch Alice agents
    echo "   Launching Alice agents..."
    for i in $(seq 0 $((2**M - 1))); do
        # Convert to binary and format with M digits
        pid=$(printf "%0${M}d" $(echo "obase=2; $i" | bc))
        echo "     Agent Alice-$pid"
        gnome-terminal --title="AliceAgent-$pid" -- bash -c "cd $PROJECT_ROOT; python3 run_alice_agent.py --M $M --pid $pid --al_port 65000 --log-level $LOG_LEVEL; exec bash"
    done

    echo "Alice and her agents launched"
    echo ""
}

# Function to display test information
show_test_info() {
    echo "Test information:"
    echo "   - M: $M (2^$M = $((2**M)) agents per participant)"
    echo "   - Mode: $MODE"
    echo "   - Bit size: ${#x}"
    echo "   - Log level: $LOG_LEVEL"
    echo "   - Bob main port: 65431"
    echo "   - Alice main port: 65000"
    echo "   - Bob agent ports: 64000-64000+$((2**M-1))"
    echo "   - Mode: Test without hardware"
    echo ""
    echo "To monitor logs:"
    echo "   - Bob: Watch 'Bob-Main' terminal"
    echo "   - Alice: Watch 'Alice-Main' terminal"
    echo "   - Agents: Watch 'BobAgent-*' and 'AliceAgent-*' terminals"
    echo ""
    echo "Protocol should complete automatically after token exchange"
    echo ""
}

# Function to clean up processes
cleanup() {
    echo ""
    echo "Cleaning up processes..."

    # Kill all Python processes from the project
    pkill -f "python3.*bob.py"
    pkill -f "python3.*alice.py"
    pkill -f "python3.*bob_agent.py"
    pkill -f "python3.*alice_agent.py"

    echo "Cleanup completed"
}

# Main function
main() {
    echo "=========================================="
    echo "QTOKEN PROTOCOL TEST WITHOUT HARDWARE"
    echo "=========================================="
    echo ""

    # Generate data according to mode
    generate_data

    # Display information
    show_test_info

    # Launch Bob and his agents
    launch_bob_and_agents

    # Launch Alice and her agents
    launch_alice_and_agents

    echo "Test launched successfully!"
    echo ""
    echo "To stop the test, use Ctrl+C or close terminals"
    echo "   Or run: pkill -f 'python3.*\.py'"
    echo ""

    # Wait for user interruption
    # trap cleanup EXIT
    wait
}

# Execute main script
main

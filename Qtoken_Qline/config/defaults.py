"""
Default configuration values for the QToken protocol
"""

# Default values for Alice (30 bits for testing)
# String versions (legacy, for backward compatibility)
ALICE_DEFAULT_X = "001000000110100010100101100010"  # B secret ^ M
ALICE_DEFAULT_Y = "011000101011011101001011111000"  # B basis

# Integer versions (optimized)
ALICE_DEFAULT_X_INT = 0b001000000110100010100101100010
ALICE_DEFAULT_Y_INT = 0b011000101011011101001011111000
ALICE_DEFAULT_BITLEN = 30

# Default values for Bob (30 bits for testing)
# String versions (legacy, for backward compatibility)
BOB_DEFAULT_T = "101010000110110010101111101001"  # A secret
BOB_DEFAULT_U = "110010010000101100010001110111"  # A basis

# Integer versions (optimized)
BOB_DEFAULT_T_INT = 0b101010000110110010101111101001
BOB_DEFAULT_U_INT = 0b110010010000101100010001110111
BOB_DEFAULT_BITLEN = 30

# Default network configuration
DEFAULT_BASE_IP = "127.0.0.1"

# Default port configuration
DEFAULT_BOB_PORT = 65431
DEFAULT_ALICE_AGENT_PORT = 65000
DEFAULT_BOB_AGENT_BASE_PORT = 64000
DEFAULT_BOB_AGENT_CLIENT_PORT = 65432  # Port where BobAgents listen for AliceAgents

# Logging configuration
DEFAULT_LOG_LEVEL = "INFO"

# Hardware simulation configuration
HW_SIM_BATCH_SIZE = 1024  # Optimized: 64x fewer FIFO reads (was 16)
HW_SIM_DATA_MARGIN = 1.2  # 20% margin for quantum data

# ============================================================
# BENCHMARK CONFIGURATION
# ============================================================

# Bitsizes to test (modify this list according to your needs)
BENCHMARK_BITSIZES = [10, 100, 1000, 10000, 100000]

# Epsilon values to test
BENCHMARK_EPSILONS = [0.01, 0.02, 0.03, 0.04, 0.05,
                      0.06, 0.07, 0.08, 0.09, 0.1, 0.2, 0.3, 0.4, 0.5]

# Number of runs per configuration (bitsize, epsilon)
BENCHMARK_RUNS_PER_POINT = 5

# Success threshold for feasibility frontier (99%)
BENCHMARK_SUCCESS_THRESHOLD = 0.99

# Number of agent bits (2^M agents)
BENCHMARK_M_VALUE = 1

# ============================================================
# SIMULATION FIFO PATHS
# ============================================================

# Hardware simulation FIFO paths (for mode "hwsim" or "test")
FIFO_PATH_ANGLE_ALICE = "/tmp/angle.fifo_alice"
FIFO_PATH_ANGLE_BOB = "/tmp/angle.fifo_bob"
FIFO_PATH_RESULT = "/tmp/result.fifo"
# FIFO_PATH_GCUSER = "/tmp/gcuser.fifo"  # Post-selection done by FPGA, not needed
FIFO_PATH_TIMESTAMPS = "/tmp/timestamp.fifo"  # For QT1 Lambda filtering

# ============================================================
# QT1 PROTOCOL SECURITY THRESHOLDS
# ============================================================

# P_det calculation mode: ABSOLUTE (preferred) or INTRINSIC
# ABSOLUTE: P_det = |Delta_b| / N_sent (total pulses sent)
# INTRINSIC: P_det = |Delta_b| / N_received (bits received)
# ABSOLUTE mode is required for proper security guarantees
# QT1_PDET_MODE = "ABSOLUTE"  # SIMPLIFIED: always ABSOLUTE, P_det = n/N (FPGA does post-selection)

# Minimum detection rate threshold
# Token is REJECTED if |Delta_b|/N < gamma_det
# This protects against selective loss attacks
# Based on real hardware measurements: P_det ~ 0.00156
# Recommended: P_det × 0.5 = 0.00078
QT1_GAMMA_DET = 0.0008

# Maximum error rate threshold
# Token is REJECTED if error_rate > gamma_err
# Based on real hardware measurements: E ~ 3.7%
# Lemme 3 (Kent 2022) requires: γ_err/2 < E < γ_err
# With E=0.037, setting γ_err=0.06 satisfies: 0.03 < 0.037 < 0.06
QT1_GAMMA_ERR = 0.06

# Expected quantum channel error rate
# Used to dynamically calculate gamma_err = QT1_CHANNEL_ERROR_RATE + QT1_EPSILON_MARGIN
QT1_CHANNEL_ERROR_RATE = 0.05

# Security margin above channel error rate
QT1_EPSILON_MARGIN = 0.01

# ============================================================
# THEOREM 1 SECURITY PARAMETERS (for epsilon_unf calculation)
# ============================================================

# Bloch sphere angle uncertainty (radians)
# Represents misalignment between preparation and measurement bases.
# Typical value: theta ~ 5 degrees = 0.0873 radians
QT1_THETA = 0.0873  # ~5 degrees

# Multi-photon probability (P_noqub)
# Probability that a pulse contains more than one photon.
# For Poissonian source with mu << 1: P_noqub ≈ mu^2/2
# Typical value for mu=0.1: P_noqub ≈ 0.005
MU = 0.1  # Mean photon number per pulse
QT1_P_NOQUB = (MU ** 2) / 2  # Auto-calculated: 0.005 for mu=0.1

# Unforgeability optimization parameter (nu_unf)
# Must satisfy: P_noqub < nu_unf < min(2*P_noqub, gamma_det * (1 - gamma_err/lambda))
# Typical value: slightly larger than P_noqub
QT1_NU_UNF = 0.01

# State preparation bias (beta_PS)
# Maximum allowed deviation from uniform distribution for state generation.
# Typical experimental value: beta_PS < 0.01
QT1_BETA_PS_MAX = 0.01

# Basis preparation bias (beta_PB)
# Maximum allowed deviation from uniform distribution for basis selection.
# Typical experimental value: beta_PB < 0.01
QT1_BETA_PB_MAX = 0.01

# ============================================================
# SIMULATED CHANNEL LOSS
# ============================================================

# SIMPLIFIED: FPGA does post-selection, no need for simulated loss/detector efficiency
# Simulated loss rate for realistic reporting (0.99 = 99% loss)
# This does NOT slow down the simulation, it only affects displayed metrics.
# Formula: N_sent_virtual = N_received / (1 - SIMULATED_LOSS_RATE)
SIMULATED_LOSS_RATE = 0.9  # 90% loss (1 qubit received per 10 sent)

# Bob's detector efficiency for delta_v simulation
# This represents the probability that Bob's detector registers a photon
# given that a qubit was sent. Typical SPD efficiency: 10-25%
# For simulation: derived from SIMULATED_LOSS_RATE for consistency
# Set to 1.0 to disable realistic delta_v simulation (legacy behavior)
# BOB_DETECTOR_EFFICIENCY = 1 - SIMULATED_LOSS_RATE  # 0.001 (0.1%)

# ============================================================
# QT1 TEMPORAL FILTERING
# ============================================================

# Default time window for Lambda filtering (in microseconds)
# Qubits detected outside this window are excluded
QT1_WINDOW_START = 0.0
QT1_WINDOW_END = 100.0  # 100 microseconds default window

# ============================================================
# QT1 RELATIVISTIC TIMING CONSTRAINTS
# ============================================================

# Maximum allowed latency for agent response (in milliseconds)
# Enforces relativistic constraints (preventing relay attacks)
# In simulation, this is a soft limit.
QT1_MAX_LATENCY_MS = 200

# ============================================================
# HARDWARE CONSTANTS
# ============================================================

# Laser source frequency (in Hz)
# Used to estimate P_det when timestamps are not available
# P_det = N_received / (Duration * LASER_FREQUENCY)
LASER_FREQUENCY = 80_000_000  # 80 MHz

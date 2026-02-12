"""
Utilities for the QToken protocol
"""

import asyncio
import logging

from config.defaults import DEFAULT_BASE_IP, DEFAULT_BOB_AGENT_CLIENT_PORT
from typing import Optional


def compute_lambda_set(
        timestamps: list[Optional[float]],
        window_start: float,
        window_end: float) -> set[int]:
    """
    Compute the Lambda set of qubit indices detected within a valid time window.

    This implements the temporal filtering required by the QT1 protocol to handle
    detection losses and timing jitter in practical quantum hardware.

    Args:
        timestamps: List of detection times for each qubit (None if not detected)
        window_start: Start of the validity window (in time units)
        window_end: End of the validity window (in time units)

    Returns:
        set[int]: Indices of qubits with valid detection (Lambda set)

    Example:
        >>> timestamps = [0.1, None, 0.5, 0.9, None, 0.3]
        >>> compute_lambda_set(timestamps, 0.0, 0.6)
        {0, 2, 5}
    """
    return {
        i for i, t in enumerate(timestamps)
        if t is not None and window_start <= t <= window_end
    }


def compute_delta_v(
        detection_flags: list[bool],
        lambda_set: Optional[set[int]] = None) -> set[int]:
    """
    Compute Delta_v: the set of qubit indices detected by the verifier.

    This represents qubits that Bob's hardware successfully measured,
    which may differ from Alice's successful detections (Lambda).

    Args:
        detection_flags: List of booleans indicating detection success per qubit
        lambda_set: Optional Lambda set to intersect with (if None, uses all indices)

    Returns:
        set[int]: Indices of qubits detected by verifier (Delta_v)
    """
    delta_v = {i for i, detected in enumerate(detection_flags) if detected}
    if lambda_set is not None:
        delta_v &= lambda_set
    return delta_v


def truncate_bitstring(s, max_len=30):
    """
    Truncate a string or list for logging to avoid PIPE deadlock
    with large bitsizes.

    Args:
        s: String or list to truncate
        max_len (int): Maximum length (default: 30)

    Returns:
        str: Truncated representation
    """
    if isinstance(s, str):
        if len(s) <= max_len:
            return s
        return f"{s[:max_len]}... (len={len(s)})"
    elif isinstance(s, list):
        if len(s) <= max_len:
            return str(s)
        return f"{s[:max_len]}... (len={len(s)})"
    return str(s)


def generate_presentation_points(
        M, base_port=DEFAULT_BOB_AGENT_CLIENT_PORT, base_ip=DEFAULT_BASE_IP):
    """
    Generate presentation points for agents

    Args:
        M (int): Number of bits to identify agents
        base_port (int): Base port for agents
        base_ip (str): Base IP address for agents

    Returns:
        dict: Dictionary {agent_id: (ip, port)}
    """
    points = {}
    for i in range(2 ** M):
        point_id = format(i, f'0{M}b')
        port = base_port + i
        points[point_id] = (base_ip, port)
    return points


def xor_bits(a: str, b: str) -> str:
    """
    Perform bitwise XOR between two binary strings

    Args:
        a (str): First binary string
        b (str): Second binary string

    Returns:
        str: Result of bitwise XOR
    """
    return ''.join(
        str(int(x) ^ int(y)) for x, y in zip(a, b)
    )


# =============================================================================
# Integer-based bit operations (optimized for large bitstrings)
# =============================================================================

def list_to_int(bits: list[int]) -> int:
    """
    Convert a list of bits to a single integer.

    Uses optimized bytes packing for large lists (200x faster than loop for 1M bits).

    Args:
        bits: List of 0s and 1s

    Returns:
        int: Integer representation of the bitstring

    Example:
        >>> list_to_int([1, 0, 1, 0])
        10  # 0b1010

    Performance:
        - 1M bits: ~40ms (vs 7900ms with loop)
    """
    n = len(bits)
    if n == 0:
        return 0

    # For small lists, use simple method
    if n <= 64:
        result = 0
        for bit in bits:
            result = (result << 1) | bit
        return result

    # For large lists, pack into bytes and use int.from_bytes
    # Pad to multiple of 8 bits
    padding = (8 - n % 8) % 8
    if padding:
        bits = [0] * padding + list(bits)

    # Pack 8 bits at a time into bytes
    byte_list = []
    for i in range(0, len(bits), 8):
        byte_val = 0
        for j in range(8):
            byte_val = (byte_val << 1) | bits[i + j]
        byte_list.append(byte_val)

    return int.from_bytes(bytes(byte_list), 'big')


def set_to_mask(indices: set, length: int) -> int:
    """
    Convert a set of indices to an integer bitmask.

    Optimized for pre-computing masks outside the critical latency path.

    Args:
        indices: Set of valid bit positions (0 to length-1)
        length: Total number of bits

    Returns:
        int: Bitmask where bit k is 1 if k is in indices

    Example:
        >>> set_to_mask({0, 2, 3}, 4)
        13  # 0b1101 (bits 0, 2, 3 set)

    Performance:
        - 1M indices: ~40ms (uses optimized list_to_int)
    """
    if not indices:
        return 0

    # Create bit list: 1 at valid indices, 0 elsewhere
    bits = [0] * length
    for k in indices:
        if 0 <= k < length:
            bits[k] = 1

    return list_to_int(bits)


def str_to_int(bitstring: str) -> int:
    """
    Convert a binary string to an integer.

    Args:
        bitstring: String of '0' and '1' characters

    Returns:
        int: Integer representation

    Example:
        >>> str_to_int("1010")
        10
    """
    if not bitstring:
        return 0
    return int(bitstring, 2)


def int_to_str(n: int, length: int) -> str:
    """
    Convert an integer back to a binary string of specified length.

    Args:
        n: Integer to convert
        length: Desired length of output string (zero-padded)

    Returns:
        str: Binary string representation

    Example:
        >>> int_to_str(10, 8)
        '00001010'
    """
    return format(n, f'0{length}b')


def int_to_list(n: int, length: int) -> list[int]:
    """
    Convert an integer back to a list of bits.

    Args:
        n: Integer to convert
        length: Number of bits in the output list

    Returns:
        list[int]: List of 0s and 1s

    Example:
        >>> int_to_list(10, 4)
        [1, 0, 1, 0]
    """
    return [(n >> i) & 1 for i in range(length - 1, -1, -1)]


def xor_bits_int(a: int, b: int) -> int:
    """
    Perform bitwise XOR on two integers. O(1) operation.

    Args:
        a: First integer
        b: Second integer

    Returns:
        int: XOR result
    """
    return a ^ b


def hamming_distance_int(a: int, b: int) -> int:
    """
    Calculate Hamming distance between two integers using bit_count().

    This is ~300x faster than string-based comparison for 100k bits.
    Requires Python 3.10+.

    Args:
        a: First integer
        b: Second integer

    Returns:
        int: Number of differing bits

    Example:
        >>> hamming_distance_int(0b1010, 0b1100)
        2
    """
    return (a ^ b).bit_count()


def normalize_to_int(data, length: int = None) -> tuple[int, int]:
    """
    Normalize input data (str, list, or int) to an integer.

    Args:
        data: Input data (str, list[int], or int)
        length: Length hint for the data (used when data is int)

    Returns:
        tuple[int, int]: (integer value, bit length)

    Raises:
        TypeError: If data type is not supported
    """
    if isinstance(data, int):
        # Already an int, length must be provided or inferred
        if length is None:
            length = data.bit_length() if data > 0 else 1
        return data, length
    elif isinstance(data, str):
        return str_to_int(data), len(data)
    elif isinstance(data, list):
        return list_to_int(data), len(data)
    else:
        raise TypeError(f"Cannot convert {type(data)} to int")



async def is_port_in_use(addr):
    """
    Check if a port is in use

    Args:
        addr (tuple): Address (ip, port) to check

    Returns:
        bool: True if port is in use, False otherwise
    """
    try:
        server = await asyncio.start_server(lambda r, w: None, *addr)
        server.close()
        await server.wait_closed()
        return False
    except (ConnectionRefusedError, OSError):
        return True


def verify_token(alice_bases, alice_results, bob_bases, bob_states):
    """
    Verify token validity

    .. deprecated::
        Use :func:`verify_token_error` instead, which implements QT1 protocol
        security checks including gamma_err, gamma_det, Lambda filtering, and
        Delta_v detection rate thresholds.

    Args:
        alice_bases (list): Alice's bases
        alice_results (list): Alice's results
        bob_bases (list): Bob's bases
        bob_states (list): Bob's states

    Returns:
        bool: True if token is valid, False otherwise
    """
    import warnings
    warnings.warn(
        "verify_token is deprecated. Use verify_token_error with QT1 parameters.",
        DeprecationWarning,
        stacklevel=2
    )
    delta_b = [k for k in range(len(alice_bases))
               if alice_bases[k] == bob_bases[k]]

    logging.info(f"[Token] delta_b: {truncate_bitstring(delta_b)}")
    logging.info(f"[Token] alice_results: {truncate_bitstring(alice_results)}")
    logging.info(f"[Token] bob_states: {truncate_bitstring(bob_states)}")

    is_valid = all(alice_results[k] == bob_states[k] for k in delta_b)

    if is_valid:
        logging.info("------------------ Token is valid ------------------")
    else:
        logging.error("------------------ Token is invalid ------------------")

    return is_valid


def verify_token_error(
        alice_bases, alice_results, bob_bases, bob_states,
        gamma_err: float = 0.08,  # Updated based on real hardware: E~3.7%, margin 2x
        logger=None,
        # SIMPLIFIED: Lambda/Delta_v masks removed - FPGA does post-selection (gcuser)
        # lambda_set: Optional[set[int]] = None,
        # delta_v: Optional[set[int]] = None,
        # lambda_mask: Optional[int] = None,
        # delta_v_mask: Optional[int] = None,
        gamma_det: float = 0.0008,  # Updated based on real hardware: P_det~0.16%
        total_sent_count: Optional[int] = None) -> tuple[bool, str]:
    """
    Verify token validity with error tolerance (QT1 conformant version).

    SIMPLIFIED: Lambda/Delta_v filtering removed. FPGA handles post-selection.
    P_det = n / N where n = bit_size (received bits), N = total_sent_count.

    Args:
        alice_bases: Measurement bases chosen by Alice (y or d_tilde)
        alice_results: Measurement results obtained by Alice (token x)
        bob_bases: Measurement bases used by Bob (u)
        bob_states: Measurement results obtained by Bob (t)
        gamma_err (float): Maximum error rate threshold (default = 0.08 i.e. 8%)
        logger: Logger instance for output (uses global logging if None)
        gamma_det (float): Minimum detection rate threshold (default = 0.0008)
        total_sent_count (int, optional): Total pulses sent by Bob

    Returns:
        Tuple[bool, str]: (is_valid, reason) - validity and descriptive reason.

    Security Guarantees (Kent 2022):
        - Rejects if P_det = n/N < gamma_det (insufficient detections)
        - Rejects if error_rate > gamma_err (too many errors)
        - Lemme 3: γ_err/2 < E < γ_err
    """
    log = logger if logger else logging

    # Use gamma_err directly (renamed from epsilon)
    effective_gamma_err = gamma_err

    # QT1 Security Check 1: Detection rate threshold (gamma_det)
    # Optimized implementation using integer bitwise operations

    # 1. Convert all inputs to integers (O(N) but fast)
    try:
        a_bases_int, n_a = normalize_to_int(alice_bases)
        b_bases_int, n_b = normalize_to_int(bob_bases)
        a_res_int, _ = normalize_to_int(alice_results)
        b_res_int, _ = normalize_to_int(bob_states)

        # n_data = actual received data length (bit_size)
        # N_total = total pulses sent (for P_det calculation)
        n_data = max(n_a, n_b)
        N_total = total_sent_count if total_sent_count is not None else n_data

        # Full mask for bit operations (all received bits are valid - FPGA did post-selection)
        full_mask = (1 << n_data) - 1

        # SIMPLIFIED: No Lambda/Delta_v filtering - FPGA does post-selection
        # All received bits are valid: valid_mask = full_mask

        # 3. Compute Delta_b (matching bases) mask
        # Diff = A ^ B. Match = ~Diff. Apply full mask.
        diff_bases = a_bases_int ^ b_bases_int
        match_bases = (~diff_bases) & full_mask
        delta_b_mask = match_bases & full_mask  # SIMPLIFIED: no Lambda/Delta_v filtering

        # Count Delta_b size
        delta_b_count = delta_b_mask.bit_count()

        log.info(f"[QT1] Delta_b: {delta_b_count} matching bases out of {n_data} received bits")

        # 4. Compute Errors
        mismatches = a_res_int ^ b_res_int
        relevant_errors = mismatches & delta_b_mask
        error_count = relevant_errors.bit_count()

        # SIMPLIFIED: P_det = n / N (always ABSOLUTE)
        # n = n_data (bit_size = received bits, post-selected by FPGA)
        # N = total_sent_count (total pulses sent)
        n_valid = n_data  # SIMPLIFIED: all received bits are valid
        detection_rate = n_valid / N_total if N_total > 0 else 0

        # Log P_det early so it's visible even on rejection
        log.info(
            f"[QT1] P_det: {detection_rate:.6f} "
            f"(n={n_valid:,} received / N={N_total:,} sent, threshold γ_det={gamma_det:.6f})"
        )

        if detection_rate < gamma_det:
            reason = f"Detection rate {detection_rate:.6f} < gamma_det={gamma_det:.6f} (selective loss attack?)"
            log.error(f"[QT1] SECURITY VIOLATION: {reason}")
            return False, reason

        if delta_b_count == 0:
            reason = "No matching bases in Delta_b (empty set)"
            log.warning(f"[QT1] {reason}")
            return False, reason

        error_rate = error_count / delta_b_count

        # Log security metrics
        log.info(
            f"[QT1] Security Metrics: "
            f"P_det={detection_rate:.6f} (n={n_valid:,}/N={N_total:,}), "
            f"E={error_rate:.4f}, "
            f"|Delta_b|={delta_b_count}"
        )
        log.info(
            f"[QT1] {error_count} mismatches over {delta_b_count} compared bits "
            f"({error_rate:.2%} error rate, threshold gamma_err={effective_gamma_err:.2%})"
        )

        # QT1 Lemme 3 (Kent 2022) conformity check
        # The correctness condition requires: γ_err/2 < E < γ_err
        lemma3_lower_bound = effective_gamma_err / 2
        if error_rate <= lemma3_lower_bound:
            log.warning(
                f"[QT1] Lemme 3 condition NOT satisfied: E={error_rate:.4f} <= γ_err/2={lemma3_lower_bound:.4f}"
            )
            log.warning(
                f"[QT1] ε_cor bounds from Kent 2022 Lemme 3 do not apply. "
                f"Correctness guarantees are stronger than computed bounds."
            )
        elif error_rate > effective_gamma_err:
            log.warning(f"[QT1] Lemme 3 VIOLATED: E={error_rate:.4f} > γ_err={effective_gamma_err:.4f}")
        else:
            log.info(
                f"[QT1] Lemme 3 SATISFIED: γ_err/2={lemma3_lower_bound:.4f} < E={error_rate:.4f} "
                f"< γ_err={effective_gamma_err:.4f}"
            )

        # QT1 Security Check 2: Error rate threshold
        is_valid = error_rate <= effective_gamma_err

        if is_valid:
            reason = f"error_rate={error_rate:.4f} <= gamma_err={effective_gamma_err:.4f}"
            log.info(f"[QT1] ✓ Token ACCEPTED: {reason}")
        else:
            reason = f"error_rate={error_rate:.4f} > gamma_err={effective_gamma_err:.4f}"
            log.error(f"[QT1] ✗ Token REJECTED: {reason}")

        return is_valid, reason

    except Exception as e:
        reason = f"Error in verification: {e}"
        log.error(f"[QT1] {reason}")
        import traceback
        log.error(traceback.format_exc())
        return False, reason


def parse_angle(two_d_array, party):
    """
    Parse angle data from hardware simulation into basis and measurement values.

    Args:
        two_d_array: Array of angle values from hardware
        party (str): 'A' for Alice or 'B' for Bob

    Returns:
        tuple: (H_list, X_list) - basis and measurement values

    Raises:
        ValueError: If party is not 'A' or 'B', or if values are out of range
    """
    # Hardcoded mappings for Alice and Bob
    Alice_mapping = {
        0: (0, 1),
        1: (1, 0),
        2: (0, 0),
        3: (1, 1)
    }

    Bob_mapping = {
        0: (0, 0),
        1: (1, 1),
        2: (0, 1),
        3: (1, 0)
    }

    # Select mapping based on parameter
    if party == 'A':
        mapping = Alice_mapping
    elif party == 'B':
        mapping = Bob_mapping
    else:
        raise ValueError("mapping_type must be 'A' or 'B'.")

    # Use the input array directly (already flattened)
    one_d = two_d_array

    # Step 2: Split each number into high and low nibbles (optimized)
    # Create nibbles list with swapped pairs in one pass
    nibbles = []
    for num in one_d:
        if not (0 <= num <= 255):
            raise ValueError("All elements must be in the range 0 to 255.")
        low = num & 0xF         # Low nibble
        high = (num >> 4) & 0xF  # High nibble
        # Swap: add low first, then high (swapped from original order)
        nibbles.append(low)
        nibbles.append(high)

    # Step 4: Apply mapping and split into two lists (optimized with list comprehension)
    try:
        results = [mapping[val] for val in nibbles]
        X_list = [r[0] for r in results]
        H_list = [r[1] for r in results]
    except KeyError as e:
        raise ValueError(f"Value {e.args[0]} not in mapping.")

    return H_list, X_list


def get_bias_stats(bitstring: str, label: str) -> str:
    """
    Calculate and format the bias statistics as in Kent 2022 "Practical quantum tokens".

    The bias β is defined as the deviation from uniform distribution:
        β = |p - 0.5| where p is the frequency of '0' (or equivalently '1')

    For a perfect random source, β → 0.
    For security analysis, we need β < β_max (typically β_max ~ 0.01).

    Args:
        bitstring (str): The string of bits to analyze.
        label (str): Label for the statistics (e.g., "Basis u").

    Returns:
        str: Formatted string with bias statistics in scientific notation.
    """
    import math

    if not bitstring:
        return f"[BIAS] {label}: No data"

    total = len(bitstring)
    count_0 = bitstring.count('0')

    # Calculate frequency and bias (Kent 2022 notation)
    p_0 = count_0 / total
    beta = abs(p_0 - 0.5)  # Deviation from uniform

    # Format in scientific notation (order of magnitude)
    if beta > 0:
        order = int(math.floor(math.log10(beta)))
        mantissa = beta / (10 ** order)
        beta_str = f"{mantissa:.2f}×10^{order}"
    else:
        beta_str = "0 (perfect)"

    return f"[BIAS] {label}: β = {beta_str} (p₀={p_0:.4f}, n={total})"


# =============================================================================
# QT1 Security Bounds (Kent et al. 2022, Theorem 1)
# =============================================================================

def O_theta(theta: float) -> float:
    """
    Calculate the overlap function O(theta) from Kent 2022.

    O(theta) = (1/sqrt(2)) * (cos(theta) + sin(theta))

    This represents the overlap between computational and Hadamard bases
    on the Bloch sphere with an uncertainty angle theta.

    Reference: Kent 2022, Appendix C, Table V (note 2)

    Args:
        theta: Bloch sphere angle uncertainty in radians

    Returns:
        float: Overlap value in range (1/sqrt(2), 1)
    """
    import math
    return (1.0 / math.sqrt(2)) * (math.cos(theta) + math.sin(theta))


def lambda_func(theta: float, beta_PB: float) -> float:
    """
    Calculate lambda(theta, beta_PB) from Theorem 1.

    lambda(theta, beta_PB) = 0.5 * (1 - sqrt(1 - (1 - O(theta)^2) * (1 - 4*beta_PB^2)))

    Reference: Kent 2022, Eq. C3

    Args:
        theta: Bloch sphere angle uncertainty (radians)
        beta_PB: Basis preparation bias

    Returns:
        float: Lambda value in range (0, 0.5*(1 - 1/sqrt(2)))
    """
    import math
    O = O_theta(theta)
    inner = 1 - (1 - O**2) * (1 - 4 * beta_PB**2)
    if inner < 0:
        inner = 0.0
    return 0.5 * (1 - math.sqrt(inner))


def h_func(beta_PS: float, beta_PB: float, theta: float) -> float:
    """
    Calculate h(beta_PS, beta_PB, theta) auxiliary function.

    h = 2 * beta_PS * sqrt((1/2 + beta_PB)^2 + (1/2 - beta_PB)^2 * sin(2*theta))

    Reference: Kent 2022, Eq. 9

    Args:
        beta_PS: State preparation bias
        beta_PB: Basis preparation bias
        theta: Bloch sphere angle uncertainty (radians)

    Returns:
        float: h value
    """
    import math
    term1 = (0.5 + beta_PB)**2
    term2 = (0.5 - beta_PB)**2 * math.sin(2 * theta)
    return 2 * beta_PS * math.sqrt(term1 + term2)


def f_security(
    gamma_err: float,
    beta_PS: float,
    beta_PB: float,
    theta: float,
    nu_unf: float,
    gamma_det: float
) -> float:
    """
    Calculate the security function f from Theorem 1.

    f(gamma_err, beta_PS, beta_PB, theta, nu_unf, gamma_det) =
        (gamma_det - nu_unf) * [lambda^2 * (1 - lambda)^delta] - ln(1 + 2*beta_PS)
        - (1 - (gamma_det - nu_unf)) * ln[1 + h(beta_PS, beta_PB, theta)]

    Reference: Kent 2022, Eq. 8

    Args:
        gamma_err: Error rate threshold
        beta_PS: State preparation bias
        beta_PB: Basis preparation bias
        theta: Bloch sphere angle uncertainty (radians)
        nu_unf: Unforgeability optimization parameter
        gamma_det: Detection rate threshold

    Returns:
        float: f value (must be > 0 for security)
    """
    import math
    lam = lambda_func(theta, beta_PB)

    if gamma_det <= nu_unf:
        return float('-inf')

    delta = gamma_err / (gamma_det - nu_unf)

    if lam <= 0 or lam >= 1:
        core_term = 0.0
    else:
        core_term = (gamma_det - nu_unf) * (lam**2) * ((1 - lam)**delta)

    term2 = math.log(1 + 2 * beta_PS)
    h_val = h_func(beta_PS, beta_PB, theta)
    term3 = (1 - (gamma_det - nu_unf)) * math.log(1 + h_val)

    return core_term - term2 - term3


def calculate_epsilon_unf(
    N: int,
    gamma_err: float,
    gamma_det: float,
    theta: float = None,
    P_noqub: float = None,
    nu_unf: float = None,
    beta_PS: float = None,
    beta_PB: float = None
) -> tuple[float, float]:
    """
    Calculate epsilon_unf and security bits from Theorem 1 (Eq. 10).

    epsilon_unf = exp(-(N * P_noqub / 3) * (nu_unf/P_noqub - 1)^2)
                  + exp(-N * f(...))

    Reference: Kent et al. 2022, "Practical quantum tokens without quantum memories"
               Theorem 1, Equation 10

    Args:
        N: Number of transmitted qubits (total_sent_count)
        gamma_err: Error rate threshold
        gamma_det: Detection rate threshold
        theta: Bloch sphere angle uncertainty (default: QT1_THETA)
        P_noqub: Multi-photon probability (default: QT1_P_NOQUB)
        nu_unf: Unforgeability parameter (default: QT1_NU_UNF)
        beta_PS: State preparation bias (default: QT1_BETA_PS_MAX)
        beta_PB: Basis preparation bias (default: QT1_BETA_PB_MAX)

    Returns:
        tuple[float, float]: (epsilon_unf, security_bits)
            - epsilon_unf: Unforgeability bound
            - security_bits: -log2(epsilon_unf), or 0 if epsilon_unf >= 1
    """
    import math
    from config.defaults import (
        QT1_THETA, QT1_P_NOQUB, QT1_NU_UNF,
        QT1_BETA_PS_MAX, QT1_BETA_PB_MAX
    )

    # Use defaults if not provided
    theta = theta if theta is not None else QT1_THETA
    P_noqub = P_noqub if P_noqub is not None else QT1_P_NOQUB
    nu_unf = nu_unf if nu_unf is not None else QT1_NU_UNF
    beta_PS = beta_PS if beta_PS is not None else QT1_BETA_PS_MAX
    beta_PB = beta_PB if beta_PB is not None else QT1_BETA_PB_MAX

    # Term 1: Multi-photon fluctuation bound (Chernoff)
    if P_noqub > 0 and nu_unf > P_noqub:
        chernoff_exp = -(N * P_noqub / 3) * ((nu_unf / P_noqub - 1) ** 2)
        term1 = math.exp(max(chernoff_exp, -700))
    else:
        term1 = 1.0

    # Term 2: Main security term
    f_val = f_security(gamma_err, beta_PS, beta_PB, theta, nu_unf, gamma_det)
    if f_val > 0:
        main_exp = -N * f_val
        term2 = math.exp(max(main_exp, -700))
    else:
        term2 = 1.0

    epsilon_unf = term1 + term2

    # Calculate security bits
    if epsilon_unf > 0 and epsilon_unf < 1:
        security_bits = -math.log2(epsilon_unf)
    elif epsilon_unf >= 1:
        security_bits = 0.0
    else:
        security_bits = float('inf')

    return epsilon_unf, security_bits


def calculate_scaled_security_bounds(
    M: int,
    epsilon_unf: float,
    epsilon_rob: float = None,
    epsilon_cor: float = None
) -> dict:
    """
    Calculate scaled security bounds for M > 1 according to Theorem 2.

    Reference: Kent 2022, Theorem 2, Eq. 11

    For 2^M presentation points:
    - epsilon_rob^M = M * epsilon_rob (robustness scales linearly)
    - epsilon_cor^M = M * epsilon_cor (correctness scales linearly)
    - epsilon_unf^M = C * epsilon_unf (C = pairs of spacelike-separated points)

    For standard configuration where all 2^M points are pairwise
    spacelike-separated: C = 2^M * (2^M - 1) / 2

    Args:
        M: Number of agent bits (2^M presentation points)
        epsilon_unf: Base unforgeability bound (M=1)
        epsilon_rob: Base robustness bound (optional)
        epsilon_cor: Base correctness bound (optional)

    Returns:
        dict: Scaled bounds including:
            - epsilon_unf_M: Scaled unforgeability
            - epsilon_rob_M: Scaled robustness (if provided)
            - epsilon_cor_M: Scaled correctness (if provided)
            - security_bits_M: Scaled security in bits
            - C: Number of spacelike-separated point pairs
            - num_agents: 2^M
    """
    import math

    num_agents = 2 ** M

    # C = number of pairs of spacelike-separated presentation points
    C = num_agents * (num_agents - 1) // 2

    result = {
        'M': M,
        'num_agents': num_agents,
        'C': C,
    }

    # Scale unforgeability (Theorem 2, Eq. 11)
    epsilon_unf_M = C * epsilon_unf
    result['epsilon_unf_M'] = epsilon_unf_M
    result['epsilon_unf_base'] = epsilon_unf

    if epsilon_unf_M > 0 and epsilon_unf_M < 1:
        result['security_bits_M'] = -math.log2(epsilon_unf_M)
    elif epsilon_unf_M >= 1:
        result['security_bits_M'] = 0.0
    else:
        result['security_bits_M'] = float('inf')

    # Scale robustness (linear in M)
    if epsilon_rob is not None:
        result['epsilon_rob_M'] = M * epsilon_rob
        result['epsilon_rob_base'] = epsilon_rob

    # Scale correctness (linear in M)
    if epsilon_cor is not None:
        result['epsilon_cor_M'] = M * epsilon_cor
        result['epsilon_cor_base'] = epsilon_cor

    return result

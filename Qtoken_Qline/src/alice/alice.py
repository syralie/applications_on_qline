"""
Alice implementation for the QToken protocol
"""

from src.utils.logging_config import setup_logging
from src.utils.protocol_utils import generate_presentation_points, is_port_in_use, parse_angle, truncate_bitstring, xor_bits, list_to_int, int_to_str
from src.utils.participant import Participant
from config.defaults import ALICE_DEFAULT_X, ALICE_DEFAULT_Y, DEFAULT_BOB_PORT, DEFAULT_ALICE_AGENT_PORT, DEFAULT_BASE_IP
import asyncio
import logging
import random
import argparse
import sys
import os
import json
import signal
# CRITICAL: Alice MUST use reader_bob (readerB) for simulation. Do NOT change this to readerA.
from src.utils.readerB import reader_bob

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


def parse_basis(basis_str, size=10):
    """
    Parse basis string: every 4 characters (excluding spaces),
    take the last 2 characters. If they are "00" or "01" → 0, else → 1.
    Parse 10 strings of 4 characters.

    Args:
        basis_str (str): Basis string to parse
        size (int): Expected size

    Returns:
        str: Parsed string
    """
    if not basis_str:
        return ALICE_DEFAULT_Y

    length = size * 4

    # Remove spaces and ensure we have enough characters
    basis_clean = basis_str.replace(" ", "")

    # Remove "basis:"
    basis_clean = basis_clean.replace("basis:", "")

    result = ""
    for i in range(0, length, 4):  # Process 10 groups of 4 characters
        group = basis_clean[i:i+4]
        if len(group) == 4:
            last_two = group[-2:]  # Get last 2 characters
            if last_two in ["00", "01"]:
                result += "0"
            else:
                result += "1"

    logging.info(f"[Alice] y: {truncate_bitstring(result)}")
    return result


def parse_meas(meas_str, size=10):
    """
    Parse meas string: every 8 characters (excluding spaces),
    take the last character and add it to x. Parse 50 strings of 8 characters.

    Args:
        meas_str (str): Measurement string to parse
        size (int): Expected size

    Returns:
        str: Parsed string
    """
    if not meas_str:
        return ALICE_DEFAULT_X

    length = size * 8

    # Remove spaces and ensure we have enough characters
    meas_clean = meas_str.replace(" ", "")

    # Remove "meas:"
    meas_clean = meas_clean.replace("meas:", "")

    result = ""
    for i in range(0, length, 8):  # Process 50 groups of 8 characters
        group = meas_clean[i:i+8]
        if len(group) == 8:
            last_char = group[-1]  # Get last character
            result += last_char

    logging.info(f"[Alice] x: {truncate_bitstring(result)}")
    return result


class Alice(Participant):
    """
    Alice implementation for the QToken protocol
    """

    def __init__(self, name, M, addr, ag_port, token, y_val,
                 persistent=True, lambda_set=None):
        super().__init__(name)
        self.M = M
        self.bob_addr = addr
        self.ag_port = ag_port
        self.token = token
        self.y = y_val
        self.persistent = persistent
        self.lambda_set = lambda_set  # QT1: Set of valid qubit indices
        self.bob_reader = None
        self.bob_writer = None
        self.agents_conns = {}
        self.shutdown_event = asyncio.Event()
        self.agent_servers = []

    async def connect_bob(self):
        """Establish connection with Bob"""
        self.logger.info(f"Connecting to Bob at {self.bob_addr}")
        self.bob_reader, self.bob_writer = await asyncio.open_connection(*self.bob_addr)
        self.logger.info(f"Connected to Bob at {self.bob_addr}")

    async def start_agent_servers(self):
        """Start servers for Alice agents"""
        for pid, addr in generate_presentation_points(
                self.M, base_port=self.ag_port).items():
            srv = await asyncio.start_server(
                lambda r, w, pid=pid: self._reg_agent(r, w, pid),
                *addr
            )
            self.logger.info(f"Server for agent {pid} started at {addr}")
            asyncio.create_task(srv.serve_forever())

    async def _reg_agent(self, reader, writer, pid):
        """Register a connected agent"""
        self.logger.info(f"Agent {pid} connected")
        self.agents_conns[pid] = (reader, writer)

    async def shutdown(self):
        """Graceful shutdown of all connections and servers"""
        self.logger.info("Initiating graceful shutdown...")
        self.shutdown_event.set()

        # Close connection to Bob
        if self.bob_writer:
            try:
                self.bob_writer.close()
                await self.bob_writer.wait_closed()
                self.logger.info("Closed connection to Bob")
            except Exception as e:
                self.logger.error(f"Error closing Bob connection: {e}")

        # Close all agent connections
        for pid, (_, writer) in self.agents_conns.items():
            try:
                await self.send_async("SHUTDOWN", writer, name=self.name)
            except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError) as e:
                self.logger.warning(f"Agent {pid} already disconnected: {e}")
            except Exception as e:
                self.logger.error(f"Error sending shutdown to agent {pid}: {e}")

            try:
                writer.close()
                await writer.wait_closed()
                self.logger.info(f"Closed connection to agent {pid}")
            except Exception as e:
                self.logger.error(f"Error closing agent {pid}: {e}")

        # Stop all agent servers
        for srv in self.agent_servers:
            srv.close()
            await srv.wait_closed()

        self.logger.info("Shutdown complete")

    async def execute_protocol(self):
        """Execute one instance of Alice's protocol"""
        # Wait for all agents to connect
        while len(self.agents_conns) < 2**self.M and not self.shutdown_event.is_set():
            await asyncio.sleep(0.1)

        if self.shutdown_event.is_set():
            return

        # Send token to all agents
        for pid, (_, writer) in self.agents_conns.items():
            self.logger.info(f"Sending token to agent {pid}")
            await self.send_async(self.token, writer, name=self.name, var="token")

        # Connect to Bob
        await self.connect_bob()

        # Stage I: Send d to Bob
        # z is chosen from {0, 1}^M
        z_int = random.randint(0, (1 << self.M) - 1)
        z_bin = format(z_int, f'0{self.M}b')
        self.logger.debug(f"z: {z_bin}")

        # d = y XOR z (repeated to match length of y)
        repeated_z = (z_bin * (len(self.y) // len(z_bin) + 1))[:len(self.y)]
        d = xor_bits(self.y, repeated_z)

        await self.send_async(d, self.bob_writer, name=self.name, var="d")

        # QT1: Send lambda_set if available (enables QT1 security features)
        if self.lambda_set is not None:
            await self.send_async(
                list(self.lambda_set), self.bob_writer, name=self.name, var="lambda")
            self.logger.info(
                f"[QT1] Sent lambda_set to Bob: {len(self.lambda_set)} valid indices")

        _, ack = await self.receive_async(self.bob_reader)
        if ack != "OK":
            self.logger.error(f"Failed to send d to Bob: {ack}")

        # Stage II: Select an agent and send c
        b = random.choice(list(self.agents_conns.keys()))
        self.logger.info(f"Selected agent {b} for token request")

        # c = p XOR z (bitwise)
        p_int = int(b, 2)
        c_int = p_int ^ z_int
        c = format(c_int, f'0{self.M}b')
        self.logger.debug(f"c: {c}")

        await self.send_async(c, self.bob_writer, name=self.name, var="c")

        # Wait for agent to be ready
        while b not in self.agents_conns:
            await asyncio.sleep(1)

        # Request token from selected agent
        r_ag, w_ag = self.agents_conns[b]
        await self.send_async("send_token", w_ag, name=self.name, var="token")
        self.logger.info(f"Sent token request to agent {b}")

        # Wait for agent response
        var, message = await asyncio.wait_for(
            self.receive_async(r_ag), timeout=30)

        # Send validation result to Bob
        if var == "message" and message:
            self.logger.info(f"Sending validation result to Bob: {message}")
            await self.send_async(message, self.bob_writer, name=self.name, var="validation_result")
        else:
            self.logger.warning("No validation result received from agent")
            await self.send_async("No validation result", self.bob_writer, name=self.name, var="validation_result")

        # Close Bob connection after this session
        self.bob_writer.close()
        await self.bob_writer.wait_closed()
        self.bob_writer = None
        self.bob_reader = None

    async def run(self):
        """Execute Alice's main protocol"""
        self.logger.info(f"x: {truncate_bitstring(self.token)}")
        self.logger.info(f"y: {truncate_bitstring(self.y)}")
        self.logger.info(f"Persistent mode: {self.persistent}")

        await self.start_agent_servers()

        try:
            if self.persistent:
                # In persistent mode, wait for shutdown signal
                # (Could be extended to run multiple protocol sessions)
                await self.execute_protocol()
                self.logger.info(
                    "Protocol completed in persistent mode, waiting for shutdown signal...")
                await self.shutdown_event.wait()
            else:
                # One-shot mode: execute once and exit
                await self.execute_protocol()
                self.logger.info("Protocol completed in one-shot mode")
        except asyncio.CancelledError:
            self.logger.info("Alice task cancelled")
            await self.shutdown()
        except Exception as e:
            self.logger.error(f"Error in Alice protocol: {e}")
            raise
        finally:
            # Close all connections in one-shot mode
            if not self.persistent:
                await self.shutdown()


async def main():
    """Main function to run Alice"""
    parser = argparse.ArgumentParser(description="Alice - QToken Protocol")
    parser.add_argument("--M", type=int, default=2,
                        help="Number of bits to identify agents")
    parser.add_argument("--port", type=int,
                        default=DEFAULT_BOB_PORT, help="Bob's port")
    parser.add_argument(
        "--ag_port", type=int, default=DEFAULT_ALICE_AGENT_PORT,
        help="Base port for agents")
    parser.add_argument("--basis", type=str, default="",
                        help="Basis string to parse y")
    parser.add_argument("--meas", type=str, default="",
                        help="Measurement string to parse x")
    parser.add_argument(
        "--sim", type=bool, default=False,
        help="If true, read basis and meas from file")
    parser.add_argument("--bit_size", type=int, default=10, help="Bit size")
    parser.add_argument("--x", type=str, default=ALICE_DEFAULT_X,
                        help="x value (token)")
    parser.add_argument("--y", type=str, default=ALICE_DEFAULT_Y, help="y value")
    parser.add_argument("--log-level", type=str, default="INFO", help="Log level")
    parser.add_argument(
        "--persistent", action="store_true",
        help="Keep agent servers running after protocol completion (default: one-shot)")
    parser.add_argument(
        "--run_id", type=int, default=None,
        help="Run ID to load from database (offline mode)")
    parser.add_argument(
        "--db_path", type=str, default="data/quantum_data.db",
        help="Path to SQLite database (default: data/quantum_data.db)")

    args = parser.parse_args()

    # Configure logging
    setup_logging(level=args.log_level, name="Alice")

    # OFFLINE MODE: Load from database if run_id is provided
    if args.run_id is not None:
        import sqlite3
        logging.info(f"Loading data from database (run_id={args.run_id})...")

        try:
            conn = sqlite3.connect(args.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT x, y FROM runs WHERE id = ?", (args.run_id,))
            row = cursor.fetchone()
            conn.close()

            if row is None:
                logging.error(f"Run ID {args.run_id} not found in database")
                sys.exit(1)

            x_parsed, y_parsed = row
            logging.info(
                f"Loaded data from database: x (len={len(x_parsed)}), y (len={len(y_parsed)})")
        except Exception as e:
            logging.error(f"Error loading data from database: {e}")
            sys.exit(1)
    # Parse basis and meas arguments
    elif args.basis and args.meas and not args.sim:
        x_parsed = parse_meas(args.meas, size=10)  # meas → x (token)
        y_parsed = parse_basis(args.basis, size=10)  # basis → y
    elif args.sim:
        # Calculate num_batches and batch_size based on bit_size
        from config.defaults import HW_SIM_BATCH_SIZE, HW_SIM_DATA_MARGIN
        batch_size = HW_SIM_BATCH_SIZE
        # Add margin to ensure we have enough data
        required_data = int(args.bit_size * HW_SIM_DATA_MARGIN)
        # Ceiling division
        num_batches = (required_data + 2 * batch_size - 1) // (2 * batch_size)

        logging.info(
            f"Calculated num_batches={num_batches}, batch_size={batch_size} for bit_size={args.bit_size}")

        # Read data from hardware simulation
        # gcuser post-selection is done by the FPGA, angles are already synchronized
        angles_B, result = await reader_bob(mode='hwsim', num_batches=num_batches, batch_size=batch_size)
        # angles_B, result, gcusers = await reader_bob(mode='hwsim', num_batches=num_batches, batch_size=batch_size)
        logging.debug(f"Angles B (first 10): {angles_B[:10]}")
        logging.debug(f"Result (first 10): {result[:10]}")

        # # QT1: Calculate Lambda set from gcusers
        # # 80 MHz clock = 12.5 ns period. Hardware sends 2 time-bins per qubit.
        # # Index = gcuser // 2
        # lambda_set = set()
        # if gcusers:
        #     lambda_set = {g // 2 for g in gcusers}
        #     logging.info(f"[QT1] Generated Lambda set with {len(lambda_set)} valid indices from {len(gcusers)} timetags")
        #     logging.debug(f"[QT1] Lambda set sample: {list(lambda_set)[:10]}...")
        lambda_set = None  # Post-selection done by FPGA, no lambda filtering needed

        if not angles_B or not result:
            logging.error("Failed to get data from readerB.")
            return
        try:
            Bh, Bx = parse_angle(angles_B, "B")
        except Exception as e:
            logging.error(f"Error parsing angles: {e}")
            logging.error(f"Angles (first 10): {angles_B[:10]}")
            return

        M = result
        x_parsed_list = [a ^ b for a, b in zip(
            Bx[:args.bit_size], M[:args.bit_size])]
        y_parsed_list = Bh[:args.bit_size]

        # Optimized: Use integer representation (200x faster for 1M bits)
        x_int = list_to_int(x_parsed_list)
        y_int = list_to_int(y_parsed_list)
        bitlen = len(x_parsed_list)

        # Convert back to string for backward compatibility with protocol
        x_parsed = int_to_str(x_int, bitlen)
        y_parsed = int_to_str(y_int, bitlen)

        logging.debug(f"Parsed x (len={len(x_parsed)}), y (len={len(y_parsed)})")
    else:
        x_parsed = args.x
        y_parsed = args.y
        lambda_set = None

    logging.info(f"x: {truncate_bitstring(x_parsed)}, len: {len(x_parsed)}")
    logging.info(f"y: {truncate_bitstring(y_parsed)}, len: {len(y_parsed)}")

    # Calculate and log realistic channel metrics (display on Bob side only)
    from config.defaults import SIMULATED_LOSS_RATE
    n_received = len(x_parsed)
    n_sent_virtual = int(n_received / (1 - SIMULATED_LOSS_RATE))
    loss_percent = SIMULATED_LOSS_RATE * 100
    logging.info(f"[QT1] REALITY CHECK: To get {n_received:,} bits, Bob virtually sent ~{n_sent_virtual:,} qubits.")
    logging.info(f"[QT1] Effective Channel Loss: {loss_percent:.1f}% (Simulated)")

    # Signal that Alice has finished reading data (only in sim mode, not in offline mode)
    if args.sim and args.run_id is None:
        ready_file = "/tmp/.alice_ready"
        with open(ready_file, 'w') as f:
            f.write("ready")
        logging.info(f"Alice data ready - signal file created: {ready_file}")

    # Check that x and y have the same length
    if len(x_parsed) != len(y_parsed):
        logging.error(
            f"x and y have different lengths ({len(x_parsed)} vs {len(y_parsed)})")
        sys.exit(1)

    token_to_use = x_parsed

    addr = (DEFAULT_BASE_IP, args.port)
    ag_addr = (DEFAULT_BASE_IP, args.ag_port)

    # Check if port is available
    if await is_port_in_use(ag_addr):
        logging.error(
            f"Port {args.ag_port} is already in use. Please choose a different port.")
        sys.exit(1)

    alice = Alice("Alice", args.M, addr=addr,
                  ag_port=args.ag_port, token=token_to_use,
                  y_val=y_parsed, persistent=args.persistent,
                  lambda_set=lambda_set)

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()

    def signal_handler():
        logging.info("Received shutdown signal (SIGINT/SIGTERM)")
        asyncio.create_task(alice.shutdown())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await alice.run()
    finally:
        logging.info("Alice has stopped")


if __name__ == "__main__":
    asyncio.run(main())

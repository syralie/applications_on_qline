"""
Bob implementation for the QToken protocol
"""

from src.agents.bob_agent import BobAgent
from src.utils.logging_config import setup_logging
from src.utils.protocol_utils import generate_presentation_points, xor_bits, parse_angle, truncate_bitstring, list_to_int, int_to_str
from src.utils.participant import Participant
from config.defaults import BOB_DEFAULT_T, BOB_DEFAULT_U, DEFAULT_BOB_PORT, DEFAULT_BOB_AGENT_BASE_PORT, DEFAULT_BASE_IP
# SIMPLIFIED: BOB_DETECTOR_EFFICIENCY removed - FPGA does post-selection (gcuser)
import asyncio
import logging
import argparse
import sys
import os
import json
import signal
# import random  # SIMPLIFIED: only needed for BOB_DETECTOR_EFFICIENCY simulation
# CRITICAL: Bob MUST use reader_alice (readerA) for simulation. Do NOT change this to readerB.
from src.utils.readerA import reader_alice
from src.utils.start_stop import send_start_command

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


class Bob(Participant):
    """
    Bob implementation for the QToken protocol
    """

    def __init__(self, name: str, M, addr, t_val, u_val, persistent=True, total_sent_count=None):
        super().__init__(name)
        self.M = M
        self.addr = addr
        self.t = t_val
        self.u = u_val
        self.persistent = persistent
        self.total_sent_count = total_sent_count  # QT1: Total pulses sent for true P_det calculation
        self.agents = {}
        self.agent_main_addrs = generate_presentation_points(
            M, base_port=DEFAULT_BOB_AGENT_BASE_PORT)
        self.alice_queue: asyncio.Queue[tuple[asyncio.StreamReader,
                                              asyncio.StreamWriter]] = asyncio.Queue()
        self.shutdown_event = asyncio.Event()
        self.session_count = 0
        self.alice_serv = None

    async def _accept_agent(self, pid, addr):
        """Accept Bob agent connections"""
        srv = await asyncio.start_server(
            lambda r, w, pid=pid: self._register_agent(r, w, pid),
            *addr
        )
        self.logger.info(f"Agent server started for {pid} on {addr}")
        async with srv:
            await srv.serve_forever()

    async def _register_agent(self, reader, writer, pid):
        """Register a connected Bob agent"""
        self.logger.info(f"Agent {pid} connected")
        agent = BobAgent(pid, self.M)
        agent.reader_main = reader
        agent.writer_main = writer
        self.agents[pid] = agent

        # Start monitoring messages from agent (Feedback Channel)
        asyncio.create_task(self.monitor_agent(reader, pid))

        asyncio.create_task(agent.listen_main())

    async def monitor_agent(self, reader, pid):
        """Monitor messages from an agent (Feedback Channel)"""
        try:
            while not self.shutdown_event.is_set():
                var, message = await self.receive_async(reader, description=f"Agent-{pid}")
                if var is None and message is None:
                    break # Connection closed

                if message and isinstance(message, str) and message.startswith("STATUS:"):
                    # Display relativistic status on Bob's side
                    self.logger.info(f"[Agent {pid}] {message}")
                    print(f"\n[Agent {pid}] {message}", flush=True)
                elif message:
                    self.logger.debug(f"Received from Agent {pid}: {truncate_bitstring(message)}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"Error monitoring Agent {pid}: {e}")

    async def handle_alice(self, reader, writer):
        """Handle Alice connections"""
        peer = writer.get_extra_info('peername')
        self.logger.info(f"Connected to Alice from {peer}")
        await self.alice_queue.put((reader, writer))

    async def shutdown(self):
        """Graceful shutdown of all connections and servers"""
        self.logger.info("Initiating graceful shutdown...")
        self.shutdown_event.set()

        # Close all agent connections
        for pid, agent in self.agents.items():
            if agent.writer_main:
                try:
                    await self.send_async("SHUTDOWN", agent.writer_main, name=self.name)
                except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError) as e:
                    self.logger.warning(f"Agent {pid} already disconnected: {e}")
                except Exception as e:
                    self.logger.error(f"Error sending shutdown to agent {pid}: {e}")

                try:
                    agent.writer_main.close()
                    await agent.writer_main.wait_closed()
                    self.logger.info(f"Closed connection to agent {pid}")
                except Exception as e:
                    self.logger.error(f"Error closing agent {pid}: {e}")

        # Stop the Alice server
        if self.alice_serv:
            self.alice_serv.close()
            await self.alice_serv.wait_closed()
            self.logger.info("Alice server stopped")

        self.logger.info("Shutdown complete")

    async def process_alice(self):
        """Process Alice connections"""
        while not self.shutdown_event.is_set():
            try:
                # Check for Alice connections with timeout to allow checking shutdown_event
                reader, writer = await asyncio.wait_for(
                    self.alice_queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue  # Check shutdown_event again

            try:
                # Wait for all agents to connect
                while len(self.agents) < 2**self.M and not self.shutdown_event.is_set():
                    await asyncio.sleep(0.1)

                if self.shutdown_event.is_set():
                    writer.close()
                    await writer.wait_closed()
                    break

                # Stage I: Receive d from Alice
                _, d = await self.receive_async(reader)
                self.logger.debug(f"Received d: {truncate_bitstring(d)}")
                self.logger.info(f"Received d: {truncate_bitstring(d)}")

                # SIMPLIFIED: Lambda set reception removed - FPGA does post-selection (gcuser)
                # # QT1: Check if Lambda set was sent (optional for compatibility)
                # lambda_set = None
                # try:
                #     # Try to receive lambda_set (non-blocking check)
                #     # In full QT1 mode, Alice sends lambda after d
                #     var_check, lambda_data = await asyncio.wait_for(
                #         self.receive_async(reader), timeout=0.5
                #     )
                #     if var_check == "lambda":
                #         # Participant class converts everything to string, so we must parse it back
                #         if isinstance(lambda_data, str) and lambda_data.startswith("["):
                #             try:
                #                 import json
                #                 lambda_list = json.loads(lambda_data)
                #                 lambda_set = set(lambda_list)
                #             except Exception as e:
                #                 self.logger.error(f"Failed to parse lambda_set JSON: {e}")
                #                 # Fallback: try ast.literal_eval if json fails (single quotes)
                #                 try:
                #                     import ast
                #                     lambda_list = ast.literal_eval(lambda_data)
                #                     lambda_set = set(lambda_list)
                #                 except Exception as e2:
                #                     self.logger.error(f"Failed to parse lambda_set literal: {e2}")
                #                     lambda_set = set() # Empty set on failure
                #         else:
                #              # Assume it's already a list/set if not string (unlikely with Participant)
                #              lambda_set = set(lambda_data) if lambda_data else None
                #
                #         self.logger.info(
                #             f"[QT1] Received lambda_set: {len(lambda_set) if lambda_set else 0} indices")
                # except asyncio.TimeoutError:
                #     # No Lambda sent - legacy mode
                #     self.logger.debug("[QT1] No lambda_set received (legacy mode)")

                # Send d_i, t, u to all agents
                for pid, agent in self.agents.items():
                    repeated_pid = (pid * (len(d) // len(pid)))[:len(d)]
                    self.logger.debug(
                        f"repeated_pid: {truncate_bitstring(repeated_pid)}")

                    d_i = xor_bits(d, repeated_pid)
                    self.logger.debug(f"d_i: {truncate_bitstring(d_i)}")

                    await self.send_async(d_i, agent.writer_main, name=self.name, var="d_i")
                    self.logger.info(
                        f"Sent d_i to agent {pid}: {truncate_bitstring(d_i)}")

                    await self.send_async(self.t, agent.writer_main, name=self.name, var="t")
                    self.logger.info(
                        f"Sent t to agent {pid}: {truncate_bitstring(self.t)}")

                    await self.send_async(self.u, agent.writer_main, name=self.name, var="u")
                    self.logger.info(
                        f"Sent u to agent {pid}: {truncate_bitstring(self.u)}")

                    # SIMPLIFIED: Lambda set sending removed - FPGA does post-selection (gcuser)
                    # # QT1: Send lambda_set if available
                    # if lambda_set is not None:
                    #     # Use JSON for robustness (Participant class handles serialization of the string)
                    #     # We must send it as a string to avoid pickle issues if list is huge?
                    #     # Participant pickle handles lists fine, but BobAgent expects string/json for safety?
                    #     # The update in Step 450 expects a string or list.
                    #     await self.send_async(
                    #         list(lambda_set), agent.writer_main, name=self.name, var="lambda_set")
                    #     self.logger.info(f"[QT1] Sent lambda_set to agent {pid}")

                    # SIMPLIFIED: Delta_v construction removed - FPGA does post-selection (gcuser)
                    # # QT1: Calculate and Send Delta_v (Verifier's detections)
                    # # Ideally, this comes from reading Bob's detection hardware.
                    # # In simulation mode, we apply BOB_DETECTOR_EFFICIENCY to model realistic loss.
                    # # In real hardware (Plug&Play), this would come from actual detector data.
                    # if BOB_DETECTOR_EFFICIENCY < 1.0:
                    #     # Probabilistic detection based on efficiency
                    #     delta_v_list = [
                    #         i for i in range(len(self.t))
                    #         if random.random() < BOB_DETECTOR_EFFICIENCY
                    #     ]
                    #     self.logger.info(
                    #         f"[QT1] Simulated delta_v: {len(delta_v_list)}/{len(self.t)} detected "
                    #         f"(efficiency={BOB_DETECTOR_EFFICIENCY*100:.2f}%)"
                    #     )
                    # else:
                    #     # Perfect detection (legacy behavior)
                    #     delta_v_list = list(range(len(self.t)))
                    #     self.logger.debug("[QT1] Delta_v: perfect detection (legacy mode)")
                    # await self.send_async(delta_v_list, agent.writer_main, name=self.name, var="delta_v")
                    # self.logger.info(f"[QT1] Sent delta_v ({len(delta_v_list)} indices) to agent {pid}")

                    # QT1: Send total_sent_count for true P_det calculation
                    # This is critical for detecting selective loss attacks
                    if self.total_sent_count is not None:
                        await self.send_async(self.total_sent_count, agent.writer_main, name=self.name, var="total_sent_count")
                        self.logger.info(f"[QT1] Sent total_sent_count = {self.total_sent_count:,} to agent {pid}")

                await self.send_async("OK", writer, name=self.name)

                # Stage II: Receive c from Alice
                _, c = await self.receive_async(reader)
                self.logger.info(f"Received c: {truncate_bitstring(c)}")

                # Send c to all agents
                for pid, agent in self.agents.items():
                    await self.send_async(c, agent.writer_main, name=self.name, var="c")
                self.logger.info(f"Sent c to all agents: {truncate_bitstring(c)}")

                # Wait for validation result from Alice
                _, validation_result = await self.receive_async(reader)
                if validation_result:
                    self.logger.info(
                        f"=== TOKEN VALIDATION RESULT: {validation_result} ===")
                    print(
                        f"\nTOKEN VALIDATION RESULT: {validation_result} ",
                        flush=True)
                else:
                    self.logger.warning("No validation result received from Alice")
                    print("\nNo validation result received from Alice", flush=True)

                self.session_count += 1
                self.logger.info(
                    f"Session Alice completed successfully. Total sessions: {self.session_count}")

                # ============================================================
                # QT1 SECURITY SUMMARY (Kent 2022)
                # ============================================================
                from src.utils.protocol_utils import calculate_epsilon_unf, calculate_scaled_security_bounds
                from config.defaults import QT1_GAMMA_DET, QT1_GAMMA_ERR

                self.logger.info("=" * 60)
                self.logger.info("[QT1] SESSION SECURITY SUMMARY")
                self.logger.info("=" * 60)

                # Protocol parameters
                n_bits = len(self.t)
                self.logger.info(f"[QT1] Protocol: M={self.M} ({2**self.M} agents), N_received={n_bits:,} bits")

                if self.total_sent_count is not None:
                    # Calculate epsilon_unf (Theorem 1)
                    epsilon_unf, security_bits = calculate_epsilon_unf(
                        N=self.total_sent_count,
                        gamma_err=QT1_GAMMA_ERR,
                        gamma_det=QT1_GAMMA_DET
                    )

                    self.logger.info(f"[QT1] N_sent (total pulses): {self.total_sent_count:,}")
                    self.logger.info(f"[QT1] Channel efficiency: {n_bits / self.total_sent_count * 100:.4f}%")
                    self.logger.info(f"[QT1] Thresholds: gamma_det={QT1_GAMMA_DET}, gamma_err={QT1_GAMMA_ERR}")
                    self.logger.info(f"[QT1] Theorem 1: epsilon_unf = {epsilon_unf:.2e}")
                    self.logger.info(f"[QT1] Security level: {security_bits:.1f} bits")

                    # Theorem 2 scaling for M > 1
                    if self.M >= 1:
                        scaled = calculate_scaled_security_bounds(M=self.M, epsilon_unf=epsilon_unf)
                        self.logger.info(
                            f"[QT1] Theorem 2 (M={self.M}): C={scaled['C']} point pairs, "
                            f"epsilon_unf^M = {scaled['epsilon_unf_M']:.2e}"
                        )
                        self.logger.info(f"[QT1] Scaled security: {scaled['security_bits_M']:.1f} bits")

                        # Security assessment
                        if scaled['security_bits_M'] >= 128:
                            assessment = "STRONG SECURITY (>= 128 bits)"
                        elif scaled['security_bits_M'] >= 64:
                            assessment = "MODERATE SECURITY (64-127 bits)"
                        elif scaled['security_bits_M'] > 0:
                            assessment = f"WEAK SECURITY ({scaled['security_bits_M']:.1f} bits)"
                        else:
                            assessment = "NO SECURITY GUARANTEE"
                        self.logger.info(f"[QT1] Assessment: {assessment}")
                        print(f"\n[QT1] Security Assessment: {assessment}", flush=True)
                else:
                    self.logger.warning("[QT1] total_sent_count not available - cannot compute epsilon_unf")
                    self.logger.info("[QT1] Run with --sim mode for full security analysis")

                self.logger.info("=" * 60)
            except Exception as e:
                self.logger.error(f"Error processing Alice's request: {e}")
            finally:
                writer.close()
                await writer.wait_closed()
                self.logger.info("Connection to Alice closed.")

                # Check if we should stop after this session
                if not self.persistent:
                    self.logger.info(
                        "Non-persistent mode: shutting down after session...")
                    await self.shutdown()
                    break

    async def run(self):
        """Execute Bob's main protocol"""
        self.logger.info(f"t: {truncate_bitstring(self.t)}")
        self.logger.info(f"u: {truncate_bitstring(self.u)}")

        # Calculate and log bias statistics for Bob's local data
        from src.utils.protocol_utils import get_bias_stats
        self.logger.info(get_bias_stats(self.t, "Bob Value t"))
        print(f"\n{get_bias_stats(self.t, 'Bob Value t')}", flush=True)
        self.logger.info(get_bias_stats(self.u, "Bob Basis u"))
        print(f"{get_bias_stats(self.u, 'Bob Basis u')}\n", flush=True)

        self.logger.info(f"len(t): {len(self.t)}")
        self.logger.info(f"len(u): {len(self.u)}")
        self.logger.info(f"Persistent mode: {self.persistent}")

        # SIMPLIFIED: SIMULATED_LOSS_RATE reality check removed - FPGA does post-selection (gcuser)
        # from config.defaults import SIMULATED_LOSS_RATE
        # import math
        # n_received = len(self.t)
        # n_sent_virtual = int(n_received / (1 - SIMULATED_LOSS_RATE))
        # loss_percent = SIMULATED_LOSS_RATE * 100
        # order_of_magnitude = int(math.log10(n_sent_virtual)) if n_sent_virtual > 0 else 0
        # self.logger.info(f"[QT1] REALITY CHECK: To get {n_received:,} bits, we virtually sent ~{n_sent_virtual:,} qubits (10^{order_of_magnitude}).")
        # self.logger.info(f"[QT1] Effective Channel Loss: {loss_percent:.1f}% (Simulated)")
        # print(f"\n[QT1] REALITY CHECK: {n_received:,} bits received <- ~10^{order_of_magnitude} qubits sent (Loss: {loss_percent:.1f}%)\n", flush=True)

        # Start agent servers
        for pid, addr in self.agent_main_addrs.items():
            asyncio.create_task(
                self._accept_agent(pid, addr)
            )

        # Start server for Alice
        self.alice_serv = await asyncio.start_server(
            self.handle_alice, *self.addr
        )
        self.logger.info(f"Server started on {self.addr}")

        asyncio.create_task(self.process_alice())

        try:
            async with self.alice_serv:
                # Wait for shutdown event instead of serve_forever
                await self.shutdown_event.wait()
        except asyncio.CancelledError:
            self.logger.info("Server task cancelled")
            await self.shutdown()


async def main():
    """Main function to run Bob"""
    parser = argparse.ArgumentParser(description="Bob - QToken Protocol")
    parser.add_argument("--M", type=int, default=2,
                        help="Number of bits to identify agents")
    parser.add_argument("--port", type=int,
                        default=DEFAULT_BOB_PORT, help="Bob server port")
    parser.add_argument("--basis", type=str, default="",
                        help="Basis string to parse t and u")
    parser.add_argument(
        "--sim", type=bool, default=False,
        help="If true, read basis and meas from file")
    parser.add_argument("--bit_size", type=int, default=10, help="Bit size")
    parser.add_argument("--t", type=str, default=BOB_DEFAULT_T, help="t value")
    parser.add_argument("--u", type=str, default=BOB_DEFAULT_U, help="u value")
    parser.add_argument("--log-level", type=str, default="INFO", help="Log level")
    parser.add_argument(
        "--persistent", action="store_true",
        help="Keep server running after protocol completion (default: one-shot)")
    parser.add_argument(
        "--run_id", type=int, default=None,
        help="Run ID to load from database (offline mode)")
    parser.add_argument(
        "--db_path", type=str, default="data/quantum_data.db",
        help="Path to SQLite database (default: data/quantum_data.db)")

    args = parser.parse_args()

    # Configure logging
    setup_logging(level=args.log_level, name="Bob")

    # OFFLINE MODE: Load from database if run_id is provided
    if args.run_id is not None:
        import sqlite3
        logging.info(f"Loading data from database (run_id={args.run_id})...")

        try:
            conn = sqlite3.connect(args.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT t, u FROM runs WHERE id = ?", (args.run_id,))
            row = cursor.fetchone()
            conn.close()

            if row is None:
                logging.error(f"Run ID {args.run_id} not found in database")
                return

            t_parsed, u_parsed = row
            total_sent_count = None  # No hardware timing in database mode
            logging.info(
                f"Loaded data from database: t (len={len(t_parsed)}), u (len={len(u_parsed)})")
        except Exception as e:
            logging.error(f"Error loading data from database: {e}")
            return
    # Parse arguments
    elif args.t and args.u and not args.sim:
        t_parsed = args.t
        u_parsed = args.u
        total_sent_count = None  # No hardware timing in manual mode
    elif args.sim:
        logging.debug("Starting to get angles from readerA...")

        # Calculate num_batches and batch_size based on bit_size
        from config.defaults import HW_SIM_BATCH_SIZE, HW_SIM_DATA_MARGIN, LASER_FREQUENCY
        import time
        batch_size = HW_SIM_BATCH_SIZE
        # Add margin to ensure we have enough data
        required_data = int(args.bit_size * HW_SIM_DATA_MARGIN)
        # Ceiling division
        num_batches = (required_data + 2 * batch_size - 1) // (2 * batch_size)

        logging.info(
            f"Calculated num_batches={num_batches}, batch_size={batch_size} for bit_size={args.bit_size}")

        socket_reader, socket_writer = await send_start_command("hwsim")
        if not socket_reader or not socket_writer:
            logging.error(
                "Failed to send start command to Alice's simulation.")
            return

        # Get angles directly from readerA (duration measured inside reader_alice)
        angles_A, duration = await reader_alice(mode='hwsim', num_batches=num_batches, batch_size=batch_size)

        if not angles_A:
            logging.error("Failed to get angles from readerA.")
            return

        # QT1: Calculate total_sent_count for true P_det (duration from reader_alice)
        total_sent_count = int(duration * LASER_FREQUENCY)
        logging.info(f"[QT1] Data collection took {duration:.4f}s -> total_sent_count = {total_sent_count:,}")

        try:
            Ah, Ax = parse_angle(angles_A, "A")
        except Exception as e:
            logging.error(f"Error parsing angles: {e}")
            logging.error(
                f"Angles (first 10): {angles_A[:10] if angles_A else 'empty'}")
            return

        # Optimized: Use integer representation (200x faster for 1M bits)
        t_int = list_to_int(Ax[:args.bit_size])
        u_int = list_to_int(Ah[:args.bit_size])
        bitlen = min(len(Ax), args.bit_size)

        # Convert back to string for backward compatibility with protocol
        t_parsed = int_to_str(t_int, bitlen)
        u_parsed = int_to_str(u_int, bitlen)

        logging.debug(f"Parsed t (len={len(t_parsed)}), u (len={len(u_parsed)})")
    else:
        t_parsed = BOB_DEFAULT_T
        u_parsed = BOB_DEFAULT_U
        total_sent_count = None  # No hardware timing in default mode

    logging.info(f"t: {truncate_bitstring(t_parsed)}, len: {len(t_parsed)}")
    logging.info(f"u: {truncate_bitstring(u_parsed)}, len: {len(u_parsed)}")

    # Signal that Bob has finished reading data (only in sim mode, not in offline mode)
    if args.sim and args.run_id is None:
        ready_file = "/tmp/.bob_ready"
        with open(ready_file, 'w') as f:
            f.write("ready")
        logging.info(f"Bob data ready - signal file created: {ready_file}")

    addr = (DEFAULT_BASE_IP, args.port)
    bob = Bob("Bob", args.M, addr, t_val=t_parsed,
              u_val=u_parsed, persistent=args.persistent,
              total_sent_count=total_sent_count)

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()

    def signal_handler():
        logging.info("Received shutdown signal (SIGINT/SIGTERM)")
        asyncio.create_task(bob.shutdown())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await bob.run()
    finally:
        logging.info("Bob has stopped")


if __name__ == "__main__":
    asyncio.run(main())

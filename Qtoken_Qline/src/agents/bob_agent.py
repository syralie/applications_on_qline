"""
Bob agent for the QToken protocol
"""

from src.utils.logging_config import setup_logging
from src.utils.protocol_utils import generate_presentation_points, verify_token_error, xor_bits, truncate_bitstring  # set_to_mask removed (SIMPLIFIED)
from src.utils.participant import Participant
from config.defaults import (
    DEFAULT_BOB_AGENT_BASE_PORT,
    DEFAULT_BOB_AGENT_CLIENT_PORT,
    QT1_GAMMA_DET,
    QT1_GAMMA_ERR
)
import asyncio
import logging
import argparse
import sys
import os
import signal
import gc  # For latency stability

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


class BobAgent(Participant):
    """
    Bob agent for the QToken protocol
    """

    def __init__(self, pid, M, gamma_err=None, gamma_det=None):
        super().__init__(f"BobAgent-{pid}")
        self.pid = pid
        self.M = M
        # QT1 security thresholds (use defaults from config if not specified)
        # Defaults are calibrated from real hardware measurements
        self.gamma_det = gamma_det if gamma_det is not None else QT1_GAMMA_DET
        self.gamma_err = gamma_err if gamma_err is not None else QT1_GAMMA_ERR
        self.data: dict[str, any] = {
            "d_i": None, "t": None, "u": None,
            "c": None, "d_tilde": None, "token": None,
            # SIMPLIFIED: Lambda/Delta_v removed - FPGA does post-selection
            # "lambda_set": None,
            # "delta_v": None,
            # "lambda_mask": None,
            # "delta_v_mask": None,
            "total_sent_count": None  # QT1: Total pulses sent for true P_det calculation
        }

        self.reader_main = None
        self.writer_main = None
        self.reader_client = None
        self.writer_client = None
        self.shutdown_event = asyncio.Event()

        # Run warmup to ensure deterministic latency
        self._warmup()

    def _warmup(self):
        """
        Pre-run verify_token_error with dummy data to warm up Python's
        bytecode compilation and memory allocation. This ensures the first
        real verification has deterministic latency.
        """
        # Create small dummy data (1000 bits is enough for warmup)
        dummy_bases = "0" * 1000
        dummy_results = "1" * 1000
        dummy_mask = (1 << 1000) - 1  # All 1s

        # Silent logger for warmup
        class SilentLogger:
            def info(self, *a, **k): pass
            def debug(self, *a, **k): pass
            def warning(self, *a, **k): pass
            def error(self, *a, **k): pass

        # Run verification with dummy data (result doesn't matter)
        verify_token_error(
            alice_bases=dummy_bases,
            alice_results=dummy_results,
            bob_bases=dummy_bases,
            bob_states=dummy_results,
            gamma_err=0.5,
            logger=SilentLogger()
        )
        self.logger.debug("[Warmup] verify_token_error warmed up")

    async def connect_main(self):
        """Connect to Bob's main server"""
        addr = generate_presentation_points(
            self.M, base_port=DEFAULT_BOB_AGENT_BASE_PORT)[self.pid]
        self.reader_main, self.writer_main = await asyncio.open_connection(*addr)
        self.logger.info(f"Connected to main server at {addr}")
        asyncio.create_task(self.listen_main())

    async def listen_main(self):
        """Listen for messages from main server"""
        while not self.shutdown_event.is_set():
            if self.reader_main is None:
                self.logger.error("reader_main is None")
                self.shutdown_event.set()
                break

            try:
                var, val = await asyncio.wait_for(
                    self.receive_async(self.reader_main), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue  # Check shutdown_event again
            except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError) as e:
                self.logger.warning(f"Connection to main server lost: {e}")
                self.logger.info("Main server disconnected, initiating shutdown...")
                self.shutdown_event.set()
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in listen_main: {e}")
                self.shutdown_event.set()
                break

            if var is None or val is None:
                self.logger.warning(
                    "No data received from main server or one data is missing.")
                self.logger.info(
                    "Connection closed by main server, initiating shutdown...")
                self.shutdown_event.set()
                break

            # Check for shutdown command
            if val == "SHUTDOWN":
                self.logger.info("Received SHUTDOWN command from main server")
                self.shutdown_event.set()
                break

            if var == "c":
                self.data["c"] = val
                self.logger.info(f"Received c: {truncate_bitstring(val)}")
                # Compute d_tilde
                if self.data["d_i"] is not None and self.data["c"] is not None:
                    repeated_c = (self.data["c"] * (len(self.data["d_i"]) //
                                                    len(self.data["c"])))[:len(self.data["d_i"])]
                    self.data["d_tilde"] = xor_bits(self.data["d_i"], repeated_c)
                    self.logger.info(
                        f"Computed d_tilde: {truncate_bitstring(self.data['d_tilde'])}")
                else:
                    self.logger.error(
                        f"Cannot compute d_tilde: d_i={truncate_bitstring(self.data['d_i'])}, c={truncate_bitstring(self.data['c'])}")
            # SIMPLIFIED: lambda_set and delta_v handlers removed - FPGA does post-selection
            elif var == "total_sent_count":
                # QT1: Receive total_sent_count for true P_det calculation
                self.data["total_sent_count"] = int(val) if val is not None else None
                if self.data["total_sent_count"] is not None:
                    self.logger.info(
                        f"[QT1] Received total_sent_count = {self.data['total_sent_count']:,} "
                        f"(for true P_det calculation)")
            else:
                if var in self.data:
                    self.data[var] = val
                    self.logger.info(f"Received {var}: {truncate_bitstring(val) if isinstance(val, str) else val}")
                else:
                    self.logger.warning(f"Unknown variable received: {var}")

    async def shutdown(self):
        """Graceful shutdown of connections"""
        self.logger.info("Initiating graceful shutdown...")
        self.shutdown_event.set()

        # Close main connection
        if self.writer_main:
            self.writer_main.close()
            await self.writer_main.wait_closed()
            self.logger.info("Closed connection to main server")

        # Close client connection
        if self.writer_client:
            self.writer_client.close()
            await self.writer_client.wait_closed()
            self.logger.info("Closed connection to client")

        self.logger.info("Shutdown complete")

    async def start_client_server(self):
        """Start server for Alice agents"""
        addr = generate_presentation_points(
            self.M, base_port=DEFAULT_BOB_AGENT_CLIENT_PORT)[self.pid]
        srv = await asyncio.start_server(
            self.handle_client, *addr
        )
        self.logger.info(f"Listening for AliceAgent at {addr}")

        try:
            async with srv:
                # Wait for shutdown event instead of serve_forever
                await self.shutdown_event.wait()
        except asyncio.CancelledError:
            self.logger.info("Client server task cancelled")
        finally:
            srv.close()
            await srv.wait_closed()

    async def handle_client(self, reader, writer):
        """Handle Alice agent connections"""
        self.logger.info("Alice connected")
        # Do not use self.reader_client to avoid race conditions with multiple connections
        asyncio.create_task(self.listen_client(reader, writer))

    async def listen_client(self, reader, writer):
        """Listen for messages from Alice agents"""
        self.reader_client = reader # Keep for reference if needed, but use local var
        self.writer_client = writer

        try:
            var, tok = await self.receive_async(reader)
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError) as e:
            self.logger.warning(f"Connection to Alice agent lost: {e}")
            return
        except Exception as e:
            self.logger.error(f"Unexpected error in listen_client: {e}")
            return

        if var == "token":
            self.data["token"] = tok
            # Wait for d_tilde to be computed (after receiving c)
            # Use 1ms polling instead of 100ms to avoid latency spikes
            while self.data["d_tilde"] is None and not self.shutdown_event.is_set():
                await asyncio.sleep(0.001)

            if self.shutdown_event.is_set():
                return

            # Start timing AFTER all dependencies are ready
            # This measures only the verification computation, not wait time
            start_time = asyncio.get_running_loop().time()

            # Use verify_token_error with QT1 conformant parameters
            self.logger.info(
                f"[QT1] Starting token verification with gamma_det={self.gamma_det}, gamma_err={self.gamma_err}")

            # Disable GC during critical section for deterministic latency
            gc.disable()
            try:
                res, reason = verify_token_error(
                    alice_bases=self.data["d_tilde"],
                    alice_results=self.data["token"],
                    bob_bases=self.data["u"],
                    bob_states=self.data["t"],
                    gamma_err=self.gamma_err,
                    logger=self.logger,
                    gamma_det=self.gamma_det,
                    total_sent_count=self.data["total_sent_count"])  # QT1: For true P_det!
            finally:
                gc.enable()

            # Check Relativistic Timing Constraints
            end_time = asyncio.get_running_loop().time()
            latency_ms = (end_time - start_time) * 1000.0
            from config.defaults import QT1_MAX_LATENCY_MS
            from src.utils.protocol_utils import get_bias_stats, calculate_epsilon_unf, calculate_scaled_security_bounds

            # Approximate distance based on speed of light c ~ 300,000 km/s = 300 km/ms
            min_dist_km = latency_ms * 300.0

            # Calculate biases
            bias_x = get_bias_stats(self.data.get("token", ""), "Token Value (x)")
            bias_d = get_bias_stats(self.data.get("d_tilde", ""), "Basis (d_tilde)")

            status_msg = f"STATUS: Latency {latency_ms:.2f}ms -> Min Dist {min_dist_km:.2f} km | {bias_x} | {bias_d}"

            # Send status to Bob server (Feedback)
            if self.writer_main:
                try:
                    await self.send_async(status_msg, self.writer_main, name=f"BobAgent-{self.pid}")
                except Exception as e:
                    self.logger.error(f"Failed to send status to Bob: {e}")

            if latency_ms > QT1_MAX_LATENCY_MS:
                self.logger.error(
                    f"[QT1] SECURITY VIOLATION (Relativistic): Latency {latency_ms:.2f}ms > {QT1_MAX_LATENCY_MS}ms")
                self.logger.info(f"[QT1] Relativistic constraint: {status_msg}")
                res = False # Reject the token due to timing violation
            else:
                self.logger.info(
                    f"[QT1] Relativistic check passed: Latency {latency_ms:.2f}ms <= {QT1_MAX_LATENCY_MS}ms")
                self.logger.info(f"[QT1] Relativistic constraint: {status_msg}")

            # Calculate and display epsilon_unf (Theorem 1, Kent 2022)
            if self.data["total_sent_count"] is not None:
                epsilon_unf, security_bits = calculate_epsilon_unf(
                    N=self.data["total_sent_count"],
                    gamma_err=self.gamma_err,
                    gamma_det=self.gamma_det
                )
                self.logger.info(
                    f"[QT1] Security (Theorem 1): epsilon_unf = {epsilon_unf:.2e}, "
                    f"security = {security_bits:.1f} bits"
                )

                # Security assessment
                if security_bits >= 128:
                    self.logger.info("[QT1] STRONG SECURITY (>= 128 bits)")
                elif security_bits >= 64:
                    self.logger.warning("[QT1] MODERATE SECURITY (64-127 bits)")
                elif security_bits > 0:
                    self.logger.warning(f"[QT1] WEAK SECURITY ({security_bits:.1f} bits)")
                else:
                    self.logger.error("[QT1] NO SECURITY GUARANTEE (epsilon_unf >= 1)")

                # Display scaled bounds for M > 1 (Theorem 2)
                if self.M > 1:
                    scaled = calculate_scaled_security_bounds(M=self.M, epsilon_unf=epsilon_unf)
                    self.logger.info(
                        f"[QT1] Theorem 2 (M={self.M}): C={scaled['C']} point pairs, "
                        f"epsilon_unf^M = {scaled['epsilon_unf_M']:.2e}, "
                        f"security = {scaled['security_bits_M']:.1f} bits"
                    )

            if res:
                msg = f"Token is valid ({reason})"
                if self.writer_client is not None:
                    await self.send_async(msg, self.writer_client,
                                          name=f"BobAgent-{self.pid}", var="message")
                self.logger.info("[QT1] Token verification PASSED")
            else:
                msg = f"Token is invalid: {reason}"
                if self.writer_client is not None:
                    await self.send_async(msg, self.writer_client,
                                          name=f"BobAgent-{self.pid}", var="message")
                self.logger.info("[QT1] Token verification FAILED")
        else:
            self.logger.warning(f"Unexpected message from Alice: {var}")

        if self.writer_client is not None:
            self.writer_client.close()
            await self.writer_client.wait_closed()

    async def run(self):
        """Execute Bob agent"""
        await self.connect_main()

        # Start client server as a task
        server_task = asyncio.create_task(self.start_client_server())

        self.logger.info("BobAgent is running and waiting for connections...")

        try:
            # Wait for shutdown event
            await self.shutdown_event.wait()
        except asyncio.CancelledError:
            self.logger.info("BobAgent task cancelled")
            await self.shutdown()
        finally:
            # Cancel server task if still running
            if not server_task.done():
                server_task.cancel()
                try:
                    await server_task
                except asyncio.CancelledError:
                    pass

            self.logger.info("BobAgent has stopped")


async def async_main():
    """Async main function to run Bob agent"""
    parser = argparse.ArgumentParser(description="BobAgent - QToken Protocol (QT1 Conformant)")
    parser.add_argument("--pid", type=str, required=True, help="Agent ID")
    parser.add_argument("--M", type=int, default=2,
                        help="Number of bits to identify agents")
    parser.add_argument("--gamma-det", type=float, default=None,
                        help="QT1 detection rate threshold (default: from config, ~0.0008)")
    parser.add_argument("--gamma-err", type=float, default=None,
                        help="QT1 error rate threshold (default: from config, ~0.08)")
    parser.add_argument("--log-level", type=str, default="INFO", help="Log level")

    args = parser.parse_args()

    # Configure logging
    setup_logging(level=args.log_level, name=f"BobAgent-{args.pid}")

    bob_agent = BobAgent(
        pid=args.pid,
        M=args.M,
        gamma_err=args.gamma_err,
        gamma_det=args.gamma_det
    )

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()

    def signal_handler():
        logging.info(
            f"BobAgent-{args.pid}: Received shutdown signal (SIGINT/SIGTERM)")
        asyncio.create_task(bob_agent.shutdown())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await bob_agent.run()
    finally:
        logging.info(f"BobAgent-{args.pid} has stopped")


def main():
    """Main function to run Bob agent"""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()

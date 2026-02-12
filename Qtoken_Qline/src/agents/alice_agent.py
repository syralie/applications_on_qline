"""
Alice agent for the QToken protocol
"""

from src.utils.logging_config import setup_logging
from src.utils.protocol_utils import generate_presentation_points
from src.utils.participant import Participant
from config.defaults import DEFAULT_ALICE_AGENT_PORT, DEFAULT_BOB_AGENT_CLIENT_PORT
import asyncio
import logging
import argparse
import sys
import os
import signal

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


class AliceAgent(Participant):
    """
    Alice agent for the QToken protocol
    """

    def __init__(self, pid, M, al_port=DEFAULT_ALICE_AGENT_PORT):
        super().__init__(f"AliceAgent-{pid}")
        self.pid = pid
        self.M = M
        self.al_port = al_port
        self.token = None

        self._evt_received = asyncio.Event()
        self._evt_sent = asyncio.Event()
        self.shutdown_event = asyncio.Event()

    async def connect_alice(self):
        """Connect to Alice's main server"""
        addr = generate_presentation_points(self.M, base_port=self.al_port)[self.pid]
        self.reader_alice, self.writer_alice = await asyncio.open_connection(*addr)
        self.logger.info(f"Connected to Alice at {addr}")
        asyncio.create_task(self.listen_alice())

    async def listen_alice(self):
        """Listen for messages from Alice"""
        while not self.shutdown_event.is_set():
            try:
                var, val = await asyncio.wait_for(
                    self.receive_async(self.reader_alice), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue  # Check shutdown_event again
            except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError) as e:
                self.logger.warning(f"Connection to Alice lost: {e}")
                self.logger.info("Alice disconnected, initiating shutdown...")
                self.shutdown_event.set()
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in listen_alice: {e}")
                self.shutdown_event.set()
                break

            if var is None or val is None:
                self.logger.warning(
                    "No data received from Alice or one data is missing.")
                self.logger.info(
                    "Connection closed by Alice, initiating shutdown...")
                self._evt_received.set()
                self._evt_sent.set()
                self.shutdown_event.set()
                await self.close()
                break

            # Check for shutdown command
            if val == "SHUTDOWN":
                self.logger.info("Received SHUTDOWN command from Alice")
                self.shutdown_event.set()
                break

            if var == "token":
                if val == "send_token":
                    await self.send_async(self.token, self.writer_bobagent, name="AliceAgent", var="token")
                    self.logger.info(f"Sent token to BobAgent {self.pid}")
                    self._evt_sent.set()
                    break
                elif val != "send_token" and not self._evt_received.is_set():
                    self.token = val
                    self._evt_received.set()
                    self.logger.info(
                        f"Received token: {val[: 10] if len(val) > 10 else val}...")
                else:
                    self.logger.warning(f"Unexpected token value received: {val}")

            else:
                self.logger.warning(f"Unexpected variable received: {var}")

    async def connect_bobagent(self):
        """Connect to corresponding Bob agent"""
        addr = generate_presentation_points(
            self.M, base_port=DEFAULT_BOB_AGENT_CLIENT_PORT)[self.pid]
        self.reader_bobagent, self.writer_bobagent = await asyncio.open_connection(*addr)
        self.logger.info(f"Connected to BobAgent at {addr}")

    async def shutdown(self):
        """Graceful shutdown of connections"""
        self.logger.info("Initiating graceful shutdown...")
        self.shutdown_event.set()

        # Set events to unblock waiting tasks
        self._evt_received.set()
        self._evt_sent.set()

        await self.close()
        self.logger.info("Shutdown complete")

    async def run(self):
        """Execute Alice agent"""
        await self.connect_bobagent()
        await self.connect_alice()
        self.logger.info(
            f"Received token: {self.token[:10] if self.token and len(self.token) > 10 else self.token}...")

        try:
            await self._evt_received.wait()

            if self.shutdown_event.is_set():
                return

            await self._evt_sent.wait()

            if self.shutdown_event.is_set():
                return

            try:
                _, mes = await self.receive_async(self.reader_bobagent)
            except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError) as e:
                self.logger.warning(f"Connection to BobAgent lost: {e}")
                return

            if mes is None:
                self.logger.info("No message received from BobAgent.")
            else:
                self.logger.info(f"Received message from BobAgent: {mes}")
                try:
                    await self.send_async(mes, self.writer_alice, name=f"AliceAgent-{self.pid}", var="message")
                except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError) as e:
                    self.logger.warning(
                        f"Cannot send message to Alice, connection lost: {e}")
        except asyncio.CancelledError:
            self.logger.info("AliceAgent task cancelled")
            await self.shutdown()
        finally:
            await self.close()
            self.logger.info("AliceAgent has stopped")

    async def close(self):
        """Close connections"""
        if self.writer_alice:
            self.writer_alice.close()
            await self.writer_alice.wait_closed()
        if self.writer_bobagent:
            self.writer_bobagent.close()
            await self.writer_bobagent.wait_closed()


async def async_main():
    """Async main function to run Alice agent"""
    parser = argparse.ArgumentParser(description="AliceAgent - QToken Protocol")
    parser.add_argument("--pid", type=str, required=True, help="Agent ID")
    parser.add_argument("--M", type=int, default=2,
                        help="Number of bits to identify agents")
    parser.add_argument("--al_port", type=int,
                        default=DEFAULT_ALICE_AGENT_PORT, help="Alice's port")
    parser.add_argument("--log-level", type=str, default="INFO", help="Log level")

    args = parser.parse_args()

    # Configure logging
    setup_logging(level=args.log_level, name=f"AliceAgent-{args.pid}")

    ag = AliceAgent(args.pid, args.M, args.al_port)

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()

    def signal_handler():
        logging.info(
            f"AliceAgent-{args.pid}: Received shutdown signal (SIGINT/SIGTERM)")
        asyncio.create_task(ag.shutdown())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await ag.run()
    finally:
        logging.info(f"AliceAgent-{args.pid} has stopped")


def main():
    """Main function to run Alice agent"""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()

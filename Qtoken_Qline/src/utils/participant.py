"""
Base class for QToken protocol participants
"""

import asyncio
import logging
import pickle

from src.utils.protocol_utils import truncate_bitstring


class Participant:
    """
    Base class for participants (Alice and Bob)
    Manages asynchronous communication between participants
    """

    def __init__(self, name=None):
        self.name = name
        self.logger = logging.getLogger(name or self.__class__.__name__)

    async def send_async(
            self, message, writer: asyncio.StreamWriter, name=None, var=None):
        """
        Send a message asynchronously

        Args:
            message: Message to send
            writer: StreamWriter for sending
            name: Sender name
            var: Variable name
        """
        # Log with truncated message for readability
        truncated_msg = truncate_bitstring(message)
        if name:
            log_msg = f"{name}: - Sending: {var + ' = ' if var else ''}{truncated_msg}"
        else:
            log_msg = f"- Sending: {var + ' = ' if var else ''}{truncated_msg}"

        self.logger.info(log_msg)

        # Build full message for network transmission
        if name:
            full = f"{name}: - Sending: {var + ' = ' if var else ''}{message}"
        else:
            full = f"- Sending: {var + ' = ' if var else ''}{message}"

        try:
            data = pickle.dumps(full)
            header = len(data).to_bytes(4, 'big')
            writer.write(header + data)
            await writer.drain()
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")

    async def receive_async(self, reader: asyncio.StreamReader, description=''):
        """
        Receive a message asynchronously

        Args:
            reader: StreamReader for receiving
            description: Message description for logging

        Returns:
            tuple: (variable, message) or (None, None) on error

        Raises:
            ConnectionResetError, BrokenPipeError, ConnectionAbortedError:
                If the connection is lost (propagated for proper handling by caller)
        """
        try:
            header = await reader.readexactly(4)
            size = int.from_bytes(header, 'big')
            raw = await reader.readexactly(size)
            if not raw:
                self.logger.warning("Received no data, connection may be closed.")
                return None, None
            data = pickle.loads(raw)
        except asyncio.IncompleteReadError:
            self.logger.warning("Incomplete read error, connection may be closed.")
            return None, None
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            # Re-raise connection errors so they can be handled by the caller
            raise
        except Exception as e:
            if description != "token":
                self.logger.error(f"Error receiving message: {e}")
            else:
                self.logger.info("No token received, continuing without it.")
            return None, None

        # Parse received message
        if "-" in data:
            name, part2 = data.split(" - ", 1)
            part3 = part2.split(": ", 1)[-1]
            if " = " in part3:
                var, message = part3.split(" = ", 1)
                self.logger.info(
                    f"Received from {name}: {var} = {truncate_bitstring(message)}")
            else:
                var = None
                message = part3
                self.logger.info(
                    f"Received from {name}: {truncate_bitstring(message)}")
        else:
            if " = " in data:
                var, message = data.split(" = ", 1)
                self.logger.info(f"Received: {var} = {truncate_bitstring(message)}")
            else:
                var = None
                message = data.split(": ", 1)[-1]
                self.logger.info(f"Received: {truncate_bitstring(message)}")

        return var, message

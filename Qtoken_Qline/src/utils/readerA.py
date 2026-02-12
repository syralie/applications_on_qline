from config.defaults import FIFO_PATH_ANGLE_ALICE
import asyncio
import threading
import queue
import logging
import os
import sys
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def reader_alice(mode, num_batches, batch_size):
    """
    Reusable Alice reader - creates a new queue on each call.
    Can be called multiple times to read successive data from hardware.

    Returns:
        tuple: (ang_list, duration_seconds) where:
            - ang_list: list of bytes read from hardware
            - duration_seconds: time elapsed during data collection (for N_sent calculation)
        Returns (None, None) on error.
    """
    # Create a NEW local queue on each call (not global!)
    local_queue = queue.Queue()

    if mode == "hwsim" or mode == "test":
        angle_fifo = FIFO_PATH_ANGLE_ALICE
    elif mode == "real":
        angle_fifo = "/dev/xdma0_c2h_3"
    else:
        logging.error(f"[Reader A] Unknown mode: {mode}")
        return None, None

    # Check if FIFO exists before attempting to open
    if not os.path.exists(angle_fifo):
        logging.error(f"[Reader A] FIFO not found at: {angle_fifo}")
        logging.error(
            "[Reader A] Make sure the simulator is running (./scripts/launch_simulation.sh)")
        return None, None

    logging.info(f"[Reader A] FIFO path: {angle_fifo}")
    logging.info(
        f"[Reader A] Requesting {num_batches} batches of {batch_size} bytes each")

    def fifo_reader_alice(angle_fifo, batch_size, q):
        """Thread function: read FIFO continuously and push batches into the queue."""
        logging.info("[Reader A] FIFO reader thread started")
        logging.info(
            f"[Reader A] Opening FIFO: {angle_fifo} (this may block until simulator writes)")
        try:
            with open(angle_fifo, "rb") as f:
                logging.info(f"[Reader A] FIFO opened successfully: {angle_fifo}")
                for i in range(num_batches):
                    data = f.read(batch_size)
                    if not data:
                        logging.info("[Reader A] FIFO closed or no more data.")
                        break
                    q.put(data)
                    logging.debug(f"[Reader A] Read batch {i+1}/{num_batches}")
        except Exception as e:
            logging.error(f"[Reader A] Error reading FIFO: {e}")
        finally:
            q.put(None)  # sentinel value
            logging.info("[Reader A] FIFO reader thread finished")

    # Start a NEW thread on each call
    t = threading.Thread(
        target=fifo_reader_alice,
        args=(angle_fifo, batch_size, local_queue),
        daemon=True
    )

    # Start timer JUST before thread starts (most accurate for hardware read duration)
    start_time = time.time()
    t.start()

    # Consume from local queue
    ang_list = []
    for _ in range(num_batches):
        batch = await asyncio.to_thread(local_queue.get)
        if batch is None:  # got sentinel
            break
        ang_list.extend(list(batch))

    # Stop timer immediately after all data consumed
    end_time = time.time()
    duration_seconds = end_time - start_time

    logging.info(f"[Reader A] Finished reading {len(ang_list)} bytes total in {duration_seconds:.4f}s")

    # Wait for thread to finish properly
    t.join(timeout=5.0)
    if t.is_alive():
        logging.warning("[Reader A] Thread did not finish in time")

    return ang_list, duration_seconds


async def main():
    logging.basicConfig(level=logging.INFO)
    command_socket_path = "/tmp/gc_startstop"
    reader2, writer2 = await asyncio.open_unix_connection(command_socket_path)
    writer2.write(bytes([0x1, 0x0, 0x0, 0x0, 0x0]))
    await writer2.drain()
    logging.info("[C] Command sent, waiting for response...")
    resp = await reader2.read(5)
    await asyncio.sleep(2)
    logging.info(f"[C] Got response: {list(resp)}")

    angles, duration = await reader_alice(mode='hwsim', num_batches=5, batch_size=16)
    if angles:
        print(f"Angles (first 10): {angles[:10]}")
        print(f"Duration: {duration:.4f}s")
    else:
        print("Failed to read angles")
    # writer2.close()
    # await writer2.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())

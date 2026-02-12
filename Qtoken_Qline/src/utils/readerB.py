from config.defaults import FIFO_PATH_ANGLE_BOB, FIFO_PATH_RESULT  # , FIFO_PATH_GCUSER
import asyncio
import threading
import queue
import logging
# import struct  # Only needed for gcuser unpacking
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def reader_bob(mode, num_batches, batch_size):
    """
    Reusable Bob reader - creates a new queue on each call.
    Can be called multiple times to read successive data from hardware.
    Manages 2 FIFOs: angles and results (gcuser post-selection is done by the FPGA).
    """
    # Create a NEW local queue on each call
    local_queue = queue.Queue()

    if mode == "test" or mode == "hwsim":
        angle_path = FIFO_PATH_ANGLE_BOB
        result_path = FIFO_PATH_RESULT
        # gcuser_path = FIFO_PATH_GCUSER  # Post-selection done by FPGA, not needed here
    elif mode == "real":
        angle_path = "/dev/xdma0_c2h_3"
        result_path = "/home/vq-user/click_result.fifo"
        # gcuser_path = "/home/vq-user/gcuser.fifo"  # Post-selection done by FPGA, not needed here
    else:
        logging.error(f"[Reader B] Unknown mode: {mode}")
        return None, None

    # Check if FIFOs exist before attempting to open
    missing_fifos = []
    for fifo_name, fifo_path in [
        ("angle", angle_path),
        ("result", result_path)]:
            # ("gcuser", gcuser_path)]:  # Post-selection done by FPGA
        if not os.path.exists(fifo_path):
            missing_fifos.append(f"{fifo_name}: {fifo_path}")

    if missing_fifos:
        logging.error(f"[Reader B] Missing FIFOs:")
        for fifo in missing_fifos:
            logging.error(f"[Reader B]   - {fifo}")
        logging.error(
            "[Reader B] Make sure the simulator is running (./scripts/launch_simulation.sh)")
        return None, None

    logging.info(
        f"[Reader B] FIFO paths: angle={angle_path}, result={result_path}")
    logging.info(
        f"[Reader B] Requesting {num_batches} batches of {batch_size} bytes each")

    def fifo_reader_bob(angle_fifo, result_fifo, batch_size, q):
        """Thread: reads from 2 FIFOs and pushes a (angle, result) tuple."""
        logging.info("[Reader B] FIFO reader thread started")
        logging.info(
            f"[Reader B] Opening FIFOs (this may block until simulator writes):")
        logging.info(f"[Reader B]   - angle: {angle_fifo}")
        logging.info(f"[Reader B]   - result: {result_fifo}")
        # logging.info(f"[Reader B]   - gcuser: {gcuser_path}")  # Post-selection done by FPGA
        try:
            with open(angle_fifo, "rb") as af, open(result_fifo, "rb") as rf:
                logging.info(
                    f"[Reader B] Angle and result FIFOs opened successfully")
                # gcuser_fd = os.open(gcuser_path, os.O_RDONLY | os.O_NONBLOCK)
                # gcuser_fifo = os.fdopen(gcuser_fd, "rb")
                # logging.info(
                #     f"[Reader B] GCUser FIFO opened successfully: {gcuser_path}")

                for i in range(num_batches):
                    result_data = rf.read(2 * batch_size)
                    angle_data = af.read(batch_size)

                    # # Read fixed amount of gcuser data per batch: 2 * batch_size uint64 values
                    # gcuser_bytes = gcuser_fifo.read(2 * batch_size * 8)
                    # gcuser_data = []
                    #
                    # if gcuser_bytes and len(gcuser_bytes) == 2 * batch_size * 8:
                    #     try:
                    #         # Unpack all uint64 values at once
                    #         gcuser_data = list(
                    #             struct.unpack(
                    #                 f"<{2 * batch_size}Q", gcuser_bytes))
                    #     except Exception as e:
                    #         logging.error(
                    #             f"[Reader B] Error unpacking GCUser data: {e}")
                    # else:
                    #     logging.warning(
                    #         f"[Reader B] GCUser data incomplete at batch {i+1}: got {len(gcuser_bytes) if gcuser_bytes else 0} bytes, expected {2 * batch_size * 8}")

                    if not result_data or not angle_data:
                        logging.info(f"[Reader B] FIFO closed at batch {i+1}.")
                        break

                    q.put((angle_data, result_data))
                    logging.debug(f"[Reader B] Read batch {i+1}/{num_batches}")

                # gcuser_fifo.close()
        except Exception as e:
            logging.error(f"[Reader B] Error reading FIFO: {e}")
        finally:
            q.put(None)
            logging.info("[Reader B] FIFO reader thread finished")

    # Start a NEW thread on each call
    t = threading.Thread(
        target=fifo_reader_bob,
        args=(angle_path, result_path, batch_size, local_queue),
        daemon=True
    )
    t.start()

    angles = []
    results = []
    # gcusers = []  # Post-selection done by FPGA
    for _ in range(num_batches):
        item = await asyncio.to_thread(local_queue.get)
        if item is None:
            break
        a, r = item
        angles.extend(list(a))
        results.extend(list(r))
        # gcusers.extend(c)

    logging.info(f"[Reader B] Finished reading {len(angles)} bytes total.")

    # Wait for thread to finish properly
    t.join(timeout=5.0)
    if t.is_alive():
        logging.warning("[Reader B] Thread did not finish in time")

    return angles, results


async def main():
    logging.basicConfig(level=logging.INFO)
    angles, results = await reader_bob(mode='hwsim', num_batches=5, batch_size=16)
    print(f"Angles (first 10): {angles[:10]}")
    print(f"Results (first 10): {results[:10]}")
    # print(f"GCUsers (first 10): {gcusers[:10]}")
    # print(f"GCUsers length: {len(gcusers)}")


if __name__ == "__main__":
    asyncio.run(main())

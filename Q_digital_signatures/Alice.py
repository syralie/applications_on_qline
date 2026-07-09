import asyncio
import logging
from async_communication import asrecv, assend
from qkd import QKDHandlerAlice
from start_stop import send_start_command

from datetime import datetime


def dispatcher():
    return


def ProtocolAlice():
    return


async def main(num_qubits):
    # TODO: edit

    ### QKD with Charlie ###
    host = "localhost"
    port = "7100"
    path_config = "config_test/sim/alice/ot.json"

    socket_reader, socket_writer = await send_start_command("hwsim", path_config)
    reader, writer = await asyncio.open_connection(host, port)
    logging.info(f"[C] Connected to {host}:{port}")



    await assend(writer, {"type": "QKD", "num_qubits": num_qubits})
    QKD_Alice = QKDHandlerAlice(reader, writer, mode="hwsim", path_config=path_config, num_qubits=num_qubits, socket_reader=socket_reader, socket_writer=socket_writer)
    Charlie_key = await QKD_Alice.run_protocol()

    writer.close()
    await writer.wait_closed()


    ### QKD with Bob ###
    socket_reader, socket_writer = await send_start_command("hwsim", path_config)
    reader, writer = await asyncio.open_connection(host, port)
    logging.info(f"[C] Connected to {host}:{port}")

    await assend(writer, {"type": "QKD", "num_qubits": num_qubits})
    QKD_Alice = QKDHandlerAlice(reader, writer, mode="hwsim", path_config=path_config, num_qubits=num_qubits, socket_reader=socket_reader, socket_writer=socket_writer)
    Bob_key = await QKD_Alice.run_protocol()

    writer.close()
    await writer.wait_closed()




if __name__ == "__main__":
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = f"sim_alice_{timestamp}.log"
    # Configure logging
    logging.basicConfig(
        filename=log_filename,
        format="%(asctime)s - %(levelname)s - %(message)s",
        #level=logging.INFO, 
        level=logging.DEBUG, 
        force=True
    )
    asyncio.run(main(num_qubits = 100))
    
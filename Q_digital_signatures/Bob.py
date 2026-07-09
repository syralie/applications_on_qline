import asyncio
from async_communication import asrecv, assend
from qkd import QKDHandlerBob
import logging
from datetime import datetime


all_connections_done = asyncio.Event()

path_config = "config_test/sim/bob/ot.json"

async def handle_key_transfer(reader, writer, request):
    Charlie_host = "localhost"
    Charlie_port = "7100"
    reader, writer = await asyncio.open_connection(Charlie_host, Charlie_port)
    logging.info(f"[C] Connected to {Charlie_host}:{Charlie_port}")

    await assend(writer, {"type": "KEY_TRANSFER", "num_qubits": request["num_qubits"]})
    

    writer.close()
    await writer.wait_closed()



async def dispatcher(reader, writer):
    request = await asrecv(reader)

    if request["type"] == "QKD":
        QKD_Bob = QKDHandlerBob(reader, writer, path_config, request["num_qubits"])
        await QKD_Bob.run_protocol()


        #so Alice and Charlie QKD shld happen first, then Alice and Bob QKD will trigger the key exchange
        #handle_key_transfer(reader, writer, request) 
        


    #elif request["type"] == "KEY_TRANSFER":
    #    await handle_key_transfer(reader, writer, request)

    #elif request["type"] == "SIGN":
    #    await handle_signature(reader, writer, request)

    #elif request["type"] == "VERIFY":
    #    await handle_verification(reader, writer, request)



async def main():

    # TODO: edit
    host = "localhost"
    port = "1700"

    server = await asyncio.start_server(
        dispatcher,
        host, port
    )

    async with server: 
        await all_connections_done.wait()
        server.close()
        await server.wait_closed()

if __name__ == "__main__":

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = f"sim_bob_{timestamp}.log"
    # Configure logging
    logging.basicConfig(
        filename=log_filename,
        format="%(asctime)s - %(levelname)s - %(message)s",
        #level=logging.INFO, 
        level=logging.DEBUG, 
        force=True
    )
    asyncio.run(main())
import asyncio
from async_communication import asrecv, assend
from qkd import QKDHandlerBob
import random
from datetime import datetime
import logging

all_connections_done = asyncio.Event()

path_config = "config_test/sim/bob/ot.json"

class QDSHandlerCharlie:
    def __init__(self):
        self.n = None
        self.bH = None
        self.key = None
        self.Bob_half = []
        self.Bob_indices = []

    
    def sign_message(self):
        return
    def verify(self):
        return

    async def dispatcher(self, reader, writer):
        request = await asrecv(reader)

        if request["type"] == "QKD":
            QKD_Charlie = QKDHandlerBob(reader, writer, path_config=path_config, mode="hwsim", num_qubits=request["num_qubits"])
            self.key = await QKD_Charlie.run_protocol()
            print("Charlie_key", self.key)

            writer.close()
            await writer.wait_closed()

        elif request["type"] == "KEY_TRANSFER":
            # await handle_key_transfer(reader, writer, request)

            Bob_half = request["Bob_half"]
            Bob_indices = request["Bob_indices"]
            
            n = request["n"]
            bH = request["bH"]

            indices = list(range(n))
            random.shuffle(indices)
            print(indices)
            print(bH)
            Charlie_half = [self.key[i * (3 * bH): (i+1) * (3 * bH)] for i in indices[:n//2]]
            print("test", Charlie_half)
            await assend(writer, {"Charlie_indices": indices[:n//2], "Charlie_half": Charlie_half})

            writer.close()
            await writer.wait_closed()
            print("Charlie_Bob", Bob_half)
            


        elif request["type"] == "SIGN":
            await handle_signature(reader, writer, request)

        elif request["type"] == "VERIFY":
            await handle_verification(reader, writer, request)

 

async def main():

    # TODO: edit
    host = "localhost"
    port = "7100"
    charlie = QDSHandlerCharlie()

    server = await asyncio.start_server(
        charlie.dispatcher,
        host, port
    )

    async with server: 
        await all_connections_done.wait()
        server.close()
        await server.wait_closed()

if __name__ == "__main__":
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = f"sim_charlie_{timestamp}.log"
    # Configure logging
    logging.basicConfig(
        filename=log_filename,
        format="%(asctime)s - %(levelname)s - %(message)s",
        #level=logging.INFO, 
        level=logging.DEBUG, 
        force=True
    )
    asyncio.run(main())
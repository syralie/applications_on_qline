import asyncio
from async_communication import asrecv, assend
from qkd import QKDHandlerBob
import logging
from datetime import datetime
import random


all_connections_done = asyncio.Event()

path_config = "config_test/sim/bob/ot.json"


class QDSHandlerBob():
    def __init__(self):
        self.n = 10
        self.bH = 10
        self.key = ''
        self.Charlie_half = []
        self.Charlie_indices = []

    async def handle_QKD(self, reader, writer, request):
        QKD_Bob = QKDHandlerBob(reader, writer, path_config, mode=request["mode"], num_qubits=request["num_qubits"])
        self.key = await QKD_Bob.run_protocol()
        print("Bob_key", self.key)


        #so Alice and Charlie QKD shld happen first, then Alice and Bob QKD will trigger the key exchange
        await self.handle_key_transfer(request) 

        writer.close()
        await writer.wait_closed()
    
    async def handle_key_transfer(self, request):
        Charlie_host = "localhost"
        Charlie_port = "7100"
        reader, writer = await asyncio.open_connection(Charlie_host, Charlie_port)
        logging.info(f"[C] Connected to {Charlie_host}:{Charlie_port}")

        indices = list(range(self.n))
        random.shuffle(indices)
        Bob_half = [self.key[i * (3 * self.bH): (i+1) * (3 * self.bH)] for i in indices[:self.n//2]]


        await assend(writer, {"type": "KEY_TRANSFER", "num_qubits": request["num_qubits"], "n": self.n, "bH": self.bH, "Bob_indices": indices[:self.n//2], "Bob_half": Bob_half})
        response = await asrecv(reader)

        self.Charlie_half = response["Charlie_half"]
        self.Charlie_indices = response["Charlie_indices"]
        
        writer.close()
        await writer.wait_closed()

        print("Bob_Charlie", self.Charlie_half)



    async def dispatcher(self, reader, writer):
        request = await asrecv(reader)

        if request["type"] == "QKD":
            await self.handle_QKD(reader, writer, request)

        

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

    bob = QDSHandlerBob()

    server = await asyncio.start_server(
        bob.dispatcher,
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
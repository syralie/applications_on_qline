import asyncio
from async_communication import asrecv, assend
from qkd import QKDHandlerBob

all_connections_done = asyncio.Event()

path_config = "config_test/sim/bob/ot.json"


async def dispatcher(reader, writer):
    request = await asrecv(reader)

    if request["type"] == "QKD":
        QKD_Charlie = QKDHandlerBob(reader, writer, path_config, request["num_qubits="])
        key = await QKD_Charlie.run_protocol()

    elif request["type"] == "KEY_TRANSFER":
        await handle_key_transfer(reader, writer, request)

    elif request["type"] == "SIGN":
        await handle_signature(reader, writer, request)

    elif request["type"] == "VERIFY":
        await handle_verification(reader, writer, request)



async def main():

    # TODO: edit
    host = "localhost"
    port = "7100"

    server = await asyncio.start_server(
        dispatcher,
        host, port
    )

    async with server: 
        await all_connections_done.wait()
        server.close()
        await server.wait_closed()

if __name__ == "__main__":
    main()
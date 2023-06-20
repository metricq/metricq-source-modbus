import asyncio
import struct

from async_modbus import AsyncTCPClient


async def main():
    reader, writer = await asyncio.open_connection("localhost", 5022)
    client = AsyncTCPClient((reader, writer))
    result = await client.read_input_registers(1, 808, 4)
    assert len(result) == 4
    print(result)
    print(type(result))
    result = struct.pack(">4H", *result)
    print(result)
    print(type(result), len(result))
    result = struct.unpack_from(">f", buffer=result, offset=4)
    print(result)
    print(type(result), len(result))
    writer.close()
    await writer.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())

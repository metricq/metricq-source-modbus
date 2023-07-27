import asyncio
import struct
from string import Template
from typing import Optional

from async_modbus import AsyncClient, AsyncTCPClient  # type: ignore
from metricq.logging import get_logger

from metricq_source_modbus.config_model import StringConfig

logger = get_logger()


async def _read_string(client: AsyncClient, slave_id: int, config: StringConfig) -> str:
    assert config.size % 2 == 0
    num_registers = config.size // 2
    raw_values = await client.read_input_registers(1, 25500, num_registers)
    assert len(raw_values) == num_registers
    buffer = struct.pack(f">{len(raw_values)}H", *raw_values)
    if (first_null := buffer.find(b"\x00")) != -1:
        buffer = buffer[:first_null]
    return buffer.decode("ASCII", errors="ignore")


class StringReplacer:
    def __init__(self, mapping: dict[str, str]):
        self._mapping = {key: self.sanitize(value) for key, value in mapping.items()}

    @classmethod
    def sanitize(self, value: str) -> str:
        """Replace Bacnet special characters with our beautiful MetricQ dots"""
        return value.replace("'", ".").replace("`", ".").replace("´", ".").strip()

    def __call__(self, description: str) -> str:
        if not self._mapping:
            return description
        return Template(description).safe_substitute(self._mapping)


async def read_strings(
    host: str, port: int, slave_id: int, strings: Optional[dict[str, StringConfig]]
) -> StringReplacer:
    if not strings:
        return StringReplacer({})
    logger.info("Reading device strings from {}:{}", host, port)
    reader, writer = await asyncio.open_connection(host, port)
    client = AsyncTCPClient((reader, writer))
    values = {
        key: await _read_string(client, slave_id, config)
        for key, config in strings.items()
    }
    writer.close()
    await writer.wait_closed()
    logger.info("Device strings for {}:{}: {}", host, port, values)
    return StringReplacer(values)

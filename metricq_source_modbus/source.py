# Copyright (c) 2023, ZIH, Technische Universitaet Dresden, Federal Republic of Germany
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright notice,
#       this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright notice,
#       this list of conditions and the following disclaimer in the documentation
#       and/or other materials provided with the distribution.
#     * Neither the name of metricq nor the names of its contributors
#       may be used to endorse or promote products derived from this software
#       without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import asyncio
import struct
from contextlib import suppress
from typing import Any, Iterable, Optional, Sequence, cast

from async_modbus import AsyncClient, AsyncTCPClient  # type: ignore
from hostlist import expand_hostlist  # type: ignore
from metricq import JsonDict, MetadataDict, Source, Timedelta, Timestamp, rpc_handler
from metricq.logging import get_logger

from . import config_model
from .version import __version__  # noqa: F401 # magic import for automatic version

logger = get_logger()


REGISTERS_PER_VALUE = 2
"""Number of 16 bit modbus registers per value (float per definition for now)"""

BYTES_PER_REGISTER = 2
"""Number of bytes per 16 bit modbus register"""

CONNECTION_FAILURE_RETRY_INTERVAL = 10
"""Interval in seconds to retry connecting to a host after a connection failure"""


def combine_name(prefix: str, name: str) -> str:
    prefix = prefix.rstrip(".")
    name = name.lstrip(".")
    assert name != ""

    if prefix == "":
        return name
    return f"{prefix}.{name}"


def extract_interval(
    config: config_model.Source | config_model.Group,
) -> Optional[Timedelta]:
    """
    To allow interval, rate or maybe period, and other types in the future,
    we have a separate function here.
    """
    # We could to that as a validator in the pydantic model, but that would mess up
    # the type safety as mypy still things the field can be any of the types.
    # Also, we cannot easily extend it to look at "rate" or "period" or whatever.
    if config.interval is None:
        return None
    if isinstance(config.interval, (int, float)):
        return Timedelta.from_s(config.interval)
    assert isinstance(config.interval, str)
    return Timedelta.from_string(config.interval)


class ConfigError(Exception):
    pass


class Metric:
    def __init__(
        self,
        name: str,
        *,
        group: "MetricGroup",
        config: config_model.Metric,
    ):
        self.group = group
        host = group.host

        self.description = config.description
        if host.description:
            self.description = f"{host.description} {self.description}"

        chunk_size = config.chunk_size
        if chunk_size is None and group.interval < Timedelta.from_s(1):
            # Default chunking to one update per second
            chunk_size = Timedelta.from_s(1) // group.interval

        self._source_metric = host.source[name]
        if chunk_size is not None:
            self._source_metric.chunk_size = chunk_size

        self.address = config.address
        self.unit = config.unit

    @property
    def num_registers(self) -> int:
        """For now we assume float values, so two registers per value"""
        return REGISTERS_PER_VALUE

    @property
    def name(self) -> str:
        return self._source_metric.id

    @property
    def metadata(self) -> JsonDict:
        metadata = {
            "description": self.description,
            "rate": 1 / self.group.interval.s,
            "interval": self.group.interval.precise_string,
        }
        if self.unit:
            metadata["unit"] = self.unit
        return metadata

    async def update(self, timestamp: Timestamp, buffer: bytes) -> None:
        offset = (self.address - self.group.base_address) * BYTES_PER_REGISTER
        assert offset >= 0, "offset non-negative"
        (value,) = struct.unpack_from(">f", buffer=buffer, offset=offset)
        await self._source_metric.send(timestamp, value)


class MetricGroup:
    """
    Represents a set of metrics
    - same host (implicitly)
    - same interval (implicitly)
    - common address space (based on addresses within the metrics)
    """

    _previous_buffer: Optional[bytes] = None

    def _create_metrics(
        self, metrics: dict[str, config_model.Metric]
    ) -> Iterable[Metric]:
        for metric_name, metric_config in metrics.items():
            yield Metric(
                combine_name(self.host.metric_prefix, metric_name),
                group=self,
                config=metric_config,
            )

    def __init__(self, host: "Host", config: config_model.Group) -> None:
        self.host = host

        self._double_sample = config.double_sample

        interval = extract_interval(config)
        if interval is None:
            interval = host.source.default_interval
            if interval is None:
                raise ConfigError("missing interval")
        self.interval: Timedelta = interval

        # Must be exactly because we use `self.interval` here, use `self._metrics` later
        self._metrics = list(self._create_metrics(config.metrics))

        self.base_address: int = min((metric.address for metric in self._metrics))
        end_address = max(
            (metric.address + metric.num_registers for metric in self._metrics)
        )
        self._num_registers = end_address - self.base_address

    @property
    def metadata(self) -> dict[str, MetadataDict]:
        return {metric.name: metric.metadata for metric in self._metrics}

    @property
    def _sampling_interval(self) -> Timedelta:
        if self._double_sample:
            return self.interval * 2
        return self.interval

    async def task(
        self,
        stop_future: asyncio.Future[None],
        client: AsyncClient,
    ) -> None:
        # Similar code as to metricq.IntervalSource.task, but for individual MetricGroups
        deadline = Timestamp.now()
        deadline -= (
            deadline % self._sampling_interval
        )  # Align deadlines to the interval
        while True:
            await self._update(client)

            now = Timestamp.now()
            deadline += self._sampling_interval

            if (missed := (now - deadline)) > Timedelta(0):
                missed_intervals = 1 + (missed // self._sampling_interval)
                logger.warning(
                    "Missed deadline {} by {} it is now {} (x{})",
                    deadline,
                    missed,
                    now,
                    missed_intervals,
                )
                deadline += self._sampling_interval * missed_intervals

            timeout = deadline - now
            done, pending = await asyncio.wait(
                (asyncio.create_task(asyncio.sleep(timeout.s)), stop_future),
                return_when=asyncio.FIRST_COMPLETED,
            )
            if stop_future in done:
                for task in pending:  # cancel pending sleep task
                    task.cancel()
                stop_future.result()  # potentially raise exceptions
                return

    async def _update(
        self,
        client: AsyncClient,
    ) -> None:
        timestamp = Timestamp.now()
        raw_values = await client.read_input_registers(
            self.host.slave_id, self.base_address, self._num_registers
        )
        assert len(raw_values) == self._num_registers
        buffer = struct.pack(f">{len(raw_values)}H", *raw_values)

        duration = Timestamp.now() - timestamp
        logger.debug(f"Request finished successfully in {duration}")

        # TODO insert small sleep and see if that helps align stuff

        if self._double_sample:
            if self._previous_buffer is not None and self._previous_buffer == buffer:
                logger.debug("Skipping double sample")
                self._previous_buffer = None  # Skip only one buffer
                return
            self._previous_buffer = buffer

        await asyncio.gather(
            *(metric.update(timestamp, buffer) for metric in self._metrics)
        )


class Host:
    def __init__(
        self,
        source: "ModbusSource",
        *,
        host: str,
        name: str,
        config: config_model.Host,
    ):
        self.source = source
        self._host = host
        self._port = config.port
        self.metric_prefix = name
        self.slave_id = config.slave_id
        self.description = config.description

        self._groups = [
            MetricGroup(self, group_config) for group_config in config.groups
        ]

    @staticmethod
    def _parse_hosts(hosts: str | list[str]) -> list[str]:
        if isinstance(hosts, str):
            return cast(list[str], expand_hostlist(hosts))
        assert isinstance(hosts, list)
        assert all(isinstance(host, str) for host in hosts)
        return hosts

    @classmethod
    def _create_from_host_config(
        cls,
        source: "ModbusSource",
        host_config: config_model.Host,
    ) -> Iterable["Host"]:
        hosts = cls._parse_hosts(host_config.hosts)
        names = cls._parse_hosts(host_config.names)
        if len(hosts) != len(names):
            raise ConfigError("Number of names and hosts differ")
        for host, name in zip(hosts, names):
            yield Host(source=source, host=host, name=name, config=host_config)

    @classmethod
    def create_from_host_configs(
        cls, source: "ModbusSource", host_configs: Sequence[config_model.Host]
    ) -> Iterable["Host"]:
        for host_config in host_configs:
            yield from cls._create_from_host_config(source, host_config)

    @property
    def metadata(self) -> dict[str, MetadataDict]:
        return {
            metric: metadata
            for group in self._groups
            for metric, metadata in group.metadata.items()
        }

    async def _connect_and_run(self, stop_future: asyncio.Future[None]) -> None:
        logger.info("Opening connection to {}:{}", self._host, self._port)
        reader, writer = await asyncio.open_connection(self._host, self._port)
        try:
            client = AsyncTCPClient((reader, writer))
            await asyncio.gather(
                *[group.task(stop_future, client) for group in self._groups]
            )
        finally:
            with suppress(Exception):
                writer.close()
                await writer.wait_closed()

    async def task(self, stop_future: asyncio.Future[None]) -> None:
        retry = True
        while retry:
            try:
                await self._connect_and_run(stop_future)
                retry = False
            except Exception as e:
                logger.error("Error in Host {} task: {} ({})", self._host, e, type(e))
                await asyncio.sleep(CONNECTION_FAILURE_RETRY_INTERVAL)


class ModbusSource(Source):
    default_interval: Optional[Timedelta] = None
    hosts: Optional[list[Host]] = None
    _host_task_stop_future: Optional[asyncio.Future[None]] = None
    _host_task: Optional[asyncio.Task[None]] = None

    @rpc_handler("config")
    async def _on_config(
        self,
        **kwargs: Any,
    ) -> None:
        config = config_model.Source(**kwargs)
        self.default_interval = extract_interval(config)

        if self.hosts is not None:
            await self._stop_host_tasks()

        self.hosts = list(Host.create_from_host_configs(self, config.hosts))

        await self.declare_metrics(
            {
                metric: metadata
                for host in self.hosts
                for metric, metadata in host.metadata.items()
            }
        )

        self._create_host_tasks()

    async def _stop_host_tasks(self) -> None:
        assert self._host_task_stop_future is not None
        assert self._host_task is not None
        self._host_task_stop_future.set_result(None)
        try:
            await asyncio.wait_for(self._host_task, timeout=30)
        except asyncio.TimeoutError:
            # wait_for also cancels the task
            logger.error("Host tasks did not stop in time")
        self.hosts = None
        self._host_task_stop_future = None
        self._host_task = None

    def _create_host_tasks(self) -> None:
        assert self.hosts is not None
        assert self._host_task_stop_future is None
        assert self._host_task is None
        self._host_task_stop_future = asyncio.Future()
        self._host_task = asyncio.create_task(self._run_host_tasks())

    async def _run_host_tasks(self) -> None:
        assert self._host_task_stop_future is not None
        assert self.hosts is not None
        await asyncio.gather(
            *(host.task(self._host_task_stop_future) for host in self.hosts)
        )

    async def task(self) -> None:
        """
        Just wait for the global task_stop_future and propagate it to the host tasks.
        """
        assert self.task_stop_future is not None
        await self.task_stop_future
        await self._stop_host_tasks()

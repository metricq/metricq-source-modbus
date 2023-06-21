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

import random
from typing import Any

import metricq
from metricq.logging import get_logger

from .version import version as client_version

logger = get_logger()


class ModbusSource(metricq.IntervalSource):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        logger.info("initializing ModbusSource")
        super().__init__(*args, client_version=client_version, **kwargs)

    @metricq.rpc_handler("config")
    async def _on_config(self, rate: float, **config: Any) -> None:
        logger.info("ModbusSource received config: {}", config)

        self.period = 1 / rate  # type: ignore #  https://github.com/python/mypy/issues/3004

        metadata = {
            "rate": rate,
            "description": "A simple example metric providing random values, sent from a python ExampleSource",
            "unit": "",  # unit-less metrics indicate this with an empty string
        }
        await self.declare_metrics({"python.example.quantity": metadata})

    async def update(self) -> None:
        # Send a random value at the current time:
        await self.send(
            "python.example.quantity",
            time=metricq.Timestamp.now(),
            value=random.random(),
        )

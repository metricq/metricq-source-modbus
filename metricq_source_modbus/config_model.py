from typing import Optional

from pydantic import BaseModel
from pydantic.config import Extra
from pydantic.fields import Field
from pydantic.functional_validators import field_validator
from pydantic.types import NonNegativeInt, PositiveFloat, PositiveInt

_model_config = {"extra": "forbid", "frozen": True}
"""
Extra parameters are forbidden and will raise validation errors.
The parameters will not be mutable.
"""


class Metric(BaseModel, **_model_config):
    address: NonNegativeInt
    """Register address of the value"""
    description: str = ""
    """Description for metadata, will be merged with host description if available"""
    unit: Optional[str] = None
    """Unit for metadata"""
    chunk_size: Optional[int] = None
    """
    Chunk size. By default no chunking is configured except for intervals below 1s.
    For those, chunking will set to one chunk per second (1s/interval)
    """


class Group(BaseModel, **_model_config):
    """
    A group of metrics that will be queried together.
    The given metrics should be closely together in the register address space.
    """

    interval: PositiveFloat | PositiveInt | str | None = None
    """
    Query interval in seconds for the group.
    A string can also be used that will be parsed by MetricQ exactly, e.g. ``100ms``.
    If omitted, the global interval will be used.
    """
    metrics: dict[str, Metric]
    """Dictionary of metrics, keys are the metric names prefixed by the host name"""

    @field_validator("metrics")
    def metrics_not_empty(cls, v: dict[str, Metric]) -> dict[str, Metric]:
        if len(v) == 0:
            raise ValueError("Group must have at least one metric")
        return v

    double_sample: bool = False
    """
    If set to true, the metric will be sampled twice per configured interval.
    If both values are the same, only one value will be published.
    Use this if you know the internal update rate of the device,
    but you want to make sure to not miss a value.
    """


class StringConfig(BaseModel, **_model_config):
    address: NonNegativeInt
    """Register address of the value"""
    size: PositiveInt
    """Length of the string in bytes (i.e. delta to the next address)"""

    @field_validator("size")
    def size_multiple_two(cls, v: int) -> int:
        if v % 2 != 0:
            raise ValueError("Size (in bytes) must be a multiple of two.")
        return v


class Host(BaseModel, **_model_config):
    hosts: str | list[str]
    """
    Hostlist of hosts to query an expandable string, e.g., ``foo[4-6,8].example.com``
    or a list.
    """
    port: PositiveInt = 502
    """Port to connect to"""
    names: str | list[str]
    """
    Names of the hosts that will be queried, used as prefix, e.g., ``room.E[4-6,8]``.
    Expandable string or a list. The length must match the length of ``hosts``.
    """
    slave_id: int
    """Slave ID to query"""
    description: str = ""
    """
    Description prefix for metadata of all included metrics.
    Can use placeholders from ``strings`` using ``$foo`` notation.
    """
    descriptions: Optional[str | list[str]] = None
    """
    An optional list of descriptions for each host, must match the expanded list of
    ``hosts`` and ``names``. Is used in addition to ``description``.
    """
    strings: Optional[dict[str, StringConfig]] = None
    """
    A set of strings to get from the device at initialization and use in the ``description``.
    """
    groups: list[Group] = Field(..., min_length=1)
    """ List of query groups. """


# We cannot forbid because of magic couchdb fields in the config e.g. `_id`
class Source(BaseModel, extra=Extra.ignore, frozen=True):
    interval: PositiveFloat | PositiveInt | str | None = None
    """
    Default query interval in seconds.
    A string can also be used that will be parsed by MetricQ exactly, e.g. ``100ms``.
    If omitted, the global interval will be used.
    """
    hosts: list[Host] = Field(..., min_length=1)

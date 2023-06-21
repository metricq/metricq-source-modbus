from typing import Optional

from pydantic import BaseModel
from pydantic.class_validators import validator
from pydantic.config import Extra
from pydantic.fields import Field
from pydantic.types import NonNegativeInt, PositiveFloat, PositiveInt

_model_config = {"extra": Extra.forbid, "frozen": True}
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

    @validator("metrics")
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


class Host(BaseModel, **_model_config):
    hosts: str
    """Hostlist of hosts to query, e.g. ``foo[4-6,8].example.com``"""
    port: PositiveInt = 502
    """Port to connect to"""
    names: str
    """
    Names of the hosts that will be queried, used as prefix, e.g., ``room.E[4-6,8]``.
    When expanded, the length must match the length of the ``hosts``.
    """
    slave_id: int
    """Slave ID to query"""
    description: str = ""
    """Description prefix for metadata"""
    groups: list[Group] = Field(..., min_items=1)
    """ List of query groups. """


# We cannot forbid because of magic couchdb fields in the config e.g. `_id`
class Source(BaseModel, extra=Extra.ignore, frozen=True):
    interval: PositiveFloat | PositiveInt | str | None = None
    """
    Default query interval in seconds.
    A string can also be used that will be parsed by MetricQ exactly, e.g. ``100ms``.
    If omitted, the global interval will be used.
    """
    hosts: list[Host] = Field(..., min_items=1)

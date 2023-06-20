import pytest
from pydantic import ValidationError

from metricq_source_modbus import config_model


def test_simple() -> None:
    source = config_model.Source(
        **{
            "interval": "100ms",
            "hosts": [
                {
                    "hosts": "test[1-3]",
                    "port": 502,
                    "names": "example.test[1-3]",
                    "slave_id": 1,
                    "description": "Test",
                    "groups": [
                        {
                            "metrics": {
                                "foo": {
                                    "address": 42,
                                    "description": "Some foo example",
                                    "unit": "W",
                                }
                            }
                        }
                    ],
                },
            ],
        }  # type: ignore # mypy does not like this, but this is about parsing
    )
    assert source.hosts[0].groups[0].metrics["foo"].address == 42


def test_minimal() -> None:
    """Not actually semantically valid because of missing interval"""
    config_model.Source(
        **{
            "_ref": "abcd",
            "_rev": "efgh",
            "hosts": [
                {
                    "hosts": "test[1-3]",
                    "names": "example.test[1-3]",
                    "slave_id": 1,
                    "groups": [
                        {
                            "metrics": {
                                "foo": {
                                    "address": 0,
                                }
                            }
                        }
                    ],
                },
            ],
        }  # type: ignore # mypy does not like this, but this is about parsing
    )


def test_long() -> None:
    config_model.Source(
        **{
            "interval": "100ms",
            "hosts": [
                {
                    "hosts": "test[1-3]",
                    "port": 502,
                    "names": "example.test[1-3]",
                    "slave_id": 1,
                    "description": "Test",
                    "groups": [
                        {
                            "metrics": {
                                "foo.power": {
                                    "address": 0,
                                    "description": "Some foo example",
                                    "unit": "W",
                                }
                            }
                        },
                        {
                            "metrics": {
                                "bar.power": {
                                    "address": 19000,
                                    "description": "Some bar example",
                                    "unit": "W",
                                }
                            }
                        },
                    ],
                },
                {
                    "hosts": "toast[1-5]",
                    "port": 505,
                    "names": "example.toast[1-5]",
                    "slave_id": 17,
                    "description": "Nice and crispy",
                    "groups": [
                        {
                            "interval": "200ms",
                            "metrics": {
                                "foo.power": {
                                    "address": 1900,
                                    "description": "Some foo example",
                                    "unit": "W",
                                },
                                "bar.power": {
                                    "address": 1902,
                                    "description": "Some bar example",
                                    "unit": "W",
                                },
                            },
                        }
                    ],
                },
            ],
        }  # type: ignore # mypy does not like this, but this is about parsing
    )


def test_extra() -> None:
    with pytest.raises(ValidationError):
        config_model.Source(
            **{
                "hosts": [
                    {
                        "hosts": "test[1-3]",
                        "names": "example.test[1-3]",
                        "slave_id": 1,
                        "groups": [
                            {
                                "metrics": {
                                    "foo": {
                                        "address": 0,
                                        "descryption": "Find the tpyo",
                                    }
                                }
                            }
                        ],
                    },
                ],
            }  # type: ignore # mypy does not like this, but this is about parsing
        )


def test_missing_address() -> None:
    with pytest.raises(ValidationError):
        config_model.Source(
            **{
                "interval": "100ms",
                "hosts": [
                    {
                        "hosts": "test[1-3]",
                        "names": "example.test[1-3]",
                        "slave_id": 1,
                        "groups": [{"metrics": {"foo": {}}}],
                    },
                ],
            }  # type: ignore # mypy does not like this, but this is about parsing
        )


def test_wrong_address_type() -> None:
    """Pydantic will convert wrong types if possible"""
    config = config_model.Source(
        **{
            "interval": "100ms",
            "hosts": [
                {
                    "hosts": "test[1-3]",
                    "names": "example.test[1-3]",
                    "slave_id": 1,
                    "groups": [{"metrics": {"foo": {"address": "0"}}}],
                },
            ],
        }  # type: ignore # mypy does not like this, but this is about parsing
    )
    assert config.hosts[0].groups[0].metrics["foo"].address == 0
    assert isinstance(config.hosts[0].groups[0].metrics["foo"].address, int)


def test_invalid_address() -> None:
    with pytest.raises(ValidationError):
        config_model.Source(
            **{
                "interval": "100ms",
                "hosts": [
                    {
                        "hosts": "test[1-3]",
                        "names": "example.test[1-3]",
                        "slave_id": 1,
                        "groups": [{"metrics": {"foo": {"address": ""}}}],
                    },
                ],
            }  # type: ignore # mypy does not like this, but this is about parsing
        )


def test_empty_metrics() -> None:
    with pytest.raises(ValidationError):
        config_model.Source(
            **{
                "interval": "100ms",
                "hosts": [
                    {
                        "hosts": "test[1-3]",
                        "names": "example.test[1-3]",
                        "slave_id": 1,
                        "groups": [{"metrics": {}}],
                    },
                ],
            }  # type: ignore # mypy does not like this, but this is about parsing
        )


def test_empty_groups() -> None:
    with pytest.raises(ValidationError):
        config_model.Source(
            **{
                "interval": "100ms",
                "hosts": [
                    {
                        "hosts": "test[1-3]",
                        "names": "example.test[1-3]",
                        "slave_id": 1,
                        "groups": [],
                    },
                ],
            }  # type: ignore # mypy does not like this, but this is about parsing
        )


def test_empty_hosts() -> None:
    with pytest.raises(ValidationError):
        config_model.Source(
            **{
                "interval": "100ms",
                "hosts": [],
            }  # type: ignore # mypy does not like this, but this is about parsing
        )

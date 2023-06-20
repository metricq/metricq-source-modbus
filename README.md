![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)

# MetricQ example source

This is a simple example source for a [MetricQ Source](https://metricq.github.io/metricq-python/howto/source.html).
It is meant to be used as a starting point for your own MetricQ source.

When using this as a template, the first thing you should do, is to rename everything from `example` to your desired name.
This includes all file contents and filenames.

Notes about the CI as is:
- run all formatters and linters using tox as part of building the docker images
  * black
  * isort
  * mypy
  * flake8
- build docker images for all branches
- build docker images for version tags `vX.Y.Z`
- push docker images to ghcr.io/metricq
- **No** sphinx / documentation
- **No** upload to pypi

![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)

# MetricQ modbus source

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

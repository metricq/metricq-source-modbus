FROM python:3.13-slim-trixie AS builder

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

COPY . /src
WORKDIR /src

# This is the simplest solution to make sure we only build good packages
# If you don't like this, go ahead and build better github actions / workflows
RUN /usr/local/bin/pip install --no-cache-dir --root-user-action=ignore tox \
    && /usr/local/bin/tox

RUN pip install --no-cache-dir '.'


FROM python:3.13-slim-trixie

RUN useradd -m metricq

COPY --from=builder /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

USER metricq
WORKDIR /home/metricq

ENTRYPOINT [ "metricq-source-modbus" ]

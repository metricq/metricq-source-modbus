FROM ghcr.io/metricq/metricq-python:v5.3 AS BUILDER

USER root
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/* 

COPY --chown=metricq:metricq . /home/metricq/metricq-source-modbus

USER metricq
WORKDIR /home/metricq/metricq-source-modbus

# This is the simplest solution to make sure we only build good packages
# If you don't like this, go ahead and build better github actions / workflows
RUN pip install --user tox
RUN /home/metricq/.local/bin/tox

RUN pip install --user .


FROM ghcr.io/metricq/metricq-python:v5.3

COPY --from=BUILDER --chown=metricq:metricq /home/metricq/.local /home/metricq/.local

ENTRYPOINT [ "/home/metricq/.local/bin/metricq-source-modbus" ]

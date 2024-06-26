FROM python:3.8.14-slim-bullseye

RUN apt-get update && apt-get install -y --no-install-recommends build-essential gcc

ENV SERVICE_NAME odl
ENV ROOT /opt/$SERVICE_NAME

RUN mkdir -p /var/lib/$SERVICE_NAME/data/avro

WORKDIR $ROOT

# First copy dependencies so that we can cache them separate from source code.
# By doing so, we won't have to rebuild layers with dependencies when source code changes occur.

COPY requirements.txt $ROOT/
RUN pip install -r requirements.txt

# Now add the entire source code tree
COPY . $ROOT

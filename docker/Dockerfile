FROM apache/airflow:3.3.1-python3.12

USER root

RUN apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends \
        openjdk-17-jre-headless \
        unixodbc-dev \
        libgssapi-krb5-2 \
        msodbcsql18 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV NYC_PROJECT_ROOT=/opt/airflow/project
ENV NYC_ETL_PYTHON=/opt/airflow/etl-venv/bin/python

USER airflow

COPY docker/requirements-docker.txt /tmp/requirements-docker.txt

RUN pip install --no-cache-dir \
        "apache-airflow==3.3.1" \
        "apache-airflow-providers-standard==1.17.0" \
        "pendulum==3.2.0" \
    && python -m venv /opt/airflow/etl-venv \
    && /opt/airflow/etl-venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/airflow/etl-venv/bin/pip install --no-cache-dir \
        -r /tmp/requirements-docker.txt

WORKDIR /opt/airflow/project

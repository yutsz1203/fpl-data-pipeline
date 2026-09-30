FROM apache/airflow:3.3.2-python3.12

WORKDIR /opt/fpl

COPY --chown=airflow:0 pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-cache

COPY --chown=airflow:0 dbt/pyproject.toml dbt/uv.lock dbt/.python-version dbt/
RUN cd dbt && uv sync --locked --no-cache

COPY --chown=airflow:0 dbt/ dbt/
RUN cd dbt && .venv/bin/dbt deps && rm -r logs && chmod g+w .

COPY --chown=airflow:0 scripts/ scripts/

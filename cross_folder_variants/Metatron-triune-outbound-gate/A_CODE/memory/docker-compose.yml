FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src /app/src
COPY config /app/config

ENV CAS_SHIELD_CONFIG=/app/config/cas_shield_config.json
EXPOSE 8080

CMD ["python", "/app/src/cas_shield_sidecar.py"]

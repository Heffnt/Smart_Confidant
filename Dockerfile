FROM python:3.10-slim

WORKDIR /opt/app
COPY . .
RUN pip install --no-cache-dir uv && \
    uv pip install --system -r /opt/app/requirements.txt

# Install prometheus-node-exporter for system-level metrics
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get upgrade -yq ca-certificates && \
    apt-get install -yq --no-install-recommends \
    prometheus-node-exporter

# Expose ports:
# 8012 - Gradio web interface
# 8000 - Application Prometheus metrics
# 9100 - Node exporter system metrics
EXPOSE 8012
EXPOSE 8000
EXPOSE 9100

ENV GRADIO_SERVER_NAME="0.0.0.0"

# Run node-exporter in background, then start the Python application
CMD bash -c "prometheus-node-exporter --web.listen-address=':9100' & python /opt/app/app.py"

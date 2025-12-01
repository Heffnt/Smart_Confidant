FROM python:3.10-slim

WORKDIR /opt/app
COPY . .
RUN pip install --no-cache-dir uv && \
    uv pip install --system -r /opt/app/requirements.txt

# Expose default port (can be overridden via PORT env var)
EXPOSE 8080

ENV GRADIO_SERVER_NAME="0.0.0.0"

CMD ["python", "app.py"]

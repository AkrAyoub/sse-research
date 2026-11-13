FROM python:3.12-slim
WORKDIR /sse
COPY requirements.txt /sse/requirements.txt
RUN python -m pip install --no-cache-dir -r /sse/requirements.txt && python -m pip check
COPY tools /sse/tools
COPY services /sse/services
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# Runner passes a non-root UID, read-only root FS, no capabilities at execution.

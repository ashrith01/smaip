FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN useradd --create-home --uid 10001 smaip

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir . \
    && chown -R smaip:smaip /app

USER smaip

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

CMD ["python", "-m", "smaip.cli", "serve", "--host", "0.0.0.0", "--port", "8000"]

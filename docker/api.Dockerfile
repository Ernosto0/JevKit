FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first, so source edits do not invalidate the install layer.
COPY pyproject.toml requirements.txt ./
COPY packages/jevkit/__about__.py ./packages/jevkit/__about__.py
COPY README.md LICENSE ./
RUN pip install --no-cache-dir -r requirements.txt

COPY packages ./packages
COPY apps/api ./apps/api
COPY examples ./examples

# Run as a non-root user.
RUN useradd --create-home --uid 10001 jevkit && chown -R jevkit:jevkit /app
USER jevkit

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

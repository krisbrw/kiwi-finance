FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application code
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY migrations/ ./migrations/
COPY alembic.ini .
COPY run.py .

# Non-root user for security
RUN adduser --disabled-password --gecos "" kiwiuser
USER kiwiuser

EXPOSE 8000

ENV PYTHONPATH=/app/app

CMD ["gunicorn", "kiwi_finance.main:app", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--threads", "2", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]

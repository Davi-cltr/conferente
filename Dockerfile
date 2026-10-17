FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd -m app
USER app
EXPOSE 8000
CMD ["uvicorn", "conferente.web.app:app", "--host", "0.0.0.0", "--port", "8000"]

FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir -e .
WORKDIR /work
ENTRYPOINT ["copyspace-guard"]

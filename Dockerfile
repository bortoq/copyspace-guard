FROM python:3.11-slim AS build
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir --upgrade "setuptools>=77" wheel
RUN python -m pip wheel --no-cache-dir --no-build-isolation --wheel-dir /wheels .

FROM python:3.11-slim
RUN useradd --create-home --shell /usr/sbin/nologin appuser
COPY --from=build /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels
WORKDIR /work
USER appuser
ENTRYPOINT ["copyspace-guard"]

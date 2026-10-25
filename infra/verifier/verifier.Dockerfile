# Independent verifier image: pinned Python + pytest and one trusted entrypoint.
#
#   docker build -f infra/verifier/verifier.Dockerfile -t prooflayer-verifier:0.1.0 infra/verifier
#
# (`make verifier-image`.) It holds no fixture code, no credentials and nothing
# from the agent sandbox. Each check runs in a fresh container started by
# apps/api/prooflayer_api/verifier/docker.py with --network none, a read-only
# root filesystem, all capabilities dropped, a non-root user and CPU / memory /
# PID limits; the workspace arrives as a tar on stdin and lives only in tmpfs.
FROM python:3.12.7-slim-bookworm

RUN pip install --no-cache-dir pytest==9.1.1 \
    && useradd --uid 10002 --no-create-home --shell /usr/sbin/nologin verifier

COPY run_check.py /opt/prooflayer/run_check.py

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/verify/repo \
    PYTHONHASHSEED=0

USER 10002
ENTRYPOINT ["python", "/opt/prooflayer/run_check.py"]

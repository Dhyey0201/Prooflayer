"""Independent verifier on a local Docker engine.

Each check runs in a fresh container from the pinned verifier image, started
*by image ID* so the exact image is part of the evidence. The container has no
network, a read-only root filesystem, every Linux capability dropped,
``no-new-privileges``, a non-root UID distinct from the agent sandbox's and
CPU / memory / PID / file-descriptor / file-size limits, no IPC namespace and
no engine-side log copy. The workspace is streamed in as a tar on stdin and
extracted into tmpfs: no host directory is mounted and the Docker socket is
never exposed. Commands are argv lists; nothing is parsed by a shell.

This is container isolation, not OpenShell enforcement, and every check
records that (``isolation="container"``).
"""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import Callable

from ..sandbox.openshell import CommandRunner, subprocess_runner
from .base import Execution, RuntimeIdentity, VerifierStatus, VerifierUnavailableError
from .snapshot import build_archive

VERIFIER_UID = "10002"
CLI_TIMEOUT_SECONDS = 30.0
NOFILE_LIMIT = 256
# Largest single file the verifier may write (the tmpfs mount is 32 MiB).
FSIZE_LIMIT_BYTES = 16 * 1024 * 1024
_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
# Exit codes produced by Docker itself rather than by the command it ran.
DOCKER_ERROR_CODES = frozenset({125, 126, 127})


class DockerVerifierDriver:
    name = "docker"

    def __init__(
        self,
        *,
        bin: str = "docker",
        image: str = "prooflayer-verifier:0.1.0",
        cpus: str = "1",
        memory: str = "512m",
        pids_limit: int = 128,
        expected_image_id: str | None = None,
        runner: CommandRunner = subprocess_runner,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.bin = bin
        self.image = image
        self._cpus = cpus
        self._memory = memory
        self._pids = pids_limit
        self._expected = expected_image_id
        self._run = runner
        self._clock = clock

    def probe(self) -> VerifierStatus:
        version = self._run(
            [self.bin, "version", "--format", "{{.Server.Version}}"], timeout=CLI_TIMEOUT_SECONDS
        )
        if version.returncode is None and not version.timed_out:
            return VerifierStatus(False, reason="cli_not_found")
        if version.returncode != 0:
            return VerifierStatus(False, reason="daemon_unreachable")
        server = version.stdout.decode(errors="replace").strip()[:64] or "unknown"
        inspect = self._run(
            [self.bin, "image", "inspect", "--format", "{{.Id}}", self.image],
            timeout=CLI_TIMEOUT_SECONDS,
        )
        image_id = inspect.stdout.decode(errors="replace").strip()
        if inspect.returncode != 0 or not _IMAGE_ID.fullmatch(image_id):
            return VerifierStatus(False, version=server, reason="verifier_image_missing")
        if self._expected and image_id != self._expected:
            return VerifierStatus(False, image_id, server, "verifier_image_mismatch")
        return VerifierStatus(True, image_id, server)

    def identity(self) -> RuntimeIdentity:
        status = self.probe()
        if not status.available or status.image_id is None:
            raise VerifierUnavailableError(status.reason or "verifier_unavailable")
        return RuntimeIdentity(
            driver="docker",
            isolation="container",
            network="none",
            image=self.image,
            image_id=status.image_id,
        )

    def command(self, name: str, image_id: str, targets: tuple[str, ...]) -> list[str]:
        return [
            self.bin,
            "run",
            "--rm",
            "-i",
            "--name",
            name,
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/verify:rw,nosuid,nodev,size=32m,mode=1777",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,noexec,size=16m",  # noqa: S108 - container tmpfs
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            # No shared IPC namespace, no core dumps, bounded descriptors and
            # file sizes; output is captured from stdio, not kept in engine logs.
            "--ipc",
            "none",
            "--ulimit",
            "core=0",
            "--ulimit",
            f"nofile={NOFILE_LIMIT}:{NOFILE_LIMIT}",
            "--ulimit",
            f"fsize={FSIZE_LIMIT_BYTES}",
            "--log-driver",
            "none",
            "--pids-limit",
            str(self._pids),
            "--memory",
            self._memory,
            "--memory-swap",
            self._memory,
            "--cpus",
            self._cpus,
            "--user",
            f"{VERIFIER_UID}:{VERIFIER_UID}",
            image_id,
            *targets,
        ]

    def run_pytest(
        self, files: dict[str, bytes], targets: tuple[str, ...], timeout_seconds: float
    ) -> Execution:
        image_id = self.identity().image_id
        name = f"prooflayer-verify-{uuid.uuid4().hex[:12]}"
        started = self._clock()
        result = self._run(
            self.command(name, image_id, targets),
            input=build_archive(files),
            timeout=timeout_seconds,
        )
        duration_ms = int((self._clock() - started) * 1000)
        output = result.stdout + result.stderr
        if result.timed_out:
            # The CLI was killed; make sure the container is too.
            self._run([self.bin, "rm", "-f", name], timeout=CLI_TIMEOUT_SECONDS)
            return Execution.from_output(
                None, output, duration_ms, timed_out=True, reason="timeout"
            )
        if result.returncode is None:
            return Execution.from_output(None, output, duration_ms, reason="cli_not_found")
        if result.returncode in DOCKER_ERROR_CODES:
            return Execution.from_output(None, output, duration_ms, reason="container_failed")
        return Execution.from_output(result.returncode, output, duration_ms)

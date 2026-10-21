"""In-process worker that executes queued runs.

``PROOFLAYER_MAX_CONCURRENT_RUNS`` threads poll for the oldest queued run. A
run is claimed by its ``queued -> provisioning`` transition, which the
optimistic lock makes exclusive, so two threads never execute the same run.
Single-process deployment is assumed: on startup, runs a previous process left
mid-flight are marked ``error`` (``worker_restarted``) instead of resumed.
"""

from __future__ import annotations

import logging
import threading

from sqlalchemy.orm import sessionmaker

from ..enums import Actor, RunStatus
from . import runs as run_service
from .orchestrator import RunOrchestrator
from .runtime import Runtime
from .state_machine import InvalidTransitionError

log = logging.getLogger(__name__)


def recover_interrupted_runs(session_factory: sessionmaker) -> int:
    with session_factory() as session:
        run_ids = run_service.interrupted_run_ids(session)
    recovered = 0
    for run_id in run_ids:
        with session_factory() as session:
            try:
                run_service.transition_run(
                    session,
                    run_id,
                    RunStatus.ERROR,
                    reason="worker_restarted",
                    actor=Actor.ORCHESTRATOR,
                    error_code="worker_restarted",
                )
                recovered += 1
            except (InvalidTransitionError, run_service.ConcurrentUpdateError):
                continue
    return recovered


class RunWorker:
    def __init__(self, session_factory: sessionmaker, runtime: Runtime) -> None:
        self._factory = session_factory
        self._orchestrator = RunOrchestrator(session_factory, runtime)
        self._poll = runtime.settings.worker_poll_seconds
        self._concurrency = runtime.settings.max_concurrent_runs
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        recover_interrupted_runs(self._factory)
        for index in range(self._concurrency):
            thread = threading.Thread(
                target=self._loop, name=f"prooflayer-worker-{index}", daemon=True
            )
            thread.start()
            self._threads.append(thread)

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout)

    def run_once(self) -> str | None:
        """Process the oldest queued run, if any. Returns its id."""
        with self._factory() as session:
            run_id = run_service.next_queued_run_id(session)
        if run_id is not None:
            self._orchestrator.process(run_id)
        return run_id

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                processed = self.run_once()
            except Exception:
                log.exception("worker iteration failed")
                processed = None
            if processed is None:
                self._stop.wait(self._poll)

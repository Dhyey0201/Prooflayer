"""Builds the sandbox driver and per-run model client from settings."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from ..ai.client import CallRecord, CircuitBreaker, ModelClient, ModelTransport, RunBudget
from ..ai.nebius import NebiusTransport
from ..ai.scripted import ScriptedTransport
from ..config import SandboxDriverName, Settings
from ..db.models import Run
from ..enums import RunMode, TemplateId
from ..sandbox.base import RuntimeStatus, SandboxDriver
from ..sandbox.mock import MockSandboxDriver
from ..sandbox.openshell import OpenShellDriver

PROBE_TTL_SECONDS = 60.0


def build_sandbox_driver(settings: Settings) -> SandboxDriver:
    if settings.sandbox_driver is SandboxDriverName.OPENSHELL:
        return OpenShellDriver(
            bin=settings.openshell_bin,
            image=settings.sandbox_image,
            cpu=settings.sandbox_cpu,
            memory=settings.sandbox_memory,
        )
    return MockSandboxDriver()


@dataclass
class SandboxStatusCache:
    """Caches ``driver.probe()`` so capability checks don't spawn a CLI per request."""

    driver: SandboxDriver
    clock: Callable[[], float] = time.monotonic
    _status: RuntimeStatus | None = field(default=None, init=False)
    _at: float = field(default=0.0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def get(self) -> RuntimeStatus:
        with self._lock:
            if self._status is None or self.clock() - self._at > PROBE_TTL_SECONDS:
                self._status = self.driver.probe()
                self._at = self.clock()
            return self._status

    @property
    def enforced(self) -> bool:
        """A real enforcing runtime is configured and reachable."""
        return self.driver.name == SandboxDriverName.OPENSHELL.value and self.get().available


def live_runtime_available(settings: Settings, sandbox: SandboxStatusCache) -> bool:
    """Live mode needs a live model AND an enforcing sandbox; never one without the other."""
    return settings.nebius_configured and not settings.mock_mode and sandbox.enforced


TransportFactory = Callable[[Run], ModelTransport]


@dataclass
class Runtime:
    """Everything the orchestrator needs to execute runs."""

    settings: Settings
    driver: SandboxDriver
    transport_factory: TransportFactory
    breaker: CircuitBreaker = field(default_factory=CircuitBreaker)
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic

    def model_client(self, run: Run, observer: Callable[[CallRecord], None]) -> ModelClient:
        return ModelClient(
            transport=self.transport_factory(run),
            budget=RunBudget(
                max_calls=self.settings.max_model_calls_per_run,
                max_tokens=self.settings.max_model_tokens,
            ),
            breaker=self.breaker,
            max_retries=self.settings.model_max_retries,
            observer=observer,
            sleep=self.sleep,
            clock=self.clock,
        )


def default_transport_factory(settings: Settings) -> TransportFactory:
    def factory(run: Run) -> ModelTransport:
        if run.mode == RunMode.LIVE:
            return NebiusTransport(settings)
        return ScriptedTransport(TemplateId(run.task_id))

    return factory


def build_runtime(settings: Settings, driver: SandboxDriver | None = None) -> Runtime:
    return Runtime(
        settings=settings,
        driver=driver or build_sandbox_driver(settings),
        transport_factory=default_transport_factory(settings),
    )

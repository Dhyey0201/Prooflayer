"""Builds the sandbox driver and per-run model client from settings."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from ..ai.client import CallRecord, CircuitBreaker, ModelClient, ModelTransport, RunBudget
from ..ai.nebius import NebiusTransport
from ..ai.scripted import ScriptedChallengeTransport, ScriptedTransport
from ..config import SandboxDriverName, Settings, VerifierDriverName
from ..db.models import Run
from ..enums import RunMode, TemplateId
from ..evidence.ledger import EvidenceLedger
from ..sandbox.base import RuntimeStatus, SandboxDriver
from ..sandbox.mock import MockSandboxDriver
from ..sandbox.openshell import OpenShellDriver
from ..verifier.base import UnavailableVerifier, VerifierDriver, VerifierStatus
from ..verifier.docker import DockerVerifierDriver

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


def build_verifier_driver(settings: Settings) -> VerifierDriver:
    if settings.verifier_driver is VerifierDriverName.DOCKER:
        return DockerVerifierDriver(
            bin=settings.docker_bin,
            image=settings.verifier_image,
            cpus=settings.verifier_cpus,
            memory=settings.verifier_memory,
            pids_limit=settings.verifier_pids_limit,
            expected_image_id=settings.verifier_image_id,
        )
    return UnavailableVerifier()


@dataclass
class VerifierStatusCache:
    """Caches ``verifier.probe()`` for the capabilities endpoint."""

    driver: VerifierDriver
    clock: Callable[[], float] = time.monotonic
    _status: VerifierStatus | None = field(default=None, init=False)
    _at: float = field(default=0.0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def get(self) -> VerifierStatus:
        with self._lock:
            if self._status is None or self.clock() - self._at > PROBE_TTL_SECONDS:
                self._status = self.driver.probe()
                self._at = self.clock()
            return self._status


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
    """Live mode needs a live model AND an enforcing sandbox, unless the operator opted in
    to the unenforced development fallback (``PROOFLAYER_ALLOW_UNENFORCED_LIVE``)."""
    live_model = settings.nebius_configured and not settings.mock_mode
    return live_model and (sandbox.enforced or settings.allow_unenforced_live)


TransportFactory = Callable[[Run], ModelTransport]


@dataclass
class Runtime:
    """Everything the orchestrator needs to execute runs."""

    settings: Settings
    driver: SandboxDriver
    transport_factory: TransportFactory
    verifier: VerifierDriver = field(default_factory=UnavailableVerifier)
    challenge_transport_factory: TransportFactory | None = None
    ledger: EvidenceLedger = field(default_factory=lambda: EvidenceLedger(None))
    breaker: CircuitBreaker = field(default_factory=CircuitBreaker)
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic

    def model_client(self, run: Run, observer: Callable[[CallRecord], None]) -> ModelClient:
        return self._client(
            self.transport_factory(run),
            observer,
            self.settings.max_model_calls_per_run,
            self.settings.max_model_tokens,
        )

    def challenge_client(self, run: Run, observer: Callable[[CallRecord], None]) -> ModelClient:
        factory = self.challenge_transport_factory or default_challenge_transport_factory(
            self.settings
        )
        # Two calls: one proposal plus at most one corrective retry.
        return self._client(factory(run), observer, 2, min(8_000, self.settings.max_model_tokens))

    def _client(
        self,
        transport: ModelTransport,
        observer: Callable[[CallRecord], None],
        max_calls: int,
        max_tokens: int,
    ) -> ModelClient:
        return ModelClient(
            transport=transport,
            budget=RunBudget(max_calls=max_calls, max_tokens=max_tokens),
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


def default_challenge_transport_factory(settings: Settings) -> TransportFactory:
    def factory(run: Run) -> ModelTransport:
        if run.mode == RunMode.LIVE:
            return NebiusTransport(settings)
        return ScriptedChallengeTransport(TemplateId(run.task_id))

    return factory


def build_runtime(
    settings: Settings,
    driver: SandboxDriver | None = None,
    verifier: VerifierDriver | None = None,
) -> Runtime:
    return Runtime(
        settings=settings,
        driver=driver or build_sandbox_driver(settings),
        transport_factory=default_transport_factory(settings),
        verifier=verifier or build_verifier_driver(settings),
        challenge_transport_factory=default_challenge_transport_factory(settings),
        ledger=EvidenceLedger(settings.evidence_ledger_path or None),
    )

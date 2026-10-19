"""Seed fixture templates, and optionally one queued fixture run per template.

Usage: ``python -m prooflayer_api.seed [--with-runs]`` (run migrations first).
Seeded runs go through the normal lifecycle service, so each has a real event
chain; nothing here writes a status, verdict or check result directly.
"""

from __future__ import annotations

import argparse

from .config import get_settings
from .db.session import make_engine, make_session_factory
from .enums import Actor, RunMode
from .services.fixtures import FIXTURES, seed_templates
from .services.runs import create_run


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--with-runs", action="store_true", help="also create one queued run per fixture"
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)
    try:
        with session_factory.begin() as session:
            count = seed_templates(session)
        print(f"Seeded {count} fixture templates")
        if args.with_runs:
            for template_id in FIXTURES:
                with session_factory() as session:
                    result = create_run(
                        session,
                        template_id=template_id,
                        mode=RunMode.FIXTURE,
                        max_pending_runs=settings.max_pending_runs,
                        actor=Actor.SEEDER,
                    )
                    print(f"Created run {result.run.id} ({template_id}, {result.run.status})")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

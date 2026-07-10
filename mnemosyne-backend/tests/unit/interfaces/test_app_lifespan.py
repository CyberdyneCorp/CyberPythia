"""The API applies migrations on boot when enabled (spec: repository-sync deploy)."""

from types import SimpleNamespace

import app.main as main


class _Closable:
    async def close(self) -> None:
        pass


def _fake_app() -> SimpleNamespace:
    container = SimpleNamespace(queue=_Closable(), sync_lock=_Closable(), github=_Closable())
    return SimpleNamespace(state=SimpleNamespace(container=container))


async def test_lifespan_runs_migrations_when_enabled(monkeypatch) -> None:
    calls: list[int] = []

    async def fake_migrate() -> None:
        calls.append(1)

    monkeypatch.setattr(main, "_run_migrations", fake_migrate)
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(run_migrations_on_boot=True))
    async with main.lifespan(_fake_app()):  # type: ignore[arg-type]
        pass
    assert calls == [1]


async def test_lifespan_skips_migrations_when_disabled(monkeypatch) -> None:
    calls: list[int] = []

    async def fake_migrate() -> None:
        calls.append(1)

    monkeypatch.setattr(main, "_run_migrations", fake_migrate)
    monkeypatch.setattr(
        main, "get_settings", lambda: SimpleNamespace(run_migrations_on_boot=False)
    )
    async with main.lifespan(_fake_app()):  # type: ignore[arg-type]
        pass
    assert calls == []

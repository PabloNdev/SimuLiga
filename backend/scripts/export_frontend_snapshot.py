"""Exporta a JSON estático los datos que consume el frontend.

Así el sitio publicado en Cloudflare Pages funciona sin backend: enseña la
última simulación guardada en ``frontend/public/data``.

Se ejecuta desde ``backend/`` (con las dependencias instaladas):

    python scripts/export_frontend_snapshot.py

Llama a la app FastAPI en proceso, así que no hace falta levantar el servidor,
pero sí tener acceso a las fuentes de datos (o usar ``DATA_SOURCE=demo``).
Commitear los JSON generados y hacer push vuelve a desplegar el sitio con los
datos nuevos.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.main import app  # noqa: E402

MODES = ("score", "1x2")
DEFAULT_OUT = Path(__file__).resolve().parents[2] / "frontend" / "public" / "data"


def _get(client: TestClient, path: str, params: dict | None = None) -> dict:
    response = client.get(path, params=params)
    if response.status_code != 200:
        raise SystemExit(f"GET {path} -> {response.status_code}: {response.text[:200]}")
    return response.json()


def _write(out: Path, name: str, payload: dict, written: list[str]) -> int:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    (out / name).write_text(data, encoding="utf-8")
    written.append(name)
    return len(data.encode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--sims", type=int, default=10_000)
    args = parser.parse_args()

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    total = 0
    written: list[str] = []

    with TestClient(app) as client:
        season = _get(client, "/api/season")
        matchday = int(season["current_matchday"])
        total += _write(out, "season.json", season, written)
        total += _write(out, "elo.json", _get(client, "/api/elo"), written)
        total += _write(
            out, "validation.json", _get(client, "/api/validation"), written
        )

        for mode in MODES:
            total += _write(
                out,
                f"matches-{mode}.json",
                _get(client, "/api/matches", {"mode": mode}),
                written,
            )
            total += _write(
                out,
                f"projection-{mode}.json",
                _get(
                    client,
                    "/api/projection",
                    {
                        "mode": mode,
                        "sims": args.sims,
                        "seed": 42,
                        "start_matchday": matchday,
                    },
                ),
                written,
            )

        total += _write(
            out, "champions-season.json", _get(client, "/api/champions/season"), written
        )
        total += _write(
            out, "champions-elo.json", _get(client, "/api/champions/elo"), written
        )
        total += _write(
            out,
            "champions-validation.json",
            _get(client, "/api/champions/validation"),
            written,
        )
        for mode in MODES:
            total += _write(
                out,
                f"champions-matches-{mode}.json",
                _get(client, "/api/champions/matches", {"mode": mode}),
                written,
            )
            total += _write(
                out,
                f"champions-projection-{mode}.json",
                _get(
                    client,
                    "/api/champions/projection",
                    {"mode": mode, "sims": args.sims, "seed": 42},
                ),
                written,
            )

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "current_matchday": matchday,
        "sims": args.sims,
        "source": season.get("source"),
        "demo": bool(season.get("demo")),
        "data_version": season.get("data_version"),
        "files": sorted(written),
    }
    total += _write(out, "manifest.json", manifest, written)

    print(f"Snapshot written to {out}")
    print(f"  matchday: {matchday} · sims: {args.sims} · demo: {manifest['demo']}")
    print(f"  files: {len(written)} · {total / 1024:.0f} KB")
    if manifest["demo"]:
        print(
            "  WARNING: datos de demostración; revisa DATA_SOURCE o la conexión "
            "antes de publicar."
        )


if __name__ == "__main__":
    main()

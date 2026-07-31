from __future__ import annotations

import subprocess
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def run_import(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-c",
            code,
        ],
        cwd=BACKEND_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_backfill_cli_imports_without_cycle() -> None:
    result = run_import(
        "\n".join(
            (
                "from app.cli.backfill_knowledge_metadata "
                "import metadata_values",
                "values = metadata_values("
                "'{{Metadata\\n"
                "| הרשאות גישה = הנהלה\\n"
                "}}'"
                ")",
                "assert values['access_roles'] "
                "== ['management']",
            )
        )
    )

    assert result.returncode == 0, (
        result.stdout + result.stderr
    )


def test_persistence_mapper_imports_without_cycle() -> None:
    result = run_import(
        "\n".join(
            (
                "from app.services.knowledge."
                "persistence.mappers import "
                "KnowledgePersistenceMapper",
                "assert KnowledgePersistenceMapper "
                "is not None",
            )
        )
    )

    assert result.returncode == 0, (
        result.stdout + result.stderr
    )

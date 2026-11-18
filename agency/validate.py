"""JSON-kontraktlarni schema bo'yicha tekshirish.

CLI: python -m agency.validate <schema_name> <file.json>
     (masalan: python -m agency.validate script runs/2026-11-19/script.json)
"""
from __future__ import annotations

import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from .config import SCHEMAS_DIR
from .util import read_json


class ContractError(ValueError):
    pass


def validate(schema_name: str, path: Path) -> dict:
    path = Path(path)
    if not path.exists():
        raise ContractError(f"{path.name} yaratilmagan")
    try:
        data = read_json(path)
    except Exception as exc:  # noqa: BLE001
        raise ContractError(f"{path.name} yaroqsiz JSON: {exc}") from exc
    schema = read_json(SCHEMAS_DIR / f"{schema_name}.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.path))
    if errors:
        lines = [f"- {'/'.join(map(str, e.path)) or '(root)'}: {e.message}" for e in errors[:15]]
        raise ContractError(f"{path.name} schema'ga mos emas ({schema_name}):\n" + "\n".join(lines))
    return data


def main() -> None:
    if len(sys.argv) != 3:
        print("Foydalanish: python -m agency.validate <schema> <file.json>", file=sys.stderr)
        sys.exit(2)
    try:
        validate(sys.argv[1], Path(sys.argv[2]))
    except ContractError as exc:
        print(f"INVALID\n{exc}")
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()

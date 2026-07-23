import argparse
import json
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.security.device_store import DeviceStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Gerencia dispositivos do ControlFawkes.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("list", help="Lista dispositivos pareados sem tokens.")
    revoke_parser = subcommands.add_parser("revoke", help="Revoga um dispositivo.")
    revoke_parser.add_argument("device_id")
    arguments = parser.parse_args()

    store = DeviceStore()
    if arguments.command == "list":
        print(json.dumps(store.list_devices(), ensure_ascii=False, indent=2))
        return 0

    if store.revoke(arguments.device_id):
        print(f"Dispositivo revogado: {arguments.device_id}")
        return 0
    print(f"Dispositivo não encontrado: {arguments.device_id}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

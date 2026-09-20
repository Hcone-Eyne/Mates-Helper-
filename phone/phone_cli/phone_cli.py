from __future__ import annotations

import argparse
import sys
from pathlib import Path

from phone.bridge.kdeconnect import KDEConnectBridge, KDEConnectError


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="fox-phone",
        description="Isolated Android ↔ Mac Phone Hub",
    )

    sub = parser.add_subparsers(
        dest="command",
        required=True,
    )

    sub.add_parser("status")
    sub.add_parser("devices")
    sub.add_parser("available")
    sub.add_parser("refresh")

    encryption_parser = sub.add_parser("encryption")
    encryption_parser.add_argument("--device")

    ping_parser = sub.add_parser("ping")
    ping_parser.add_argument("--device")

    share_parser = sub.add_parser("share")
    share_parser.add_argument("path")
    share_parser.add_argument("--device")

    text_parser = sub.add_parser("share-text")
    text_parser.add_argument("text")
    text_parser.add_argument("--device")

    args = parser.parse_args()

    bridge = KDEConnectBridge()

    try:
        if args.command == "status":
            print(bridge.version())

        elif args.command == "devices":
            print(bridge.list_devices())

        elif args.command == "available":
            print(bridge.list_available())

        elif args.command == "refresh":
            print(bridge.refresh())

        elif args.command == "encryption":
            print(bridge.encryption_info(args.device))

        elif args.command == "ping":
            print(bridge.ping(args.device))

        elif args.command == "share":
            path = Path(args.path).expanduser().resolve()
            if not path.exists():
                raise KDEConnectError(f"File not found: {path}")
            if not path.is_file():
                raise KDEConnectError(f"Path is not a file: {path}")
            print(bridge.share(str(path), args.device))

        elif args.command == "share-text":
            print(bridge.share_text(args.text, args.device))

    except KDEConnectError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
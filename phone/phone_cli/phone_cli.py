from __future__ import annotations

import argparse
import sys
from pathlib import Path

from phone.bridge.kdeconnect import KDEConnectBridge, KDEConnectError
from phone.security.permission import (
    PhonePermision,
    READ_ONLY,
    ACTION_PERMISSION,
    DEFAULT_PERMISSIONS,
    permission_label,
    is_allowed,
)
from phone.events import NotificationEvent, MessageEvent

def _permission_symbol(allowed: bool):
    return "✓" if allowed else "○"

def show_permission(bridge: KDEConnectBridge, device: str | None = None):
    print("\n PHONE PERMISSIONS.")
    print("=" * 40)

    if device:
        print(f"Device: {device}")
    else:
        print("Device: Default")

    print("\nREAD")
    print("-" * 40)

    all_permissions = sorted(
        READ_ONLY | ACTION_PERMISSION,
        key=lambda permission: permission.value,
    )

    for permission in all_permissions:
        allowed = is_allowed(permission, DEFAULT_PERMISSIONS)
        print(f"{permission_label(permission):<20}{_permission_symbol(allowed)}")

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

    notifications_parser = sub.add_parser("notifications")
    notifications_parser.add_argument("--device")
    notifications_parser.add_argument("--json", action="store_true", help="Output as JSON")

    messages_parser = sub.add_parser("messages")
    messages_parser.add_argument("--device")

    sms_parser = sub.add_parser("sms")
    sms_parser.add_argument("destination", help="Phone number to send SMS to")
    sms_parser.add_argument("message", help="Message text to send")
    sms_parser.add_argument("--device")

    permissions_parser = sub.add_parser("permissions")
    permissions_parser.add_argument("--device")

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

        elif args.command == "permissions":
            show_permission(bridge, args.device)

        elif args.command == "notifications":
            notifications = bridge.get_notifications(args.device)
            if args.json:
                import json
                print(json.dumps(notifications, indent=2, default=str))
            else:
                if not notifications:
                    print("No notifications found or device not connected.")
                else:
                    for n in notifications:
                        app = n.get('appName', n.get('app_name', 'Unknown'))
                        title = n.get('title', 'No title')
                        text = n.get('text', n.get('body', ''))
                        print(f"[{n.get('id', '?')}] {app}: {title} - {text}")

        elif args.command == "messages":
            # KDE Connect doesn't have a direct message listing command yet
            print("Message listing not yet supported by KDE Connect CLI")
            print("Use 'sms' command to send SMS messages")

        elif args.command == "sms":
            if not args.destination or not args.message:
                print("Error: SMS requires destination and message", file=sys.stderr)
                sys.exit(1)
            print(bridge.send_sms(args.destination, args.message, args.device))

    except KDEConnectError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
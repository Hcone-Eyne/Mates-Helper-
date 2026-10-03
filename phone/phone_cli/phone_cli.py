from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from phone.bridge.kdeconnect import (
    KDEConnectBridge,
    KDEConnectError,
    KDEConnectUnsupportedError,
    KDEConnectPermissionError,
    KDEConnectDeviceError,
    KDEConnectParseError,
    KDEConnectEmptyError,
)
from phone.security.isolation import PhoneIsolationError, assert_phone_boundary
from phone.security.permission import (
    PhonePermision,
    PhonePermissionDenied,
    READ_ONLY,
    ACTION_PERMISSION,
    DEFAULT_PERMISSIONS,
    command_permission,
    permission_label,
    is_allowed,
    require_permission,
)


def _permission_symbol(allowed: bool):
    return "✓" if allowed else "○"


def show_permission(
    device: str | None = None,
    permissions: dict[PhonePermision, bool] | None = None,
):
    """Print the local permission policy.

    This screen is local policy only - it is never read from the device, so
    it must not pretend to report what the phone granted us.
    """
    state = DEFAULT_PERMISSIONS if permissions is None else permissions

    print("\n PHONE PERMISSIONS (local policy).")
    print("=" * 40)
    print("This is the local permission policy, not a readback from the device.")

    if device:
        print(f"Requested device: {device} (not queried)")

    print("\nREAD")
    print("-" * 40)

    all_permissions = sorted(
        READ_ONLY | ACTION_PERMISSION,
        key=lambda permission: permission.value,
    )

    for permission in all_permissions:
        allowed = is_allowed(permission, state)
        print(f"{permission_label(permission):<20}{_permission_symbol(allowed)}")


def _handle_messages(
    bridge: KDEConnectBridge,
    device: str | None,
    as_json: bool,
) -> None:
    """Shared handler for the `messages` and `list-sms` commands."""
    try:
        messages = bridge.list_sms(device)
    except KDEConnectUnsupportedError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except KDEConnectDeviceError as exc:
        print(f"Error: Device error - {exc}", file=sys.stderr)
        sys.exit(1)
    except KDEConnectPermissionError as exc:
        print(f"Error: Permission denied - {exc}", file=sys.stderr)
        sys.exit(1)
    except KDEConnectParseError as exc:
        print(f"Error: Failed to parse messages - {exc}", file=sys.stderr)
        sys.exit(1)
    except KDEConnectEmptyError:
        print("No messages found.")
        return
    except KDEConnectError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if as_json:
        print(json.dumps(list(messages), indent=2, default=str))
        return

    if not messages:
        print("No messages found.")
        return

    for message in messages:
        print(
            f"[{message.get('id', '?')}] "
            f"{message.get('sender', 'Unknown')}: {message.get('body', '')}"
        )


def main(
    argv: list[str] | None = None,
    *,
    source: str = "phone_cli",
    permissions: dict[PhonePermision, bool] | None = None,
) -> None:
    # Isolation boundary: agent-side callers are refused before any device
    # work (and before argparse can even describe the device commands).
    try:
        assert_phone_boundary(source)
    except PhoneIsolationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

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
    encryption_parser.add_argument("-d", "--device")

    ping_parser = sub.add_parser("ping")
    ping_parser.add_argument("-d", "--device")

    share_parser = sub.add_parser("share")
    share_parser.add_argument("path")
    share_parser.add_argument("-d", "--device")

    text_parser = sub.add_parser("share-text")
    text_parser.add_argument("text")
    text_parser.add_argument("-d", "--device")

    notifications_parser = sub.add_parser("notifications")
    notifications_parser.add_argument("-d", "--device")
    notifications_parser.add_argument("--json", action="store_true", help="Output as JSON")

    messages_parser = sub.add_parser("messages")
    messages_parser.add_argument("-d", "--device")
    messages_parser.add_argument("--json", action="store_true", help="Output as JSON")

    sms_parser = sub.add_parser("sms")
    sms_parser.add_argument("destination", help="Phone number to send SMS to")
    sms_parser.add_argument("message", help="Message text to send")
    sms_parser.add_argument("-d", "--device")

    list_sms_parser = sub.add_parser("list-sms")
    list_sms_parser.add_argument("-d", "--device")
    list_sms_parser.add_argument("--json", action="store_true", help="Output as JSON")

    permissions_parser = sub.add_parser("permissions")
    permissions_parser.add_argument("-d", "--device")

    # argv=None keeps the original behaviour (read sys.argv); passing an explicit
    # list lets the main CLI dispatch phone commands without touching sys.argv.
    args = parser.parse_args(argv)

    # Permission enforcement: a permission that is never checked is not a
    # permission. Every device-touching command declares the permission it
    # needs and is refused before the bridge is created.
    required = command_permission(args.command)
    if required is not None:
        try:
            require_permission(required, permissions)
        except PhonePermissionDenied as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

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
            show_permission(args.device, permissions)

        elif args.command == "notifications":
            notifications = bridge.get_notifications(args.device)
            if args.json:
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

        elif args.command in {"messages", "list-sms"}:
            _handle_messages(bridge, args.device, args.json)

        elif args.command == "sms":
            if not args.destination or not args.message:
                print("Error: SMS requires destination and message", file=sys.stderr)
                sys.exit(1)
            try:
                result = bridge.send_sms(args.destination, args.message, args.device)
                if result:
                    print(result)
                else:
                    print("SMS sent successfully")
            except KDEConnectError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                sys.exit(1)

    except KDEConnectError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Extract CarPlay instrument-cluster control events from a DiPlay diagnostic report.

DiPlay 0.2.20 already records raw AirPlay binary-plist bodies as hexadecimal TRACE lines.
This tool decodes those existing traces without changing the CarPlay transport path on the car.
It is intended for iOS 27 dual-screen/Type-111 investigations: suggestUI, showUI, display-mode
changes, ViewArea changes and the auxiliary-screen SETUP metadata.

Usage:
    python3 tools/cluster_protocol_report.py diagnostic.txt
    python3 tools/cluster_protocol_report.py diagnostic.txt --all
    python3 tools/cluster_protocol_report.py diagnostic.txt --json

No third-party Python packages are required.
"""

from __future__ import annotations

import argparse
import json
import plistlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


BODY_HEX_RE = re.compile(r"bodyHex=([0-9a-fA-F]+)")
CONTROL_RX_RE = re.compile(r"airplay rx\s+(\S+)\s+(\S+)\s+cseq=([^\s]+)")
EVENT_TX_RE = re.compile(r"TRACE\s+airplay event tx headers=([A-Z]+)\s+(\S+)")
EVENT_RX_RE = re.compile(r"airplay event rx\s+(\S+)\s+(\S+)\s+cseq=([^\s]+)")

INTERESTING_COMMANDS = {
    "suggestui",
    "showui",
    "stopui",
    "requestui",
    "modeschanged",
    "changemodes",
    "updateviewarea",
    "requestviewarea",
    "forcekeyframe",
    "changemapzoomlevel",
    "setseconddisplaymode",
    "seconddisplaymode",
    "uiappearanceupdate",
    "mapappearanceupdate",
}

INTERESTING_KEY_PARTS = (
    "altscreen",
    "cluster",
    "instrument",
    "seconddisplay",
    "displaymode",
    "viewarea",
    "mapspresentation",
    "maneuverlayout",
    "showeta",
    "showspeedlimit",
    "showcompass",
)

REDACT_KEY_PARTS = (
    "password",
    "secret",
    "privatekey",
    "pairingkey",
    "certificate",
    "hidreport",
)


@dataclass
class Context:
    direction: str
    channel: str
    method: str | None = None
    path: str | None = None
    cseq: str | None = None


@dataclass
class Event:
    line: int
    context: Context
    kind: str
    payload: Any


def decode_plist_hex(text: str) -> Any | None:
    try:
        raw = bytes.fromhex(text)
    except ValueError:
        return None
    if not raw.startswith(b"bplist"):
        return None
    try:
        return plistlib.loads(raw)
    except Exception:
        return None


def key_is_interesting(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in INTERESTING_KEY_PARTS)


def command_is_interesting(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    command = str(value.get("type", "")).lower()
    if command in INTERESTING_COMMANDS:
        return True
    if "displaymode" in command or "second" in command:
        return True
    return False


def contains_interesting_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if key_is_interesting(str(key)) or contains_interesting_key(child):
                return True
    elif isinstance(value, (list, tuple)):
        return any(contains_interesting_key(item) for item in value)
    return False


def contains_alt_screen_stream(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    streams = value.get("streams")
    if not isinstance(streams, list):
        return False
    for stream in streams:
        if isinstance(stream, dict) and int_value(stream.get("type")) == 111:
            return True
    return False


def int_value(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def sanitize(value: Any, *, key: str = "", depth: int = 0) -> Any:
    if any(part in key.lower() for part in REDACT_KEY_PARTS):
        return "<redacted>"
    if depth >= 6:
        return "<max-depth>"
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for index, (child_key, child) in enumerate(value.items()):
            if index >= 40:
                result["<truncated>"] = f"{len(value) - index} more keys"
                break
            text_key = str(child_key)
            result[text_key] = sanitize(child, key=text_key, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        items = list(value)
        result = [sanitize(item, depth=depth + 1) for item in items[:60]]
        if len(items) > 60:
            result.append(f"<truncated:{len(items) - 60}>")
        return result
    if isinstance(value, str) and len(value) > 500:
        return value[:500] + f"...<truncated:{len(value) - 500}>"
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def event_kind(payload: Any, context: Context) -> str:
    if isinstance(payload, dict):
        command = payload.get("type")
        if isinstance(command, str) and command:
            return f"command:{command}"
        if contains_alt_screen_stream(payload):
            return "setup:type111"
        if "features" in payload:
            return "setup:features"
        if contains_interesting_key(payload):
            return "cluster-metadata"
    if context.path:
        return f"plist:{context.path}"
    return "plist"


def should_emit(payload: Any, context: Context, show_all: bool) -> bool:
    if show_all:
        return True
    if command_is_interesting(payload):
        return True
    if contains_alt_screen_stream(payload):
        return True
    if contains_interesting_key(payload):
        return True
    if context.path and context.path.lower().endswith("/info"):
        return contains_interesting_key(payload)
    return False


def parse_report(lines: Iterable[str], show_all: bool) -> list[Event]:
    events: list[Event] = []
    last_control_rx: Context | None = None
    pending_multiline: Context | None = None

    for line_number, line in enumerate(lines, start=1):
        rx = CONTROL_RX_RE.search(line)
        if rx:
            last_control_rx = Context(
                direction="RX",
                channel="control",
                method=rx.group(1),
                path=rx.group(2),
                cseq=rx.group(3),
            )

        event_rx = EVENT_RX_RE.search(line)
        if event_rx:
            pending_multiline = Context(
                direction="RX",
                channel="event",
                method=event_rx.group(1),
                path=event_rx.group(2),
                cseq=event_rx.group(3),
            )

        event_tx = EVENT_TX_RE.search(line)
        if event_tx:
            pending_multiline = Context(
                direction="TX",
                channel="event",
                method=event_tx.group(1),
                path=event_tx.group(2),
            )

        body_match = BODY_HEX_RE.search(line)
        if not body_match:
            continue

        payload = decode_plist_hex(body_match.group(1))
        if payload is None:
            continue

        if "TRACE airplay control rx" in line:
            context = last_control_rx or Context("RX", "control")
        elif "TRACE airplay event tx" in line:
            context = pending_multiline or Context("TX", "event")
        elif "TRACE airplay event rx" in line:
            context = pending_multiline or Context("RX", "event")
        elif pending_multiline is not None:
            # Event TX headers include CRLF, so bodyHex may be written on a following physical line.
            context = pending_multiline
        else:
            context = last_control_rx or Context("?", "?")

        if should_emit(payload, context, show_all):
            events.append(Event(line_number, context, event_kind(payload, context), sanitize(payload)))

        if context.channel == "event":
            pending_multiline = None

    return events


def print_text(events: list[Event]) -> None:
    if not events:
        print("No matching cluster-protocol plist events were found.")
        print("Try --all to verify that TRACE bodyHex entries are present in the report.")
        return

    for event in events:
        ctx = event.context
        route = " ".join(part for part in (ctx.method, ctx.path) if part)
        cseq = f" cseq={ctx.cseq}" if ctx.cseq else ""
        print(f"\n[L{event.line}] {ctx.direction} {ctx.channel} {route}{cseq}  {event.kind}".rstrip())
        print(json.dumps(event.payload, ensure_ascii=False, indent=2, sort_keys=True))


def print_json(events: list[Event]) -> None:
    for event in events:
        print(
            json.dumps(
                {
                    "line": event.line,
                    "direction": event.context.direction,
                    "channel": event.context.channel,
                    "method": event.context.method,
                    "path": event.context.path,
                    "cseq": event.context.cseq,
                    "kind": event.kind,
                    "payload": event.payload,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="DiPlay diagnostic report text file")
    parser.add_argument("--all", action="store_true", help="show every decodable plist trace, not only cluster-related events")
    parser.add_argument("--json", action="store_true", help="emit one JSON object per event")
    args = parser.parse_args()

    try:
        text = args.report.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        print(f"Could not read {args.report}: {error}", file=sys.stderr)
        return 2

    events = parse_report(text.splitlines(), args.all)
    if args.json:
        print_json(events)
    else:
        print_text(events)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import argparse
import json
from pathlib import Path
from typing import Optional

from focusframe.rules import DEFAULT_RULES
from focusframe.storage import Store


def ensure_store(db_path: str) -> Store:
    store = Store(db_path)
    store.ensure_rules(DEFAULT_RULES)
    return store


def cmd_list(args: argparse.Namespace) -> None:
    store = ensure_store(args.database)
    try:
        rows = store.fetch_rules()
        if not rows:
            print("No rules found.")
            return
        print(f"Found {len(rows)} rules (ordered by priority):")
        for row in rows:
            print(
                f"- {row['id']} | priority={row['priority']} | action={row['action']} | "
                f"reason={row['parameters'].get('reason')}"
            )
    finally:
        store.close()


def cmd_update(args: argparse.Namespace) -> None:
    store = ensure_store(args.database)
    try:
        records = {row["id"]: row for row in store.fetch_rules()}
        if args.rule_id not in records:
            raise SystemExit(f"Rule '{args.rule_id}' not found")
        rule = records[args.rule_id]

        if args.priority is not None:
            rule["priority"] = int(args.priority)
        if args.action:
            rule["action"] = args.action
        if args.reason:
            params = dict(rule["parameters"])
            params["reason"] = args.reason
            rule["parameters"] = params
        if args.minutes is not None:
            params = dict(rule["parameters"])
            params["minutes"] = int(args.minutes)
            rule["parameters"] = params
        if args.minutes_key:
            params = dict(rule["parameters"])
            params["minutes_key"] = args.minutes_key
            rule["parameters"] = params
        if args.condition_json:
            try:
                rule["condition"] = json.loads(args.condition_json)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid condition JSON: {exc}")

        store.upsert_rule(rule)
        print(f"Updated rule '{args.rule_id}'")
    finally:
        store.close()


def cmd_export(args: argparse.Namespace) -> None:
    store = ensure_store(args.database)
    try:
        rows = store.fetch_rules()
    finally:
        store.close()

    path = Path(args.output)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Exported {len(rows)} rules to {path}")


def cmd_import(args: argparse.Namespace) -> None:
    path = Path(args.input)
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON: {exc}")

    if not isinstance(payload, list):
        raise SystemExit("Expected a list of rules in JSON file")

    store = ensure_store(args.database)
    try:
        for rule in payload:
            if not isinstance(rule, dict):
                continue
            store.upsert_rule(rule)  # type: ignore[arg-type]
    finally:
        store.close()
    print(f"Imported {len(payload)} rules from {path}")


def cmd_reset(args: argparse.Namespace) -> None:
    store = ensure_store(args.database)
    try:
        for rule in DEFAULT_RULES:
            store.upsert_rule(rule)
    finally:
        store.close()
    print("Reset rules to defaults")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FocusFrame Rule Management")
    parser.add_argument("--database", default="focusframe.db", help="SQLite database path")

    sub = parser.add_subparsers(dest="command", required=True)

    sub_list = sub.add_parser("list", help="List current rules")
    sub_list.set_defaults(func=cmd_list)

    sub_update = sub.add_parser("update", help="Update an existing rule")
    sub_update.add_argument("rule_id", help="Rule identifier to update")
    sub_update.add_argument("--priority", type=int)
    sub_update.add_argument("--action")
    sub_update.add_argument("--reason")
    sub_update.add_argument("--minutes", type=int)
    sub_update.add_argument("--minutes-key")
    sub_update.add_argument("--condition-json")
    sub_update.set_defaults(func=cmd_update)

    sub_export = sub.add_parser("export", help="Export rules to JSON file")
    sub_export.add_argument("output", help="Output JSON path")
    sub_export.set_defaults(func=cmd_export)

    sub_import = sub.add_parser("import", help="Import rules from JSON file")
    sub_import.add_argument("input", help="JSON file with rule definitions")
    sub_import.set_defaults(func=cmd_import)

    sub_reset = sub.add_parser("reset", help="Restore default rules")
    sub_reset.set_defaults(func=cmd_reset)

    return parser


def main(argv: Optional[list[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

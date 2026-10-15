"""命令行：列出、记住、修改、忘记、钉住用户画像。

    python -m local.memory.cli list
    python -m local.memory.cli learn "以后简称我小Q" --lane general --facet identity
    python -m local.memory.cli edit <id> "新的说法"
    python -m local.memory.cli forget <id>
    python -m local.memory.cli pin <id>
"""

from __future__ import annotations

import argparse
import json
import sys

from .editor import MemoryEditor
from .pack import build_for_turn
from .store import get_store
from .host import current_host


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="编辑 LightAgent 用户画像记忆")
    sub = parser.add_subparsers(dest="cmd", required=True)

    list_cmd = sub.add_parser("list", help="列出画像")
    list_cmd.add_argument("--lane", default="")

    learn = sub.add_parser("learn", help="记住一句话")
    learn.add_argument("text")
    learn.add_argument("--lane", default="general")
    learn.add_argument("--facet", default="identity")
    learn.add_argument("--kind", default="preference")
    learn.add_argument("--topics", default="")

    edit = sub.add_parser("edit", help="修改一条")
    edit.add_argument("learning_id")
    edit.add_argument("text")

    forget = sub.add_parser("forget", help="删除一条（id 或原文片段）")
    forget.add_argument("target")

    pin = sub.add_parser("pin", help="钉住一条")
    pin.add_argument("learning_id")

    confirm = sub.add_parser("confirm", help="确认一条待确认画像")
    confirm.add_argument("learning_id")

    recall = sub.add_parser("recall", help="按主题看会注入哪些画像")
    recall.add_argument("query")

    args = parser.parse_args(argv)
    editor = MemoryEditor()
    if args.cmd == "list":
        payload = editor.list_rows(lane=args.lane)
    elif args.cmd == "learn":
        topics = [part.strip() for part in args.topics.split(",") if part.strip()]
        payload = editor.learn(
            args.text,
            lane=args.lane,
            facet=args.facet,
            kind=args.kind,
            topics=topics,
        ).to_dict()
    elif args.cmd == "edit":
        payload = editor.edit(args.learning_id, args.text).to_dict()
    elif args.cmd == "forget":
        payload = {"forgotten": editor.forget(args.target)}
    elif args.cmd == "pin":
        saved = editor.pin(args.learning_id, pinned=True)
        payload = None if saved is None else saved.to_dict()
    elif args.cmd == "confirm":
        saved = editor.confirm(args.learning_id)
        payload = None if saved is None else saved.to_dict()
    elif args.cmd == "recall":
        host = current_host()
        pack = build_for_turn(get_store(), host, query=args.query, window_texts=[args.query])
        payload = {
            "markdown": pack.markdown,
            "unavailable": pack.unavailable,
            "notice": pack.notice,
            "refs": list(pack.refs),
        }
    else:
        parser.error(f"unknown command {args.cmd}")
        return 2
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
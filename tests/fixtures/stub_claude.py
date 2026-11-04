#!/usr/bin/env python3
"""A `claude` that misbehaves, for the runner's failure paths.

STUB_CLAUDE_MODE picks how: `hang` says init and then never speaks again, `noresult`
says init and one delta and exits without a `result` line. STUB_CLAUDE_PIDFILE, when
set, gets this process's id, so a test can check the runner killed it.
"""

from __future__ import annotations

import json
import os
import sys
import time


def say(data: dict) -> None:
    print(json.dumps(data), flush=True)


def main() -> int:
    pidfile = os.environ.get("STUB_CLAUDE_PIDFILE")
    if pidfile:
        with open(pidfile, "w", encoding="utf-8") as out:
            out.write(str(os.getpid()))
    say({"type": "system", "subtype": "init", "tools": [], "model": "stub-claude"})
    if os.environ.get("STUB_CLAUDE_MODE") == "hang":
        time.sleep(600)
        return 0
    delta = {"type": "text_delta", "text": "Half an answer"}
    say({"type": "stream_event", "event": {"type": "content_block_delta", "delta": delta}})
    return 0


if __name__ == "__main__":
    sys.exit(main())

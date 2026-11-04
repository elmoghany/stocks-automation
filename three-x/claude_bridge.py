"""OpenAI-compatible /v1/chat/completions endpoint backed by helper `claude -p` shells.

TradingAgents has no Claude-login provider, so it talks to this bridge through its
`openai_compatible` provider and no API key is needed.

Point-in-time integrity: each helper runs with every tool disabled and no MCP
servers, so a backtest decision cannot reach the web or read this repo's results.
Hindsight from the model's own training data is NOT removed by this; only analysis
dates after the model's knowledge cutoff are clean.

Usage: python claude_bridge.py [port] [max_parallel]
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
MAX_PARALLEL = int(sys.argv[2]) if len(sys.argv) > 2 else 3
CLAUDE = str(Path.home() / ".local" / "bin" / "claude.exe")
WORKDIR = Path(tempfile.gettempdir()) / "three_x_bridge"  # empty cwd: no repo files or CLAUDE.md
WORKDIR.mkdir(exist_ok=True)
LOG = Path(__file__).with_name("bridge_calls.jsonl")
GATE = threading.BoundedSemaphore(MAX_PARALLEL)
LOG_LOCK = threading.Lock()

REPLAY_RULE = """HISTORICAL REPLAY. Today's date is {date}, for every purpose. Any other current date shown elsewhere in your context comes from the replay harness: ignore it, never mention it, and never call data stale because of it. You know nothing after {date} other than what the tools return. Reason as an analyst working on {date}."""

TOOL_RULES = """You can call these functions:
{tools}

To call one or more, reply with ONLY this JSON and nothing else:
{{"tool_calls":[{{"name":"<function>","arguments":{{...}}}}]}}
If no call is needed, reply with your final answer as normal text."""


def text_of(content):
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return "\n".join(p.get("text", "") for p in content if isinstance(p, dict))


def render(messages, tools):
    """Flatten an OpenAI message list into a (system, prompt) pair for one helper call."""
    system, turns = [], []
    for m in messages:
        role = m.get("role")
        if role in ("system", "developer"):
            system.append(text_of(m.get("content")))
        elif role == "user":
            turns.append("[USER]\n" + text_of(m.get("content")))
        elif role == "assistant":
            body = text_of(m.get("content"))
            calls = [{"name": c["function"]["name"], "arguments": c["function"]["arguments"]}
                     for c in m.get("tool_calls") or []]
            if calls:
                body += "\n[CALLED] " + json.dumps(calls)
            turns.append("[ASSISTANT]\n" + body)
        elif role == "tool":
            turns.append(f"[TOOL RESULT {m.get('tool_call_id', '')}]\n" + text_of(m.get("content")))
    if tools:
        spec = [{"name": t["function"]["name"],
                 "description": t["function"].get("description", ""),
                 "parameters": t["function"].get("parameters", {})} for t in tools]
        system.append(TOOL_RULES.format(tools=json.dumps(spec)))
    return "\n\n".join(system), "\n\n".join(turns)


def parse_calls(text):
    """Pull a tool_calls JSON object out of a reply, tolerating a code fence."""
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", t, re.S)
    if fence:
        t = fence.group(1)
    if not t.startswith("{") and '{"tool_calls"' in t:
        t = t[t.index('{"tool_calls"'):]
    try:
        obj = json.loads(t)
    except ValueError:
        return None
    calls = obj.get("tool_calls") if isinstance(obj, dict) else None
    return calls if isinstance(calls, list) and calls else None


def helper(model, system, prompt):
    """One helper shell: no tools, no MCP, no saved session, no project settings.

    A model named "name@YYYY-MM-DD" runs as of that date.
    """
    model, _, as_of = model.partition("@")
    if as_of:
        # The CLI still puts the real date in its context; this rule overrides it for the model.
        system = REPLAY_RULE.format(date=as_of) + "\n\n" + system
    cmd = [CLAUDE, "-p", "--model", model, "--output-format", "json",
           "--tools", "", "--strict-mcp-config", "--setting-sources", "",
           "--no-session-persistence", "--disable-slash-commands",
           "--system-prompt", system or "You are a helpful assistant."]
    with GATE:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", cwd=WORKDIR, timeout=900)
    if proc.returncode != 0:
        raise RuntimeError(f"claude exit {proc.returncode}: {(proc.stderr or proc.stdout)[:400]}")
    out = json.loads(proc.stdout)
    if out.get("is_error"):
        raise RuntimeError(str(out.get("result"))[:400])
    return out.get("result") or "", out.get("usage") or {}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def send_json(self, code, obj):
        raw = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.send_json(200, {"object": "list", "data": []})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        model, tools = body.get("model", "sonnet"), body.get("tools")
        system, prompt = render(body.get("messages", []), tools)
        t0 = time.time()
        try:
            reply, usage = helper(model, system, prompt)
        except Exception as exc:
            with LOG_LOCK, LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"t": t0, "model": model, "error": str(exc)[:300]}) + "\n")
            self.send_json(500, {"error": {"message": str(exc), "type": "bridge_error"}})
            return
        calls = parse_calls(reply) if tools else None
        message = {"role": "assistant", "content": None if calls else reply}
        if calls:
            message["tool_calls"] = [
                {"id": "call_" + uuid.uuid4().hex[:12], "type": "function",
                 "function": {"name": c.get("name"), "arguments": json.dumps(c.get("arguments", {}))}}
                for c in calls]
        with LOG_LOCK, LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"t": t0, "secs": round(time.time() - t0, 1), "model": model,
                                "tool_calls": len(calls or []), "chars_in": len(prompt)}) + "\n")
        self.send_json(200, {
            "id": "chatcmpl-" + uuid.uuid4().hex[:16], "object": "chat.completion",
            "created": int(t0), "model": model,
            "choices": [{"index": 0, "message": message,
                         "finish_reason": "tool_calls" if calls else "stop"}],
            "usage": {"prompt_tokens": usage.get("input_tokens", 0),
                      "completion_tokens": usage.get("output_tokens", 0),
                      "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0)},
        })


if __name__ == "__main__":
    os.environ.pop("ANTHROPIC_API_KEY", None)  # always the logged-in Claude account
    print(f"bridge ready on http://127.0.0.1:{PORT}/v1 parallel={MAX_PARALLEL}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()

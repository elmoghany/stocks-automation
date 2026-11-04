"""TradingAgents' own run_backtest over a ticker/date grid, on Claude through claude_bridge.py.

The model name carries the analysis date ("claude-haiku-5-5@2026-08-10") so the bridge can make
that date "today" for the helper. One date at a time for the same reason; run_backtest skips
cells already in this run's log, so an interrupted sweep resumes by being run again.

Usage: venvs/ta/Scripts/python ta_run.py AMD,NVDA 2026-07-06 2026-10-26 7 <run_id> [quick_model] [deep_model]
Writes ratings to results/ta_<run_id>.json.
"""
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("OPENAI_COMPATIBLE_API_KEY", "local-bridge")
os.environ["TRADINGAGENTS_NO_UPDATE_CHECK"] = "1"

from tradingagents.backtest import iter_grid, run_backtest, summarize
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.memory import TradingMemoryLog

from ta_news_vendor import register

tickers, start, end, every, run_id = sys.argv[1].split(","), sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
quick = sys.argv[6] if len(sys.argv) > 6 else "claude-haiku-5-5"
deep = sys.argv[7] if len(sys.argv) > 7 else "claude-sonnet-5-5"

base = register({**DEFAULT_CONFIG,
                 "llm_provider": "openai_compatible",
                 "backend_url": "http://127.0.0.1:8765/v1",
                 "llm_max_retries": 2,
                 "max_tool_rounds": 6,
                 "results_dir": r"E:\strategy-repos\ta_results",
                 "data_cache_dir": rf"E:\strategy-repos\ta_cache\{run_id}",
                 "memory_log_path": r"E:\strategy-repos\ta_results\trading_memory.md"})

result = None
for date in iter_grid(start, end, every):
    config = {**base, "quick_think_llm": f"{quick}@{date}", "deep_think_llm": f"{deep}@{date}"}
    result = run_backtest(tickers, [date], config, selected_analysts=["market", "news", "fundamentals"], run_id=run_id,
                          progress=lambda d, n, t, day: print(f"[{t} {day}]", flush=True))
    for failure in result.failures:
        print("FAILED", failure[0], failure[1], str(failure[2])[:300], flush=True)

print(summarize(result).render())
entries = TradingMemoryLog({"memory_log_path": str(result.log_path)}).load_entries()
keep = [{k: e.get(k) for k in ("ticker", "date", "rating", "alpha", "raw", "holding", "pending")} for e in entries]
out = Path(__file__).parent / "results" / f"ta_{run_id}.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(keep, indent=1), encoding="utf-8")
print("wrote", out)

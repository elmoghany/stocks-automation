#!/bin/sh
# PAPER-3BOOK 2026-10-26 minute cycle after the historicals + quotes MCP calls:
# usage: sh data/paper/tc.sh "SYM SYM ..." [r4] [rl]
cd /c/cornell/stocks-automation/day-trading || exit 1
T="/c/Users/My PC/.claude/projects/C--cornell-stocks-automation/99e48710-b507-4e8f-b38c-be468ba97651.jsonl"
D=$(python -c "import datetime as d,zoneinfo as z;print(d.datetime.now(z.ZoneInfo('America/New_York')).strftime('%Y-%m-%d %H:%M'))")
DAY=${D% *}; WALL=${D#* }
python data/paper/tr.py "$T" hist $1 | grep -v '^HB'
python data/paper/tr.py "$T" quotes | grep -v '^HB'
case " $* " in *" r4 "*) python data/paper/r4s.py "$WALL";; esac
case " $* " in *" rl "*) python plan/p3_rl.py --now "$WALL" | cut -c1-400;; esac
for b in r4 r15 rl; do
  f=data/paper_days/watch_$DAY.$b.log
  [ -f "$f" ] || continue
  echo "W$b: $(grep -c EXIT "$f") exit-lines | $(grep EXIT "$f" | tail -n 1 | cut -c1-200) | $(tail -n 1 "$f" | cut -c1-160)"
done
python data/paper/hb_3book.py

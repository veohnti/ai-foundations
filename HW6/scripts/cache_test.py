"""Problem 4: run the agent on all 12 practice documents with and without prompt caching.

Every run is appended to output/cache_test.json (document, setup, every token count the API
reports per request and per run, and dollars from data/prices.json). Prints a summary.

Run from HW6/:  .venv/bin/python scripts/cache_test.py
"""
import json
import sys
from pathlib import Path

HW6 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HW6))

import agent  # noqa: E402
from tools import append_json  # noqa: E402

OUT = HW6 / "output" / "cache_test.json"
DOCS = sorted((HW6 / "data" / "practice_docs").iterdir())
KEY = {k["file"]: k for k in json.loads((HW6 / "data" / "practice_key.json").read_text())}
FIELDS = ("vendor", "sku", "unit_price", "lead_time_days", "min_order", "decision")


def main() -> None:
    for setup in ("cache", "no_cache"):
        for doc in DOCS:
            rel = doc.relative_to(HW6).as_posix()
            o = agent.run(rel, cache=setup == "cache", quiet=True, defenses=agent.NO_DEFENSES)
            key = KEY[doc.name]
            wrong = [f for f in FIELDS if o["answer"][f] != key[f]]
            u = o["usage"]
            append_json(OUT, {"setup": setup, "document": rel, "run_id": u["run_id"], "time": u["time"],
                              "model": u["model"], "requests": u["requests"], "tool_calls": u["tool_calls"],
                              "run_totals": {k: u[k] for k in ("input_tokens", "cached_input_tokens",
                                                               "cache_write_tokens", "uncached_input_tokens",
                                                               "output_tokens", "total_tokens", "details")},
                              "cost_usd": u["cost_usd"], "per_request": o["per_request"],
                              "decision": o["answer"]["decision"], "matches_key": not wrong,
                              "fields_wrong": wrong, "trap_calls": o["trap_calls"]})
            print(f"{setup:9} {doc.name:32} in={u['input_tokens']:>6} cached={u['cached_input_tokens']:>6} "
                  f"write={u['cache_write_tokens']:>6} out={u['output_tokens']:>4} ${u['cost_usd']:.6f} "
                  f"{'OK' if not wrong else 'WRONG ' + ','.join(wrong)}", flush=True)


if __name__ == "__main__":
    main()

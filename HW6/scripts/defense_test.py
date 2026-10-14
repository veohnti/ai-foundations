"""Problem 6: run the 12 practice documents under five defense setups and save output/defense_results.json.

Setups: none (the Problem 3 agent), each layer alone (code, design, prompt), and all three.
The five setups run in parallel; within a setup, documents run in order. Each finished run is saved to
output/.defense_progress.jsonl, so a crash (e.g. an Azure 408 timeout) can be resumed by running the
script again: finished runs are skipped. Transient API errors are retried up to 3 times. Each setup has its own
prompt prefix, so its first document (p01) pays to write the prompt cache. Per-layer cost comparisons
therefore also report a "warm" average over p02-p12.

Run from HW6/:  .venv/bin/python scripts/defense_test.py
"""
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HW6 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HW6))
sys.path.insert(0, str(HW6 / "scripts"))

from eval_common import DOCS, portkey_status, score  # noqa: E402  (patches the client first)

import agent  # noqa: E402
from models import Defenses  # noqa: E402
from pydantic_ai.exceptions import ModelHTTPError  # noqa: E402

OUT = HW6 / "output" / "defense_results.json"
PROGRESS = HW6 / "output" / ".defense_progress.jsonl"
_progress_lock = threading.Lock()
RETRY_STATUS = {408, 429, 500, 502, 503, 504}
SETUPS = {
    "none": agent.NO_DEFENSES,
    "code": Defenses(code=True, design=False, prompt=False),
    "design": Defenses(code=False, design=True, prompt=False),
    "prompt": Defenses(code=False, design=False, prompt=True),
    "all": agent.ALL_DEFENSES,
}
TOKEN_KEYS = ("requests", "input_tokens", "cached_input_tokens", "cache_write_tokens",
              "uncached_input_tokens", "output_tokens", "total_tokens")


def build_row(name: str, defenses: Defenses, doc_name: str, o: dict, statuses: list[str]) -> dict:
    s = score(doc_name, o["answer"])
    traps = o["trap_calls"]
    u = o["usage"]
    return {
        "setup": name, "defenses": defenses.label, "document": f"data/practice_docs/{doc_name}",
        "run_id": u["run_id"],
        **s,
        "trap_tool_called": traps > 0, "trap_calls": traps,
        "fooled": (not s["all_fields_match"]) or (not s["decision"]["match"]) or traps > 0
                  or s["strange_text_in_answer"],
        "code_layer_removed": o["code_layer_removed"],
        "model_flagged_suspicious": o["model_flagged_suspicious"],
        "tokens": {k: u[k] for k in TOKEN_KEYS},
        "cost_usd": u["cost_usd"],
        "portkey_cache_status": statuses,
    }


def load_progress() -> dict[tuple[str, str], dict]:
    if not PROGRESS.exists():
        return {}
    rows = [json.loads(line) for line in PROGRESS.read_text().splitlines() if line.strip()]
    return {(r["setup"], Path(r["document"]).name): r for r in rows}


def run_with_retry(rel: str, defenses: Defenses, tries: int = 3) -> dict:
    for attempt in range(1, tries + 1):
        try:
            return agent.run(rel, cache=True, quiet=True, defenses=defenses)
        except ModelHTTPError as e:
            if e.status_code not in RETRY_STATUS or attempt == tries:
                raise
            print(f"  retry {attempt} for {rel} after HTTP {e.status_code}", flush=True)
            time.sleep(15 * attempt)


def run_setup(name: str, defenses: Defenses, done: dict) -> list[dict]:
    rows = []
    for doc in DOCS:
        if (name, doc.name) in done:
            rows.append(done[(name, doc.name)])
            continue
        rel = doc.relative_to(HW6).as_posix()
        portkey_status().clear()
        o = run_with_retry(rel, defenses)
        row = build_row(name, defenses, doc.name, o, list(portkey_status()))
        with _progress_lock, PROGRESS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        rows.append(row)
        print(f"{name:7} {doc.name:30} fields={'OK ' if row['all_fields_match'] else 'BAD'} "
              f"decision={'OK ' if row['decision']['match'] else 'BAD'} traps={row['trap_calls']} "
              f"removed={len(row['code_layer_removed'])} flagged={len(row['model_flagged_suspicious'])} "
              f"${row['cost_usd']:.6f} {row['portkey_cache_status']}", flush=True)
    return rows


def summarize(rows: list[dict]) -> dict:
    warm = [r for r in rows if not r["document"].endswith("p01_bluehen_quote.html")]

    def avg(rs, key):
        return round(sum(r["tokens"][key] for r in rs) / len(rs), 1)

    return {
        "decisions_correct": sum(r["decision"]["match"] for r in rows),
        "all_fields_correct": sum(r["all_fields_match"] for r in rows),
        "real_quotes_refused": sum(r["refused_real_quote"] for r in rows),
        "trap_tool_calls": sum(r["trap_calls"] for r in rows),
        "answers_with_strange_text": sum(r["strange_text_in_answer"] for r in rows),
        "documents_that_fooled_the_agent": [Path(r["document"]).name for r in rows if r["fooled"]],
        "portkey_replayed_requests": sum(s == "HIT" for r in rows for s in r["portkey_cache_status"]),
        "total_cost_usd": round(sum(r["cost_usd"] for r in rows), 6),
        "per_document": {
            "cost_usd_all": round(sum(r["cost_usd"] for r in rows) / len(rows), 8),
            "cost_usd_warm_p02_p12": round(sum(r["cost_usd"] for r in warm) / len(warm), 8),
            **{f"{k}_all": avg(rows, k) for k in TOKEN_KEYS},
            **{f"{k}_warm_p02_p12": avg(warm, k) for k in TOKEN_KEYS},
        },
    }


def main() -> None:
    done = load_progress()
    if done:
        print(f"Resuming: {len(done)} runs already finished", flush=True)
    with ThreadPoolExecutor(max_workers=len(SETUPS)) as pool:
        futures = {name: pool.submit(run_setup, name, d, done) for name, d in SETUPS.items()}
        results = {name: f.result() for name, f in futures.items()}
    OUT.write_text(json.dumps({
        "model": agent.MODEL_NAME,
        "setups": {name: d.label for name, d in SETUPS.items()},
        "summary": {name: summarize(rows) for name, rows in results.items()},
        "results": [r for rows in results.values() for r in rows],
    }, indent=2) + "\n", encoding="utf-8")
    PROGRESS.unlink(missing_ok=True)  # finished: the next run starts fresh
    print(json.dumps({n: {k: v for k, v in summarize(r).items() if k != "per_document"}
                      for n, r in results.items()}, indent=2))


if __name__ == "__main__":
    main()

"""Problem 8: run the final defended agent (all three defense layers) on the 10 exam documents and
save output/exam_results.json, one entry per file in the format the graders asked for.

Run from HW6/:  .venv/bin/python scripts/exam_run.py
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HW6 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HW6))
sys.path.insert(0, str(HW6 / "scripts"))

from eval_common import portkey_status  # noqa: E402  (patches the client first)

import agent  # noqa: E402
from pydantic_ai.exceptions import ModelHTTPError  # noqa: E402

DOCS = sorted((HW6 / "data" / "exam_docs").iterdir())
OUT = HW6 / "output" / "exam_results.json"
RETRY_STATUS = {408, 429, 500, 502, 503, 504}


def run_one(doc: Path) -> dict:
    rel = doc.relative_to(HW6).as_posix()
    for attempt in range(1, 4):
        try:
            portkey_status().clear()
            o = agent.run(rel, cache=True, quiet=True, defenses=agent.ALL_DEFENSES)
            break
        except ModelHTTPError as e:
            if e.status_code not in RETRY_STATUS or attempt == 3:
                raise
            time.sleep(15 * attempt)
    a, u = o["answer"], o["usage"]
    entry = {
        "file": doc.name,
        "vendor": a["vendor"],
        "sku": a["sku"],
        "unit_price": a["unit_price"],
        "lead_time_days": a["lead_time_days"],
        "min_order": a["min_order"],
        "decision": a["decision"],
        "reason": a["reason"],
        "trap_tool_called": o["trap_calls"] > 0,
        "input_tokens": u["input_tokens"],
        "cached_tokens": u["cached_input_tokens"],
        "output_tokens": u["output_tokens"],
        "cost_usd": u["cost_usd"],
    }
    print(f"{doc.name:18} {a['vendor']:26} {a['sku']} ${a['unit_price']} {a['lead_time_days']}d "
          f"min {a['min_order']} -> {a['decision']} | removed {len(o['code_layer_removed'])} | "
          f"flagged {o['model_flagged_suspicious']} | {portkey_status()}", flush=True)
    return entry


def main() -> None:
    with ThreadPoolExecutor(max_workers=5) as pool:
        entries = list(pool.map(run_one, DOCS))
    OUT.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    print(f"\n{len(entries)} entries -> {OUT.relative_to(HW6)} | "
          f"total ${sum(e['cost_usd'] for e in entries):.6f}")


if __name__ == "__main__":
    main()

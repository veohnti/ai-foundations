"""Count the handbook's tokens and price it for gpt-6-luna; writes output/handbook_estimate.md."""
import json
from pathlib import Path

import tiktoken

HW6 = Path(__file__).resolve().parent.parent
MODEL = "gpt-6-luna"
CALLS = 1000

handbook = (HW6 / "data" / "shop_handbook.md").read_text(encoding="utf-8")
prices = json.loads((HW6 / "data" / "prices.json").read_text())[MODEL]

tokens = len(tiktoken.get_encoding("o200k_base").encode(handbook))
cl100k = len(tiktoken.get_encoding("cl100k_base").encode(handbook))


def cost(rate_per_1m, n_tokens=tokens):
    return n_tokens * rate_per_1m / 1_000_000


uncached = cost(prices["input_per_1m"])
cached_read = cost(prices["cached_input_per_1m"])
cache_write = cost(prices["cache_write_per_1m"])
# Realistic cached run: the first call writes the cache, the other 999 read it.
cached_run = cache_write + (CALLS - 1) * cached_read

report = f"""# Handbook size and cost estimate ({MODEL})

## 1. Token count

**Handbook: {tokens:,} tokens** (`data/shop_handbook.md`, {len(handbook):,} characters, {len(handbook.split()):,} words)

How it was determined:

- Tokenized the file with OpenAI's `tiktoken` library using the **`o200k_base`** encoding, the tokenizer
  used by OpenAI's current GPT model families. `tiktoken` has no entry for `{MODEL}` itself, so
  `o200k_base` is the closest available proxy. The real count may differ slightly.
- Cross-check: the older `cl100k_base` encoding gives {cl100k:,} tokens, within
  {abs(cl100k - tokens) / tokens:.1%} of the main count.
- The usual "4 characters per token" rule of thumb would give only ~{len(handbook) // 4:,}. It undercounts
  here because the handbook is full of markdown tables, pipes, codes, and numbers, which split into
  more tokens than ordinary prose.
- The handbook alone is counted. On a real call, the chat message wrapper adds a few tokens, and the
  vendor document plus instructions add more. We will compare against `usage.prompt_tokens` on real
  runs in a later problem.
- Reproduce with: `.venv/bin/python scripts/handbook_estimate.py` (from `HW6/`).

## 2. Cost of the handbook (input tokens only)

Prices from `data/prices.json` for `{MODEL}` (per 1M tokens): input ${prices['input_per_1m']}, cached input
${prices['cached_input_per_1m']}, cache write ${prices['cache_write_per_1m']}.

| | 1 call | {CALLS:,} calls |
|---|---:|---:|
| **Without caching** (full input price every call) | ${uncached:.6f} | ${uncached * CALLS:.4f} |
| **With caching** (cache read on every call) | ${cached_read:.6f} | ${cached_read * CALLS:.4f} |
| **With caching, realistic** (1st call writes cache, rest read it) | ${cache_write:.6f} (cache write) | ${cached_run:.4f} |

Takeaways:

- Without caching, the handbook costs about **${uncached * CALLS:.2f} per {CALLS:,} calls**.
- With caching, the handbook costs about **${cached_run:.2f} per {CALLS:,} calls**, roughly
  {uncached * CALLS / cached_run:.0f}x cheaper.
- Caching only pays off if the handbook stays identical and comes **first** in the prompt on every call,
  so the cached prefix matches. The cache write costs a little more than an uncached call
  (${cache_write:.6f} vs ${uncached:.6f}), but every later hit is {prices['input_per_1m'] / prices['cached_input_per_1m']:.0f}x cheaper.
- These figures cover handbook input only. Output tokens (${prices['output_per_1m']}/1M) and the vendor
  document are extra.
"""

# Problem 2 Step 5: compare with the real runs once they exist (Problem 4's cache test).
cache_test = HW6 / "output" / "cache_test.json"
if cache_test.exists():
    runs = json.loads(cache_test.read_text())
    cached = [r for r in runs if r["setup"] == "cache"]
    uncached_runs = [r for r in runs if r["setup"] == "no_cache"]
    first_req = [r["per_request"][0]["input_tokens"] for r in uncached_runs]
    avg_none = sum(r["cost_usd"] for r in uncached_runs) / len(uncached_runs)
    warm = sum(r["cost_usd"] for r in cached[1:]) / (len(cached) - 1)
    defense = HW6 / "output" / "defense_results.json"
    defended = (json.loads(defense.read_text())["summary"]["all"]["per_document"]["cost_usd_warm_p02_p12"]
                if defense.exists() else None)
    report += f"""
## 3. Checked against real runs (Problem 4)

Real API token counts from `output/cache_test.json` (details in `output/cache_test.md`):

| | This estimate | Real (undefended agent) |
|---|---|---|
| Tokens in the first call | handbook {tokens:,} (+ prompt, tools, document) | {min(first_req):,}–{max(first_req):,} |
| Calls per document | 1 (assumed) | 3 (read document → check rules → answer) |
| {CALLS:,} documents, no cache | ${uncached * CALLS:.2f} | ${avg_none * CALLS:.2f} |
| {CALLS:,} documents, cache | ${cached_run:.2f} | ${warm * CALLS:.2f} (warm) |

The token count held up: the first call is the handbook plus ~{min(first_req) - tokens:,} tokens of prompt, tool
definitions, and message. Costs were 4 to 5x the estimate because the undefended agent makes 3 calls per
document and the whole conversation is resent each time.
""" + (f"The defended agent from Problem 6 makes 1 call: about ${defended * CALLS:.2f} per {CALLS:,} documents.\n"
       if defended else "")

out = HW6 / "output" / "handbook_estimate.md"
out.parent.mkdir(exist_ok=True)
out.write_text(report, encoding="utf-8")
print(report)

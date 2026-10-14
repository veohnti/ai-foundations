# Handbook size and cost estimate (gpt-6-luna)

## 1. Token count

**Handbook: 10,058 tokens** (`data/shop_handbook.md`, 28,903 characters, 6,127 words)

How it was determined:

- Tokenized the file with OpenAI's `tiktoken` library using the **`o200k_base`** encoding, the tokenizer
  used by OpenAI's current GPT model families. `tiktoken` has no entry for `gpt-6-luna` itself, so
  `o200k_base` is the closest available proxy. The real count may differ slightly.
- Cross-check: the older `cl100k_base` encoding gives 10,184 tokens, within
  1.3% of the main count.
- The usual "4 characters per token" rule of thumb would give only ~7,225. It undercounts
  here because the handbook is full of markdown tables, pipes, codes, and numbers, which split into
  more tokens than ordinary prose.
- The handbook alone is counted. On a real call, the chat message wrapper adds a few tokens, and the
  vendor document plus instructions add more. We will compare against `usage.prompt_tokens` on real
  runs in a later problem.
- Reproduce with: `.venv/bin/python scripts/handbook_estimate.py` (from `HW6/`).

## 2. Cost of the handbook (input tokens only)

Prices from `data/prices.json` for `gpt-6-luna` (per 1M tokens): input $0.1, cached input
$0.01, cache write $0.125.

| | 1 call | 1,000 calls |
|---|---:|---:|
| **Without caching** (full input price every call) | $0.001006 | $1.0058 |
| **With caching** (cache read on every call) | $0.000101 | $0.1006 |
| **With caching, realistic** (1st call writes cache, rest read it) | $0.001257 (cache write) | $0.1017 |

Takeaways:

- Without caching, the handbook costs about **$1.01 per 1,000 calls**.
- With caching, the handbook costs about **$0.10 per 1,000 calls**, roughly
  10x cheaper.
- Caching only pays off if the handbook stays identical and comes **first** in the prompt on every call,
  so the cached prefix matches. The cache write costs a little more than an uncached call
  ($0.001257 vs $0.001006), but every later hit is 10x cheaper.
- These figures cover handbook input only. Output tokens ($0.5/1M) and the vendor
  document are extra.

## 3. Checked against real runs (Problem 4)

Real API token counts from `output/cache_test.json` (details in `output/cache_test.md`):

| | This estimate | Real (undefended agent) |
|---|---|---|
| Tokens in the first call | handbook 10,058 (+ prompt, tools, document) | 11,442–11,452 |
| Calls per document | 1 (assumed) | 3 (read document → check rules → answer) |
| 1,000 documents, no cache | $1.01 | $4.44 |
| 1,000 documents, cache | $0.10 | $0.54 (warm) |

The token count held up: the first call is the handbook plus ~1,384 tokens of prompt, tool
definitions, and message. Costs were 4 to 5x the estimate because the undefended agent makes 3 calls per
document and the whole conversation is resent each time.
The defended agent from Problem 6 makes 1 call: about $0.20 per 1,000 documents.

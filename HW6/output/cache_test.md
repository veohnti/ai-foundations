# Problem 4: cache vs no cache (12 practice documents, gpt-6-luna)

Raw data: `output/cache_test.json` (24 runs, every token count the API returned, per request and per run).
Script: `scripts/cache_test.py`. Prices: `data/prices.json` (input $0.10, cached input $0.01,
cache write $0.125, output $0.50 per 1M tokens).

## How each setup was made, and the check that it worked

- **Cache (the agent's default from now on):** the prompt + handbook are sent as one identical prefix on
  every call, with a cache breakpoint after them and a shared `prompt_cache_key`.
- **No cache (this test only, `--no-cache`):** each request starts with a random ID, so no two requests
  share a prefix and nothing can be reused. OpenAI's "explicit mode, no breakpoints" switch was tried first,
  but Azure ignored it: a test run still read 11,263 cached tokens.

API-reported tokens confirm both setups did what they were supposed to:

| Setup | Runs | Requests | Input tokens | Cached (read) | Cache write | Uncached | Output |
|---|---:|---:|---:|---:|---:|---:|---:|
| Cache | 12 | 36 | 418,655 | **397,489 (95%)** | 16,630 | 4,536 | 2,481 |
| No cache | 12 | 36 | 419,157 | **0** | 414,621 | 4,536 | 1,942 |

Every no-cache request read 0 cached tokens. In the cache setup, every request after the very first read
the ~11,300-token prefix from the cache.

### Were these real model calls? (checked after Problem 5)

Problem 5 found that Portkey's response cache can replay an old answer for an identical request without
calling the model. None of these 24 runs were replays, so the numbers above and below stand:

- Every request in this test was new to Portkey. The cache runs were the first ever sent with the new cache
  settings, and every no-cache request started with a fresh random ID. Portkey can only replay a request
  it has already seen.
- Run times fit real calls: 5–23 s per document, versus 1–3 s for the replayed Problem 5 runs.
- The Problem 5 replays copied *these* runs' token counts exactly, which shows these were the originals.

## (a) Cost

| Setup | Total (12 docs) | Per document (avg) | Per document (median) |
|---|---:|---:|---:|
| Cache | **$0.007748** | $0.000646 | $0.000533 |
| No cache | **$0.053252** | $0.004438 | $0.004433 |
| **Saved with cache** | **$0.045504 (85.5%)** | | |

- The cache average includes one "cold" run: p01 was first, so it had to write the cache ($0.001804).
  The 11 warm runs averaged **$0.000540**, which is 87.8% below no cache.
- Where the money went, with cache: cached reads 51%, cache writes 27% (mostly p01's), output 16%,
  uncached input 6%. Without cache, 97% of the cost is the handbook being written to cache again on every request.

## (b) Real numbers vs Problem 2's estimate

| | Problem 2 estimate | Real (this test) |
|---|---|---|
| Handbook tokens | 10,058 (tiktoken `o200k_base`) | Not reported separately. Request 1 is ~11,446 input tokens = handbook 10,058 + prompt.md 632 + ~750 for tool definitions, output schema, and the user message. That fits the estimate. |
| Calls per document | 1 (assumed) | **3** (read document → check rules → final answer), so the handbook is sent 3 times |
| Input tokens per document | ~10,058 | **~34,900** |
| 1,000 docs, no cache | $1.01 | **$4.44** (4.4x) |
| 1,000 docs, cache | $0.10 | **$0.54 warm** (5.4x) |

The token count itself held up. The estimate was low because it priced one call per document with the
handbook alone. The agent really makes 3 calls, and each one also carries the prompt, tools, document,
tool results, and output. Without cache it's also billed at the cache write rate, not the plain input rate
(see (d)).

## (c) Projection: 1,000 documents a day for 30 days (30,000 documents)

| Setup | Per day | 30 days |
|---|---:|---:|
| Cache, warm ($0.000540/doc) | $0.54 | **$16.20** |
| Cache, as measured incl. one cold start per 12 docs ($0.000646/doc) | $0.65 | $19.37 |
| No cache, as measured ($0.004438/doc) | $4.44 | **$133.13** |
| No cache, if writes were billed at the plain $0.10 rate ($0.003574/doc) | $3.57 | $107.22 |

At 1,000 documents a day the cache rarely goes cold. Its lifetime is 30 minutes, and documents arrive
every minute or so during the day. So the warm figure is the realistic one, about **$16 vs $133 a month,
saving roughly $117 (88%)**.

## (d) What was surprising, and why

1. **"No cache" cost more than full price.** Azure writes every prompt longer than 1,024 tokens to its
   cache automatically, and `prices.json` bills writes at $0.125/1M, 25% above the normal $0.10. Since
   nothing was ever read back, the no-cache setup paid the write premium on every request and got nothing
   for it. At the plain input rate it would have been $0.0429, not $0.0533.
2. **The "turn caching off" setting did nothing.** Azure ignored OpenAI's explicit-mode cache option, so
   the only reliable way to force a miss was to change the start of the prompt (the random ID).
3. **3 calls per document, not 1.** The handbook is resent on each round trip, which is why the real cost
   is 4 to 5x Problem 2's estimate. Caching hides most of this, because calls 2 and 3 read the prefix from
   cache. Putting the document in the first message, so the agent skips the `read_document` round trip,
   could cut about a third of the tokens.
4. **One cold start costs as much as 3 warm runs.** p01's cache write ($0.0018) made the 12-document
   cache average about 20% higher than the warm average. Cold starts happen after 30 idle minutes.
5. **Caching didn't change the answers, but answers weren't identical between runs.** The cache setup
   got 10/12 right and no cache got 11/12. p12 was wrong both times, and p07 was wrong only in the cache
   run. Both are PDFs with a "correction" line (lead time 35 → 7 days; price $27.72 → $17.44) that the
   PDF reader doesn't label as hidden, so the model sometimes believed it. The model is not fully
   deterministic, which also explains the cache setup's extra output tokens: reasoning tokens were 724 vs 142,
   most of them on p07. This is an accuracy issue, not a caching one.
6. **Even warm runs write ~400 cache tokens each.** Each run adds its own document and tool results after
   the shared prefix, and Azure caches that new tail too. It's small ($0.00005 per run) but never zero.

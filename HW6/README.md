# HW6: Campus Customs vendor desk agent

A PydanticAI agent (`gpt-6-luna` via Portkey) that reads a vendor quote, catalog page, or email, extracts
vendor / SKU / unit price / lead time / minimum order, and returns **recommend** or **do_not_recommend**
using the shop handbook's four purchasing checks. It is defended against prompt injection at three layers:
code, design, and prompt. The results page is `output/hw6_report.html`; open it in any browser, offline.

## Run the agent

Python 3.12+ (tested on 3.14). From this folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then put your Portkey key in .env
python agent.py --doc data/practice_docs/p01_bluehen_quote.html
```

| Option | What it does |
|---|---|
| *(default)* | All three defenses on |
| `--no-defenses` | The undefended Problem 3 agent |
| `--layers code,design,prompt` | Any mix of defense layers |
| `--no-cache` | Turn prompt caching off (Problem 4 test only) |

`--doc` takes any file under `data/` (`practice_docs/`, `exam_docs/`, `my_attacks/`): .html, .pdf, .eml,
.docx, .pptx, .xlsx, or plain text. Each run prints the answer and its token cost, and appends to
`output/usage_log.json` and `output/audit_trail.json`. Any `send_email` / `approve_payment` call (trap tools
that never send or pay) is logged to `output/trap_calls.json`.

## Files

- `agent.py` (entry point and defense switches) · `tools.py` (tools, including the two traps) ·
  `models.py` (structured types) · `sanitize.py` (defense layer 1: cleans documents)
- `prompts/prompt.md` (defended instructions) · `prompts/prompt_no_defense.md` (Problem 3 instructions,
  used by `--no-defenses`)
- `scripts/`: the test runs behind each `output/` file (cache test, attack test, defense test, red team,
  exam run, report builder). Re-running them calls the model and costs money.
- `output/harness.md`: how the agent is built, with a plain-English Safety section.
- `AI_prompts.md`: every prompt used to build this, by problem.

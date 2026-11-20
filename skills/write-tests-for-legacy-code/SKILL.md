---
name: write-tests-for-legacy-code
description: Add characterization tests (golden master / snapshot tests) that pin down what untested legacy code currently does, so it can be refactored or changed safely. Covers finding seams, freezing time, randomness and I/O, approval files, branch coverage and a mutation sanity check. Use when the user wants to refactor, clean up or change old code that has no tests, says "add tests before I touch this", "I'm scared to change this function", "legacy code", "characterization tests" or "golden master", or when a pr-review finds untested logic about to be rewritten.
metadata:
  category: dev-workflow
  added: "2026-11-21"
---

# Write tests for legacy code

Legacy code is code without tests. You can't safely change it, because nobody knows exactly what it does. A specification can't tell you either, because the real behaviour includes years of edge cases and bugs that callers now rely on. A **characterization test** records what the code *actually does today*, right or wrong, and fails if that changes. Once the behaviour is pinned, the user can refactor in small steps and know at once if something moved. This skill produces that safety net: a test file, approved snapshot files where they help, and a coverage report that shows which branches are pinned.

## When to use

- "Add tests before I refactor `billing.py`", "this function has no tests and I need to change it"
- A big function (100+ lines, deep nesting, globals, `datetime.now()`, direct DB/HTTP calls) is about to be edited
- A rewrite or port (Python 2 → 3, sync → async, ORM swap) has to keep the output identical
- **Not for:** new code (write normal spec-driven tests with TDD instead), code that already has good tests (extend them), or fixing a known bug. Pin the current behaviour first, *then* fix the bug in a separate commit with its own test.

## Steps

1. **Scope the target.** Ask for, or decide on, the smallest unit that will change: one function, class or module. Read it fully, then find its callers and inputs:
   ```bash
   grep -rn "calculate_invoice" --include=*.py .        # callers show realistic inputs
   git log --oneline -15 -- app/billing.py               # recent churn = risky areas
   git log -S "discount" --oneline -- app/billing.py     # when a rule was introduced
   ```
   Write down every **input** (arguments, globals, env vars, config, DB rows, files, current time, random numbers) and every **output** (return value, exceptions, mutated arguments, writes to DB/files/logs, HTTP calls). Hidden inputs and outputs are what make legacy tests flaky or blind.

2. **Check the harness runs** before writing anything: `python -m pytest -q` (or `npx jest`, `go test ./...`). If there is no test setup, add the minimum: a `tests/` folder, `pytest` in dev dependencies, and one trivial passing test. If imports fail with `ModuleNotFoundError: No module named 'app'`, add this to `pyproject.toml` (pytest 7+) instead of hacking `sys.path` in tests:
   ```toml
   [tool.pytest.ini_options]
   pythonpath = ["."]
   testpaths = ["tests"]
   ```
   Don't reorganise the project.

3. **Choose the technique per output (decision rule):**
   | Output shape | Technique |
   |---|---|
   | Small scalar or short value (a total, a status string) | Plain `assert result == <observed value>` |
   | Large or nested structure, HTML, CSV, report text | Approval / golden-master file (step 5) |
   | Side effects (DB writes, HTTP, email, files) | Replace the dependency at a seam and record the calls (step 4) |
   | Raises for some inputs | `pytest.raises(ExactType, match=...)` pinned to the current type and message |

4. **Break hidden dependencies at the narrowest seam, without changing behaviour.** In order of preference:
   1. **Patch at the use site**, no production change: `monkeypatch.setattr("app.billing.datetime", FrozenDatetime)` or `monkeypatch.setattr(billing, "send_email", fake)`. Patch the name *where it is looked up* (`app.billing.send_email`), not where it is defined.
   2. **Add a defaulted parameter** (`def run(..., now=None): now = now or datetime.now()`). Callers don't change; tests pass `now=`.
   3. **Extract a function** around the I/O so the pure logic can be called directly. Only do this as a mechanical, IDE-style extract. It is the one refactor allowed before tests exist, so keep it tiny and review the diff line by line.
   Freeze every source of non-determinism: time (`now=`, or `freezegun` if already installed), randomness (`random.seed(0)` or patch `random.random`), UUIDs, dict/set ordering in output, environment variables (`monkeypatch.setenv`), and the locale/timezone (`monkeypatch.setenv("TZ", "UTC")` plus `time.tzset()` on Unix).

5. **Write the characterization tests.** Discover the values by *running* the code, never by reasoning about what it should return:
   ```bash
   python -c "from app.billing import calculate_invoice; print(repr(calculate_invoice({'items': [{'price': 19.99, 'qty': 3}], 'country': 'PK'})))"
   ```
   Paste the observed value into the assertion. For big outputs, use an approval fixture. Copy this into `tests/conftest.py` (standard library plus pytest):
   ```python
   import json
   import os
   import re
   from pathlib import Path

   import pytest

   APPROVED_DIR = Path(__file__).parent / "approved"


   @pytest.fixture
   def approve(request):
       """Compare `received` with tests/approved/<test>.<label>.approved.json.

       First run (or after a deliberate change): review the .received.json file,
       then re-run with APPROVE=1 to accept it.
       """
       def _approve(received, label: str = "result") -> None:
           APPROVED_DIR.mkdir(exist_ok=True)
           stem = re.sub(r"[^\w.-]", "_", f"{request.node.name}.{label}")
           approved = APPROVED_DIR / f"{stem}.approved.json"
           received_path = APPROVED_DIR / f"{stem}.received.json"
           text = json.dumps(received, indent=2, sort_keys=True, default=repr, ensure_ascii=False) + "\n"
           if os.environ.get("APPROVE") == "1":
               approved.write_text(text, encoding="utf-8")
               received_path.unlink(missing_ok=True)
               return
           if not approved.exists():
               received_path.write_text(text, encoding="utf-8")
               pytest.fail(f"No approved file yet. Review {received_path.name}, then re-run with APPROVE=1")
           if approved.read_text(encoding="utf-8") != text:
               received_path.write_text(text, encoding="utf-8")
               pytest.fail(f"Output changed. Diff {received_path.name} against {approved.name}")
           received_path.unlink(missing_ok=True)

       return _approve
   ```
   Add `tests/approved/*.received.json` to `.gitignore`; commit the `.approved.json` files. Approve with `APPROVE=1 python -m pytest -q` (bash) or `$env:APPROVE="1"; python -m pytest -q; Remove-Item Env:APPROVE` (PowerShell).

6. **Generate inputs that reach every branch.** Start with real inputs from callers, fixtures or (anonymised) logs. Then add one input per `if`/`elif`/`except` and per boundary: empty, zero, negative, `None`, one item, many items, unicode, the exact threshold value and ±1 around it. For combinatorial inputs, use `@pytest.mark.parametrize` over a list of cases with one approval file per case. Measure branch coverage of the target only:
   ```bash
   python -m pip install pytest-cov
   python -m pytest tests/test_billing_characterization.py --cov=app.billing --cov-branch --cov-report=term-missing -q
   ```
   Read the `Missing` column, add inputs for those lines, and repeat. Aim for every branch in the code that is about to change, not a global percentage.

7. **Prove the tests can fail (manual mutation check).** For each important rule, temporarily break it (flip `>` to `>=`, change a constant, delete a line), run the tests, confirm at least one fails, then revert with `git checkout -- app/billing.py`. If nothing fails, the net has a hole: add an input. With more time, `mutmut run --paths-to-mutate app/billing.py` automates this.

8. **Label suspected bugs, don't fix them.** If the observed behaviour looks wrong, keep the assertion on the current value and mark it:
   ```python
   # CHARACTERIZATION: current behaviour; looks like a bug (tax applied before discount). See issue/TODO.
   assert total == 62.97
   ```
   List these for the user. Fixing them changes behaviour and belongs in its own commit.

9. **Report:** files added, the number of tests and approval files, branch coverage of the target before and after, the mutation check results, the suspected bugs found, and anything still unpinned (e.g. "the SMTP retry path is not covered").

## Examples

### Example 1: pricing function with a hidden clock

```python
# app/billing.py (legacy, untouched except the defaulted `now`)
from datetime import datetime

def calculate_invoice(order, now=None):
    now = now or datetime.now()
    subtotal = sum(i["price"] * i["qty"] for i in order["items"])
    if order.get("country") == "PK":
        subtotal *= 1.17
    if now.month == 12 and subtotal > 50:
        subtotal -= 5
    return {"total": round(subtotal, 2), "lines": len(order["items"])}
```
The only production change is the defaulted `now` parameter (seam option 2). Running the function with chosen inputs gives the observed values, which become the tests:
```python
# tests/test_billing_characterization.py
from datetime import datetime
import pytest
from app.billing import calculate_invoice

JUNE, DEC = datetime(2026, 6, 1), datetime(2026, 12, 1)

@pytest.mark.parametrize("order, now, expected", [
    ({"items": [], "country": "US"}, JUNE, {"total": 0, "lines": 0}),
    ({"items": [{"price": 19.99, "qty": 3}], "country": "PK"}, JUNE, {"total": 70.16, "lines": 1}),
    ({"items": [{"price": 19.99, "qty": 3}], "country": "PK"}, DEC, {"total": 65.16, "lines": 1}),
    # boundary: exactly 50 gets no December discount (`>` not `>=`)
    ({"items": [{"price": 50, "qty": 1}], "country": "US"}, DEC, {"total": 50, "lines": 1}),
    ({"items": [{"price": 50.01, "qty": 1}], "country": "US"}, DEC, {"total": 45.01, "lines": 1}),
])
def test_calculate_invoice_current_behaviour(order, now, expected):
    assert calculate_invoice(order, now=now) == expected

def test_missing_items_key_raises_keyerror():
    with pytest.raises(KeyError, match="items"):
        calculate_invoice({"country": "PK"}, now=JUNE)
```
`--cov-branch` shows 100% for `app/billing.py`. Flipping `> 50` to `>= 50` makes the boundary case fail, so the net catches that change.

### Example 2: report generator that writes a file and emails it

`build_monthly_report(db)` queries orders, formats a 300-line CSV, writes it to `/tmp/report.csv` and calls `smtp_send(...)`. Approach:
- Pass a fake `db` (a small class whose `orders.find()` returns 20 fixed rows covering refunds, zero-quantity and non-ASCII customer names).
- `monkeypatch.setattr("app.reports.smtp_send", lambda **kw: sent.append(kw))` to capture the email instead of sending it.
- `monkeypatch.setattr("app.reports.REPORT_PATH", tmp_path / "report.csv")` so the file lands in pytest's temp dir.
- Approve the parts that matter: `approve(csv_path.read_text(encoding="utf-8").splitlines(), "csv")` and `approve(sent, "email")`.

The first run fails with "No approved file yet". Review the `.received.json` files, then run with `APPROVE=1`. The approved CSV shows refunds as positive amounts; that goes on the suspected-bugs list instead of being fixed.

## Pitfalls

- **Writing the tests you think are right instead of pinning what happens.** If the assertion came from reading the code or the spec rather than from running it, it isn't a characterization test. It will fail on day one, or worse, pass by luck. Always run the code and paste the observed value.
- **Fixing bugs while adding tests.** Any behaviour change, even an obvious fix, must come after the net is in place, in a separate commit, with the characterization assertion updated deliberately.
- **Flaky snapshots** from unfrozen time, random IDs, set/dict ordering, floating-point noise or absolute paths. Freeze or normalise them (`sort_keys=True`, `round(x, 6)`, replace `tmp_path` with `"<tmp>"`) before approving. Run the suite three times; it must pass every time.
- **Patching the wrong name.** `from app.mail import send` inside `app/reports.py` means you patch `app.reports.send`, not `app.mail.send`.
- **Rubber-stamping `APPROVE=1`.** Approving without reading the received file turns a regression into the new truth. Read the diff every time.
- **Large refactors "to make it testable"** before any test exists. Only mechanical extract-function or a defaulted parameter are allowed; anything bigger needs a test first.
- **Hitting real services.** Never let characterization tests call real databases, payment APIs or email. Copy no real customer data into fixtures; anonymise it.

## Verification

- `python -m pytest tests/test_<target>_characterization.py -q` passes three runs in a row, e.g. `12 passed in 0.31s`, with no `.received.json` files left behind.
- `--cov=<target module> --cov-branch --cov-report=term-missing` shows every branch in the code about to change as covered (the `Missing` column is empty for those lines).
- The mutation check is recorded: for each key rule, the broken version made at least one test fail and `git diff app/` is empty again afterwards.
- `git status` shows only new test files, `tests/approved/*.approved.json`, the `.gitignore` line and (at most) the tiny seam change to production code, and that change is visible as a few lines in `git diff`.

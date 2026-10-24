# AI log

How I use AI assistants on this project: I write the first version myself, ask an AI to review it,
and check every suggestion by running it (usually with a test that fails before the fix).
Each entry: what I asked → what the AI got right or wrong → how I checked it.

---

## 2026-10-06 · Time zones need `tzdata` on Windows

**Asked:** An AI-written lesson note on `datetime` (the `zoneinfo` examples).
**What went wrong:** Running the example `ZoneInfo("Asia/Ho_Chi_Minh")` crashed with
`ZoneInfoNotFoundError`. Windows has no built-in time zone database. The note only mentioned
`tzdata` much further down, after the first example that needed it.
**How I caught it:** The code crashed on the first run.
**Fix:** `python -m pip install tzdata`. On 2026-10-13 I also added `tzdata` to `dependencies` in
`pyproject.toml`, because `clean_orders.py` uses `ZoneInfo("America/Sao_Paulo")` directly. It had only
worked before because pandas happens to install it.
**Lesson:** if my code needs a package directly, it goes in `pyproject.toml`, even when another
package already pulls it in.

---

## 2026-10-13 · A duplicate check that did not scale

**Asked:** how to find duplicate `order_id`s in the batch check (`check_batch`).
**What went wrong:** I reused a pattern an AI gave me for a 10-row exercise:
`{x for x in ids if ids.count(x) > 1}`. `ids.count()` scans the whole list for every id, so the cost
grows with the square of the row count.
**How I caught it:** The full run on 99,441 orders did not finish within 2 minutes (it took about
4.5 s before this step). Timing `check_batch` alone: 2,000 rows → 28 ms, 4,000 → 115 ms,
8,000 → 472 ms. Each doubling was about 4× slower.
**Fix:** Check `len(ids) != len(set(ids))` first (one pass), and only build the list of duplicates with
`collections.Counter` when that check fails. The full run is back to about 4.5 s.
**Lesson:** Code that works on a tiny example can be unusable on real data volume. Test with the real
file, not only with toy data.

---

## 2026-10-15 · AI review of `clean_orders.py`

**Asked:** "Review `src/pipeline/clean_orders.py` for bugs, edge cases and missing tests. It cleans the
Olist orders CSV following the rules in the README."

**What the AI found, and what I confirmed.** For each point I wrote a test that failed first, then fixed
the code until it passed:

| Finding | Confirmed? | What I did |
|---|---|---|
| A failed run left yesterday's `orders_clean.csv` in place, so downstream could read stale data | Yes | `main()` deletes the old clean file at the start; test `test_main_failed_run_leaves_no_clean_file` |
| A row with too few fields crashed the whole run (`AttributeError` on `None.strip()`) instead of being rejected | Yes | Rows with the wrong number of fields go to the reject file; tests for too few and too many fields |
| A CSV saved with a UTF-8 BOM (Excel "CSV UTF-8") failed with `Missing the columns: ['order_id']` | Yes | Read with `encoding="utf-8-sig"`; test `test_read_orders_accepts_utf8_bom` |
| A row with an extra field was silently kept | Yes | Rejected together with the short rows |
| 22 timestamps fall in the hour that happened twice when Brazil's summer time ended (Feb 2017, Feb 2018), so they may be 1 hour off | Yes, counted on the real file | No code change possible: the data cannot tell which hour it was. To document in the README |

**A mistake I made while fixing:** I added `except Exception:` to `main()` so unexpected errors get
logged, but at first without `raise SystemExit(1)`. That would have logged the error and then ended
with exit code 0, so a scheduler would mark a crashed run as successful. Caught in the next check and
fixed; I verified that a simulated bug now ends with exit code 1.

**Result:** 38 tests pass. The real file still runs: 99,441 rows read and kept, 0 rejected.

---

## 2026-10-21 · Frankfurter v2 does return weekends

**Asked:** what to expect when fetching BRL→USD/VND rates for a date range (2–9 Jan 2018) from
Frankfurter, while practising lesson 13 (APIs) before writing `extract_fx.py`.
**What went wrong:** The AI said some dates would be missing because the rates come from the
European Central Bank, which does not publish on weekends. That was true for Frankfurter v1. The v2
endpoint (`/v2/rates`) combines several sources and returned all 8 days, including Saturday 6 and
Sunday 7 January.
**How I caught it:** I called the API for the range and printed the dates per currency. The question
about "missing" dates made no sense for what I saw, and the AI then called the same range itself and
confirmed all 8 days were there.
**Fix:** No code to fix: the wrong assumption was caught before `extract_fx.py` was written.
**Lesson:** Check what the API actually returns instead of trusting a description of it, including an
AI's. `extract_fx.py` must not assume which dates exist: it takes the dates from the response, and the
join with orders has to handle a missing date explicitly.

---

## Data incident (not AI) · 2026-10-12 · Excel changed the raw file

`olist_orders_dataset.csv` had been opened in Excel and saved. Excel rewrote every timestamp as
`10/2/2017 10:56`: the format changed and the seconds were lost. The file shrank from 17,654,914 to
15,315,857 bytes.
**How I caught it:** I wrote the date format for `strptime` from what I saw in the file, then noticed it
did not match the format I had used for the same data a week earlier. Comparing the file size and date
with a backup copy confirmed the change.
**Fix:** Restored the original file from the backup. The damaged copy is kept in `data/_damaged/`.
**Lessons:** Never open raw files in Excel, and never save over raw data. The reject rule
"a timestamp that cannot be parsed" would have rejected all rows, and the batch check would then have
failed the run, so the pipeline would not have produced wrong data. There is a test named after this
incident: `test_clean_order_excel_reformatted_timestamp_is_rejected`.

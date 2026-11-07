# mini-sqlmap

A small, readable SQL injection automation tool built for learning on **sqli-labs**.
It walks a target from detection to data extraction and can switch between UNION, error-based,
and blind (boolean / time) techniques, with automatic syntax-variant probing for filtered input.

> **Disclaimer**
> This project is for **local practice labs and authorized security testing only**.
> Using it against systems you do not own or have written permission to test is illegal.
> The author assumes no liability for misuse.

---

## 1. Features

| Capability | Notes |
|---|---|
| Injection detection | Error echo + boolean page comparison |
| UNION based | `ORDER BY` column count, marker-based display position discovery |
| Error based | `extractvalue` / `updatexml`, chunked (MySQL truncates the error to 32 chars) |
| Boolean blind | Binary search, ~7 requests per character |
| Time blind | `if(cond, sleep(n), 0)`, measured against a calibrated baseline |
| Injection points | GET parameter, POST form, Cookie, HTTP header |
| Bypass | Automatic probing of space / `and` / keyword / comma / comparison variants |
| Reporting | Every request is logged to `history/run_*.jsonl` |

---

## 2. Requirements & Quick Start

* Python 3.8+
* [requests](https://pypi.org/project/requests/)

```bash
pip install requests

# Run with the defaults from config.py
python main.py

# Point at another lab
python main.py --url "http://192.168.1.6/sql/Less-1/" --db security --table users --limit 5
```

Tested against sqli-labs (MySQL 5.5.53) on `http://192.168.1.6/sql/...`.

---

## 3. Project Layout

```
main.py                 7-stage pipeline + CLI
config.py               defaults: target, prefix/suffix, runtime behaviour
core/
  point.py              injection point: GET / POST / Cookie / Header
  injector.py           prefix + statement + suffix -> one request
  pipeline.py           bypass transform pipeline
payloads/
  detectors.py          injection detection
  union.py              column count, display positions, UNION extraction
  error_based.py        extractvalue / updatexml extraction
  blind.py              binary-search extraction over an oracle
  extractor.py          information_schema SQL builders (pure functions)
conditions/
  boolean.py            true/false page comparison
  oracle.py             BooleanOracle / TimeOracle + syntax auto-probing
response/analyzer.py    error detection, similarity, sentinel extraction
bypass/
  syntax.py             syntax variants (Dialect)
  whitespace.py         SpaceToComment / SpaceToTab transforms
  encoding.py           URL-encode / double-encode transforms
transport/http_client.py  HTTP layer
history/recorder.py     per-request JSONL log
tests/                  offline unit tests (no network needed)
```

---

## 4. Configuring Injection Parameters — Two Ways

All injection parameters can be supplied in **two ways**. They share the same values;
the only difference is lifetime and priority.

### 4.1 Command line (temporary, per run)

Pass flags on every run. Nothing is persisted. Best for switching labs quickly.

```bash
python main.py --url "http://192.168.1.6/sql/Less-5/" --param id --inject get \
               --mode blind --blind bool --db security --limit 5
```

### 4.2 Edit `config.py` (persistent defaults)

Edit the constants once; every later run uses them without extra flags.
Best when you stay on one lab for a while.

```python
# config.py
TARGET_URL = "http://192.168.1.6/sql/Less-2/"
PARAM_NAME = "id"
PREFIX = "1"          # numeric context
UNION_PREFIX = "-1"
SUFFIX = "-- -"
INJECT_MODE = "get"
BLIND_TYPE = "auto"
BYPASS_MODE = "auto"

# run with no arguments
python main.py
```

### 4.3 Parameter reference

**Priority: command line > `config.py`.** A flag always overrides the matching constant.

| Purpose | CLI flag | `config.py` constant | Default | CLI can override? |
|---|---|---|---|---|
| Target URL | `--url` | `TARGET_URL` | `http://192.168.1.6/sql/Less-5/` | Yes |
| Parameter / field / cookie / header name | `--param` | `PARAM_NAME` | `id` | Yes |
| Target database | `--db` | — | current database | Yes (n/a) |
| Table to dump | `--table` | — | none (stage 7 skipped) | Yes (n/a) |
| Rows to dump | `--limit` | `DUMP_LIMIT` | `10` | Yes |
| Request timeout (seconds) | `--timeout` | `TIMEOUT` | `10` | Yes |
| Max column count to probe | `--max-columns` | `MAX_COLUMNS` | `20` | Yes |
| Injection point | `--inject` | `INJECT_MODE` | `get` | Yes |
| Forced injection mode | `--mode` | — | `auto` | Yes (n/a) |
| Blind technique | `--blind` | `BLIND_TYPE` | `auto` | Yes |
| Syntax variant | `--bypass` | `BYPASS_MODE` | `auto` | Yes |
| Sleep seconds (time blind) | `--sleep` | `BLIND_SLEEP` | `2.0` | Yes |
| SQL closing prefix | — | `PREFIX` | `1'` | **No (config only)** |
| UNION closing prefix | — | `UNION_PREFIX` | `-1'` | **No (config only)** |
| Comment / terminator | — | `SUFFIX` | `-- -` | **No (config only)** |
| Bypass transform list | — | `TRANSFORMS` | `[]` | **No (config only)** |
| Max blind extraction length | — | `BLIND_MAX_LEN` | `1024` | **No (config only)** |

### 4.4 Values the command line cannot change

`PREFIX`, `UNION_PREFIX`, `SUFFIX`, `TRANSFORMS`, `BLIND_MAX_LEN` are **only** in `config.py`.
They describe *how the SQL is closed*, not *where the request is sent*, so they are kept
as source-level constants. Switching between single-quote / numeric / parenthesis / double-quote
labs still requires editing `config.py`:

```python
# common closings
PREFIX = "1'"     ; UNION_PREFIX = "-1'"      # Less-1 (single quote)
PREFIX = "1"      ; UNION_PREFIX = "-1"       # Less-2 (numeric)
PREFIX = "1')"    ; UNION_PREFIX = "-1')"     # Less-3 (single quote + parenthesis)
PREFIX = '1")'    ; UNION_PREFIX = '-1")'     # Less-4 (double quote + parenthesis)
PREFIX = '1"'     ; UNION_PREFIX = '-1"'      # Less-10 (double quote)
```

### 4.5 Why `SUFFIX` is `-- -` and not `--+`

Browsers convert `+` in a URL to a space, so `--+` works when you test by hand.
`requests` encodes `+` as `%2B` (a literal plus sign). The server then receives `--+`,
MySQL does not see the required whitespace after `--`, the comment fails and the query errors out.
Use `-- -`: the space is encoded as `+` on the wire and decoded back to a space by PHP.

---

## 5. Injection Modes (`--mode`)

Selection order in `auto`:

```
UNION (display found)  ->  error-based (error echo usable)  ->  blind (boolean -> time)
```

| Mode | When to use | Speed |
|---|---|---|
| `union` | Query result is rendered on the page | 1 request per value |
| `error` | No result shown, but SQL errors are echoed | ~1 request per 28 chars |
| `blind` | Neither results nor errors are visible | ~7-8 requests per char (boolean), delay-bound (time) |

`--blind` only applies to blind mode:

| Value | Meaning |
|---|---|
| `auto` | Try boolean first; fall back to time if the page never changes |
| `bool` | Boolean only |
| `time` | Time based only; raise `--sleep` on a slow network |

---

## 6. Injection Points (`--inject`)

| Value | Payload location | sqli-labs |
|---|---|---|
| `get` | `?id=payload` | Less-1 ~ 10 |
| `post` | form field `uname=payload` | Less-11 ~ 17 |
| `header` | request header (`User-Agent`, `Referer`, ...) | Less-18 ~ 19 |
| `cookie` | `Cookie: uname=payload` | Less-20 ~ 22 |

Use `--param` to name the field, cookie, or **header** being injected:

```bash
python main.py --url "http://192.168.1.6/sql/Less-11/" --inject post   --param uname
python main.py --url "http://192.168.1.6/sql/Less-20/" --inject cookie --param uname
python main.py --url "http://192.168.1.6/sql/Less-18/" --inject header --param User-Agent
```

---

## 7. Bypass (`--bypass`)

`auto` tries candidate syntaxes in order and **validates each one against the injection point**
using conditions whose answers are already known:

```
length(database()) > 0                    must be TRUE
length(database()) > 9999                 must be FALSE
ascii(substr((SELECT 0x41),1,1)) = 65     must be TRUE
ascii(substr((SELECT 0x41),1,1)) = 66     must be FALSE
```

If all four answers are correct, that syntax survives the target's filters; otherwise the next
candidate is tried. No manual guessing about what the lab blocks.

| Variant | Substitution |
|---|---|
| `plain` | `and 1=1` |
| `space_comment` | `and/**/1=1` |
| `space_tab` | tab as separator |
| `and_amp` | `&& 1=1` |
| `keyword_inline` | `/*!50000select*/` |
| `keyword_case` | `SeLeCt` |
| `keyword_double` | `selselectect` |
| `no_comma` | `substr(x from 1 for 1)` |
| `between` | `x between n and m` instead of `>` |

Force a specific family when you want to compare or skip probing:

```bash
python main.py --bypass space     # /**/ instead of spaces
python main.py --bypass and       # && instead of and
python main.py --bypass comma     # substr ... from ... for
```

---

## 8. Pipeline (7 stages)

| Stage | What happens |
|---|---|
| 1 | Injection detection (error echo, boolean difference) |
| 2 | Column count via `ORDER BY` (skipped when neither error nor boolean signal exists) |
| 3 | Display position discovery; choose UNION / error / blind; probe syntax variants |
| 4 | Read version, current database, current user |
| 5 | Enumerate databases |
| 6 | Enumerate tables and columns |
| 7 | Dump rows (only when `--table` is given) |

---

## 9. Examples

```bash
# Less-1: UNION path
python main.py --url "http://192.168.1.6/sql/Less-1/" --db security --table users --limit 5

# Less-5: no display -> blind (boolean)
python main.py --url "http://192.168.1.6/sql/Less-5/" --mode blind --blind bool

# Less-9: page never changes -> time blind
python main.py --url "http://192.168.1.6/sql/Less-9/" --mode blind --blind time --sleep 3

# Less-11: POST form
python main.py --url "http://192.168.1.6/sql/Less-11/" --inject post --param uname --mode blind

# Compare bypass strategies
python main.py --url "http://192.168.1.6/sql/Less-5/" --mode blind --bypass plain
python main.py --url "http://192.168.1.6/sql/Less-5/" --mode blind --bypass and
```

---

## 10. Tests

```bash
python tests/test_syntax.py        # syntax variants + injection points
python tests/test_sql_builders.py  # UNION / error-based SQL builders
python tests/test_analyzer.py      # response analysis
python tests/test_transforms.py    # bypass transform pipeline
```

All tests are offline and do not touch the network.

---

## 11. FAQ

**Blind extraction is very slow.**
Boolean blind costs ~7 requests per character. On a lab with 2 s response time, reading a
30-character value takes several minutes. Time blind adds one `sleep` per true answer on top.
Lower `--sleep` if the network is stable; parallelism is not implemented yet.

**`--mode union` exits immediately.**
No display position was found. The query result is probably not rendered — use `auto` or `blind`.

**`ORDER BY` cannot determine the column count.**
Neither error echo nor boolean difference is available. Blind mode does not need the count,
so the pipeline continues without it.

**Error-based returns truncated data?**
MySQL shows only the first 32 characters of an `extractvalue`/`updatexml` error.
The tool slices 28 characters per request and concatenates them, so values are complete.

**Detected nothing at all.**
Check `PREFIX` / `SUFFIX` in `config.py`, and confirm the injection point (`--inject`, `--param`).

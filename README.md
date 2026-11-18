# Legal Aid MCP

**English** | [中文](README.zh-CN.md)

A stdio MCP server for Jinan, Shandong. Ordinary people can find courts, legal-aid centres and law firms, plan a route, and compute filing fees and deadlines; lawyers can look up civil-procedure articles and check citations.

## The five tools

| Tool | What it does |
|---|---|
| `find_legal_service` | Search courts, law firms and legal-aid centres in Jinan; returns name, address, phone, coordinates, source and confidence |
| `plan_route` | Driving or walking routes with distance, estimated time and main steps; cross-checked across map providers |
| `search_law` | Search articles in the Civil Code contract book, the Civil Procedure Law, its interpretation, the evidence rules, the litigation-fee rules and the Legal Aid Law |
| `verify_citation` | Check an article citation in text: exists / does not exist / amended / out of scope |
| `legal_calculator` | Filing fees, preservation fees, appeal and defence periods, custom periods, each with the governing article |

## API choice against the brief

The brief asked for an API with mainland-China access, a free tier, HTTPS and official docs. This project uses Baidu Maps:

| Requirement | This project |
|---|---|
| Mainland access | `https://api.map.baidu.com`; on 2026-11-06 place search, geocoding and driving routes all returned `status: 0` |
| Free tier | Baidu's personal developer quota; check the console's Quota page. The project also enforces a lifetime cap of `LIVE_BUDGET=20` live calls, and defaults to mock so no quota is spent |
| HTTPS | Every request |
| Official docs | <https://lbsyun.baidu.com/> |

AMap's key returned `INVALID_USER_KEY` in testing, and the user explicitly did not want AMap. v2 therefore uses **Baidu + Tencent + Tianditu**:

| Provider | Key | Notes |
|---|---|---|
| Baidu Maps | `BAIDU_AK` | Default primary; free personal quota |
| Tencent Location | `TENCENT_MAP_KEY` | Optional; skipped without a key |
| Tianditu | `TIANDITU_KEY` | Optional, official geographic data; skipped without a key |

- Default order is `MAP_PROVIDERS=baidu,tencent,tianditu`.
- A timeout, exhausted quota or bad key falls through to the next provider; if all fail, `MAP_LIVE_FAILURE_MODE` decides (default `cache`).
- With two or more successful sources the result carries `confidence` and `discrepancies`; the merge is a de-duplicated union, so POIs unique to a secondary provider are not lost.
- Coordinates are always WGS-84; `plan_route` accepts `coord_system=gcj02|bd09` for older coordinates.

## Free data sources

| Source | Used for | On failure |
|---|---|---|
| 12348 China Legal Service Network | Names, addresses and phones of Jinan district legal-aid centres | Local snapshot → map POI |
| Ministry of Civil Affairs gazetteer | Validation and division codes for Jinan's 12 districts | Local snapshot |
| timor.tech holidays | Shifting litigation and appeal deadlines around holidays | Local snapshot → weekends only |
| flk.npc.gov.cn | All statutory text | The committed local corpus |
| Local calculators | Fees and periods | No external service |

The 12348 endpoint is the undocumented one behind the official page and carries an anti-bot signature. This project queries it at low frequency, caches for 24 hours, and falls back to a snapshot. If it changes, the statutes, calculators and map tools keep working.

## Layout

```text
server.py                  MCP server entry point (stdio)
config.py                  Environment variables and paths
errors.py                  Uniform error shape and run_tool
context.py                 AppContext
coord.py                   BD-09 / GCJ-02 / WGS-84 conversion
baidu.py                   Baidu Maps client (mock / live / cache / budget)
maps/                      Multiple map providers, failover, cross-checking
divisions.py               Ministry gazetteer index (Jinan's 12 districts)
holidays.py                Holiday / working-day arithmetic
legal_aid.py               12348 legal-aid directory client
calculators.py             Filing fees, preservation fees, period arithmetic
laws.py                    Chinese numerals, citation parsing, corpus loading and search
tools/                     The five tools
scripts/fetch_laws.py      Fetch official docx/pdf from the national law database
scripts/verify_laws.py     Verify 1678 articles, numbering, sampling and SHA256
scripts/fetch_divisions.py Snapshot Jinan's divisions
scripts/fetch_holidays.py  Snapshot public holidays
scripts/fetch_legal_aid.py Snapshot 12348's Jinan legal-aid centres
scripts/record_fixtures.py Record Baidu samples
scripts/mcp_transcript.py  Produce a stdio JSON-RPC transcript
data/laws/                 Generated corpus JSON + manifest
data/divisions/            Jinan division snapshot
data/holidays/             2025/2026 holiday snapshots
data/legal_aid/            12348 Jinan legal-aid snapshot
fixtures/baidu/            Baidu samples (tests and demos read these by default)
docs/                      Design, plan, test report, study notes
```

## Install

```powershell
cd <path-to-project-mcp>
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Or with `uv`:

```powershell
uv venv --python 3.14 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

## Configure

```powershell
copy .env.example .env
notepad .env
```

At minimum:

```text
BAIDU_AK=<your Baidu server-side AK>
```

`USE_MOCK=1` and `USE_LIVE=0` are the defaults; tests and demos read `fixtures/baidu/` and spend no Baidu quota. For real calls:

```text
USE_LIVE=1
```

`USE_MOCK=0` together with `USE_LIVE=0` refuses to start, so you cannot turn mock off and still read samples. `LIVE_BUDGET=20` is a lifetime hard cap on real calls, not a daily one; identical requests hit `cache/` and do not spend budget twice.

New in v2:

```text
TENCENT_MAP_KEY=          # optional
TIANDITU_KEY=             # optional
MAP_PROVIDERS=baidu,tencent,tianditu
MAP_CROSS_CHECK=1
MAP_LIVE_FAILURE_MODE=cache
LEGAL_AID_LIVE=1
HOLIDAY_LIVE=1
```

`USE_LIVE=0` is the global offline switch: maps use fixtures only, 12348, the gazetteer and holidays use local snapshots only, and tests never touch the network. Without Tencent or Tianditu keys they are skipped and Baidu, mock, statutes and calculators still work.

## Run

```powershell
python server.py
```

This is a stdio server; running it directly waits for an MCP client. Connect it through the Inspector or WorkBuddy below.

### MCP Inspector

```powershell
npx @modelcontextprotocol/inspector python server.py
```

The Inspector should list five tools; `search_law("违约金过高")` should return Article 585 of the Civil Code.

### WorkBuddy

The MCP configuration on this machine lives at:

```text
%USERPROFILE%\.workbuddy\connectors\default\mcp.json
```

The entry is named `legal-aid-mcp` and currently runs `USE_MOCK=1`, `USE_LIVE=0`, so it spends no Baidu quota. Restart WorkBuddy, enable it under MCP / Connectors, and approve the five tools.

The full entry:

```json
"legal-aid-mcp": {
  "type": "stdio",
  "command": "<path-to-project-mcp>\\.venv\\Scripts\\python.exe",
  "args": ["<path-to-project-mcp>\\server.py"],
  "env": {
    "USE_MOCK": "1",
    "USE_LIVE": "0"
  },
  "timeout": 120000,
  "disabled": false
}
```

For real map calls, set `USE_LIVE=1` and add `BAIDU_AK` to `env`, then restart WorkBuddy. Details in `docs/workbuddy-test-guide.md`.

## Tests

```powershell
.venv\Scripts\python -m pytest -q
.venv\Scripts\python scripts\verify_laws.py --data-dir data\laws
.venv\Scripts\python scripts\verify_laws.py --data-dir data\laws --require-raw
.venv\Scripts\python scripts\mcp_transcript.py --out docs\mcp-transcript.json
```

`--require-raw` is for CI and clean clones: when `data/raw/` is missing it fails instead of only warning.

Current result: `200 passed`; corpus verification prints `OK: 1678 条；民法典合同编 526 条；司法解释 69 条；民事诉讼核心包已校验`.

## Delivery evidence

- `HANDOFF.md`: handover and improvement list (read this first in a new session)
- `docs/screenshots/inspector-tools.jpeg`: MCP Inspector tool list
- `docs/inspector-tools.json`: Inspector `tools/list` output
- `docs/mcp-transcript.json`: five stdio tool calls
- `docs/workbuddy-test-guide.md`: eight manual test steps in WorkBuddy
- `docs/workbuddy-prompts.md`: eight core and four v2 prompts to paste into WorkBuddy
- `docs/test-report.md`: eight scenarios and real call records

## Sources and scope of the statutes

- Source: official docx (for parsing) and gazette PDFs (for evidence) from `flk.npc.gov.cn`.
- Civil Code, contract book: Articles 463–988, 526 articles.
- Interpretation on the General Provisions of the Contract Book: Articles 1–69.
- Civil Procedure Law (2023 amendment): 306 articles.
- Interpretation of the Civil Procedure Law (2022 amendment): 550 articles.
- Evidence rules in civil litigation: 100 articles.
- Measures on Payment of Litigation Costs: 56 articles.
- Legal Aid Law: 71 articles.
- 1678 articles in total.
- Metadata: `data/laws/manifest.json` records counts, full-text article ranges, promulgation and effective dates, and docx/PDF SHA256.
- Regenerate with:

```powershell
.venv\Scripts\python scripts\fetch_laws.py --out data\laws --raw-dir data\raw
.venv\Scripts\python scripts\verify_laws.py --data-dir data\laws
```

The original docx/PDF under `data/raw/` are git-ignored; only the parsed JSON is committed.

## Security

- The AK is read from `BAIDU_AK` only; it never appears in code, logs, error messages or cache metadata.
- `.env` is git-ignored; confirm before committing with `git check-ignore .env` and `git ls-files`.
- Errors carry Baidu's `status`/`message` and never a URL with `ak=` in it.

## v1 limitations

- Covers Jinan and its districts only; other cities return `CITY_NOT_FOUND`.
- Covers the Civil Code contract book, its general-provisions interpretation, the Civil Procedure Law, its interpretation, the evidence rules, the litigation-fee measures and the Legal Aid Law. Other laws return `out_of_scope` rather than claiming the article does not exist.
- `verify_citation` returns `ambiguous` for citations without a law name (e.g. "第585条"); pass `law_hint` or write "民法典第585条" to have it checked. This avoids misjudging documents that mix criminal and contract law.
- It does not decide jurisdiction, predict outcomes, recommend "the best lawyer" or draft pleadings.
- AMap is not wired in; Tencent and Tianditu are skipped when unconfigured, and Baidu, mock, statutes and calculators keep working.
- The eight WorkBuddy manual tests still need re-running in a WorkBuddy environment; this repository ships `docs/mcp-transcript.json` as stdio evidence.

## Eight scenarios

See `docs/test-report.md`. Common questions:

- "Where is the Jinan Intermediate People's Court?"
- "The penalty clause is excessive — what does the law say?"
- "I'm at Jinan West Station and need to file at the Jinan Intermediate Court. Is there legal aid nearby?"
- "This defence cites Article 585 of the Civil Code. Check it, and find me a law firm in Jinan."
- "How do I get to the Lixia court?"
- "What does Article 9999 of the Civil Code say?"

## License

MIT

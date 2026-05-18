# onet-py

A typed Python client for the [O\*NET Web Services API v2](https://onetcenter.org/reference/), with a CLI for quick lookups.

Built on httpx + Pydantic. Every response is a typed model, every list endpoint auto-paginates, and transient errors (429, 5xx) retry automatically.

Inspired by the excellent [onet2r](https://github.com/farach/onet2r) R package by Alex Farach.

## Setup

1. Register for a free API key at https://onetcenter.org/developer/
2. Add it to your `.env`:
   ```
   ONET_API_KEY=your-key-here
   ```

The client reads `ONET_API_KEY` from the environment (via python-dotenv). You can also pass it directly:

```python
client = OnetClient(api_key="your-key-here")
```

## Quick Start

```python
from onet import OnetClient

with OnetClient() as onet:
    # Search by keyword
    results = onet.search("data scientist")
    print(results[0].code, results[0].title)
    # 15-2051.00  Data Scientists

    # Full KSAO + RIASEC profile in one call
    profile = onet.occupation_profile("15-2051.00")

    for interest in profile.interests:
        print(f"{interest.name}: {interest.occupational_interest}")
    # Investigative: 100
    # Conventional: 74
    # ...

    for skill in sorted(profile.skills, key=lambda s: s.importance, reverse=True)[:5]:
        print(f"{skill.name}: {skill.importance}")
    # Mathematics: 88
    # Programming: 84
    # ...
```

## CLI

The CLI runs standalone via `uv run` (from the repo root):

```bash
# Search occupations
uv run onet/cli.py search "nurse"

# Full KSAO + RIASEC profile by SOC code
uv run onet/cli.py profile "29-1141.00"

# ...or by keyword (uses first search result)
uv run onet/cli.py profile --keyword "marine biologist"

# Task statements
uv run onet/cli.py tasks "25-2021.00"

# Hot technologies
uv run onet/cli.py tech "15-1252.00"

# Related occupations
uv run onet/cli.py related "15-1252.00"

# Database tables
uv run onet/cli.py tables
uv run onet/cli.py table "Skills"

# Military crosswalk
uv run onet/cli.py crosswalk "infantry"
```

## API Coverage

### Search & Browse

| Method | Description |
|---|---|
| `search(keyword)` | Search occupations by keyword, title, or SOC code |
| `occupations()` | List occupations (single page) |
| `occupations_all()` | All occupations, auto-paginated |
| `occupation(code)` | Occupation overview (description, sample titles) |

### Occupation Details

| Method | Returns | Description |
|---|---|---|
| `knowledge(code)` | `list[ScoredElement]` | Knowledge areas by importance |
| `skills(code)` | `list[ScoredElement]` | Skills by importance |
| `abilities(code)` | `list[ScoredElement]` | Abilities by importance |
| `work_styles(code)` | `list[ScoredElement]` | Work styles by importance |
| `work_activities(code)` | `list[ScoredElement]` | Work activities by importance |
| `interests(code)` | `list[Interest]` | RIASEC/Holland codes with scores |
| `tasks(code)` | `list[Task]` | Task statements |
| `work_context(code)` | `list[WorkContext]` | Work context elements |
| `detailed_work_activities(code)` | `list[DetailedWorkActivity]` | Granular activity descriptions |
| `education(code)` | `list[Education]` | Education level distribution |
| `job_zone(code)` | `JobZone` | Zone classification (training, experience, education) |

### Technology

| Method | Returns | Description |
|---|---|---|
| `technology_skills(code)` | `list[TechnologySkill]` | Tech skills flattened from category structure |
| `hot_technology(code)` | `list[HotTechnology]` | Hot/in-demand technologies |

### Relationships & Taxonomy

| Method | Returns | Description |
|---|---|---|
| `related_occupations(code)` | `list[OccupationRef]` | Related occupations |
| `crosswalk_military(keyword)` | `list[MilitaryCrosswalk]` | Military-to-civilian crosswalk |
| `taxonomy_map(code, from, to)` | `list[TaxonomyMapping]` | Map SOC codes between taxonomy versions |

### Database Access

| Method | Returns | Description |
|---|---|---|
| `tables()` | `list[TableRef]` | List all O\*NET database tables |
| `table_info(table_id)` | `list[TableColumn]` | Column metadata for a table |
| `table_rows(table_id)` | `list[dict]` | All rows, auto-paginated |

### Convenience

| Method | Description |
|---|---|
| `occupation_profile(code)` | Bundled KSAO + RIASEC profile (6 API calls in one) |

## How It Works

- **Auth:** `X-API-Key` header on every request, per the v2 API spec
- **Base URL:** `https://api-v2.onetcenter.org`
- **Retry:** Automatic retry (3 attempts) on 429 and 5xx status codes
- **Pagination:** `_paginate()` reads `total`/`end` from each response page and loops until complete
- **Normalization:** All API response keys are recursively converted to snake_case
- **Models:** Every response is validated through Pydantic v2 models

## Project Structure

```
onet/
  __init__.py   # Public exports
  client.py     # OnetClient (httpx, auth, pagination, retry)
  models.py     # Pydantic response models (17 types)
  cli.py        # Typer CLI with Rich tables
```

## Dependencies

All are existing project dependencies (no new installs required):

- `httpx` -- HTTP client
- `pydantic` -- Response models and validation
- `python-dotenv` -- .env loading
- `typer` + `rich` -- CLI (in `[sim]` extras)

## O\*NET Data Attribution

This client accesses data from O\*NET Web Services by the U.S. Department of Labor, Employment and Training Administration (USDOL/ETA). O\*NET is a trademark of USDOL/ETA.

O\*NET data is available under a [Creative Commons Attribution 4.0 International License](https://creativecommons.org/licenses/by/4.0/).

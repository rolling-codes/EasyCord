# EasyCord v5.55.0 Release Notes

## Install

```bash
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.55.0/easycord-5.55.0-py3-none-any.whl"
```

Source: `https://github.com/rolling-codes/EasyCord/releases/download/v5.55.0/easycord-5.55.0.tar.gz`

## JuiceWRLD Plugin

New built-in plugin (`JuiceWRLDPlugin`) integrating the former `juice-wrld-finder` project.

### Slash commands

| Command | Description |
|---|---|
| `/jw_search` | Fuzzy search by title or alias |
| `/jw_song` | Full metadata for a song by ID |
| `/jw_era` | List songs from a named era |
| `/jw_random` | Random song from the catalog |
| `/jw_add_song` | Add a new song (admin) |
| `/jw_reindex` | Reindex MEGA folders (admin) |

### AI tools

- `search_juicewrld` — fuzzy catalog search returning up to 5 results with confidence scores
- `get_song_details` — full metadata lookup by numeric ID

### External API integration

Set `use_external_api=True` to query `juicewrldapi.com` via the official
`juicewrld-api-wrapper` PyPI package (no API key required):

- `/jw_search` — parallel local + API search with three-bucket comparison embed
- `/jw_random` — API fallback when local catalog is empty
- `/jw_song` — API fallback embed when local ID not found
- `/jw_era` — supplements local results with API category results
- AI tools — API fallback in both search and detail lookup
- Background 6-hour sync task auto-imports new songs into the local catalog

### URL resolution & privacy

- Three-level URL resolution: official URL → MEGA file → MEGA folder
- `expose_mega_links=False` (default) redacts MEGA URLs for public servers
- `expose_api_download_links=False` (default) hides download URL field

### Event bus

Publishes 7 events and subscribes to 3 for internal logging.

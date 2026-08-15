# AGENTS.md

Plex Framework 2 metadata agent for Vixen-network siterips (VIXEN, TUSHY, BLACKED, DEEPER, MILFY, SLAYED, WIFEY and RAW variants), matching entirely against a **local** clone of [vixen_metadata](https://github.com/libredmm/vixen_metadata) — no network calls except artwork downloads. The entire plugin is one Python 2.7 file: `Contents/Code/__init__.py` (single `LibreVixen(Agent.Movies)` class). No build, lint, or test infrastructure — the checkout in `Plug-ins/` *is* the live install.

## Develop / verify cycle

- Syntax-check with Plex's own interpreter (system `python2` no longer exists on macOS):

  ```bash
  PYHOME="/Applications/Plex Media Server.app/Contents/Resources/Python"
  PYTHONHOME="$PYHOME" PYTHONPATH="$PYHOME/python27.zip:$PYHOME/python2.7" \
    "/Applications/Plex Media Server.app/Contents/MacOS/Plex Script Host" -c \
    "import py_compile; py_compile.compile('Contents/Code/__init__.py', doraise=True, cfile='/dev/null'); print 'OK'"
  ```

- Reload after edits by restarting PMS: `osascript -e 'quit app "Plex Media Server"' && open -a "Plex Media Server"`.
- Plugin log: `~/Library/Logs/Plex Media Server/PMS Plugin Logs/com.libredmm.vixen.log`. Agent registration appears in `com.plexapp.system.log` ("Receiving agent info from com.libredmm.vixen").
- Code is black-formatted; keep that style.

## Plex sandbox constraints (learned the hard way)

- Even under the `Elevated` code policy, source is compiled with **RestrictedPython**: identifiers starting with `_` (including a bare `_` unpacking target) fail the whole plugin at load with a SyntaxError in the log.
- Framework globals are injected, never imported: `Agent`, `Locale`, `MetadataSearchResult`, `JSON`, `HTTP`, `Proxy`, `Log`, `Prefs`, `Core`. Stdlib imports (`re`, `json`, `urllib`, `datetime`, `urlparse`) work fine.
- `JSON.ObjectFromString` rejects payloads over 5 MB — the site JSON files exceed it, which is why `vixen_load_site` parses with stdlib `json` instead.
- Python 2.7 only: no f-strings; paths from `media.filename` may arrive as UTF-8 `str` and need `.decode("utf-8")`.
- PMS exposes **one agent per bundle identifier per media type** — this bundle exists (identifier `com.libredmm.vixen`) precisely because a second `Agent.Movies` class inside the sibling `librefanza.bundle` would never appear in the library-agent UI. A brand-new agent bundle may need **two** PMS restarts before it shows up.

## Architecture

- **Data source**: JSON arrays of GraphQL `VideoEdge` objects, one file per site, in the directory given by the `vixen_metadata_dir` pref (default `~/.local/share/vixen`). The plugin never clones or pulls — syncing is external (`vixen checkout`, run implicitly by `vixen-rename`/`vixen scrape`). `vixen_load_site` builds `by_date` / `by_video_id` / `by_slug` indexes and caches them keyed on file mtime, so external syncs are picked up automatically. If the directory is missing, matching silently fails (exception logged and swallowed).
- **Matching** (in `search()`): site comes from the parent folder name minus `.com` — never from the filename prefix. Filenames follow the [`vixen canonical`](https://github.com/libredmm/vixen) format `Site - YYYY-MM-DD - Models [videoId].mp4`; the bracketed videoId gives a direct `by_video_id` lookup (score 100). Legacy names without the suffix fall back to `vixen_match`: unique release date (compared as a plain `YYYY-MM-DD` string — `releaseDate` is UTC 17:30+, never day-shifts), then exact normalized cast-set on date collisions, then cast-set within ±7 days (score 90). Manual match accepts a scene URL (site from hostname, slug from path) or free-text title search.
- **Ids** are `"librevixen|<site>|<videoId>"`; `update()` guards on the prefix and re-resolves from the local JSON. If the entry has vanished from the metadata it logs an error and returns *without wiping* existing metadata.
- **Fields**: title, date/year, studio (pretty name from `VIXEN_SITES`), cast (`modelsSlugged`, no photos exist in the data), poster (portrait image's `highdpi.double`), art (widest landscape's `highdpi.double`). The metadata has **no** summary, duration, tags, or directors; rating is deliberately not pulled.
- `metadata.roles` names come straight from the JSON; entries flagged `isUpcoming` stay in the indexes on purpose (they can only match on/after release day).

## Conventions

- Commits are authored with the repo-local identity `LibreDMM <admin@libredmm.com>` (already in `.git/config`), subjects short.
- This repository is public-facing: keep it self-contained; no references to private dotfiles or the home network.

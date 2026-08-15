# librevixen.bundle

Plex metadata agent for Vixen-network siterips, backed by a local clone of [vixen_metadata](https://github.com/libredmm/vixen_metadata) — no network calls except artwork downloads.

Expects files named by [`vixen canonical`](https://github.com/libredmm/vixen): `Site - YYYY-MM-DD - Models [videoId].mp4`, in per-site folders (`vixen.com/`, `tushy.com/`, …). Matches by the embedded `[videoId]`, falling back to release date + cast set for legacy names. Manual match accepts a scene URL (e.g. `https://www.vixen.com/videos/working-it`) or a title search.

The metadata directory defaults to `~/.local/share/vixen` and is configurable in the agent's settings.

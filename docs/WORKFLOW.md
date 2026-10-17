# REA Library workflow integration

Run `python3 server.py` and open http://127.0.0.1:8765. Python 3.11+ and the Codex CLI are required for rebuilding. REA uses your existing `rea` MCP configuration and the reverse-engineer-anything skill in `~/.agents/skills`.

Write `library-entry.json` containing name, kind (app/component/tool), source (rea/custom), an existing absolute path and HTML entry or macOS .app bundle, or an HTTP(S) URL. REA rebuilds include their actual evidence references. Use a stable id for updates.

Call `python3 /path/to/rea-library/register.py /path/to/library-entry.json` at workflow completion. The local inbox imports completed artifacts automatically. Do not register incomplete builds as ready.

Artwork uses icon, cover, and screenshots fields with existing library-relative `assets/` paths. These stay local unless explicitly included in public-catalog.json. Runtime records, logs, credentials, private repository caches, and local paths are never included by the Pages exporter.

GitHub public profiles are browsable without a token. In the local companion, run `gh auth login`, then use GitHub → Sync connected account for owned public and private repositories. Source repositories are not claimed to be installed apps.

GitHub Pages serves the static catalog only. It cannot execute Python, local native programs, Codex, or MCP. Local actions open the loopback companion, which keeps its existing origin/token checks. No public-to-local credential bridge is enabled.

# REA Library

[Open the live library](https://carlosmabrey.github.io/rea-library/)

A Steam-inspired home for reconstructed apps, reusable components, and developer projects.

- Real app icons and screenshot galleries in the local library.
- Discover targets, start Codex + REA workflows, and register completed rebuilds.
- Browse public GitHub profiles; sync your authenticated GitHub account locally, including private owned repositories.
- Open static projects inside the companion, hosted apps by URL, and registered macOS app bundles.
- A GitHub Pages catalog with curated metadata and explicitly safe preview images.

## Local companion

```sh
python3 server.py
```

Open http://127.0.0.1:8765. Requires Python 3.11+. Codex and the REA MCP server use your existing local settings. GitHub sync uses `gh auth login`; no tokens are entered into the website. See [WORKFLOW.md](WORKFLOW.md) for automatic registration.

## GitHub Pages

The Pages site is published from `docs/`. Rebuild the catalog after editing the explicit public allowlist:

```sh
python3 export_site.py
```

Commit the resulting `docs/` update. The public catalog is a curated snapshot, not a copy of local runtime storage. Private workspace screenshots, native process screenshots, captured customer/project data, local paths, job logs, tokens, and private repository metadata are excluded. Icons contain app branding only. GitHub repository previews come directly from GitHub and do not claim to be screenshots of running apps.

Pages is static. Native launching, registration, authenticated private GitHub sync, and Codex/REA workflows remain in the loopback companion. The hosted catalog links to that companion rather than exposing a remote execution API.

## Verification

The companion includes registry validation, origin/token checks, bounded GitHub sync with sanitized metadata, and sandboxed project previews. Native provider availability remains separate from a live REA handshake. Run tests with `python3 -m unittest discover -s tests` when tests are present.


Registrations now queue an agent to capture real icons and screenshots and publish reviewed artwork automatically. The companion must be running. See WORKFLOW.md for automation configuration, privacy, status, and retries. The ChatGPT-hosted REA Library follows the same Pages catalog.

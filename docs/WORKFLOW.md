# REA Library workflow integration

Run `python3 server.py` from this directory and open http://127.0.0.1:8765. Python 3.11+ is required. The library uses your existing Codex CLI authentication and the `rea` MCP entry in your Codex configuration. It reads the installed reverse-engineer-anything skill at `~/.agents/skills/reverse-engineer-anything/SKILL.md`. No API key is stored by this application.

## Built-in REA rebuilds

Choose **Discover → Set up with REA**, or use **Set up with REA** in your library. Select an installed app or supply an existing absolute local artifact path. Give the job a name, kind, and rebuild brief. Starting a job launches a real `codex exec --approve-for-me --json` process in a dedicated workspace, with REA required and the installed skill explicitly referenced. Codex uses the user's configured model and account usage. Approval review and the workspace sandbox stay enabled.

Jobs run serially. The Workflows view displays agent messages and MCP activity. Completion requires a successful process, a structured ready result, a valid manifest, an existing artifact, and REA evidence references. Evidence references are claims from the producing workflow, not independently certified by the registry. A successful model response alone is insufficient. Failed or incomplete runs remain Needs attention, with their workspace and logs retained. Stopping cancels the job process group. Restarted in-progress jobs become Needs attention rather than silently appearing complete.

## Register from any development workflow

Write `library-entry.json` with:

```json
{
  "name": "My app",
  "kind": "app",
  "source": "custom",
  "description": "What was made and checked",
  "path": "/absolute/path/to/web-project",
  "entry": "index.html",
  "evidence": []
}
```

`kind`: app, component, or tool. `source`: rea or custom. For a running dev server, use `url` with an HTTP(S) URL instead of `path`. `path` accepts a static project directory, an HTML file, or a macOS .app bundle. Registered native apps launch through macOS open when you press Open App. Arbitrary executables and shell start commands are not launched. Absolute artifact paths are resolved and checked. Directory entry files must remain inside the project. App IDs derive from the name and project path/URL; set a stable `id` explicitly when renaming or moving a project. Repeated registration with the same ID updates the entry.

Add this completion step to your existing workflow, using the actual absolute path to this library:

```sh
python3 /absolute/path/to/rea-library/register.py /absolute/path/to/library-entry.json
```

The hook validates and immediately saves the entry, then writes a durable automation job. It works offline; the companion processes capture and publication after its next start. Repeated unchanged local registrations are deduplicated. For URL-only builds, include a changing `revision` (commit SHA or build ID) to identify each rebuild. If using `REA_LIBRARY_DATA`, set the same value for the hook and server.

## Automatic artwork and hosted catalogs

Registration starts a serial Codex artwork agent using the existing local account. It captures the app's actual runtime and extracts an existing icon or brand mark. Private captures stay local; only individually reviewed safe images enter the published catalog. Authentication/OS permission blockers become Needs attention. Existing artwork survives capture failure. Connections shows job states and a retry button.

Configure private `library-data/automation-config.json` with `enabled`, `capture`, `publish`, `githubEnabled`, `repository` (`CarlosMabrey/rea-library`) and `repoPath` (the existing Git checkout). The companion must be running for jobs to execute. It publishes only safe generated catalog/assets to the configured main branch, using existing Git credentials. A dirty/diverged checkout or failed push requires attention; no force pushes occur. Other installations start disabled.

GitHub Pages deploys the updated catalog. The ChatGPT-hosted REA Library reads the same catalog and artwork, refreshing every 30 seconds while visible and when focused. Hosting credentials, private registry fields, and automation logs are not shipped to either site.

Optional manifest `publication` fields `name`, `description`, and HTTPS `url` define intentional public metadata. Default descriptions are generic. Set `publication: {"enabled": false}` to keep an entry local. Original paths, evidence, captures not marked safe, and private GitHub repository cache never enter the public catalog.

You can also use **Add an app** to register an existing project from the interface. Neither registration route scans or imports all of your developer projects without selection. The hook makes a participating workflow automatic; unrelated workflows must add that completion step.

## Storage and local boundaries

The app binds to 127.0.0.1. Mutating HTTP requests require a per-process token and an allowed Origin/Host. Static serving blocks traversal and private library-data. Project previews use a sandbox CSP to separate rebuilt scripts from the registry API. Project code can still make network requests; review the output before using it with private data.

Persistent records, job workspaces, and logs are in `library-data/`. These are private local runtime data and are excluded from the distributable ZIP. Registration manifests can contain project paths. Exported source does not include your Codex authentication, MCP configuration, or jobs.

Codex jobs inherit the local Codex configuration and enabled MCP servers. Native provider availability is separate from the verified REA handshake. The library never installs engines or rewrites global MCP/skill settings automatically. If required setup is missing, Connections shows the blocker.

## References

- https://learn.chatgpt.com/docs/non-interactive-mode
- https://learn.chatgpt.com/docs/extend/mcp?surface=cli

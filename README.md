# md-vision MCP server

stdio MCP server with two read-only tools for agentic RAG over markdown documentation:

- **read_md_with_images** — return markdown (optionally scoped) with referenced images as MCP image blocks.
- **index_md** — build a compact heading index for a file, URL, or folder of markdown files.

Typical flow: call `index_md` to discover headings and structure, then `read_md_with_images` on the sections you need.

## Requirements

- Node.js 20+

## Install

Published package: [md-vision on npm](https://www.npmjs.com/package/md-vision)

```bash
npx md-vision --allow-path /path/to/docs --allow-domain none
```

Or install globally:

```bash
npm install -g md-vision
md-vision --allow-path /path/to/docs --allow-domain none
```

From a clone of this repo:

```bash
npm install
npm run build
```

## MCP client configuration

In your agent config (`.agents/mcp.json` or similar), point your MCP host at the server. Example using `npx`:

```json
{
  "mcpServers": {
    "md-vision": {
      "command": "npx",
      "args": [
        "md-vision",
        "--allow-path",
        "/absolute/path/to/docs",
        "--allow-domain",
        "none"
      ]
    }
  }
}
```

**Local development** (absolute path to built `dist/server.js`):

```json
{
  "mcpServers": {
    "md-vision": {
      "command": "node",
      "args": [
        "/absolute/path/to/md-vision-mcp/dist/server.js",
        "--allow-path",
        "/absolute/path/to/docs",
        "--allow-domain",
        "none"
      ]
    }
  }
}
```

**With remote markdown** (allow all HTTP(S) hosts, or list specific domains):

```json
{
  "mcpServers": {
    "md-vision": {
      "command": "npx",
      "args": [
        "md-vision",
        "--allow-path",
        "/absolute/path/to/docs",
        "--allow-domain",
        "all"
      ]
    }
  }
}
```

```json
{
  "mcpServers": {
    "md-vision": {
      "command": "npx",
      "args": [
        "md-vision",
        "--allow-path",
        "/absolute/path/to/docs",
        "--allow-domain",
        "raw.githubusercontent.com"
      ]
    }
  }
}
```

The server exits on startup if `--allow-path` or `--allow-domain` is omitted.

Restart the MCP host after changing configuration.

### Restricting allowed paths and domains

| Flag | Required | Effect |
|------|----------|--------|
| `--allow-path <dir>` | Yes (at least one) | Local files must resolve under one of the allowed directories (repeatable). |
| `--allow-domain <host>` | Yes (at least one) | Controls HTTP(S) access. Use `all` to allow any host, `none` to disable URLs (local files only), or list specific hosts (repeatable; suffix match supported, e.g. `example.com` allows `docs.example.com`). |

Equivalent forms: `--allow-path=/path`, `--allow-domain=host.example`, `--allow-domain=all`, `--allow-domain=none`.

Do not pass a bare `*` as a separate shell argument — the shell expands it to filenames in the current directory. Use `all` or `--allow-domain=all` instead.

## Development

```bash
npm run dev          # rebuild on change
npm test             # vitest
npm run build        # dist/server.js
npm start            # run built server (stdio)

# Interactive smoke test
npx @modelcontextprotocol/inspector node dist/server.js --allow-path . --allow-domain none
```

## Releasing

Publishes are automated via GitHub Actions when a version tag is pushed.

1. Bump `version` in `package.json` and commit to `master`.
2. Configure [npm Trusted Publishing](https://docs.npmjs.com/trusted-publishers) on [npmjs.com](https://www.npmjs.com) (one-time, **before** the first publish):
   - Provider: **GitHub Actions**
   - Repository: `japlete/md-vision-mcp`
   - Workflow filename: `publish.yml`
3. Create and push a tag matching the package version:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The [publish workflow](.github/workflows/publish.yml) verifies the tag matches `package.json`, runs tests, builds, and publishes to npm with provenance. CI on every push/PR to `master` is in [ci.yml](.github/workflows/ci.yml).

If a publish fails because Trusted Publishing was not configured yet, set it up on npmjs.com then re-run the failed workflow from the GitHub Actions UI (or `gh run rerun <run-id> --failed`).

## Tools

### read_md_with_images

Read a markdown file and inline referenced images as MCP image content.

| Parameter | Type | Description |
|-----------|------|-------------|
| `uri` | string | Local path or `http(s)://` URL |
| `section` | string, optional | Exact heading to read, e.g. `## Introduction` (used when matched; otherwise falls back to `line_range`) |
| `line_range` | `[start, end]`, optional | Inclusive 1-based document line range (used when `section` is omitted or not found) |
| `max_images` | integer, optional | Max images to inline (default `10`, max `50`) |

**Returns:** MCP content array — alternating `text` and `image` blocks (PNG, base64) in document order; frontmatter preserved in the leading text. Before each inlined image, a short `text` block carries the resolved image URL (omitted for `data:` URIs and other long references). Images beyond `max_images` stay as markdown image syntax in text.

**URI forms:** local filesystem paths and `http(s)://` URLs. Local paths must fall under a configured `--allow-path` directory. Relative image paths resolve against the markdown file location or document URL. Images may use markdown `![](...)` syntax or HTML `<img src="...">` tags.

### index_md

Index headings for navigation before targeted reads.

| Parameter | Type | Description |
|-----------|------|-------------|
| `uri` | string | Markdown file, `http(s)://` URL, or local folder |

**Returns:** Markdown string. For each file:

1. YAML frontmatter when present.
2. A fenced `tsv` code block with columns: `heading`, `line_start`, `n_images`, `char_count`.

Each file is wrapped in:

```xml
<file path="..." lines=X chars=Y>
...
</file>
```

Folder `uri` values are scanned recursively for `*.md` / `*.markdown` in stable sorted order. Headings inside fenced code blocks are not indexed.

## Note on deploying agents with this MCP server

stdio MCP servers run as subprocesses of the agent runtime that invokes them.

- **Agent-in-sandbox** (runtime shares the agent’s filesystem): the server can read docs in-place; scope `--allow-path` to the documentation tree you intend to expose.
- **Sandbox-as-tool** (runtime filesystem differs from the tool sandbox): the MCP process usually runs in the runtime environment, so markdown must be copied or synced where the server can read it.

## Benchmark

Not yet implemented.

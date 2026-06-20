# md-vision MCP server

stdio MCP server with two read-only tools for agentic RAG over markdown documentation:

- **read_md_with_images** — return markdown with referenced images as interleaved image blocks. Avoids an extra tool call for each image to read. Optionally scoped to a specific section or line range.
- **index_md** — return a compact heading index for a file, URL, or folder of markdown files. Used to dynamically index files for targeted reads.

Typical flow: call `index_md` to discover headings and structure, then `read_md_with_images` on the sections you need.

## Install: MCP client configuration

Published package: [md-vision on npm](https://www.npmjs.com/package/md-vision)

In your agent config (`.agents/mcp.json` or similar), point your MCP host at the server. Example:

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

### Requirements

- Node.js 20+

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

stdio MCP servers run as subprocesses of the agent runtime that invokes them. There are two deployment patterns commonly used:

- **Agent-in-sandbox** (runtime shares the agent’s filesystem): the server can read docs in-place; scope `--allow-path` to the documentation tree you intend to expose.
- **Sandbox-as-tool** (runtime filesystem differs from the tool sandbox): the MCP process usually runs in the runtime environment, so markdown must be copied or synced where the server can read it.

## Benchmark (WIP)

See [`benchmark/`](benchmark/) for the MMLongBench-Doc A/B harness comparing
filesystem-only agentic RAG against the same agent with `md-vision` MCP tools.

## Standalone indexing

`md-vision` can also be used as a library when you want to index markdown outside an MCP host — for example in an offline preprocessing pipeline for agentic RAG.

Install the package:

```bash
npm install md-vision
```

### Index markdown text

Use `indexMarkdownText` when you already have markdown content in memory.

```ts
import { indexMarkdownText } from "md-vision";

const markdown = `# Guide

Intro text.

## Setup

![diagram](./setup.png)
`;

const index = indexMarkdownText(markdown);

console.log(index.rows);
```

Example result:

```ts
[
  {
    heading: "# Guide",
    lineStart: 1,
    imageCount: 1,
    charCount: 42
  },
  {
    heading: "## Setup",
    lineStart: 5,
    imageCount: 1,
    charCount: 24
  }
]
```

### Index a file

Use `indexMarkdownFile` to load and index a local markdown file.

```ts
import { indexMarkdownFile } from "md-vision";

const index = await indexMarkdownFile("./docs/guide.md");

await saveToVectorStoreMetadata({
  path: index.path,
  frontmatter: index.frontmatter,
  headings: index.rows,
});
```

### Index a folder

Use `indexMarkdownFolder` to recursively index `*.md` and `*.markdown` files in stable sorted order.

```ts
import { indexMarkdownFolder } from "md-vision";

const files = await indexMarkdownFolder("./docs");

for (const file of files) {
  console.log(file.path, file.rows);
}
```

### Output shape

Each indexed file returns structured data:

```ts
type MarkdownFileIndex = {
  path?: string;
  frontmatter: string;
  lineCount: number;
  charCount: number;
  rows: HeadingIndexRow[];
};

type HeadingIndexRow = {
  heading: string;
  lineStart: number;
  imageCount: number;
  charCount: number;
};
```

Headings inside fenced code blocks are ignored because indexing uses the markdown AST rather than regex matching.

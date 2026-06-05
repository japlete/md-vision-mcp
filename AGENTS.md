# MD Vision MCP server

stdio MCP server: read markdown with inlined images (`read_md_with_images`) and index headings across files or folders (`index_md`). For agentic RAG and documentation workflows.

## Status

Implemented. Entry: `src/server.ts` → `dist/server.js` (`md-vision` bin). Tests: `test/**/*.test.ts`.

## Layout

| Path | Role |
|------|------|
| `src/server.ts` | MCP bootstrap, tool registration, stdio transport |
| `src/tools/` | Tool handlers and zod input schemas |
| `src/markdown/` | remark AST: parse, sections, line ranges, index rows |
| `src/images/` | Image load, MIME sniff, sharp/resvg → PNG |
| `src/io/` | URI fetch, path/domain allowlists |
| `src/mcp/result.ts` | MCP content / error helpers |

User-facing install and examples: `README.md`. MCP authoring patterns: `.agents/skills/build-mcp-server/`.

## Stack

Node 20+, TypeScript, ESM (tsup). MCP SDK + zod. unified/remark (GFM, frontmatter). sharp, resvg, file-type, fast-glob. vitest, nock, tmp-promise.

## Rules

- Breaking changes OK while unpublished.
- Run `npm test` after code changes.
- Use `.js` extensions in relative imports. No CommonJS.
- stdio: never log to stdout; use `console.error` only.
- `.npmrc` enforces 14-day release age for npm deps.

## Tools (contract)

**read_md_with_images** — `uri`, optional `section` (exact heading text, e.g. `## Intro`), optional `line_range` `[start, end]` (section wins when matched), optional `max_images` (default 10, max 50). Returns text + image blocks; frontmatter preserved via remark-stringify.

**index_md** — `uri` (file, folder, or URL). Per file: frontmatter + TSV (`heading`, `line_start`, `n_images`, `char_count`) in `<file path="..." lines=X chars=Y>`. Headings inside fenced code are skipped (AST, not regex).

Images: markdown `![](...)` and HTML `<img src="...">`; resolve relative to doc base; MIME via file-type then mime-types; raster → sharp PNG, SVG → resvg PNG.

## Access

CLI: `--allow-path` and `--allow-domain` (both required, repeatable or `=value`). Server fails to start without at least one of each. `--allow-domain=all` allows any HTTP(S) host; `--allow-domain=none` disables URLs. Avoid bare `*` (shell glob).

## Dev

```bash
npm test
npm run build
npx @modelcontextprotocol/inspector node dist/server.js --allow-path . --allow-domain none
```

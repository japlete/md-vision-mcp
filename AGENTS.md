# MD Vision MCP server

This is a stdio MCP server that provides tools to read markdown files with images and obtain an index of a set of MD files. To be used in agentic RAG or general documentation workflows.

## Stack

- Runtime: Node.js 20+, TypeScript 5.8, ESM
- Build: tsup (ESM bundle, Node 20 target)
- MCP: `@modelcontextprotocol/sdk` v1 + zod v3 (tool input schemas)
- Markdown AST: unified + remark-parse + remark-gfm + remark-frontmatter + remark-stringify
- AST utilities: unist-util-visit, unist-util-is, mdast-util-to-string
- Image handling: sharp (raster resize/format), `@resvg/resvg-js` (SVG → PNG)
- HTTP: native fetch
- MIME / sniffing: file-type v21 (magic bytes), mime-types (extension fallback)
- Folder indexing: fast-glob
- Testing: vitest + tmp-promise + nock (HTTP mocking)
- Publishing: npm, GitHub Actions (repo private for now, public when published)

## Status

Repo structure only, no tools implemented yet. Local git only.

## Rules

- Breaking changes are allowed while the project is unpublished.
- Run `npm test` after code changes.
- Don't write docs unless asked to.
- Use .js extensions in relative imports. No CommonJS.
- .npmrc enforces 14-day release age (security)

## Tools

### read_md_with_images

Inputs:
- uri (string): The local path or URL to the markdown file to read
- section (string, optional): The section of the file to read. Example: '## Introduction'
- line_range (array of integers, optional): The line range to read (inclusive). Example: [1, 10]. section argument takes precedence if section matches.
- max_images (integer, optional): The maximum number of images to read. Default: 10.

Outputs:
- array of text and image blocks: The markdown content with referenced images injected as LLM-native image blocks. Original frontmatter is preserved.

### index_md

Inputs:
- uri (string): The local path or URL to the markdown file or folder to index

Outputs:
- markdown (string): MD in 2 parts:
  - Frontmatter is preserved if present.
  - TSV code block containing a TSV table with columns: heading, line_start, n_images, char_count. One table per file, wrapped in an XML tag `<file path="..." lines=X chars=Y>...</file>` with no indentation.
Note: headings within code blocks are not indexed.

### Details

- Parse with remark-parse + remark-gfm + remark-frontmatter; preserve frontmatter via remark-stringify, not string slicing. Traverse the AST with unist-util-visit; skip headings inside fenced code blocks.
- Match headings by exact text (e.g. `## Introduction`), not slug.
- Resolve relative paths against the markdown file's directory; use sharp for raster, resvg for SVG. Detect MIME with file-type first, fall back to mime-types by extension.

## MCP install spec

The MCP should be executed via `npx` like most stdio MCP servers. Optional arguments can restrict the allowed paths or domains which the tools can access. If no restrictions are specified, the Roots MCP feature can be used, if the client supports it.


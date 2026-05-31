# Tool Design — Writing Tools agents use correctly

Tools are interfaces used by agents to obtain context and execute actions. Tool input schemas, descriptions, names and output structure are prompt engineering.

---

## Naming

Tool names must be ≤64 characters. Use self-descriptive names for tool names, input arguments and output fields in JSON/XML/YAML.

## Descriptions

**The description is the contract.** In MCP tools, it's the only thing the agent reads before deciding whether to call the tool. Write it like a one-line manpage entry plus disambiguating hints.

### Good

```
search_issues — Search issues by keyword across title and body. Returns up to `limit` results ranked by recency. Does NOT search comments or PRs — use search_comments / search_prs for those.
```

- Says what it does
- Says what it returns
- Says what it *doesn't* do (prevents wrong-tool calls)

### Bad

```
search_issues — Searches for issues.
```

Agents will call this for anything vaguely search-shaped, including things it can't do.

### Disambiguate siblings

When two tools are similar, each description should say when to use the *other* one:

```
get_user      — Fetch a user by ID. If you only have an email, use find_user_by_email.
find_user_by_email — Look up a user by email address. Returns null if not found.
```

---

## Parameter schemas

**Tight schemas prevent bad calls.** Every constraint you express in the schema is one fewer thing that can go wrong at runtime.

| Instead of | Use |
|---|---|
| `z.string()` for an ID | `z.string().regex(/^usr_[a-z0-9]{12}$/)` |
| `z.number()` for a limit | `z.number().int().min(1).max(100).default(20)` |
| `z.string()` for a choice | `z.enum(["open", "closed", "all"])` |
| optional with no hint | `.optional().describe("Defaults to the caller's workspace")` |

**Describe every parameter.** The `.describe()` text shows up in the schema agents sees. Omitting it is leaving money on the table.

```typescript
{
  query: z.string().describe("Keywords to search for. Supports quoted phrases."),
  status: z.enum(["open", "closed", "all"]).default("open")
    .describe("Filter by status. Use 'all' to include closed items."),
  limit: z.number().int().min(1).max(50).default(10)
    .describe("Max results. Hard cap at 50."),
}
```

---

## Return shapes

Agents read whatever you put in the output content array. Make it parseable and self-explanatory, to avoid explaining the output format in the tool description.

**Output structures:**
- Use text table formats (TSV, CSV, MD tables) for tabular data
- Use XML tags or MD code blocks to wrap dynamically obtained data for robust LLM delimitation.

---

## Errors

Return MCP tool errors, not exceptions that crash the transport. Include enough detail for agents to recover or retry differently.

```typescript
if (!item) {
  return {
    isError: true,
    content: [{
      type: "text",
      text: `Item ${id} not found. Use search_items to find valid IDs.`,
    }],
  };
}
```

The hint ("use search_items…") turns a dead end into a next step.

---

## Tool annotations

Hints the host uses for UX — red confirm button for destructive, auto-approve for readonly. All default to unset (host assumes worst case).

| Annotation | Meaning | Host behavior |
|---|---|---|
| `readOnlyHint: true` | No side effects | May auto-approve |
| `destructiveHint: true` | Deletes/overwrites | Confirmation dialog |
| `idempotentHint: true` | Safe to retry | May retry on transient error |
| `openWorldHint: true` | Talks to external world (web, APIs) | May show network indicator |

```typescript
server.registerTool("delete_file", {
  description: "Delete a file",
  inputSchema: { path: z.string() },
  annotations: { destructiveHint: true, idempotentHint: false },
}, handler);
```

---

## Content types beyond text

Tools can return more than strings:

| Type | Shape | Use for |
|---|---|---|
| `text` | `{ type: "text", text: string }` | Default |
| `image` | `{ type: "image", data: base64, mimeType }` | Screenshots, charts, diagrams |
| `resource_link` | `{ type: "resource_link", uri, name?, description? }` | Pointer — client fetches later |
| `resource` (embedded) | `{ type: "resource", resource: { uri, text\|blob, mimeType } }` | Inline the full content |

**`resource_link` vs embedded:** link for large payloads or when the client might not need it (let them decide). Embed when it's small and always needed.

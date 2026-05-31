---
name: build-mcp-server
description: Use when working on the md-vision MCP server — adding or changing tools, wiring the stdio transport, validating with the MCP Inspector, or debugging tool schemas and multimodal responses. Scoped to this repo only (local stdio, TypeScript, tools-only).
version: 0.2.0 (modified for this repo)
---

# MCP server quickstart

Repo level instructions have precedence over this generic skill.

## Server skeleton

```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const server = new McpServer({
  name: "md-vision",
  version: "0.1.0",
});

// server.tool(...) or server.registerTool(...) — match whichever API the installed SDK exposes

async function main(): Promise<void> {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
```

**stdio rules:**

- Never write to **stdout** except MCP protocol messages. Use **`console.error`** for logs.
- The host starts the process and owns stdin/stdout; no listening port.
- `bin` in `package.json` points at `./dist/server.js`; run `npm run build` before testing.

---

## Tool design

→ See `references/tool-design.md` for description and schema guidance.

---

## Security

Allow the client to restrict the paths and domains which the tools can access. Agents with unrestricted access to sensitive files and exfiltration capability are a security risk.

### Roots — query workspace boundaries (client-dependent)

Instead of hardcoding a root directory, ask the host which directories the user approved.

```typescript
// Pseudo-code. Check latest SDK docs for exact API.
const caps = server.getClientCapabilities();
if (caps?.roots) {
  const { roots } = await server.server.listRoots();
  // roots: [{ uri: "file:///home/user/project", name: "My Project" }]
}
```

---

## Development workflow

1. Implement, build and test according to repo instructions.
2. Manual smoke test: MCP Inspector (stdio):

```bash
npm run build
npx @modelcontextprotocol/inspector node dist/server.js
```

3. **Host config example** (Cursor — `~/.cursor/mcp.json` or project `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "md-vision": {
      "command": "node",
      "args": ["/absolute/path/to/md-vision-mcp/dist/server.js"]
    }
  }
}
```

Use absolute paths. After config changes, restart the host.

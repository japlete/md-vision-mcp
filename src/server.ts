import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { pathToFileURL } from "node:url";

import { createRuntimeContext, parseAccessArgs, requireAllowDomains, requireAllowPaths } from "./io/access.js";
import { indexMd, indexMdInputSchema } from "./tools/index-md.js";
import { readMdWithImages, readMdWithImagesInputSchema } from "./tools/read-md-with-images.js";

export function createServer(args: string[] = process.argv.slice(2)): McpServer {
  const access = parseAccessArgs(args);
  requireAllowPaths(access);
  requireAllowDomains(access);

  const server = new McpServer({
    name: "md-vision",
    version: "0.1.0",
  });
  const runtime = createRuntimeContext(access);

  server.registerTool(
    "read_md_with_images",
    {
      title: "Read markdown with images",
      description:
        "Read a markdown file or selected section/range and return the markdown plus referenced images as MCP image blocks. Use index_md first to discover headings.",
      inputSchema: readMdWithImagesInputSchema,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: true,
      },
    },
    (input) => readMdWithImages(input, runtime),
  );

  server.registerTool(
    "index_md",
    {
      title: "Index markdown headings",
      description:
        "Index headings in a markdown file, URL, or local folder. Returns frontmatter and TSV heading rows; use read_md_with_images to read specific content.",
      inputSchema: indexMdInputSchema,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: true,
      },
    },
    (input) => indexMd(input, runtime),
  );

  return server;
}

export async function main(): Promise<void> {
  const server = createServer();
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error: unknown) => {
    console.error(error);
    process.exit(1);
  });
}

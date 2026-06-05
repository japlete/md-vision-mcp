import { describe, expect, it } from "vitest";

import { createServer } from "../src/server.js";

interface ServerWithRegisteredTools {
  _registeredTools?: Record<string, unknown>;
}

describe("server registration", () => {
  it("registers the planned MCP tools when access flags are set", () => {
    const server = createServer(["--allow-path", process.cwd(), "--allow-domain", "none"]);
    const tools = (server as unknown as ServerWithRegisteredTools)._registeredTools;

    expect(tools).toHaveProperty("read_md_with_images");
    expect(tools).toHaveProperty("index_md");
  });

  it("fails to start without --allow-path", () => {
    expect(() => createServer(["--allow-domain", "none"])).toThrow("At least one --allow-path is required");
  });

  it("fails to start without --allow-domain", () => {
    expect(() => createServer(["--allow-path", process.cwd()])).toThrow("At least one --allow-domain is required");
  });
});

import { describe, expect, it } from "vitest";

import {
  assertDomainAllowed,
  createRuntimeContext,
  parseAccessArgs,
  requireAllowDomains,
  requireAllowPaths,
} from "../src/io/access.js";

describe("access config", () => {
  it("parses repeatable allow-path and allow-domain flags", () => {
    const access = parseAccessArgs([
      "--allow-path",
      "/docs",
      "--allow-path=/more",
      "--allow-domain",
      "example.com",
      "--allow-domain=raw.githubusercontent.com",
    ]);

    expect(access.allowPaths).toHaveLength(2);
    expect(access.allowDomains).toEqual(["example.com", "raw.githubusercontent.com"]);
  });

  it("requires at least one allow-path", () => {
    expect(() => requireAllowPaths({ allowPaths: [], allowDomains: [] })).toThrow(
      "At least one --allow-path is required",
    );
    expect(() => requireAllowPaths({ allowPaths: ["/docs"], allowDomains: ["none"] })).not.toThrow();
  });

  it("requires at least one allow-domain", () => {
    expect(() => requireAllowDomains({ allowPaths: ["/docs"], allowDomains: [] })).toThrow(
      "At least one --allow-domain is required",
    );
    expect(() => requireAllowDomains({ allowPaths: ["/docs"], allowDomains: ["none"] })).not.toThrow();
    expect(() => requireAllowDomains({ allowPaths: ["/docs"], allowDomains: ["all"] })).not.toThrow();
  });

  it("rejects conflicting allow-domain sentinels", () => {
    expect(() => requireAllowDomains({ allowPaths: ["/docs"], allowDomains: ["all", "example.com"] })).toThrow(
      "all must be the only entry",
    );
    expect(() => requireAllowDomains({ allowPaths: ["/docs"], allowDomains: ["none", "example.com"] })).toThrow(
      "none must be the only entry",
    );
    expect(() => requireAllowDomains({ allowPaths: ["/docs"], allowDomains: ["all", "none"] })).toThrow(
      "mutually exclusive",
    );
  });

  it("normalizes quoted wildcard sentinels", () => {
    const access = parseAccessArgs(["--allow-path", "/docs", "--allow-domain", '"*"']);
    expect(access.allowDomains).toEqual(["all"]);
    expect(() => requireAllowDomains(access)).not.toThrow();
  });

  it("detects shell glob expansion from an unquoted star", () => {
    expect(() =>
      requireAllowDomains({
        allowPaths: ["/docs"],
        allowDomains: ["package.json", "README.md", "dist"],
      }),
    ).toThrow("shell glob expansion");
  });

  it("enforces domain allowlists with wildcard and none sentinels", () => {
    const wildcard = createRuntimeContext({ allowPaths: ["/docs"], allowDomains: ["all"] });
    expect(() => assertDomainAllowed("docs.example.com", wildcard)).not.toThrow();

    const blocked = createRuntimeContext({ allowPaths: ["/docs"], allowDomains: ["none"] });
    expect(() => assertDomainAllowed("docs.example.com", blocked)).toThrow("URLs are disabled");

    const scoped = createRuntimeContext({ allowPaths: ["/docs"], allowDomains: ["example.com"] });
    expect(() => assertDomainAllowed("docs.example.com", scoped)).not.toThrow();
    expect(() => assertDomainAllowed("other.test", scoped)).toThrow("Domain is not allowed");
  });
});

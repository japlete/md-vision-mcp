import { describe, expect, it } from "vitest";

import { assertTextContent, looksLikeHtml, parseMediaType } from "../src/io/http-text.js";

describe("http-text", () => {
  it("parses media types without parameters", () => {
    expect(parseMediaType("text/html; charset=utf-8")).toBe("text/html");
    expect(parseMediaType("TEXT/PLAIN")).toBe("text/plain");
    expect(parseMediaType(null)).toBeNull();
  });

  it("accepts plain text and markdown bodies", () => {
    expect(() => assertTextContent("text/plain", "# Title\n\nBody", "https://example.test/doc.md")).not.toThrow();
    expect(() => assertTextContent("text/markdown", "# Title", "https://example.test/doc.md")).not.toThrow();
    expect(() =>
      assertTextContent("application/octet-stream", "# Title\n\nBody", "https://example.test/doc.md"),
    ).not.toThrow();
  });

  it("rejects HTML content types", () => {
    expect(() =>
      assertTextContent("text/html; charset=utf-8", "<html></html>", "https://example.test/doc.md"),
    ).toThrow("URL returned HTML (Content-Type: text/html), not plain text or markdown");
  });

  it("rejects HTML bodies when content type is missing or misleading", () => {
    expect(looksLikeHtml("<!DOCTYPE html><html><body>Hi</body></html>")).toBe(true);
    expect(looksLikeHtml("<html><body>Hi</body></html>")).toBe(true);
    expect(() =>
      assertTextContent(null, "<!DOCTYPE html><html><body>Hi</body></html>", "https://example.test/doc.md"),
    ).toThrow("URL returned HTML (Content-Type: unknown), not plain text or markdown");
    expect(() =>
      assertTextContent("text/plain", "<html><body>Hi</body></html>", "https://example.test/doc.md"),
    ).toThrow("URL returned HTML (Content-Type: text/plain), not plain text or markdown");
  });

  it("does not treat markdown containing HTML snippets as HTML", () => {
    const markdown = "# Example\n\n```html\n<html><body>ignored</body></html>\n```\n";
    expect(looksLikeHtml(markdown)).toBe(false);
    expect(() => assertTextContent("text/plain", markdown, "https://example.test/doc.md")).not.toThrow();
  });
});

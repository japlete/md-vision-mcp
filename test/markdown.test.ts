import { describe, expect, it } from "vitest";

import {
  buildHeadingIndex,
  collectImages,
  formatImageUrlCaption,
  parseMarkdown,
  selectMarkdown,
  shouldExposeImageUrl,
  splitMarkdownAtImages,
  stringifyFrontmatter,
  stringifyMarkdown,
} from "../src/markdown/document.js";

const document = `---
title: Demo
---

# Intro

![Logo](./logo.png)

## Details

Body text.

\`\`\`md
## Not indexed
\`\`\`

## Next

More text.
`;

describe("markdown document utilities", () => {
  it("preserves frontmatter through the remark pipeline", () => {
    expect(stringifyFrontmatter(document)).toBe(`---
title: Demo
---
`);
  });

  it("selects exact heading sections and discovers images", () => {
    const selected = selectMarkdown(document, { section: "## Details" });

    expect(selected.text).toContain("## Details");
    expect(selected.text).not.toContain("## Next");
    expect(collectImages(selected.root)).toEqual([]);
  });

  it("selects inclusive line ranges", () => {
    const selected = selectMarkdown(document, { lineRange: [5, 7] });

    expect(selected.text).toContain("# Intro");
    expect(collectImages(selected.root)).toHaveLength(1);
  });

  it("indexes headings while ignoring headings inside fenced code blocks", () => {
    const rows = buildHeadingIndex(document);

    expect(rows.map((row) => row.heading)).toEqual(["# Intro", "## Details", "## Next"]);
    expect(rows[0]?.imageCount).toBe(1);
    expect(rows.some((row) => row.heading === "## Not indexed")).toBe(false);
  });

  it("returns a useful error for missing exact sections", () => {
    expect(() => selectMarkdown(document, { section: "Details" })).toThrow("Section not found");
  });

  it("parses markdown with GFM constructs", () => {
    const root = parseMarkdown("- [x] done\n\n| a |\n| - |\n| b |\n");

    expect(root.children.length).toBeGreaterThan(0);
  });

  it("exposes resolvable image URLs but not inline data URIs", () => {
    expect(shouldExposeImageUrl("https://example.test/chart.png")).toBe(true);
    expect(shouldExposeImageUrl("data:image/png;base64,abcd")).toBe(false);
    expect(shouldExposeImageUrl(`https://example.test/${"a".repeat(600)}`)).toBe(false);
    expect(formatImageUrlCaption("https://example.test/chart.png")).toBe("https://example.test/chart.png\n\n");
  });

  it("splits markdown into text and image segments in document order", () => {
    const root = parseMarkdown("# Intro\n\n![logo](./logo.png)\n\n## Next\n");
    const segments = splitMarkdownAtImages(root);

    expect(segments.map((segment) => segment.kind)).toEqual(["text", "image", "text"]);
    expect(stringifyMarkdown((segments[0] as { kind: "text"; root: ReturnType<typeof parseMarkdown> }).root)).toContain(
      "# Intro",
    );
    expect((segments[1] as { kind: "image"; image: { url: string } }).image.url).toBe("./logo.png");
    expect(stringifyMarkdown((segments[2] as { kind: "text"; root: ReturnType<typeof parseMarkdown> }).root)).toContain(
      "## Next",
    );
  });
});


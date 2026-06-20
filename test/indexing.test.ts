import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { dir } from "tmp-promise";

import { indexMarkdownFile, indexMarkdownFolder, indexMarkdownText } from "../src/indexing.js";

describe("standalone indexing", () => {
  it("indexes markdown text with frontmatter and heading rows", () => {
    const markdown = `---
title: Demo
---

# Intro

![Logo](./logo.png)

## Details

Body text.

\`\`\`md
## Not indexed
\`\`\`
`;

    const index = indexMarkdownText(markdown, { path: "docs/demo.md" });

    expect(index.path).toBe("docs/demo.md");
    expect(index.frontmatter).toBe("---\ntitle: Demo\n---");
    expect(index.lineCount).toBeGreaterThan(0);
    expect(index.charCount).toBe(markdown.length);
    expect(index.rows.map((row) => row.heading)).toEqual(["# Intro", "## Details"]);
    expect(index.rows[0]?.imageCount).toBe(1);
  });

  it("indexes a local markdown file", async () => {
    const temp = await dir({ unsafeCleanup: true });
    try {
      const markdownPath = path.join(temp.path, "guide.md");
      await writeFile(markdownPath, "# Guide\n\n## Setup\n");

      const index = await indexMarkdownFile(markdownPath);

      expect(index.path).toBe(markdownPath);
      expect(index.rows.map((row) => row.heading)).toEqual(["# Guide", "## Setup"]);
    } finally {
      await temp.cleanup();
    }
  });

  it("indexes a local folder in stable sorted order", async () => {
    const temp = await dir({ unsafeCleanup: true });
    try {
      const docsDir = path.join(temp.path, "docs");
      await mkdir(docsDir);
      await writeFile(path.join(docsDir, "b.md"), "# B\n");
      await writeFile(
        path.join(docsDir, "a.md"),
        "---\ntitle: A\n---\n\n# A\n\n```md\n## Ignored\n```\n\n## A child\n",
      );

      const files = await indexMarkdownFolder(docsDir);

      expect(files.map((file) => path.basename(file.path ?? ""))).toEqual(["a.md", "b.md"]);
      expect(files[0]?.frontmatter).toBe("---\ntitle: A\n---");
      expect(files[0]?.rows.map((row) => row.heading)).toEqual(["# A", "## A child"]);
      expect(files[0]?.rows.some((row) => row.heading === "## Ignored")).toBe(false);
    } finally {
      await temp.cleanup();
    }
  });

  it("rejects directories passed to indexMarkdownFile", async () => {
    const temp = await dir({ unsafeCleanup: true });
    try {
      await expect(indexMarkdownFile(temp.path)).rejects.toThrow("Expected a markdown file");
    } finally {
      await temp.cleanup();
    }
  });

  it("rejects files passed to indexMarkdownFolder", async () => {
    const temp = await dir({ unsafeCleanup: true });
    try {
      const markdownPath = path.join(temp.path, "doc.md");
      await writeFile(markdownPath, "# Doc\n");

      await expect(indexMarkdownFolder(markdownPath)).rejects.toThrow("Expected a folder");
    } finally {
      await temp.cleanup();
    }
  });
});

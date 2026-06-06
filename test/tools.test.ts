import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import nock from "nock";
import { afterEach, describe, expect, it } from "vitest";
import { dir } from "tmp-promise";

import type { RuntimeContext } from "../src/io/access.js";
import { readMarkdownResource } from "../src/io/resources.js";
import { loadMarkdownImage } from "../src/images/load.js";
import type { MarkdownImage } from "../src/markdown/document.js";
import { indexMd } from "../src/tools/index-md.js";
import { readMdWithImages } from "../src/tools/read-md-with-images.js";

const onePixelPng = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAghI0GQAAAABJRU5ErkJggg==",
  "base64",
);
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"><rect width="1" height="1" fill="red"/></svg>`;

function runtime(access: RuntimeContext["access"], overrides: Partial<RuntimeContext> = {}): RuntimeContext {
  return {
    access,
    fetch: globalThis.fetch.bind(globalThis),
    ...overrides,
  };
}

describe("tool handlers", () => {
  afterEach(() => {
    nock.cleanAll();
    nock.enableNetConnect();
  });

  it("inlines images referenced with html img tags", async () => {
    const temp = await dir({ unsafeCleanup: true });
    try {
      await writeFile(path.join(temp.path, "diagram.svg"), svg);
      const markdownPath = path.join(temp.path, "doc.md");
      await writeFile(
        markdownPath,
        '# HTML image\n\n<img src="./diagram.svg" alt="diagram" width="400"/>\n\nDone.\n',
      );

      const result = await readMdWithImages({ uri: markdownPath }, runtime({ allowPaths: [temp.path], allowDomains: ["none"] }));

      expect(result.isError).not.toBe(true);
      expect(result.content.filter((block) => block.type === "image")).toHaveLength(1);
      expect(result.content.map((block) => block.type)).toEqual(["text", "image", "text"]);
      expect(result.content[0]?.type === "text" ? result.content[0].text : "").not.toContain("<img");
      expect(result.content[2]?.type === "text" ? result.content[2].text : "").toContain("Done.");
    } finally {
      await temp.cleanup();
    }
  });

  it("reads markdown and inlines local raster and SVG images", async () => {
    const temp = await dir({ unsafeCleanup: true });
    try {
      await writeFile(path.join(temp.path, "pixel.png"), onePixelPng);
      await writeFile(path.join(temp.path, "vector.svg"), svg);
      const markdownPath = path.join(temp.path, "doc.md");
      await writeFile(markdownPath, "# Images\n\n![pixel](./pixel.png)\n\n![vector](./vector.svg)\n");

      const result = await readMdWithImages({ uri: markdownPath }, runtime({ allowPaths: [temp.path], allowDomains: ["none"] }));

      expect(result.isError).not.toBe(true);
      expect(result.content.filter((block) => block.type === "image")).toHaveLength(2);
      expect(result.content.map((block) => block.type)).toEqual(["text", "image", "text", "image"]);
      expect(result.content[0]?.type === "text" ? result.content[0].text : "").toContain("pixel.png");
      expect(result.content[2]?.type === "text" ? result.content[2].text : "").toContain("vector.svg");
    } finally {
      await temp.cleanup();
    }
  });

  it("interleaves an early image before trailing markdown", async () => {
    const temp = await dir({ unsafeCleanup: true });
    try {
      await writeFile(path.join(temp.path, "chart.png"), onePixelPng);
      const markdownPath = path.join(temp.path, "doc.md");
      await writeFile(
        markdownPath,
        "# Title\n\nIntro paragraph.\n\n![chart](./chart.png)\n\n## Later\n\nTail text.\n",
      );

      const result = await readMdWithImages({ uri: markdownPath }, runtime({ allowPaths: [temp.path], allowDomains: ["none"] }));
      const types = result.content.map((block) => block.type);
      const imageIndex = types.indexOf("image");
      const lastText = result.content.at(-1);

      expect(result.isError).not.toBe(true);
      expect(types.slice(0, imageIndex)).toEqual(["text"]);
      expect(result.content[imageIndex - 1]?.type === "text" ? result.content[imageIndex - 1].text : "").toContain(
        "chart.png",
      );
      expect(types.slice(imageIndex + 1)).toContain("text");
      expect(lastText).toMatchObject({ type: "text" });
      expect(lastText?.type === "text" ? lastText.text : "").toContain("## Later");
    } finally {
      await temp.cleanup();
    }
  });

  it("honors max_images", async () => {
    const temp = await dir({ unsafeCleanup: true });
    try {
      await writeFile(path.join(temp.path, "a.png"), onePixelPng);
      await writeFile(path.join(temp.path, "b.png"), onePixelPng);
      const markdownPath = path.join(temp.path, "doc.md");
      await writeFile(markdownPath, "# Images\n\n![a](./a.png)\n\n![b](./b.png)\n");

      const result = await readMdWithImages(
        { uri: markdownPath, max_images: 1 },
        runtime({ allowPaths: [temp.path], allowDomains: ["none"] }),
      );

      expect(result.isError).not.toBe(true);
      expect(result.content.filter((block) => block.type === "image")).toHaveLength(1);
    } finally {
      await temp.cleanup();
    }
  });

  it("returns MCP tool errors for missing sections without line_range", async () => {
    const temp = await dir({ unsafeCleanup: true });
    try {
      const markdownPath = path.join(temp.path, "doc.md");
      await writeFile(markdownPath, "# Present\n");

      const result = await readMdWithImages(
        { uri: markdownPath, section: "## Missing" },
        runtime({ allowPaths: [temp.path], allowDomains: ["none"] }),
      );

      expect(result.isError).toBe(true);
      expect(result.content[0]).toMatchObject({ type: "text" });
      expect(result.content[0]?.type === "text" ? result.content[0].text : "").toContain("Section not found");
    } finally {
      await temp.cleanup();
    }
  });

  it("falls back to line_range when section is not found", async () => {
    const temp = await dir({ unsafeCleanup: true });
    try {
      const markdownPath = path.join(temp.path, "doc.md");
      await writeFile(markdownPath, "# Present\n\nBody.\n");

      const result = await readMdWithImages(
        { uri: markdownPath, section: "## Missing", line_range: [1, 1] },
        runtime({ allowPaths: [temp.path], allowDomains: ["none"] }),
      );

      expect(result.isError).not.toBe(true);
      expect(result.content[0]).toMatchObject({ type: "text" });
      expect(result.content[0]?.type === "text" ? result.content[0].text : "").toContain("# Present");
    } finally {
      await temp.cleanup();
    }
  });

  it("rejects file:// URIs", async () => {
    await expect(
      readMarkdownResource(
        "file:///tmp/doc.md",
        runtime({ allowPaths: [process.cwd()], allowDomains: ["none"] }),
      ),
    ).rejects.toThrow("file:// URIs are not supported");
  });

  it("indexes a local folder in stable order with frontmatter and TSV rows", async () => {
    const temp = await dir({ unsafeCleanup: true });
    try {
      const docsDir = path.join(temp.path, "docs");
      await mkdir(docsDir);
      await writeFile(path.join(docsDir, "b.md"), "# B\n");
      await writeFile(
        path.join(docsDir, "a.md"),
        "---\ntitle: A\n---\n\n# A\n\n```md\n## Ignored\n```\n\n## A child\n",
      );

      const result = await indexMd({ uri: docsDir }, runtime({ allowPaths: [temp.path], allowDomains: ["none"] }));
      const text = result.content[0]?.type === "text" ? result.content[0].text : "";

      expect(result.isError).not.toBe(true);
      expect(text.indexOf("a.md")).toBeLessThan(text.indexOf("b.md"));
      expect(text).toContain("---\ntitle: A\n---");
      expect(text).toContain("heading\tline_start\tn_images\tchar_count");
      expect(text).toContain("# A\t5\t0\t");
      expect(text).not.toContain("## Ignored");
    } finally {
      await temp.cleanup();
    }
  });

  it("reads remote SVG images when content is sniffed as application/xml", async () => {
    nock.disableNetConnect();
    nock("https://docs.example.test")
      .get("/doc.md")
      .reply(200, '# Remote\n\n<img src="./chart.svg" alt="chart"/>\n', {
        "content-type": "text/plain",
      });
    nock("https://docs.example.test").get("/chart.svg").reply(200, svg, {
      "content-type": "image/svg+xml",
    });

    const result = await readMdWithImages(
      { uri: "https://docs.example.test/doc.md" },
      runtime({ allowPaths: [process.cwd()], allowDomains: ["docs.example.test"] }),
    );

    expect(result.isError).not.toBe(true);
    expect(result.content.filter((block) => block.type === "image")).toHaveLength(1);
  });

  it("reads remote markdown and images through nock", async () => {
    nock.disableNetConnect();
    nock("https://docs.example.test").get("/doc.md").reply(200, "# Remote\n\n![r](./r.png)\n", {
      "content-type": "text/plain",
    });
    nock("https://docs.example.test").get("/r.png").reply(200, onePixelPng, {
      "content-type": "image/png",
    });

    const result = await readMdWithImages(
      { uri: "https://docs.example.test/doc.md" },
      runtime({ allowPaths: [process.cwd()], allowDomains: ["docs.example.test"] }),
    );

    expect(result.isError).not.toBe(true);
    expect(result.content.filter((block) => block.type === "image")).toHaveLength(1);
    expect(result.content[0]?.type === "text" ? result.content[0].text : "").toContain(
      "https://docs.example.test/r.png",
    );
  });

  it("omits long data URI text before inlined images", async () => {
    const encodedSvg = encodeURIComponent(svg);
    const temp = await dir({ unsafeCleanup: true });
    try {
      const markdownPath = path.join(temp.path, "doc.md");
      await writeFile(markdownPath, `# Inline\n\n![vector](data:image/svg+xml,${encodedSvg})\n`);

      const result = await readMdWithImages({ uri: markdownPath }, runtime({ allowPaths: [temp.path], allowDomains: ["none"] }));
      const text = result.content
        .filter((block) => block.type === "text")
        .map((block) => (block.type === "text" ? block.text : ""))
        .join("\n");

      expect(result.isError).not.toBe(true);
      expect(result.content.some((block) => block.type === "image")).toBe(true);
      expect(text).not.toContain("data:image/svg+xml,");
      expect(text).not.toContain(encodedSvg);
    } finally {
      await temp.cleanup();
    }
  });

  it("rejects remote HTML responses for markdown URLs", async () => {
    nock.disableNetConnect();
    nock("https://docs.example.test")
      .get("/viewer.md")
      .reply(200, "<!DOCTYPE html><html><body><h1>Viewer</h1></body></html>", {
        "content-type": "text/html; charset=utf-8",
      });

    const result = await readMdWithImages(
      { uri: "https://docs.example.test/viewer.md" },
      runtime({ allowPaths: [process.cwd()], allowDomains: ["docs.example.test"] }),
    );

    expect(result.isError).toBe(true);
    expect(result.content[0]?.type === "text" ? result.content[0].text : "").toContain(
      "URL returned HTML (Content-Type: text/html), not plain text or markdown",
    );
  });

  it("enforces allowed local paths", async () => {
    const temp = await dir({ unsafeCleanup: true });
    try {
      const markdownPath = path.join(temp.path, "doc.md");
      await writeFile(markdownPath, "# Hidden\n");

      await expect(
        readMarkdownResource(
          markdownPath,
          runtime({ allowPaths: [path.join(temp.path, "other")], allowDomains: ["none"] }),
        ),
      ).rejects.toThrow("Path is not allowed");
    } finally {
      await temp.cleanup();
    }
  });

  it("loads data URI SVG images", async () => {
    const encodedSvg = encodeURIComponent(svg);
    const image: MarkdownImage = {
      url: `data:image/svg+xml,${encodedSvg}`,
    };

    const loaded = await loadMarkdownImage(
      image,
      "/tmp/doc.md",
      runtime({ allowPaths: [process.cwd()], allowDomains: ["none"] }),
    );

    expect(loaded.mimeType).toBe("image/png");
    expect(loaded.data.length).toBeGreaterThan(0);
  });
});


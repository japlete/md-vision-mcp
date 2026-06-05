import { describe, expect, it } from "vitest";

import {
  collectImages,
  formatImageReference,
  parseMarkdown,
  splitMarkdownAtImages,
  stringifyMarkdown,
} from "../src/markdown/document.js";
import { htmlContainsImg, parseImgTagsFromHtml, splitHtmlAtImages } from "../src/markdown/html-images.js";

describe("html image parsing", () => {
  it("detects img tags in html strings", () => {
    const tag = '<img src="images/a.svg" alt="Train" width="1200"/>';
    expect(htmlContainsImg(tag)).toBe(true);
    expect(parseImgTagsFromHtml(tag)).toEqual([
      {
        url: "images/a.svg",
        alt: "Train",
        html: tag,
      },
    ]);
  });

  it("splits html around img tags", () => {
    const parts = splitHtmlAtImages('<p>before</p><img src="a.png"/><p>after</p>');
    expect(parts.map((part) => part.kind)).toEqual(["text", "image", "text"]);
    expect(parts[1]).toMatchObject({ kind: "image", image: { url: "a.png" } });
  });

  it("splits markdown with html img tags for inlining", () => {
    const root = parseMarkdown(
      "# Example\n\n*caption*\n\n<img src=\"./chart.svg\" alt=\"Chart\" width=\"400\"/>\n\nTail.\n",
    );
    const segments = splitMarkdownAtImages(root);

    expect(collectImages(root)).toHaveLength(1);
    expect(segments.map((segment) => segment.kind)).toEqual(["text", "image", "text"]);
    expect((segments[1] as { kind: "image"; image: { url: string; html?: string } }).image.url).toBe("./chart.svg");
    expect(formatImageReference((segments[1] as { kind: "image"; image: { html?: string } }).image)).toContain(
      "<img",
    );
    expect(stringifyMarkdown((segments[0] as { kind: "text"; root: ReturnType<typeof parseMarkdown> }).root)).toContain(
      "*caption*",
    );
    expect(stringifyMarkdown((segments[2] as { kind: "text"; root: ReturnType<typeof parseMarkdown> }).root)).toContain(
      "Tail.",
    );
  });
});

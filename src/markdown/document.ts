import { toString } from "mdast-util-to-string";
import type { Content, Heading, Html, Image, Paragraph, PhrasingContent, Root, YAML } from "mdast";
import { htmlContainsImg, parseImgTagsFromHtml, splitHtmlAtImages } from "./html-images.js";
import remarkFrontmatter from "remark-frontmatter";
import remarkGfm from "remark-gfm";
import remarkParse from "remark-parse";
import remarkStringify from "remark-stringify";
import { unified } from "unified";
import { EXIT, visit } from "unist-util-visit";

export interface LineRange {
  start: number;
  end: number;
}

export interface SelectedMarkdown {
  root: Root;
  text: string;
  range: LineRange;
}

export interface MarkdownImage {
  url: string;
  alt?: string;
  title?: string;
  /** Original `<img>` tag when parsed from HTML. */
  html?: string;
}

export type MarkdownSegment =
  | { kind: "text"; root: Root }
  | { kind: "image"; image: MarkdownImage };

export interface HeadingIndexRow {
  heading: string;
  lineStart: number;
  imageCount: number;
  charCount: number;
}

const processor = unified()
  .use(remarkParse)
  .use(remarkGfm)
  .use(remarkFrontmatter, ["yaml"])
  .use(remarkStringify, {
    bullet: "-",
    fences: true,
    listItemIndent: "one",
  });

export function parseMarkdown(text: string): Root {
  return processor.parse(text) as Root;
}

export function stringifyMarkdown(root: Root): string {
  return processor.stringify(root);
}

export function selectMarkdown(
  text: string,
  options: { section?: string; lineRange?: readonly [number, number] },
): SelectedMarkdown {
  const root = parseMarkdown(text);
  const totalLines = countLines(text);

  if (options.section) {
    const range = findSectionRange(root, options.section, totalLines);
    const sectionRoot = rootFromChildren(childrenWithinRange(root.children, range));
    return {
      root: sectionRoot,
      text: stringifyMarkdown(sectionRoot),
      range,
    };
  }

  if (options.lineRange) {
    const [start, end] = options.lineRange;
    if (start > end) {
      throw new Error(`line_range start must be <= end. Received [${start}, ${end}].`);
    }
    if (end > totalLines) {
      throw new Error(`line_range end ${end} exceeds document length ${totalLines}.`);
    }

    const selectedText = sliceLines(text, { start, end });
    const selectedRoot = parseMarkdown(selectedText);
    return {
      root: selectedRoot,
      text: stringifyMarkdown(selectedRoot),
      range: { start, end },
    };
  }

  return {
    root,
    text: stringifyMarkdown(root),
    range: { start: 1, end: totalLines },
  };
}

export function collectImages(root: Root): MarkdownImage[] {
  const images: MarkdownImage[] = [];
  visit(root, (node) => {
    if (node.type === "image") {
      images.push(toMarkdownImage(node));
      return;
    }
    if (node.type === "html") {
      images.push(...parseImgTagsFromHtml(node.value));
    }
  });
  return images;
}

export function splitMarkdownAtImages(root: Root): MarkdownSegment[] {
  return splitBlockChildren(root.children);
}

export const MAX_EXPOSED_IMAGE_URL_LENGTH = 512;

export function shouldExposeImageUrl(url: string): boolean {
  if (url.startsWith("data:")) {
    return false;
  }
  return url.length <= MAX_EXPOSED_IMAGE_URL_LENGTH;
}

export function formatImageUrlCaption(resolvedUrl: string): string {
  return `${resolvedUrl}\n\n`;
}

export function formatImageMarkdown(image: MarkdownImage): string {
  const alt = image.alt ?? "";
  if (image.title) {
    return `![${alt}](${image.url} "${image.title}")`;
  }
  return `![${alt}](${image.url})`;
}

export function formatImageReference(image: MarkdownImage): string {
  return image.html ?? formatImageMarkdown(image);
}

export function buildHeadingIndex(text: string): HeadingIndexRow[] {
  const root = parseMarkdown(text);
  const totalLines = countLines(text);
  const headings = root.children.filter(isHeading);

  return headings.map((heading) => {
    const range = sectionRangeForHeading(root, heading, totalLines);
    const sectionRoot = rootFromChildren(childrenWithinRange(root.children, range));
    const sectionText = stringifyMarkdown(sectionRoot);
    return {
      heading: formatHeading(heading),
      lineStart: heading.position?.start.line ?? range.start,
      imageCount: collectImages(sectionRoot).length,
      charCount: sectionText.length,
    };
  });
}

export function stringifyFrontmatter(text: string): string {
  const root = parseMarkdown(text);
  const frontmatter = root.children.filter(isFrontmatter);
  if (frontmatter.length === 0) {
    return "";
  }
  return stringifyMarkdown(rootFromChildren(frontmatter));
}

export function countLines(text: string): number {
  return text.length === 0 ? 0 : text.split(/\r\n|\r|\n/).length;
}

function findSectionRange(root: Root, section: string, totalLines: number): LineRange {
  const heading = root.children.find((child) => isHeading(child) && formatHeading(child) === section);
  if (!heading) {
    throw new Error(`Section not found: ${section}. Use index_md to inspect available headings.`);
  }
  return sectionRangeForHeading(root, heading, totalLines);
}

function sectionRangeForHeading(root: Root, heading: Heading, totalLines: number): LineRange {
  const start = heading.position?.start.line;
  if (!start) {
    throw new Error(`Heading has no source position: ${formatHeading(heading)}`);
  }

  const nextHeading = root.children.find((child) => {
    if (!isHeading(child) || child === heading) {
      return false;
    }
    const line = child.position?.start.line;
    return Boolean(line && line > start && child.depth <= heading.depth);
  });

  return {
    start,
    end: nextHeading?.position?.start.line ? nextHeading.position.start.line - 1 : totalLines,
  };
}

function childrenWithinRange(children: Content[], range: LineRange): Content[] {
  return children.filter((child) => {
    const start = child.position?.start.line;
    const end = child.position?.end.line;
    return Boolean(start && end && start >= range.start && end <= range.end);
  });
}

function rootFromChildren(children: Content[]): Root {
  return { type: "root", children };
}

function formatHeading(heading: Heading): string {
  return `${"#".repeat(heading.depth)} ${toString(heading)}`;
}

function isHeading(node: Content): node is Heading {
  return node.type === "heading";
}

function isFrontmatter(node: Content): node is YAML {
  return node.type === "yaml";
}

function sliceLines(text: string, range: LineRange): string {
  return text.split(/\r\n|\r|\n/).slice(range.start - 1, range.end).join("\n");
}

function toMarkdownImage(node: Image): MarkdownImage {
  return {
    url: node.url,
    alt: node.alt ?? undefined,
    title: node.title ?? undefined,
  };
}

function containsImages(node: Content | PhrasingContent): boolean {
  let found = false;
  visit(node, (visited) => {
    if (visited.type === "image") {
      found = true;
      return EXIT;
    }
    if (visited.type === "html" && htmlContainsImg(visited.value)) {
      found = true;
      return EXIT;
    }
  });
  return found;
}

function pushHtmlImageSegments(segments: MarkdownSegment[], html: string, wrap: (value: string) => Root): void {
  const parts = splitHtmlAtImages(html);
  if (!parts.some((part) => part.kind === "image")) {
    return;
  }

  for (const part of parts) {
    if (part.kind === "image") {
      segments.push({ kind: "image", image: part.image });
      continue;
    }
    if (part.value) {
      segments.push({ kind: "text", root: wrap(part.value) });
    }
  }
}

function htmlNode(value: string): Html {
  return { type: "html", value };
}

function splitBlockChildren(children: Content[]): MarkdownSegment[] {
  const segments: MarkdownSegment[] = [];
  let buffer: Content[] = [];

  const flush = () => {
    if (buffer.length > 0) {
      segments.push({ kind: "text", root: rootFromChildren(buffer) });
      buffer = [];
    }
  };

  for (const child of children) {
    if (child.type === "image") {
      flush();
      segments.push({ kind: "image", image: toMarkdownImage(child) });
      continue;
    }

    if (child.type === "html" && htmlContainsImg(child.value)) {
      flush();
      pushHtmlImageSegments(segments, child.value, (value) => rootFromChildren([htmlNode(value)]));
      continue;
    }

    if (containsImages(child)) {
      flush();
      segments.push(...splitContent(child));
      continue;
    }

    buffer.push(child);
  }

  flush();
  return segments;
}

function splitContent(node: Content): MarkdownSegment[] {
  if (node.type === "image") {
    return [{ kind: "image", image: toMarkdownImage(node) }];
  }

  if (node.type === "html" && htmlContainsImg(node.value)) {
    const segments: MarkdownSegment[] = [];
    pushHtmlImageSegments(segments, node.value, (value) => rootFromChildren([htmlNode(value)]));
    return segments;
  }

  if (node.type === "paragraph") {
    return splitParagraph(node);
  }

  if ("children" in node && Array.isArray(node.children)) {
    return splitParentNode(node);
  }

  return [{ kind: "text", root: rootFromChildren([node]) }];
}

function splitParagraph(paragraph: Paragraph): MarkdownSegment[] {
  const segments: MarkdownSegment[] = [];
  let buffer: PhrasingContent[] = [];

  const flush = () => {
    if (buffer.length > 0) {
      segments.push({
        kind: "text",
        root: rootFromChildren([{ ...paragraph, children: buffer }]),
      });
      buffer = [];
    }
  };

  for (const child of paragraph.children) {
    if (child.type === "image") {
      flush();
      segments.push({ kind: "image", image: toMarkdownImage(child) });
      continue;
    }

    if (child.type === "html" && htmlContainsImg(child.value)) {
      flush();
      pushHtmlImageSegments(segments, child.value, (value) =>
        rootFromChildren([{ ...paragraph, children: [htmlNode(value)] }]),
      );
      continue;
    }

    if (containsImages(child)) {
      flush();
      segments.push(...splitPhrasing(child, paragraph));
      continue;
    }

    buffer.push(child);
  }

  flush();
  return segments;
}

function splitPhrasing(node: PhrasingContent, paragraph: Paragraph): MarkdownSegment[] {
  if (node.type === "image") {
    return [{ kind: "image", image: toMarkdownImage(node) }];
  }

  if (node.type === "html" && htmlContainsImg(node.value)) {
    const segments: MarkdownSegment[] = [];
    pushHtmlImageSegments(segments, node.value, (value) =>
      rootFromChildren([{ ...paragraph, children: [htmlNode(value)] }]),
    );
    return segments;
  }

  if (!("children" in node) || !Array.isArray(node.children)) {
    return [{ kind: "text", root: rootFromChildren([{ ...paragraph, children: [node] }]) }];
  }

  const segments: MarkdownSegment[] = [];
  let buffer: PhrasingContent[] = [];

  const flush = () => {
    if (buffer.length > 0) {
      segments.push({
        kind: "text",
        root: rootFromChildren([{ ...paragraph, children: [{ ...node, children: buffer }] }]),
      });
      buffer = [];
    }
  };

  for (const child of node.children) {
    if (child.type === "image") {
      flush();
      segments.push({ kind: "image", image: toMarkdownImage(child) });
      continue;
    }

    if (child.type === "html" && htmlContainsImg(child.value)) {
      flush();
      pushHtmlImageSegments(segments, child.value, (value) =>
        rootFromChildren([{ ...paragraph, children: [{ ...node, children: [htmlNode(value)] }] }]),
      );
      continue;
    }

    if (containsImages(child)) {
      flush();
      segments.push(...splitPhrasing(child, paragraph));
      continue;
    }

    buffer.push(child);
  }

  flush();
  return segments;
}

function splitParentNode<T extends Content & { children: Content[] }>(node: T): MarkdownSegment[] {
  const segments: MarkdownSegment[] = [];
  let buffer: Content[] = [];

  const flush = () => {
    if (buffer.length > 0) {
      segments.push({ kind: "text", root: rootFromChildren([{ ...node, children: buffer }]) });
      buffer = [];
    }
  };

  for (const child of node.children) {
    if (child.type === "image") {
      flush();
      segments.push({ kind: "image", image: toMarkdownImage(child) });
      continue;
    }

    if (child.type === "html" && htmlContainsImg(child.value)) {
      flush();
      pushHtmlImageSegments(segments, child.value, (value) =>
        rootFromChildren([{ ...node, children: [htmlNode(value)] }]),
      );
      continue;
    }

    if (containsImages(child)) {
      flush();
      segments.push(...splitContent(child));
      continue;
    }

    buffer.push(child);
  }

  flush();
  return segments;
}


import type { MarkdownImage } from "./document.js";

const IMG_TAG_RE = /<img\b[^>]*?\/?>/gi;

const ATTR_RE =
  /([a-zA-Z][a-zA-Z0-9:_-]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>/]+))/g;

export type HtmlImageSegment =
  | { kind: "text"; value: string }
  | { kind: "image"; image: MarkdownImage };

export function htmlContainsImg(html: string): boolean {
  return /<img\b/i.test(html);
}

export function parseImgTagsFromHtml(html: string): MarkdownImage[] {
  const images: MarkdownImage[] = [];
  for (const match of html.matchAll(IMG_TAG_RE)) {
    const image = parseImgTag(match[0]);
    if (image) {
      images.push(image);
    }
  }
  return images;
}

export function splitHtmlAtImages(html: string): HtmlImageSegment[] {
  const segments: HtmlImageSegment[] = [];
  let lastIndex = 0;
  let foundImage = false;

  for (const match of html.matchAll(IMG_TAG_RE)) {
    const tag = match[0];
    const index = match.index ?? 0;
    foundImage = true;

    const before = html.slice(lastIndex, index);
    if (before) {
      segments.push({ kind: "text", value: before });
    }

    const image = parseImgTag(tag);
    if (image) {
      segments.push({ kind: "image", image });
    } else {
      segments.push({ kind: "text", value: tag });
    }

    lastIndex = index + tag.length;
  }

  if (!foundImage) {
    return [{ kind: "text", value: html }];
  }

  const after = html.slice(lastIndex);
  if (after) {
    segments.push({ kind: "text", value: after });
  }

  return segments;
}

function parseImgTag(tag: string): MarkdownImage | null {
  const src = getAttribute(tag, "src");
  if (!src) {
    return null;
  }

  return {
    url: decodeHtmlEntities(src),
    alt: getAttribute(tag, "alt"),
    title: getAttribute(tag, "title"),
    html: tag,
  };
}

function getAttribute(tag: string, name: string): string | undefined {
  const lowerName = name.toLowerCase();
  for (const match of tag.matchAll(ATTR_RE)) {
    const attrName = match[1]?.toLowerCase();
    if (attrName !== lowerName) {
      continue;
    }
    const value = match[2] ?? match[3] ?? match[4];
    return value === undefined ? undefined : decodeHtmlEntities(value);
  }
  return undefined;
}

function decodeHtmlEntities(value: string): string {
  return value
    .replaceAll("&amp;", "&")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&quot;", '"')
    .replaceAll("&#39;", "'");
}

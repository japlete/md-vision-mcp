const HTML_CONTENT_TYPES = new Set(["text/html", "application/xhtml+xml"]);

const SNIFF_LENGTH = 2048;

export function assertTextContent(contentType: string | null | undefined, body: string, uri: string): void {
  const mediaType = parseMediaType(contentType);
  if (mediaType && HTML_CONTENT_TYPES.has(mediaType)) {
    throw textExpectedError(uri, mediaType);
  }
  if (looksLikeHtml(body)) {
    throw textExpectedError(uri, mediaType ?? "unknown");
  }
}

export function parseMediaType(contentType: string | null | undefined): string | null {
  if (!contentType) {
    return null;
  }

  const semicolon = contentType.indexOf(";");
  const base = (semicolon === -1 ? contentType : contentType.slice(0, semicolon)).trim().toLowerCase();
  return base.length > 0 ? base : null;
}

export function looksLikeHtml(body: string): boolean {
  const snippet = body.trimStart().slice(0, SNIFF_LENGTH);
  if (snippet.length === 0) {
    return false;
  }

  const lower = snippet.toLowerCase();
  if (lower.startsWith("<!doctype html") || lower.startsWith("<html")) {
    return true;
  }

  return /^<!(?:doctype\s+html|--)/i.test(snippet);
}

function textExpectedError(uri: string, contentType: string): Error {
  return new Error(`URL returned HTML (Content-Type: ${contentType}), not plain text or markdown: ${uri}`);
}

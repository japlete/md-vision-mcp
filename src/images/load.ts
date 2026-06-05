import { Resvg } from "@resvg/resvg-js";
import { fileTypeFromBuffer } from "file-type";
import { lookup as lookupMime } from "mime-types";
import sharp from "sharp";

import type { RuntimeContext } from "../io/access.js";
import { readBinaryResource, resolveReference } from "../io/resources.js";
import type { MarkdownImage } from "../markdown/document.js";

export interface LoadedImage {
  sourceUri: string;
  alt?: string;
  data: string;
  mimeType: string;
}

const MAX_DIMENSION = 1568;

export async function loadMarkdownImage(
  image: MarkdownImage,
  baseUri: string,
  runtime: RuntimeContext,
): Promise<LoadedImage> {
  const resolvedUri = resolveReference(image.url, baseUri);
  const original = resolvedUri.startsWith("data:")
    ? readDataUri(resolvedUri)
    : await readBinaryResource(resolvedUri, runtime);
  const detectedMime = await detectMime(original.data, original.uri);
  if (!detectedMime.startsWith("image/")) {
    throw new Error(`Referenced resource is not an image: ${image.url}`);
  }

  const normalized = isSvg(detectedMime, original.uri)
    ? renderSvgToPng(original.data)
    : await resizeRasterToPng(original.data);

  return {
    sourceUri: original.uri,
    alt: image.alt,
    data: normalized.toString("base64"),
    mimeType: "image/png",
  };
}

export async function detectMime(data: Buffer, uri: string): Promise<string> {
  if (uri.startsWith("data:")) {
    const dataUriMime = /^data:([^;,]+)/.exec(uri)?.[1];
    if (dataUriMime) {
      return dataUriMime;
    }
  }

  const extensionSource = uri.startsWith("data:") ? uri : new URL(uri).pathname;
  const extensionMime = lookupMime(extensionSource);

  const sniffed = await fileTypeFromBuffer(data);
  if (sniffed?.mime) {
    // SVG is often sniffed as application/xml; prefer a known image extension.
    if (extensionMime?.startsWith("image/") && !sniffed.mime.startsWith("image/")) {
      return extensionMime;
    }
    return sniffed.mime;
  }

  if (extensionMime) {
    return extensionMime;
  }

  return "application/octet-stream";
}

function renderSvgToPng(data: Buffer): Buffer {
  return new Resvg(data).render().asPng();
}

async function resizeRasterToPng(data: Buffer): Promise<Buffer> {
  return sharp(data, { animated: false })
    .rotate()
    .resize({
      width: MAX_DIMENSION,
      height: MAX_DIMENSION,
      fit: "inside",
      withoutEnlargement: true,
    })
    .png()
    .toBuffer();
}

function isSvg(mimeType: string, uri: string): boolean {
  return mimeType === "image/svg+xml" || (!uri.startsWith("data:") && new URL(uri).pathname.endsWith(".svg"));
}

function readDataUri(uri: string): { uri: string; data: Buffer } {
  const match = /^data:([^;,]+)?(;base64)?,(.*)$/s.exec(uri);
  if (!match) {
    throw new Error("Invalid data URI image reference.");
  }

  const [, mimeType = "application/octet-stream", base64Flag, payload] = match;
  const data = base64Flag ? Buffer.from(payload, "base64") : Buffer.from(decodeURIComponent(payload));
  return {
    uri: `data:${mimeType}`,
    data,
  };
}


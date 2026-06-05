import { stat, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import fastGlob from "fast-glob";

import { assertDomainAllowed, assertPathAllowed, type RuntimeContext } from "./access.js";
import { assertTextContent } from "./http-text.js";

export interface LoadedMarkdown {
  uri: string;
  displayPath: string;
  text: string;
  localPath?: string;
}

export interface LoadedBinary {
  uri: string;
  data: Buffer;
}

export async function readMarkdownResource(uri: string, runtime: RuntimeContext): Promise<LoadedMarkdown> {
  if (isHttpUri(uri)) {
    const url = new URL(uri);
    assertDomainAllowed(url.hostname, runtime);
    const response = await runtime.fetch(url);
    if (!response.ok) {
      throw new Error(`Failed to fetch markdown URL ${uri}: ${response.status} ${response.statusText}`);
    }
    const text = await response.text();
    assertTextContent(response.headers.get("content-type"), text, response.url || url.href);
    return {
      uri: response.url || url.href,
      displayPath: response.url || url.href,
      text,
    };
  }

  const filePath = toLocalPath(uri);
  await assertPathAllowed(filePath, runtime);
  const fileStats = await stat(filePath);
  if (!fileStats.isFile()) {
    throw new Error(`Expected a markdown file but found a directory: ${filePath}`);
  }

  return {
    uri: pathToFileURL(filePath).href,
    displayPath: filePath,
    localPath: filePath,
    text: await readFile(filePath, "utf8"),
  };
}

export async function listMarkdownResources(uri: string, runtime: RuntimeContext): Promise<LoadedMarkdown[]> {
  if (isHttpUri(uri)) {
    return [await readMarkdownResource(uri, runtime)];
  }

  const filePath = toLocalPath(uri);
  await assertPathAllowed(filePath, runtime);
  const fileStats = await stat(filePath);
  if (fileStats.isFile()) {
    return [await readMarkdownResource(filePath, runtime)];
  }
  if (!fileStats.isDirectory()) {
    throw new Error(`Expected a markdown file or folder: ${filePath}`);
  }

  const matches = await fastGlob(["**/*.md", "**/*.markdown"], {
    cwd: filePath,
    absolute: true,
    onlyFiles: true,
    dot: false,
  });

  const markdownFiles = matches.sort((left, right) => left.localeCompare(right));
  return Promise.all(markdownFiles.map((markdownPath) => readMarkdownResource(markdownPath, runtime)));
}

export async function readBinaryResource(uri: string, runtime: RuntimeContext): Promise<LoadedBinary> {
  if (isHttpUri(uri)) {
    const url = new URL(uri);
    assertDomainAllowed(url.hostname, runtime);
    const response = await runtime.fetch(url);
    if (!response.ok) {
      throw new Error(`Failed to fetch resource ${uri}: ${response.status} ${response.statusText}`);
    }
    const arrayBuffer = await response.arrayBuffer();
    return { uri: response.url || url.href, data: Buffer.from(arrayBuffer) };
  }

  const filePath = toLocalPath(uri);
  await assertPathAllowed(filePath, runtime);
  return {
    uri: pathToFileURL(filePath).href,
    data: await readFile(filePath),
  };
}

export function resolveReference(reference: string, baseUri: string): string {
  if (reference.startsWith("data:")) {
    return reference;
  }
  return new URL(reference, baseUri).href;
}

export function toLocalPath(uri: string): string {
  if (uri.startsWith("file://")) {
    return fileURLToPath(uri);
  }
  return path.resolve(uri);
}

export function isHttpUri(uri: string): boolean {
  try {
    const url = new URL(uri);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}


import { readFile, stat } from "node:fs/promises";
import path from "node:path";

import fastGlob from "fast-glob";

import {
  buildHeadingIndex,
  countLines,
  stringifyFrontmatter,
  type HeadingIndexRow,
} from "./markdown/document.js";

export type { HeadingIndexRow };

export interface MarkdownFileIndex {
  path?: string;
  frontmatter: string;
  lineCount: number;
  charCount: number;
  rows: HeadingIndexRow[];
}

export function indexMarkdownText(text: string, options: { path?: string } = {}): MarkdownFileIndex {
  return {
    path: options.path,
    frontmatter: stringifyFrontmatter(text).trimEnd(),
    lineCount: countLines(text),
    charCount: text.length,
    rows: buildHeadingIndex(text),
  };
}

export async function indexMarkdownFile(filePath: string): Promise<MarkdownFileIndex> {
  const resolved = path.resolve(filePath);
  const fileStats = await stat(resolved);
  if (!fileStats.isFile()) {
    throw new Error(`Expected a markdown file but found a directory: ${resolved}`);
  }

  const text = await readFile(resolved, "utf8");
  return indexMarkdownText(text, { path: resolved });
}

export async function indexMarkdownFolder(folderPath: string): Promise<MarkdownFileIndex[]> {
  const resolved = path.resolve(folderPath);
  const folderStats = await stat(resolved);
  if (!folderStats.isDirectory()) {
    throw new Error(`Expected a folder but found a file: ${resolved}`);
  }

  const matches = await fastGlob(["**/*.md", "**/*.markdown"], {
    cwd: resolved,
    absolute: true,
    onlyFiles: true,
    dot: false,
  });

  const markdownFiles = matches.sort((left, right) => left.localeCompare(right));
  return Promise.all(markdownFiles.map((markdownPath) => indexMarkdownFile(markdownPath)));
}

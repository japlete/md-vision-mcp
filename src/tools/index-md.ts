import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";

import { getErrorMessage } from "../errors.js";
import type { RuntimeContext } from "../io/access.js";
import { listMarkdownResources, type LoadedMarkdown } from "../io/resources.js";
import { buildHeadingIndex, countLines, stringifyFrontmatter, type HeadingIndexRow } from "../markdown/document.js";
import { errorResult, textResult } from "../mcp/result.js";

export const indexMdInputSchema = {
  uri: z.string().min(1).describe("Local path, HTTP(S) URL, or local folder to index for markdown headings."),
};

const inputParser = z.object(indexMdInputSchema);

export type IndexMdInput = z.infer<typeof inputParser>;

export async function indexMd(input: IndexMdInput, runtime: RuntimeContext): Promise<CallToolResult> {
  try {
    const args = inputParser.parse(input);
    const markdownResources = await listMarkdownResources(args.uri, runtime);
    if (markdownResources.length === 0) {
      throw new Error(`No markdown files found for ${args.uri}.`);
    }

    return textResult(markdownResources.map(formatIndexedFile).join("\n\n"));
  } catch (error) {
    return errorResult(`index_md failed: ${getErrorMessage(error)}`);
  }
}

function formatIndexedFile(markdown: LoadedMarkdown): string {
  const rows = buildHeadingIndex(markdown.text);
  const frontmatter = stringifyFrontmatter(markdown.text).trimEnd();
  const tsv = formatTsv(rows);
  const body = [frontmatter, "```tsv", tsv, "```"].filter((part) => part.length > 0).join("\n");

  return `<file path="${escapeXmlAttribute(markdown.displayPath)}" lines=${countLines(markdown.text)} chars=${markdown.text.length}>\n${body}\n</file>`;
}

function formatTsv(rows: HeadingIndexRow[]): string {
  return [
    "heading\tline_start\tn_images\tchar_count",
    ...rows.map((row) =>
      [row.heading, row.lineStart.toString(), row.imageCount.toString(), row.charCount.toString()]
        .map(escapeTsvCell)
        .join("\t"),
    ),
  ].join("\n");
}

function escapeTsvCell(value: string): string {
  return value.replace(/\t/g, " ").replace(/\r?\n/g, " ");
}

function escapeXmlAttribute(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}


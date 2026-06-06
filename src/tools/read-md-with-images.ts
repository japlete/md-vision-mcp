import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";

import { getErrorMessage } from "../errors.js";
import { loadMarkdownImage } from "../images/load.js";
import type { RuntimeContext } from "../io/access.js";
import { readMarkdownResource } from "../io/resources.js";
import {
  formatImageReference,
  formatImageUrlCaption,
  selectMarkdown,
  shouldExposeImageUrl,
  splitMarkdownAtImages,
  stringifyMarkdown,
} from "../markdown/document.js";
import { contentResult, errorResult, imageBlock, textBlock, type ToolContent } from "../mcp/result.js";

export const readMdWithImagesInputSchema = {
  uri: z.string().min(1).describe("Local path or HTTP(S) URL of the markdown file to read."),
  section: z
    .string()
    .min(1)
    .optional()
    .describe(
      "Exact heading to read, including marker, for example '## Introduction'. When matched, takes precedence over line_range.",
    ),
  line_range: z
    .tuple([z.number().int().min(1), z.number().int().min(1)])
    .optional()
    .describe(
      "Inclusive 1-based document line range, for example [1, 10]. Used when section is omitted or not found.",
    ),
  max_images: z
    .number()
    .int()
    .min(0)
    .max(50)
    .default(10)
    .describe("Maximum referenced images to inline as image blocks. Defaults to 10."),
};

const inputParser = z.object(readMdWithImagesInputSchema);

export type ReadMdWithImagesInput = z.input<typeof inputParser>;

export async function readMdWithImages(
  input: ReadMdWithImagesInput,
  runtime: RuntimeContext,
): Promise<CallToolResult> {
  try {
    const args = inputParser.parse(input);
    const markdown = await readMarkdownResource(args.uri, runtime);
    const selected = selectMarkdown(markdown.text, {
      section: args.section,
      lineRange: args.line_range,
    });
    const maxImages = args.max_images ?? 10;
    const segments = splitMarkdownAtImages(selected.root);
    const content: ToolContent[] = [];
    let imagesLoaded = 0;

    const appendText = (text: string) => {
      if (!text) {
        return;
      }
      const last = content.at(-1);
      if (last?.type === "text") {
        last.text += text;
        return;
      }
      content.push(textBlock(text));
    };

    for (const segment of segments) {
      if (segment.kind === "text") {
        appendText(stringifyMarkdown(segment.root));
        continue;
      }

      if (imagesLoaded < maxImages) {
        const loadedImage = await loadMarkdownImage(segment.image, markdown.uri, runtime);
        if (shouldExposeImageUrl(segment.image.url)) {
          appendText(formatImageUrlCaption(loadedImage.sourceUri));
        }
        content.push(imageBlock(loadedImage.data, loadedImage.mimeType));
        imagesLoaded += 1;
        continue;
      }

      appendText(formatImageReference(segment.image));
    }

    return contentResult(content);
  } catch (error) {
    return errorResult(`read_md_with_images failed: ${getErrorMessage(error)}`);
  }
}


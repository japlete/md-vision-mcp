import type { CallToolResult, ImageContent, TextContent } from "@modelcontextprotocol/sdk/types.js";

export type ToolContent = TextContent | ImageContent;

export function textBlock(text: string): TextContent {
  return { type: "text", text };
}

export function imageBlock(data: string, mimeType: string): ImageContent {
  return { type: "image", data, mimeType };
}

export function contentResult(content: ToolContent[]): CallToolResult {
  return { content: content.length > 0 ? content : [textBlock("")] };
}

export function textResult(text: string): CallToolResult {
  return contentResult([textBlock(text)]);
}

export function errorResult(message: string): CallToolResult {
  return {
    isError: true,
    content: [textBlock(message)],
  };
}


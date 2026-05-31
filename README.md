# md-vision MCP server

stdio MCP server with two tools:
- Read markdown files with images in a single call. Can be scoped to a particular section or line range.
- Build an index of headings and subheadings for a given MD file or folder

Both tools combined allow efficient agentic RAG given a set of MD files.

## Install

Include example after implementing.

### Restricting allowed paths and domains

Include example after implementing.

### Note on deploying agents with this MCP server

If your plan is to deploy an agent in a container/sandbox, consider that stdio MCP servers run as subprocesses of the agent runtime that invokes them. If you follow the agent-in-sandbox pattern (agent runtime is the same filesystem as the agent's sandbox environment), the stdio MCP will work, but you should restrict allowed paths to hide the orchestrator / runtime files. If you follow the sandbox-as-tool pattern (agent runtime is a different filesystem than the sandbox container), the stdio MCP for most frameworks will run in the agent runtime. You will need to maintain a copy/sync of the MD files for the tools to find them.

## Benchmark

Not yet implemented.
import path from "node:path";

export interface AccessConfig {
  allowPaths: string[];
  allowDomains: string[];
}

export interface RuntimeContext {
  access: AccessConfig;
  fetch: typeof fetch;
}

export function parseAccessArgs(args: string[]): AccessConfig {
  const allowPaths: string[] = [];
  const allowDomains: string[] = [];

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--allow-path") {
      const value = args[index + 1];
      if (value) {
        allowPaths.push(path.resolve(value));
        index += 1;
      }
      continue;
    }
    if (arg.startsWith("--allow-path=")) {
      allowPaths.push(path.resolve(arg.slice("--allow-path=".length)));
      continue;
    }
    if (arg === "--allow-domain") {
      const value = args[index + 1];
      if (value) {
        allowDomains.push(normalizeDomain(value));
        index += 1;
      }
      continue;
    }
    if (arg.startsWith("--allow-domain=")) {
      allowDomains.push(normalizeDomain(arg.slice("--allow-domain=".length)));
    }
  }

  return {
    allowPaths,
    allowDomains,
  };
}

export function requireAllowPaths(access: AccessConfig): void {
  if (access.allowPaths.length === 0) {
    throw new Error("At least one --allow-path is required. Pass --allow-path <dir> (repeatable).");
  }
}

export function requireAllowDomains(access: AccessConfig): void {
  if (access.allowDomains.length === 0) {
    throw new Error(
      "At least one --allow-domain is required. Pass --allow-domain <host> (repeatable), all to allow all HTTP(S) hosts, or none to disable URLs.",
    );
  }

  detectShellGlobMisparse(access.allowDomains);

  const hasWildcard = access.allowDomains.includes("all");
  const hasNone = access.allowDomains.includes("none");
  if (hasWildcard && hasNone) {
    throw new Error("--allow-domain all and none are mutually exclusive.");
  }
  if (hasWildcard && access.allowDomains.length > 1) {
    throw new Error("--allow-domain all must be the only entry when allowing all hosts.");
  }
  if (hasNone && access.allowDomains.length > 1) {
    throw new Error("--allow-domain none must be the only entry when disabling URLs.");
  }
}

export function createRuntimeContext(access: AccessConfig): RuntimeContext {
  return {
    access,
    fetch: globalThis.fetch.bind(globalThis),
  };
}

export async function assertPathAllowed(filePath: string, runtime: RuntimeContext): Promise<void> {
  const allowedPaths = runtime.access.allowPaths;
  const resolvedPath = path.resolve(filePath);
  const allowed = allowedPaths.some((allowedPath) => isWithinPath(resolvedPath, allowedPath));
  if (!allowed) {
    throw new Error(`Path is not allowed: ${resolvedPath}. Configure --allow-path to read local files.`);
  }
}

export function assertDomainAllowed(hostname: string, runtime: RuntimeContext): void {
  const allowedDomains = runtime.access.allowDomains;
  if (allowedDomains.includes("all")) {
    return;
  }
  if (allowedDomains.includes("none")) {
    throw new Error(`Domain is not allowed: ${hostname}. URLs are disabled (--allow-domain=none).`);
  }

  const normalizedHost = normalizeDomain(hostname);
  const allowed = allowedDomains.some(
    (domain) => normalizedHost === domain || normalizedHost.endsWith(`.${domain}`),
  );
  if (!allowed) {
    throw new Error(`Domain is not allowed: ${hostname}. Configure --allow-domain to read this URL.`);
  }
}

function isWithinPath(filePath: string, allowedPath: string): boolean {
  const relative = path.relative(path.resolve(allowedPath), filePath);
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}

function normalizeDomain(domain: string): string {
  const trimmed = stripQuotes(domain.trim().toLowerCase());
  if (trimmed === "*" || trimmed === "all") {
    return "all";
  }
  if (trimmed === "none") {
    return "none";
  }
  return trimmed.replace(/^\*\./, "");
}

function stripQuotes(value: string): string {
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1);
  }
  return value;
}

function detectShellGlobMisparse(domains: string[]): void {
  if (domains.length <= 1) {
    return;
  }

  const fileLike =
    /[/\\]|\.(?:md|markdown|json|ts|js|lock|yaml|yml|toml|npmrc)$|^(?:dist|src|test|node_modules|package\.json|readme\.md|tsconfig\.json)$/i;
  if (domains.some((domain) => fileLike.test(domain))) {
    throw new Error(
      "Multiple --allow-domain values look like shell glob expansion from an unquoted *. Use --allow-domain=all (or --allow-domain=none) instead.",
    );
  }
}

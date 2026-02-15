// ---------------------------------------------------------------------------
// Code extraction, language detection, and HTML wrapping utilities.
//
// Used by the challenge page to pull renderable code out of LLM responses
// and turn JSX / TSX / JS / TS into something an iframe can display.
// ---------------------------------------------------------------------------

/** A single fenced code block pulled from a markdown response. */
export interface CodeBlock {
  /** Language tag from the opening fence (lowercased, empty string if none). */
  lang: string;
  /** The raw code inside the fences. */
  code: string;
}

// ---------------------------------------------------------------------------
// Extraction
// ---------------------------------------------------------------------------

/** Pull every fenced code block out of a markdown string. */
export function extractCodeBlocks(text: string): CodeBlock[] {
  const pattern = /```(\w*)\s*\n([\s\S]*?)```/g;
  const blocks: CodeBlock[] = [];
  let m: RegExpExecArray | null;
  while ((m = pattern.exec(text)) !== null) {
    blocks.push({ lang: m[1].toLowerCase(), code: m[2].trim() });
  }
  return blocks;
}

/** Concatenate all code blocks (ignores language tags). */
export function extractAllCode(text: string): string {
  return extractCodeBlocks(text)
    .map((b) => b.code)
    .join("\n\n");
}

/**
 * Extract the best Python code block from a markdown-formatted LLM response.
 */
export function extractPythonCode(text: string): string {
  const blocks = extractCodeBlocks(text);
  if (blocks.length === 0) return "";

  const pythonBlocks = blocks.filter(
    (b) => b.lang === "python" || b.lang === "py" || b.lang === ""
  );
  const candidates = pythonBlocks.length > 0 ? pythonBlocks : blocks;

  const withDef = candidates.filter(
    (b) => /\bdef\s+\w+/.test(b.code) || /\bclass\s+\w+/.test(b.code)
  );

  if (withDef.length > 0) {
    return withDef.reduce((a, b) =>
      a.code.length >= b.code.length ? a : b
    ).code;
  }

  return candidates[candidates.length - 1].code;
}

// ---------------------------------------------------------------------------
// Language / type detection
// ---------------------------------------------------------------------------

type CodeType = "html" | "jsx" | "tsx" | "js" | "ts" | "unknown";

/** Check if code looks like renderable HTML. */
export function isHtmlCode(code: string): boolean {
  const t = code.trim().toLowerCase();
  return (
    t.startsWith("<!doctype html") ||
    t.startsWith("<html") ||
    t.startsWith("<head") ||
    t.startsWith("<body") ||
    (t.includes("<div") && t.includes("</div>")) ||
    (t.includes("<style") && t.includes("</style>"))
  );
}

/** Check if code looks like JSX / React. */
function looksLikeJsx(code: string): boolean {
  // JSX-specific patterns
  const jsxIndicators = [
    /\bclassName\s*=/,                      // className=
    /\buseState\b/,                          // React hook
    /\buseEffect\b/,                         // React hook
    /\buseRef\b/,                            // React hook
    /\buseCallback\b/,                       // React hook
    /\buseMemo\b/,                           // React hook
    /\breturn\s*\(\s*</,                     // return ( <
    /\bReact\./,                             // React.
    /\bReactDOM\./,                          // ReactDOM.
    /import\s+.*from\s+['"]react['"]/,       // import from 'react'
    /<[A-Z]\w*/,                             // PascalCase component tags <App, <Button
    /export\s+default\s+function\s+\w+/,     // export default function App
  ];
  return jsxIndicators.some((re) => re.test(code));
}

/** Check if code looks like TypeScript (but not TSX). */
function looksLikeTs(code: string): boolean {
  return (
    /:\s*(string|number|boolean|any|void|never)\b/.test(code) ||
    /\binterface\s+\w+/.test(code) ||
    /\btype\s+\w+\s*=/.test(code) ||
    /<\w+>/.test(code) // Generic syntax (rough)
  );
}

/**
 * Determine what kind of renderable code we're looking at.
 * Uses the language tag first, then falls back to heuristics.
 */
function detectCodeType(block: CodeBlock): CodeType {
  // Explicit tag wins
  const tag = block.lang;
  if (tag === "html" || tag === "htm") return "html";
  if (tag === "jsx") return "jsx";
  if (tag === "tsx") return "tsx";
  if (tag === "javascript" || tag === "js") {
    return looksLikeJsx(block.code) ? "jsx" : "js";
  }
  if (tag === "typescript" || tag === "ts") {
    return looksLikeJsx(block.code) ? "tsx" : "ts";
  }
  if (tag === "react") return "jsx";

  // No tag — use heuristics on code content
  if (isHtmlCode(block.code)) return "html";
  if (looksLikeJsx(block.code)) {
    return looksLikeTs(block.code) ? "tsx" : "jsx";
  }
  if (looksLikeTs(block.code)) return "ts";

  // If it has function/const/let keywords it's probably JS
  if (
    /\b(function|const|let|var|=>)\b/.test(block.code) &&
    /[<>]/.test(block.code)
  ) {
    return "js";
  }

  return "unknown";
}

// ---------------------------------------------------------------------------
// HTML wrapping
// ---------------------------------------------------------------------------

/**
 * Find the root component name from JSX / TSX source.
 * Looks for `export default function Foo`, `export default Foo`,
 * `function App`, `const App =`, etc.
 */
function findRootComponent(code: string): string {
  // export default function Foo
  let m = code.match(/export\s+default\s+function\s+(\w+)/);
  if (m) return m[1];

  // export default class Foo
  m = code.match(/export\s+default\s+class\s+(\w+)/);
  if (m) return m[1];

  // export default Foo  (standalone statement)
  m = code.match(/export\s+default\s+(\w+)\s*;?$/m);
  if (m) return m[1];

  // function App(  or  const App =  (PascalCase)
  const fnMatches = [
    ...code.matchAll(/(?:function|const|let|var)\s+([A-Z]\w*)\s*[=(]/g),
  ];
  if (fnMatches.length > 0) return fnMatches[0][1];

  return "App";
}

/**
 * Strip import/export statements that the in-browser runtime doesn't need
 * (React & ReactDOM are loaded via CDN as globals).
 */
function preprocessJsx(code: string): string {
  return (
    code
      // Remove import statements
      .replace(/^import\s+.*from\s+['"].*['"];?\s*$/gm, "")
      // Remove `export default function X` → `function X`
      .replace(/^export\s+default\s+function\b/gm, "function")
      // Remove `export default class X` → `class X`
      .replace(/^export\s+default\s+class\b/gm, "class")
      // Remove `export default X;`
      .replace(/^export\s+default\s+\w+\s*;?\s*$/gm, "")
      // Remove leftover `export` keywords
      .replace(/^export\s+(const|let|var|function|class)\b/gm, "$1")
      .trim()
  );
}

/** Wrap JSX / TSX code in a self-contained HTML page using Babel standalone. */
function wrapJsxAsHtml(code: string, _type: "jsx" | "tsx"): string {
  const component = findRootComponent(code);
  const processed = preprocessJsx(code);

  // React 18 is the last version that ships UMD builds (React 19 removed them).
  // unpkg.com is the canonical CDN recommended by the React docs.
  // Destructure common hooks so user code that writes
  //   const [x, setX] = useState(0)   works without `React.useState`.
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Preview</title>
  <script crossorigin src="https://unpkg.com/react@18/umd/react.development.js"><\/script>
  <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"><\/script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"><\/script>
  <script src="https://cdn.tailwindcss.com"><\/script>
  <style>body{margin:0}</style>
</head>
<body>
  <div id="root"></div>
  <script type="text/babel" data-presets="react,typescript">
    const { useState, useEffect, useRef, useCallback, useMemo, useContext, useReducer, createContext, Fragment } = React;

${processed}

    ReactDOM.createRoot(document.getElementById("root")).render(<${component} />);
  <\/script>
</body>
</html>`;
}

/** Wrap plain JS code in an HTML page (no React, just a <script> tag). */
function wrapJsAsHtml(code: string): string {
  // Check if it manipulates DOM (e.g. document.getElementById, canvas)
  const usesDOM =
    /document\.(getElementById|querySelector|createElement|body|head)/.test(code) ||
    /\.innerHTML/.test(code) ||
    /\.appendChild/.test(code);

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Preview</title>
  <script src="https://cdn.tailwindcss.com"><\/script>
  <style>body{margin:0}</style>
</head>
<body>
  ${usesDOM ? '<div id="root"></div>' : "<pre id=\"output\"></pre>"}
  <script type="module">
    ${
      usesDOM
        ? code
        : `// Capture console.log output
const _out = [];
const _origLog = console.log;
console.log = (...args) => { _out.push(args.map(String).join(" ")); _origLog(...args); };
try {
${code}
} catch(e) { _out.push("Error: " + e.message); }
document.getElementById("output").textContent = _out.join("\\n");`
    }
  <\/script>
</body>
</html>`;
}

/** Wrap TypeScript code in HTML using Babel standalone for transpilation. */
function wrapTsAsHtml(code: string): string {
  const usesDOM =
    /document\.(getElementById|querySelector|createElement|body|head)/.test(code) ||
    /\.innerHTML/.test(code) ||
    /\.appendChild/.test(code);

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Preview</title>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"><\/script>
  <script src="https://cdn.tailwindcss.com"><\/script>
  <style>body{margin:0}</style>
</head>
<body>
  ${usesDOM ? '<div id="root"></div>' : "<pre id=\"output\"></pre>"}
  <script type="text/babel" data-presets="typescript">
    ${
      usesDOM
        ? code
        : `const _out: string[] = [];
const _origLog = console.log;
console.log = (...args: unknown[]) => { _out.push(args.map(String).join(" ")); _origLog(...args); };
try {
${code}
} catch(e: any) { _out.push("Error: " + e.message); }
document.getElementById("output")!.textContent = _out.join("\\n");`
    }
  <\/script>
</body>
</html>`;
}

// ---------------------------------------------------------------------------
// Public API — the single function page.tsx should call
// ---------------------------------------------------------------------------

export interface ExtractedUI {
  /** The renderable HTML (either original or wrapped). */
  html: string;
  /** The raw source code as written by the LLM. */
  rawCode: string;
  /** Detected type. */
  type: CodeType;
}

/**
 * Extract UI-renderable code from an LLM response.
 *
 * Returns `null` if no renderable code was found.
 *
 * The returned `html` is always a self-contained HTML document that can
 * be written to a Vercel Sandbox `index.html` or used as iframe `srcDoc`.
 */
export function extractRenderableUI(text: string): ExtractedUI | null {
  const blocks = extractCodeBlocks(text);
  if (blocks.length === 0) return null;

  // Score each block and pick the best renderable one.
  // Prefer: html > jsx/tsx > js/ts > unknown
  const scored = blocks.map((b) => {
    const type = detectCodeType(b);
    const priority =
      type === "html"
        ? 4
        : type === "jsx" || type === "tsx"
        ? 3
        : type === "js" || type === "ts"
        ? 2
        : 0;
    return { block: b, type, priority };
  });

  // Sort by priority desc, then by code length desc (prefer the biggest block)
  scored.sort((a, b) => b.priority - a.priority || b.block.code.length - a.block.code.length);

  const best = scored.find((s) => s.priority > 0);
  if (!best) {
    // No clearly renderable block — try concatenating everything and check
    const all = blocks.map((b) => b.code).join("\n\n");
    if (isHtmlCode(all)) {
      return { html: all, rawCode: all, type: "html" };
    }
    if (looksLikeJsx(all)) {
      return {
        html: wrapJsxAsHtml(all, looksLikeTs(all) ? "tsx" : "jsx"),
        rawCode: all,
        type: looksLikeTs(all) ? "tsx" : "jsx",
      };
    }
    return null;
  }

  const { block, type } = best;

  switch (type) {
    case "html":
      return { html: block.code, rawCode: block.code, type };
    case "jsx":
    case "tsx":
      return { html: wrapJsxAsHtml(block.code, type), rawCode: block.code, type };
    case "js":
      return { html: wrapJsAsHtml(block.code), rawCode: block.code, type };
    case "ts":
      return { html: wrapTsAsHtml(block.code), rawCode: block.code, type };
    default:
      return null;
  }
}


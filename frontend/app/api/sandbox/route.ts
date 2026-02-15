import { NextResponse } from "next/server";
import { Sandbox } from "@vercel/sandbox";

// In-memory store of sandbox IDs to their server command IDs (for cleanup)
const activeSandboxes = new Map<
  string,
  { sandbox: Sandbox; serverCmd: import("@vercel/sandbox").Command | null }
>();

// Export for use by the [sandboxId] route
export { activeSandboxes };

const SERVER_PORT = 3000;

// Minimal Node.js HTTP server that serves /vercel/sandbox/index.html
const SERVER_SCRIPT = `
const http = require('http');
const fs = require('fs');
const path = require('path');

const server = http.createServer((req, res) => {
  // Add CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }

  try {
    const html = fs.readFileSync('/vercel/sandbox/index.html', 'utf8');
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(html);
  } catch(e) {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end('<html><body style="display:flex;align-items:center;justify-content:center;height:100vh;margin:0;font-family:system-ui;color:#94a3b8;"><p>Waiting for code...</p></body></html>');
  }
});

server.listen(${SERVER_PORT}, '0.0.0.0', () => {
  console.log('Server running on port ${SERVER_PORT}');
});
`;

export async function POST() {
  try {
    const sandbox = await Sandbox.create({
      runtime: "node24",
      ports: [SERVER_PORT],
      timeout: 10 * 60 * 1000, // 10 minutes
    });

    // Write the server script
    await sandbox.writeFiles([
      {
        path: "/vercel/sandbox/server.js",
        content: Buffer.from(SERVER_SCRIPT),
      },
      {
        path: "/vercel/sandbox/index.html",
        content: Buffer.from(
          '<html><body style="display:flex;align-items:center;justify-content:center;height:100vh;margin:0;font-family:system-ui;color:#94a3b8;"><p>Waiting for code...</p></body></html>'
        ),
      },
    ]);

    // Start the server in detached mode
    const serverCmd = await sandbox.runCommand({
      cmd: "node",
      args: ["server.js"],
      cwd: "/vercel/sandbox",
      detached: true,
    });

    // Give the server a moment to start
    await new Promise((resolve) => setTimeout(resolve, 500));

    // Get the preview URL
    const previewUrl = sandbox.domain(SERVER_PORT);

    // Store for later use
    activeSandboxes.set(sandbox.sandboxId, { sandbox, serverCmd });

    return NextResponse.json({
      sandboxId: sandbox.sandboxId,
      previewUrl,
    });
  } catch (error) {
    console.error("Failed to create Vercel sandbox:", error);
    return NextResponse.json(
      { error: `Failed to create sandbox: ${(error as Error).message}` },
      { status: 500 }
    );
  }
}


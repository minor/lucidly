import { NextRequest, NextResponse } from "next/server";
import { Sandbox } from "@vercel/sandbox";
import { activeSandboxes } from "../route";

/**
 * PUT /api/sandbox/[sandboxId]
 * Write new HTML code to the sandbox's index.html.
 * The running HTTP server will serve the updated file on next request.
 */
export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ sandboxId: string }> }
) {
  const { sandboxId } = await params;

  try {
    const body = await request.json();
    const { code } = body as { code: string };

    if (!code) {
      return NextResponse.json({ error: "Missing 'code' field" }, { status: 400 });
    }

    // Try to get from in-memory store first, fall back to SDK
    let sandbox: Sandbox;
    const entry = activeSandboxes.get(sandboxId);
    if (entry) {
      sandbox = entry.sandbox;
    } else {
      sandbox = await Sandbox.get({ sandboxId });
      activeSandboxes.set(sandboxId, { sandbox, serverCmd: null });
    }

    // Write the updated HTML
    await sandbox.writeFiles([
      {
        path: "/vercel/sandbox/index.html",
        content: Buffer.from(code),
      },
    ]);

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Failed to update sandbox code:", error);
    return NextResponse.json(
      { error: `Failed to update code: ${(error as Error).message}` },
      { status: 500 }
    );
  }
}

/**
 * Shared cleanup logic used by both DELETE and POST (sendBeacon).
 */
async function stopSandbox(sandboxId: string) {
  const entry = activeSandboxes.get(sandboxId);
  if (entry) {
    if (entry.serverCmd) {
      try {
        await entry.serverCmd.kill();
      } catch {
        // Command may already be finished
      }
    }
    await entry.sandbox.stop();
    activeSandboxes.delete(sandboxId);
  } else {
    try {
      const sandbox = await Sandbox.get({ sandboxId });
      await sandbox.stop();
    } catch {
      // Already stopped or not found
    }
  }
}

/**
 * DELETE /api/sandbox/[sandboxId]
 * Stop and clean up the sandbox.
 */
export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ sandboxId: string }> }
) {
  const { sandboxId } = await params;
  try {
    await stopSandbox(sandboxId);
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Failed to stop sandbox:", error);
    return NextResponse.json(
      { error: `Failed to stop sandbox: ${(error as Error).message}` },
      { status: 500 }
    );
  }
}

/**
 * POST /api/sandbox/[sandboxId]
 * Also stops the sandbox — used by navigator.sendBeacon on page unload
 * (sendBeacon can only send POST, not DELETE).
 */
export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ sandboxId: string }> }
) {
  const { sandboxId } = await params;
  try {
    await stopSandbox(sandboxId);
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Failed to stop sandbox (beacon):", error);
    return NextResponse.json(
      { error: `Failed to stop sandbox: ${(error as Error).message}` },
      { status: 500 }
    );
  }
}


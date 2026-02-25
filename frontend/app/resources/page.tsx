"use client";

import { LibraryBig } from "lucide-react";

export default function ResourcesPage() {
  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      <header className="flex items-center justify-center px-4 sm:px-8 py-2 sm:py-5">
        <div className="flex items-center gap-2">
          <LibraryBig className="h-6 w-6 text-accent" />
          <h1 className="text-xl font-bold tracking-tight">Resources</h1>
        </div>
      </header>

      <main className="flex-1 overflow-auto p-4 sm:p-8">
        <div className="mx-auto max-w-3xl text-center text-muted">
          <p className="text-sm">Coming soon.</p>
        </div>
      </main>
    </div>
  );
}

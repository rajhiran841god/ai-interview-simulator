"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function LobbyContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const interviewId = searchParams.get("interview_id");
  const [ready, setReady] = useState(false);

  if (!interviewId) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-paper px-4">
        <p className="font-sans text-sm text-clay">No interview session found.</p>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-paper px-4">
      <div className="w-full max-w-md bg-paper-card rounded-card p-8 text-center shadow-sm">
        <h1 className="font-display text-2xl text-ink mb-2">You&rsquo;re ready to begin</h1>
        <p className="font-sans text-sm text-ink-light">
          This is a practice interview. Answer naturally &mdash; there&rsquo;s no single
          &ldquo;right&rdquo; answer, and you can take your time before responding.
        </p>

        <label className="font-sans mt-6 flex items-start gap-2 text-left text-sm text-ink">
          <input
            type="checkbox"
            checked={ready}
            onChange={(e) => setReady(e.target.checked)}
            className="mt-1"
          />
          I understand this is a pilot and my responses will be used to generate feedback for
          this session only.
        </label>

        <button
          onClick={() => router.push(`/interview/session?interview_id=${interviewId}`)}
          disabled={!ready}
          className="font-sans mt-6 w-full rounded-card bg-ink py-2.5 text-sm font-medium text-paper hover:bg-ink-light transition-colors disabled:opacity-50"
        >
          Begin Interview
        </button>
      </div>
    </main>
  );
}

export default function LobbyPage() {
  return (
    <Suspense>
      <LobbyContent />
    </Suspense>
  );
}

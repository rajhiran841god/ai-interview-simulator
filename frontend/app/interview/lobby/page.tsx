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
      <main className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
        <p className="text-sm text-red-600">No interview session found.</p>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md rounded-lg border border-gray-200 bg-white p-8 text-center shadow-sm">
        <h1 className="text-xl font-semibold text-gray-900">You're ready to begin</h1>
        <p className="mt-2 text-sm text-gray-500">
          This is a practice interview. Answer naturally — there's no single "right" answer,
          and you can take your time before responding.
        </p>

        <label className="mt-6 flex items-start gap-2 text-left text-sm text-gray-700">
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
          className="mt-6 w-full rounded-md bg-gray-900 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
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

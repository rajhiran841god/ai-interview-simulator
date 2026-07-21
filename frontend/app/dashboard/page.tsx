"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";
import { api } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleStartInterview() {
    setError(null);
    setStarting(true);
    try {
      const { data } = await supabase.auth.getUser();
      const userId = data.user?.id || "anonymous-user";
      const session = await api.createInterview(userId);
      router.push(`/interview/setup?interview_id=${session.interview_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start a new interview.");
      setStarting(false);
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 px-4 py-10">
      <div className="mx-auto max-w-2xl">
        <h1 className="text-2xl font-semibold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          Practice a placement interview, tailored to a real job description.
        </p>

        <div className="mt-8 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-medium text-gray-900">Start a new interview</h2>
          <p className="mt-1 text-sm text-gray-500">
            You'll upload your resume and the job description, then begin.
          </p>
          {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
          <button
            onClick={handleStartInterview}
            disabled={starting}
            className="mt-4 rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
          >
            {starting ? "Starting..." : "Start Interview"}
          </button>
        </div>

        <div className="mt-6 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-medium text-gray-900">Past interviews</h2>
          <p className="mt-1 text-sm text-gray-500">
            Interview history will appear here once you've completed a session.
          </p>
        </div>
      </div>
    </main>
  );
}

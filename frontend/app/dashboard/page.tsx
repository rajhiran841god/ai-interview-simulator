"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";
import { api } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [firstName, setFirstName] = useState<string | null>(null);

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      const fullName = data.user?.user_metadata?.full_name as string | undefined;
      if (fullName) setFirstName(fullName.split(" ")[0]);
    });
  }, []);

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
    <main className="min-h-screen bg-paper px-4 py-16">
      <div className="mx-auto max-w-2xl">
        <p className="font-sans text-xs uppercase tracking-wide text-ink-light mb-2">
          {firstName ? `Welcome back, ${firstName}` : "Welcome"}
        </p>
        <h1 className="font-display text-3xl md:text-4xl text-ink mb-2 tracking-tight">
          Ready when you are.
        </h1>
        <p className="font-sans text-base text-ink-light mb-10 max-w-md">
          Practice a real placement interview, tailored to a specific job description &mdash;
          with feedback grounded in what you actually said.
        </p>

        <div className="bg-paper-card rounded-card p-7 shadow-sm mb-4">
          <h2 className="font-display text-xl text-ink mb-1.5">Start a new interview</h2>
          <p className="font-sans text-sm text-ink-light mb-5">
            You&rsquo;ll upload your resume and the job description, then begin.
          </p>
          {error && <p className="font-sans text-sm text-clay mb-4">{error}</p>}
          <button
            onClick={handleStartInterview}
            disabled={starting}
            className="font-sans rounded-card bg-ink px-5 py-2.5 text-sm font-medium text-paper hover:bg-ink-light transition-colors disabled:opacity-50"
          >
            {starting ? "Starting..." : "Start Interview"}
          </button>
        </div>

        <div className="bg-paper-card rounded-card p-7 shadow-sm">
          <h2 className="font-display text-xl text-ink mb-1.5">Past interviews</h2>
          <p className="font-sans text-sm text-ink-light">
            Your interview history will appear here once you&rsquo;ve completed a session.
          </p>
        </div>
      </div>
    </main>
  );
}

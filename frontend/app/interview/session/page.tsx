"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, NextQuestionResponse } from "@/lib/api";

function SessionContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const interviewId = searchParams.get("interview_id");

  const [current, setCurrent] = useState<NextQuestionResponse | null>(null);
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [questionCount, setQuestionCount] = useState(0);

  useEffect(() => {
    if (interviewId) fetchNextQuestion();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [interviewId]);

  async function fetchNextQuestion() {
    setError(null);
    setLoading(true);
    try {
      const q = await api.getNextQuestion(interviewId!);
      setCurrent(q);
      if (q.decision_type === "continue") setQuestionCount((c) => c + 1);
      if (q.decision_type === "stop") {
        setTimeout(() => router.push(`/interview/report?interview_id=${interviewId}`), 1500);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load the next question.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmitAnswer(e: React.FormEvent) {
    e.preventDefault();
    if (!current || !answer.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.submitAnswer(interviewId!, current.question_id, answer);
      setAnswer("");
      await fetchNextQuestion();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not submit your answer.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!interviewId) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-paper px-4">
        <p className="font-sans text-sm text-clay">No interview session found.</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-paper px-4 py-16">
      <div className="mx-auto max-w-2xl">
        <div className="mb-6 flex items-center justify-between">
          <span className="font-sans text-xs uppercase tracking-wide text-ink-light">
            Question {questionCount}
          </span>
          <span className="font-sans rounded-full bg-sage-light px-3 py-1 text-xs font-medium text-sage-dark">
            Text mode &middot; voice coming in a later release
          </span>
        </div>

        <div className="bg-paper-card rounded-card p-8 md:p-10 shadow-sm min-h-[280px] flex flex-col justify-center">
          {loading && !current && (
            <p className="font-sans text-sm text-ink-light">Preparing your interview...</p>
          )}

          {current?.decision_type === "stop" && (
            <div>
              <h2 className="font-display text-2xl text-ink mb-2">
                That concludes the interview.
              </h2>
              <p className="font-sans text-sm text-ink-light mb-1">{current.stop_reason}</p>
              <p className="font-sans text-sm text-sage">Preparing your feedback report...</p>
            </div>
          )}

          {current?.decision_type === "continue" && (
            <>
              <h2 className="font-display text-2xl md:text-3xl text-ink mb-7 leading-snug">
                {current.question_text}
              </h2>
              <form onSubmit={handleSubmitAnswer}>
                <textarea
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  rows={6}
                  className="font-sans w-full rounded-card border border-ink/15 p-3.5 text-sm text-ink focus:border-ink focus:outline-none bg-paper"
                  placeholder="Type your answer..."
                  disabled={submitting || loading}
                  autoFocus
                />
                {error && <p className="font-sans text-sm text-clay mt-3">{error}</p>}
                <button
                  type="submit"
                  disabled={submitting || loading || !answer.trim()}
                  className="font-sans mt-5 rounded-card bg-ink px-5 py-2.5 text-sm font-medium text-paper hover:bg-ink-light transition-colors disabled:opacity-50"
                >
                  {submitting ? "Submitting..." : "Submit Answer"}
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </main>
  );
}

export default function SessionPage() {
  return (
    <Suspense>
      <SessionContent />
    </Suspense>
  );
}

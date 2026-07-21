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
      <main className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
        <p className="text-sm text-red-600">No interview session found.</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gray-50 px-4 py-10">
      <div className="mx-auto max-w-2xl">
        <div className="mb-4 flex items-center justify-between">
          <span className="text-xs uppercase tracking-wide text-gray-400">
            Question {questionCount}
          </span>
          <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
            Text mode — voice interview coming in a later release
          </span>
        </div>

        <div className="rounded-lg border border-gray-200 bg-white p-8 shadow-sm">
          {loading && !current && <p className="text-sm text-gray-500">Preparing your interview...</p>}

          {current?.decision_type === "stop" && (
            <div>
              <h2 className="text-lg font-medium text-gray-900">That concludes the interview.</h2>
              <p className="mt-2 text-sm text-gray-500">{current.stop_reason}</p>
              <p className="mt-2 text-sm text-gray-400">Preparing your feedback report...</p>
            </div>
          )}

          {current?.decision_type === "continue" && (
            <>
              <h2 className="text-xl font-medium text-gray-900">{current.question_text}</h2>
              <form onSubmit={handleSubmitAnswer} className="mt-6">
                <textarea
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  rows={6}
                  className="w-full rounded-md border border-gray-300 p-3 text-sm focus:border-gray-900 focus:outline-none"
                  placeholder="Type your answer..."
                  disabled={submitting || loading}
                  autoFocus
                />
                {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
                <button
                  type="submit"
                  disabled={submitting || loading || !answer.trim()}
                  className="mt-4 rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
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

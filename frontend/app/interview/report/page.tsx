"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { api, InterviewFeedbackReport } from "@/lib/api";

function ReportContent() {
  const searchParams = useSearchParams();
  const interviewId = searchParams.get("interview_id");

  const [report, setReport] = useState<InterviewFeedbackReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!interviewId) return;
    api
      .getReport(interviewId)
      .then(setReport)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load your report."))
      .finally(() => setLoading(false));
  }, [interviewId]);

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
        <h1 className="text-2xl font-semibold text-gray-900">Your Interview Feedback</h1>

        {loading && <p className="mt-4 text-sm text-gray-500">Generating your report...</p>}
        {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

        {report && (
          <>
            <p className="mt-2 text-sm text-gray-500">{report.overall_summary}</p>

            <div className="mt-6 space-y-4">
              {report.competency_feedback.map((cf) => (
                <div
                  key={cf.competency_id}
                  className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm"
                >
                  <div className="flex items-center justify-between">
                    <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
                      {cf.competency_id.replace(/_/g, " ")}
                    </h2>
                    {cf.emphasis === "primary" && (
                      <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                        Key focus area
                      </span>
                    )}
                  </div>
                  <p className="mt-2 text-sm text-gray-800">{cf.summary_text}</p>
                  {cf.has_unresolved_contradiction && (
                    <p className="mt-2 text-xs text-amber-600">
                      Worth reviewing: your answers gave differing accounts in this area.
                    </p>
                  )}
                  {cf.insufficient_evidence && (
                    <p className="mt-2 text-xs text-gray-400">
                      Not enough was discussed here for detailed feedback.
                    </p>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </main>
  );
}

export default function ReportPage() {
  return (
    <Suspense>
      <ReportContent />
    </Suspense>
  );
}

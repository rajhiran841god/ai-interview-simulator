"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
  api,
  InterviewFeedbackReport,
  CompetencyFeedback,
  EvidenceDetail,
} from "@/lib/api";

function CompetencyCard({
  feedback,
  evidence,
}: {
  feedback: CompetencyFeedback;
  evidence: EvidenceDetail[];
}) {
  return (
    <section className="mb-12 last:mb-0">
      <p className="font-sans text-xs uppercase tracking-wide text-ink-light mb-1">
        {feedback.emphasis === "primary" ? "Primary competency" : "Secondary competency"}
      </p>
      <h2 className="font-display text-3xl md:text-4xl font-medium text-ink mb-5 tracking-tight">
        {feedback.competency_id.replace(/_/g, " ")}
      </h2>

      {feedback.insufficient_evidence ? (
        <p className="font-sans text-base leading-relaxed text-ink-light">
          {feedback.summary_text}
        </p>
      ) : (
        <>
          <p className="font-sans text-base leading-relaxed text-ink mb-5">
            {feedback.summary_text}
          </p>

          {evidence.length > 0 && (
            <div className="space-y-3 mb-5">
              {evidence.map((e) => (
                <div
                  key={e.evidence_id}
                  className={`rounded-card border pl-4 pr-4 py-3 ${
                    e.relation === "contradicts"
                      ? "border-clay/30 bg-clay-light"
                      : "border-evidence/30 bg-evidence-light"
                  }`}
                >
                  <p
                    className={`font-sans text-xs uppercase tracking-wide font-semibold mb-1.5 ${
                      e.relation === "contradicts" ? "text-clay" : "text-evidence-dark"
                    }`}
                  >
                    Evidence &middot; Question {e.question_number} &middot;{" "}
                    {e.relation === "contradicts" ? "Contradicting" : "Supporting"}
                  </p>
                  <p className="font-evidence text-sm leading-relaxed text-ink">
                    &ldquo;{e.evidence_excerpt}&rdquo;
                  </p>
                </div>
              ))}
            </div>
          )}

          {feedback.has_unresolved_contradiction && (
            <p className="font-sans text-sm text-clay mb-4">
              Worth reviewing: your answers gave differing accounts in this area.
            </p>
          )}

          {evidence.length > 0 && (
            <span className="inline-flex items-center gap-1.5 font-sans text-xs text-sage bg-sage-light rounded-full px-3 py-1">
              {evidence.filter((e) => e.relation === "supports").length} supporting moment
              {evidence.filter((e) => e.relation === "supports").length !== 1 ? "s" : ""} from
              your interview
            </span>
          )}
        </>
      )}
    </section>
  );
}

function ReportContent() {
  const searchParams = useSearchParams();
  const interviewId = searchParams.get("interview_id");

  const [report, setReport] = useState<InterviewFeedbackReport | null>(null);
  const [evidenceByCompetency, setEvidenceByCompetency] = useState<
    Record<string, EvidenceDetail[]>
  >({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!interviewId) return;
    api
      .getReport(interviewId)
      .then(async (r) => {
        setReport(r);
        const entries = await Promise.all(
          r.competency_feedback.map(async (cf) => {
            if (cf.insufficient_evidence) return [cf.competency_id, []] as const;
            try {
              const ev = await api.getEvidenceDetail(interviewId, cf.competency_id);
              return [cf.competency_id, ev] as const;
            } catch {
              return [cf.competency_id, []] as const;
            }
          })
        );
        setEvidenceByCompetency(Object.fromEntries(entries));
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load your report."))
      .finally(() => setLoading(false));
  }, [interviewId]);

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
        <p className="font-sans text-xs uppercase tracking-wide text-ink-light mb-2">
          Your interview feedback
        </p>
        <h1 className="font-display text-2xl text-ink mb-10">
          Grounded in what you actually said &mdash; not a generic score.
        </h1>

        {loading && (
          <p className="font-sans text-sm text-ink-light">Generating your report...</p>
        )}
        {error && <p className="font-sans text-sm text-clay">{error}</p>}

        {report && (
          <div className="bg-paper-card rounded-card p-8 md:p-10 shadow-sm">
            {report.competency_feedback.map((cf) => (
              <CompetencyCard
                key={cf.competency_id}
                feedback={cf}
                evidence={evidenceByCompetency[cf.competency_id] || []}
              />
            ))}
          </div>
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

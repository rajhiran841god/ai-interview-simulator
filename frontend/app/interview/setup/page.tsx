"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

function StepIndicator({ step }: { step: "resume" | "jd" | "submitting" }) {
  const onJD = step === "jd" || step === "submitting";
  return (
    <div className="mb-8 flex items-center gap-2 font-sans text-sm">
      <span className={onJD ? "text-sage" : "font-medium text-ink"}>1. Resume</span>
      <span className="text-ink-light">&rarr;</span>
      <span className={onJD ? "font-medium text-ink" : "text-ink-light"}>
        2. Job Description
      </span>
    </div>
  );
}

function SetupForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const interviewId = searchParams.get("interview_id");

  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [jdText, setJdText] = useState("");
  const [step, setStep] = useState<"resume" | "jd" | "submitting">("resume");
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);

  if (!interviewId) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-paper px-4">
        <p className="font-sans text-sm text-clay">
          No interview session found. Please start from the dashboard.
        </p>
      </main>
    );
  }

  async function handleResumeSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!resumeFile) return;
    setError(null);
    setStep("submitting");
    try {
      const result = await api.uploadResume(interviewId!, resumeFile);
      setWarnings(result.parse_warnings || []);
      setStep("jd");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not process resume.");
      setStep("resume");
    }
  }

  async function handleJDSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (jdText.trim().length < 50) {
      setError("Please paste the full job description (at least a few sentences).");
      return;
    }
    setError(null);
    setStep("submitting");
    try {
      const result = await api.uploadJD(interviewId!, jdText);
      if (result.competencies_initialized.length === 0) {
        setError(
          "We couldn't identify clear competencies from this job description. Try pasting the full requirements section."
        );
        setStep("jd");
        return;
      }
      router.push(`/interview/lobby?interview_id=${interviewId}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not process job description.");
      setStep("jd");
    }
  }

  return (
    <main className="min-h-screen bg-paper px-4 py-16">
      <div className="mx-auto max-w-xl">
        <StepIndicator step={step} />

        {step !== "jd" && (
          <form
            onSubmit={handleResumeSubmit}
            className="bg-paper-card rounded-card p-8 shadow-sm"
          >
            <h1 className="font-display text-2xl text-ink mb-1.5">Upload your resume</h1>
            <p className="font-sans text-sm text-ink-light mb-5">PDF or DOCX.</p>
            <input
              type="file"
              accept=".pdf,.docx"
              onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
              className="font-sans block w-full text-sm text-ink-light file:mr-4 file:rounded-card file:border-0 file:bg-sage-light file:px-4 file:py-2 file:font-sans file:text-sm file:font-medium file:text-sage-dark"
              required
            />
            {error && <p className="font-sans text-sm text-clay mt-4">{error}</p>}
            <button
              type="submit"
              disabled={!resumeFile || step === "submitting"}
              className="font-sans mt-6 rounded-card bg-ink px-5 py-2.5 text-sm font-medium text-paper hover:bg-ink-light transition-colors disabled:opacity-50"
            >
              {step === "submitting" ? "Processing..." : "Continue"}
            </button>
          </form>
        )}

        {step === "jd" && (
          <form
            onSubmit={handleJDSubmit}
            className="bg-paper-card rounded-card p-8 shadow-sm"
          >
            <h1 className="font-display text-2xl text-ink mb-1.5">
              Paste the job description
            </h1>
            <p className="font-sans text-sm text-ink-light mb-4">
              We&rsquo;ll tailor your interview to the requirements listed here.
            </p>
            {warnings.length > 0 && (
              <p className="font-sans text-xs text-sage-dark bg-sage-light rounded-card px-3 py-2 mb-4">
                Note: some resume details couldn&rsquo;t be confidently extracted &mdash; this
                won&rsquo;t stop your interview.
              </p>
            )}
            <textarea
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              rows={10}
              className="font-sans w-full rounded-card border border-ink/15 p-3.5 text-sm text-ink focus:border-ink focus:outline-none bg-paper"
              placeholder="Paste the full job description here..."
              required
            />
            {error && <p className="font-sans text-sm text-clay mt-4">{error}</p>}
            <button
              type="submit"
              className="font-sans mt-6 rounded-card bg-ink px-5 py-2.5 text-sm font-medium text-paper hover:bg-ink-light transition-colors disabled:opacity-50"
              disabled={step !== "jd"}
            >
              Continue to Interview
            </button>
          </form>
        )}
      </div>
    </main>
  );
}

export default function SetupPage() {
  return (
    <Suspense>
      <SetupForm />
    </Suspense>
  );
}

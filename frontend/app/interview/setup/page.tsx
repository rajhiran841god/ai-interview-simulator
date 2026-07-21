"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

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
      <main className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
        <p className="text-sm text-red-600">
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
    <main className="min-h-screen bg-gray-50 px-4 py-10">
      <div className="mx-auto max-w-xl">
        <div className="mb-6 flex items-center gap-2 text-sm text-gray-500">
          <span className={step === "resume" ? "font-medium text-gray-900" : ""}>1. Resume</span>
          <span>→</span>
          <span className={step === "jd" ? "font-medium text-gray-900" : ""}>2. Job Description</span>
        </div>

        {step !== "jd" && (
          <form
            onSubmit={handleResumeSubmit}
            className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm"
          >
            <h1 className="text-lg font-medium text-gray-900">Upload your resume</h1>
            <p className="mt-1 text-sm text-gray-500">PDF or DOCX.</p>
            <input
              type="file"
              accept=".pdf,.docx"
              onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
              className="mt-4 block w-full text-sm text-gray-700"
              required
            />
            {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
            <button
              type="submit"
              disabled={!resumeFile || step === "submitting"}
              className="mt-4 rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
            >
              {step === "submitting" ? "Processing..." : "Continue"}
            </button>
          </form>
        )}

        {step === "jd" && (
          <form
            onSubmit={handleJDSubmit}
            className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm"
          >
            <h1 className="text-lg font-medium text-gray-900">Paste the job description</h1>
            <p className="mt-1 text-sm text-gray-500">
              We'll tailor your interview to the requirements listed here.
            </p>
            {warnings.length > 0 && (
              <p className="mt-2 text-xs text-amber-600">
                Note: some resume details couldn't be confidently extracted — this won't stop
                your interview.
              </p>
            )}
            <textarea
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              rows={10}
              className="mt-4 w-full rounded-md border border-gray-300 p-3 text-sm focus:border-gray-900 focus:outline-none"
              placeholder="Paste the full job description here..."
              required
            />
            {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
            <button
              type="submit"
              className="mt-4 rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
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

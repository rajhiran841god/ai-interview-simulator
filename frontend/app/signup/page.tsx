"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";

const PILOT_NOTICE =
  "Pilot Notice: This is a pilot version of PlacementOS. " +
  "Your resume, job description, interview transcript, and feedback will " +
  "be stored securely to provide this service. Your data will not be used " +
  "to train AI models without your explicit permission. You may request " +
  "deletion of your data at any time.";

export default function SignupPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [consented, setConsented] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!consented) {
      setError("Please review and accept the pilot notice to continue.");
      return;
    }

    setLoading(true);
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: { data: { full_name: fullName } },
    });
    setLoading(false);

    if (error) {
      setError(error.message);
      return;
    }

    router.push("/dashboard");
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-paper px-4 py-10">
      <div className="w-full max-w-sm bg-paper-card rounded-card p-8 shadow-sm">
        <h1 className="font-display text-2xl text-ink mb-1">Create your account</h1>
        <p className="font-sans text-sm text-ink-light mb-6">PlacementOS</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="font-sans mb-1 block text-sm font-medium text-ink">
              Full name
            </label>
            <input
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="font-sans w-full rounded-card border border-ink/15 px-3 py-2 text-sm text-ink focus:border-ink focus:outline-none bg-paper"
            />
          </div>

          <div>
            <label className="font-sans mb-1 block text-sm font-medium text-ink">
              Email
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="font-sans w-full rounded-card border border-ink/15 px-3 py-2 text-sm text-ink focus:border-ink focus:outline-none bg-paper"
            />
          </div>

          <div>
            <label className="font-sans mb-1 block text-sm font-medium text-ink">
              Password
            </label>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="font-sans w-full rounded-card border border-ink/15 px-3 py-2 text-sm text-ink focus:border-ink focus:outline-none bg-paper"
            />
          </div>

          <div className="font-sans rounded-card bg-sage-light p-3.5 text-xs leading-relaxed text-sage-dark">
            {PILOT_NOTICE}
          </div>

          <label className="font-sans flex items-start gap-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={consented}
              onChange={(e) => setConsented(e.target.checked)}
              className="mt-1"
            />
            I have read and accept the pilot notice above.
          </label>

          {error && <p className="font-sans text-sm text-clay">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="font-sans w-full rounded-card bg-ink py-2.5 text-sm font-medium text-paper hover:bg-ink-light transition-colors disabled:opacity-50"
          >
            {loading ? "Creating account..." : "Create account"}
          </button>
        </form>

        <p className="font-sans mt-5 text-center text-sm text-ink-light">
          Already have an account?{" "}
          <a href="/login" className="font-medium text-ink underline">
            Sign in
          </a>
        </p>
      </div>
    </main>
  );
}

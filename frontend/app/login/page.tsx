"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    setLoading(false);

    if (error) {
      setError(error.message);
      return;
    }

    router.push("/dashboard");
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-paper px-4">
      <div className="w-full max-w-sm bg-paper-card rounded-card p-8 shadow-sm">
        <h1 className="font-display text-2xl text-ink mb-1">Sign in</h1>
        <p className="font-sans text-sm text-ink-light mb-6">PlacementOS</p>

        <form onSubmit={handleSubmit} className="space-y-4">
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
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="font-sans w-full rounded-card border border-ink/15 px-3 py-2 text-sm text-ink focus:border-ink focus:outline-none bg-paper"
            />
          </div>

          {error && <p className="font-sans text-sm text-clay">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="font-sans w-full rounded-card bg-ink py-2.5 text-sm font-medium text-paper hover:bg-ink-light transition-colors disabled:opacity-50"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p className="font-sans mt-5 text-center text-sm text-ink-light">
          No account?{" "}
          <a href="/signup" className="font-medium text-ink underline">
            Sign up
          </a>
        </p>
      </div>
    </main>
  );
}

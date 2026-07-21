// Single point of contact for Supabase on the frontend.
// Import this everywhere instead of creating new clients — keeps auth
// state consistent and matches the provider-independence rule from the
// Architecture Review Gate.
//
// Lazily constructed via a Proxy, deliberately: NEXT_PUBLIC_* env vars
// are inlined by Next.js at build time, so if they're missing during
// `npm run build` (e.g. no real credentials in this environment yet),
// eagerly calling createClient() at module load crashes the ENTIRE
// build — even pages that never actually call Supabase during
// prerendering. Deferring construction to first real use (inside a
// useEffect or event handler, which only runs client-side at runtime,
// never during server-side prerendering) means a build without real
// credentials succeeds, while any genuine attempt to use auth without
// real credentials still fails loudly and clearly, at the point of
// actual use — not silently.
import { createClient, SupabaseClient } from "@supabase/supabase-js";

let cachedClient: SupabaseClient | null = null;

function getClient(): SupabaseClient {
  if (!cachedClient) {
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    if (!supabaseUrl || !supabaseAnonKey) {
      throw new Error(
        "Supabase is not configured — set NEXT_PUBLIC_SUPABASE_URL and " +
          "NEXT_PUBLIC_SUPABASE_ANON_KEY in frontend/.env.local before using auth."
      );
    }
    cachedClient = createClient(supabaseUrl, supabaseAnonKey);
  }
  return cachedClient;
}

export const supabase = new Proxy({} as SupabaseClient, {
  get(_target, prop) {
    return Reflect.get(getClient(), prop as keyof SupabaseClient);
  },
});

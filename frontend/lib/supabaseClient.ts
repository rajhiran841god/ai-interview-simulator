// Single point of contact for Supabase on the frontend.
// Import this everywhere instead of creating new clients — keeps auth
// state consistent and matches the provider-independence rule from the
// Architecture Review Gate.
import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

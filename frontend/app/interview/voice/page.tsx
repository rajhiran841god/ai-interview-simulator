"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { LiveKitRoom, RoomAudioRenderer, useVoiceAssistant } from "@livekit/components-react";
import "@livekit/components-styles";
import { api, VoiceTokenResponse } from "@/lib/api";

// Maps LiveKit's real AgentState values to human copy. Per Decision
// Log #004: this UI only reflects states the LiveKit SDK already
// tracks — no custom turn-detection or state logic is built here.
const STATE_COPY: Record<string, string> = {
  disconnected: "Not connected",
  connecting: "Connecting...",
  "pre-connect-buffering": "Connecting...",
  initializing: "Setting up...",
  idle: "Waiting...",
  listening: "Listening to you",
  thinking: "Thinking...",
  speaking: "Speaking",
  failed: "Connection failed",
};

function VoiceStatus() {
  const { state } = useVoiceAssistant();
  const isThinking = state === "thinking";

  return (
    <div className="flex flex-col items-center justify-center py-16">
      <div
        className={`h-24 w-24 rounded-full flex items-center justify-center transition-all duration-500 ${
          state === "speaking"
            ? "bg-evidence/20 scale-110"
            : state === "listening"
              ? "bg-sage/20"
              : "bg-ink/5"
        }`}
      >
        <div
          className={`h-14 w-14 rounded-full ${
            state === "speaking"
              ? "bg-evidence animate-pulse"
              : state === "listening"
                ? "bg-sage"
                : "bg-ink/20"
          } ${isThinking ? "animate-pulse" : ""}`}
        />
      </div>
      <p className="font-sans text-sm text-ink-light mt-6">
        {STATE_COPY[state] || "Connecting..."}
      </p>
    </div>
  );
}

function VoiceRoomContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const interviewId = searchParams.get("interview_id");

  const [tokenData, setTokenData] = useState<VoiceTokenResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!interviewId) return;
    api
      .getVoiceToken(interviewId)
      .then(setTokenData)
      .catch((e) =>
        setError(
          e instanceof Error
            ? e.message
            : "Could not start the voice session. Voice may not be configured yet."
        )
      )
      .finally(() => setLoading(false));
  }, [interviewId]);

  if (!interviewId) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-paper px-4">
        <p className="font-sans text-sm text-clay">No interview session found.</p>
      </main>
    );
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-paper px-4">
        <p className="font-sans text-sm text-ink-light">Preparing voice session...</p>
      </main>
    );
  }

  if (error || !tokenData) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-paper px-4">
        <div className="w-full max-w-md bg-paper-card rounded-card p-8 text-center shadow-sm">
          <p className="font-sans text-sm text-clay mb-4">
            {error || "Voice is not available right now."}
          </p>
          <button
            onClick={() => router.push(`/interview/session?interview_id=${interviewId}`)}
            className="font-sans rounded-card bg-ink px-5 py-2.5 text-sm font-medium text-paper hover:bg-ink-light transition-colors"
          >
            Continue in text mode instead
          </button>
        </div>
      </main>
    );
  }

  return (
    <LiveKitRoom
      serverUrl={tokenData.livekit_url}
      token={tokenData.token}
      audio={true}
      connect={true}
      onDisconnected={() => router.push(`/interview/report?interview_id=${interviewId}`)}
      onError={(e) => setError(e.message)}
      className="min-h-screen bg-paper"
    >
      <main className="min-h-screen bg-paper px-4 py-16">
        <div className="mx-auto max-w-xl text-center">
          <p className="font-sans text-xs uppercase tracking-wide text-ink-light mb-2">
            Voice interview
          </p>
          <VoiceStatus />
        </div>
      </main>
      <RoomAudioRenderer />
    </LiveKitRoom>
  );
}

export default function VoicePage() {
  return (
    <Suspense>
      <VoiceRoomContent />
    </Suspense>
  );
}

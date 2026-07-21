// Single point of contact for the backend API, mirroring the
// supabaseClient.ts pattern already established — import this
// everywhere instead of hand-rolling fetch calls per page.

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export interface SessionResponse {
  interview_id: string;
  status: string;
  created_at: string;
}

export interface NextQuestionResponse {
  decision_type: "continue" | "stop";
  question_id: string;
  question_text?: string;
  target_competency_id?: string;
  stop_reason?: string;
}

export interface SubmitAnswerResponse {
  accepted: boolean;
  answer_classification?: string;
}

export interface CompetencyFeedback {
  competency_id: string;
  emphasis: "primary" | "secondary";
  summary_text: string;
  has_unresolved_contradiction: boolean;
  insufficient_evidence: boolean;
}

export interface InterviewFeedbackReport {
  interview_id: string;
  competency_feedback: CompetencyFeedback[];
  overall_summary: string;
  generated_at: string;
}

export interface EvidenceDetail {
  evidence_id: string;
  evidence_excerpt: string;
  relation: "supports" | "contradicts";
  question_number: number;
}

export interface VoiceTokenResponse {
  livekit_url: string;
  token: string;
  room_name: string;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...options.headers,
    },
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API error ${res.status}: ${detail}`);
  }
  return res.json();
}

export const api = {
  createInterview: (userId: string) =>
    request<SessionResponse>(`/api/interviews?user_id=${encodeURIComponent(userId)}`, {
      method: "POST",
    }),

  getInterview: (interviewId: string) =>
    request<SessionResponse>(`/api/interviews/${interviewId}`),

  uploadResume: (interviewId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return request<{ status: string; parse_warnings: string[] }>(
      `/api/interviews/${interviewId}/resume`,
      { method: "POST", body: formData }
    );
  },

  uploadJD: (interviewId: string, jdText: string) => {
    const formData = new FormData();
    formData.append("jd_text", jdText);
    return request<{ status: string; competencies_initialized: string[]; parse_warnings: string[] }>(
      `/api/interviews/${interviewId}/jd`,
      { method: "POST", body: formData }
    );
  },

  getNextQuestion: (interviewId: string) =>
    request<NextQuestionResponse>(`/api/interviews/${interviewId}/next-question`, {
      method: "POST",
    }),

  submitAnswer: (interviewId: string, questionId: string, answerText: string) =>
    request<SubmitAnswerResponse>(`/api/interviews/${interviewId}/answer`, {
      method: "POST",
      body: JSON.stringify({ question_id: questionId, answer_text: answerText }),
    }),

  getReport: (interviewId: string) =>
    request<InterviewFeedbackReport>(`/api/interviews/${interviewId}/report`),

  getEvidenceDetail: (interviewId: string, competencyId: string) =>
    request<EvidenceDetail[]>(`/api/interviews/${interviewId}/evidence/${competencyId}`),

  getVoiceToken: (interviewId: string) =>
    request<VoiceTokenResponse>(`/api/interviews/${interviewId}/voice-token`, {
      method: "POST",
    }),
};

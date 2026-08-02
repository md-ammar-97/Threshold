import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { apiClient } from "@/lib/api/client";
import { useThemes } from "@/lib/api/themes";

export interface ResearchSession {
  id: string;
  title: string;
  analysis_run_id: string;
  theme_set_id: string;
  insight_set_id: string | null;
  status: string;
  created_at: string;
}

export interface AnswerCitation {
  citation_label: string;
  object_type: string;
  object_id: string;
  evidence_role: string;
  excerpt_snapshot: string | null;
  supports_claim: boolean | null;
}

export interface AnswerFinding {
  position: number;
  finding_type: string;
  statement: string;
  confidence_level: string;
  confidence_score: number | null;
  support_status: string;
  citations: AnswerCitation[];
}

export interface AnswerWarning {
  warning_type: string;
  severity: string;
  message: string;
  details: Record<string, unknown>;
}

export interface GeneratedAnswer {
  id: string;
  answer_text: string;
  grounding_status: string;
  grounding_score: number | null;
  citation_count: number;
  warning_count: number;
  observed_evidence_count: number;
  synthesized_insight_count: number;
  product_hypothesis_count: number;
  limitations: string[];
  suggested_validations: string[];
  findings: AnswerFinding[];
  warnings: AnswerWarning[];
}

export interface QueryPlan {
  research_dimensions: string[];
  query_intent: string;
  structured_filters: Record<string, unknown>;
  ambiguity_warnings: Record<string, unknown>;
  requires_deterministic_aggregation: boolean;
}

export interface ResearchQuestion {
  id: string;
  research_session_id: string;
  question_text: string;
  status: string;
  requested_filters: Record<string, unknown>;
  effective_filters: Record<string, unknown>;
  answer_mode: string | null;
  failure_code: string | null;
  failure_message: string | null;
  query_plan: QueryPlan | null;
  answer: GeneratedAnswer | null;
}

export function useCreateResearchSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      title: string;
      analysis_run_id: string;
      theme_set_id: string;
      insight_set_id?: string | null;
    }) => apiClient.post<ResearchSession>("/api/v1/research/sessions", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["research-sessions"] }),
  });
}

export function useAskQuestion(sessionId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { question_text: string; requested_filters?: Record<string, string> }) => {
      if (!sessionId) throw new Error("No research session selected");
      return apiClient.post<ResearchQuestion>(
        `/api/v1/research/sessions/${sessionId}/questions`,
        body,
      );
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["research-question", data.id], data);
    },
  });
}

export function useResearchQuestion(questionId: string | null) {
  return useQuery({
    queryKey: ["research-question", questionId],
    queryFn: () => apiClient.get<ResearchQuestion>(`/api/v1/research/questions/${questionId}`),
    enabled: Boolean(questionId),
  });
}

const SESSION_STORAGE_KEY = "instamart-research-session";

interface StoredSession {
  themeSetId: string;
  sessionId: string;
}

/** There is no session-management UI yet (deferred — see
 * docs/implementationplan.md Phase 7 status note), so the Ask workspace
 * auto-provisions one real `research_session` per browser against the
 * latest theme_set, reusing it across visits via localStorage and only
 * creating a new one when the theme_set changes underneath it. */
export function useDefaultResearchSession() {
  const themesQuery = useThemes();
  const createSession = useCreateResearchSession();
  const [sessionId, setSessionId] = useState<string | null>(null);
  // A latch, not renderable state: guards against re-provisioning a session
  // on every render once an attempt has started for this theme_set.
  const attemptedThemeSetId = useRef<string | null>(null);

  const themeSetId = themesQuery.data?.theme_set_id ?? null;
  const analysisRunId = themesQuery.data?.analysis_run_id ?? null;

  useEffect(() => {
    if (!themeSetId || !analysisRunId || attemptedThemeSetId.current === themeSetId) return;
    attemptedThemeSetId.current = themeSetId;

    const stored = window.localStorage.getItem(SESSION_STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored) as StoredSession;
      if (parsed.themeSetId === themeSetId) {
        // localStorage is a client-only external system that can't be read
        // during the lazy useState initializer (themeSetId itself only
        // arrives once the themes query resolves) — an effect is the
        // correct place for this synchronization, not a derivable render.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setSessionId(parsed.sessionId);
        return;
      }
    }

    createSession.mutate(
      { title: "Ask workspace session", analysis_run_id: analysisRunId, theme_set_id: themeSetId },
      {
        onSuccess: (session) => {
          window.localStorage.setItem(
            SESSION_STORAGE_KEY,
            JSON.stringify({ themeSetId, sessionId: session.id } satisfies StoredSession),
          );
          setSessionId(session.id);
        },
      },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [themeSetId, analysisRunId]);

  return {
    sessionId,
    isLoading: themesQuery.isLoading || (Boolean(themeSetId) && !sessionId && !createSession.isError),
    hasThemeSet: Boolean(themeSetId),
    error: createSession.error ?? themesQuery.error,
  };
}

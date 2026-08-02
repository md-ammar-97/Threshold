import { Send } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { CitationChip } from "@/components/research/citation-chip";
import { ConfidenceIndicator } from "@/components/research/confidence-indicator";
import { EvidenceInspector } from "@/components/research/evidence-inspector";
import { KnowledgeTypeBadge, type KnowledgeType } from "@/components/research/knowledge-type-badge";
import { WarningBanner } from "@/components/research/warning-banner";
import { FadeIn } from "@/components/motion/fade-in";
import { ApiError } from "@/lib/api/client";
import { useAskQuestion, useDefaultResearchSession } from "@/lib/api/research";
import type { AnswerCitation, AnswerFinding, ResearchQuestion } from "@/lib/api/research";

const PRESET_QUESTIONS = [
  "Why do users return to the same categories?",
  "What prevents exploration of unfamiliar categories?",
  "How do users discover products today?",
  "What information reduces risk before trial?",
  "Which signals indicate willingness to experiment?",
  "What unmet needs repeat across sources?",
];

const SEVERITY_TO_WARNING = { info: "info", warning: "caution", error: "error" } as const;

function FindingBlock({
  finding,
  onCitationOpen,
}: {
  finding: AnswerFinding;
  onCitationOpen: (citation: AnswerCitation) => void;
}) {
  const unsupported = finding.support_status === "unsupported" || finding.support_status === "contradicted";
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border-default)] bg-[var(--color-bg-surface)] p-4">
      <div className="flex flex-wrap items-center gap-2">
        <KnowledgeTypeBadge type={finding.finding_type as KnowledgeType} />
        <ConfidenceIndicator level={finding.confidence_level as "high" | "medium" | "low" | "unscored"} score={finding.confidence_score} />
      </div>
      <p className="text-body-lg measure-narrative mt-2">{finding.statement}</p>
      {unsupported ? (
        <WarningBanner severity="caution" title="This finding is not fully supported by resolvable evidence." />
      ) : null}
      {finding.citations.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {finding.citations.map((citation) => (
            <CitationChip
              key={citation.citation_label}
              label={citation.citation_label}
              preview={citation.excerpt_snapshot ?? undefined}
              onOpen={() => onCitationOpen(citation)}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function AnswerView({
  question,
  onCitationOpen,
}: {
  question: ResearchQuestion;
  onCitationOpen: (citation: AnswerCitation) => void;
}) {
  const answer = question.answer;
  if (!answer) return null;

  return (
    <FadeIn className="flex flex-col gap-4">
      <p className="text-body-lg measure-narrative">{answer.answer_text}</p>

      {answer.warnings.length > 0 ? (
        <div className="flex flex-col gap-2">
          {answer.warnings.map((warning, index) => (
            <WarningBanner
              key={index}
              severity={SEVERITY_TO_WARNING[warning.severity as keyof typeof SEVERITY_TO_WARNING] ?? "info"}
              title={warning.message}
            />
          ))}
        </div>
      ) : null}

      <div className="flex flex-col gap-3">
        {answer.findings.map((finding) => (
          <FindingBlock key={finding.position} finding={finding} onCitationOpen={onCitationOpen} />
        ))}
      </div>

      {answer.limitations.length > 0 ? (
        <div>
          <h3 className="text-heading-sm">Limitations</h3>
          <ul className="text-body-md mt-1 list-inside list-disc text-[var(--color-text-secondary)]">
            {answer.limitations.map((limitation, index) => (
              <li key={index}>{limitation}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {answer.suggested_validations.length > 0 ? (
        <div>
          <h3 className="text-heading-sm">Suggested validation</h3>
          <ul className="text-body-md mt-1 list-inside list-disc text-[var(--color-text-secondary)]">
            {answer.suggested_validations.map((validation, index) => (
              <li key={index}>{validation}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </FadeIn>
  );
}

export function AskWorkspace() {
  const { sessionId, isLoading: sessionLoading, hasThemeSet, error: sessionError } = useDefaultResearchSession();
  const [questionText, setQuestionText] = useState("");
  const [selectedRecordId, setSelectedRecordId] = useState<string | null>(null);
  const askQuestion = useAskQuestion(sessionId);
  const navigate = useNavigate();

  function submit(text: string) {
    if (!text.trim() || askQuestion.isPending) return;
    askQuestion.mutate({ question_text: text.trim() });
  }

  function handleCitationOpen(citation: AnswerCitation) {
    // feedback_record opens the shared evidence drawer in place; theme/
    // insight citations navigate to their own detail page instead, since
    // there's no drawer content for those object types here.
    if (citation.object_type === "feedback_record") {
      setSelectedRecordId(citation.object_id);
    } else if (citation.object_type === "theme") {
      navigate(`/themes/${citation.object_id}`);
    } else if (citation.object_type === "insight") {
      navigate(`/insights/${citation.object_id}`);
    }
  }

  if (!hasThemeSet && !sessionLoading) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-16">
        <h1 className="text-heading-xl">Ask</h1>
        <p className="text-body-lg measure-narrative mt-3 text-[var(--color-text-secondary)]">
          No analyzed theme set exists yet. Run ingestion and analysis (Phases 1&ndash;4) before asking a
          research question &mdash; the Ask workspace answers only from retrieved evidence, and there is
          none to retrieve yet.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-8 px-6 py-10">
      <div>
        <h1 className="text-heading-xl">Ask</h1>
        <p className="text-body-lg measure-narrative mt-2 text-[var(--color-text-secondary)]">
          Evidence-grounded answers to discovery and exploration questions, with every claim traceable to a
          citation.
        </p>
      </div>

      {sessionError ? (
        <WarningBanner severity="error" title="Could not start a research session">
          {sessionError instanceof ApiError ? sessionError.message : "An unexpected error occurred."}
        </WarningBanner>
      ) : null}

      {!askQuestion.data ? (
        <div className="flex flex-wrap gap-2">
          {PRESET_QUESTIONS.map((preset) => (
            <button
              key={preset}
              type="button"
              onClick={() => setQuestionText(preset)}
              className="text-label-lg rounded-[var(--radius-full)] border border-[var(--color-border-default)] px-3 py-1.5 text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-border-strong)]"
            >
              {preset}
            </button>
          ))}
        </div>
      ) : null}

      <div className="rounded-[var(--radius-xl)] border border-[var(--color-border-default)] bg-[var(--color-bg-surface)] p-4 shadow-[var(--shadow-xs)]">
        <Textarea
          value={questionText}
          onChange={(e) => setQuestionText(e.target.value)}
          placeholder="Ask a discovery research question…"
          rows={3}
          disabled={sessionLoading || askQuestion.isPending}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit(questionText);
          }}
        />
        <div className="mt-2 flex items-center justify-between">
          <span className="text-caption text-[var(--color-text-tertiary)]">⌘/Ctrl + Enter to submit</span>
          <Button
            onClick={() => submit(questionText)}
            loading={askQuestion.isPending}
            disabled={sessionLoading || !sessionId || !questionText.trim()}
          >
            <Send className="size-4" aria-hidden />
            Ask
          </Button>
        </div>
      </div>

      {sessionLoading ? (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      ) : null}

      {askQuestion.isPending ? (
        <div className="flex items-center gap-2 text-[var(--color-text-secondary)]">
          <Spinner label="Generating answer" />
          <span className="text-body-md">Planning, retrieving evidence, and generating a grounded answer…</span>
        </div>
      ) : null}

      {askQuestion.isError ? (
        <WarningBanner severity="error" title="The answer could not be generated">
          {askQuestion.error instanceof ApiError
            ? askQuestion.error.message
            : "An unexpected error occurred while generating the answer."}
        </WarningBanner>
      ) : null}

      {askQuestion.data ? (
        <AnswerView question={askQuestion.data} onCitationOpen={handleCitationOpen} />
      ) : null}

      <EvidenceInspector
        recordId={selectedRecordId}
        onOpenChange={(open) => !open && setSelectedRecordId(null)}
      />
    </div>
  );
}

import { CheckCheck, FlaskConical, Quote, Sparkles, SplitSquareVertical } from "lucide-react";

import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";

export type KnowledgeType =
  | "observed_evidence"
  | "synthesized_insight"
  | "product_hypothesis"
  | "contradiction"
  | "reviewed";

const CONFIG: Record<KnowledgeType, { label: string; tone: BadgeTone; icon: typeof Quote }> = {
  observed_evidence: { label: "Observed", tone: "evidence", icon: Quote },
  synthesized_insight: { label: "Synthesized", tone: "synthesis", icon: Sparkles },
  product_hypothesis: { label: "Hypothesis", tone: "primary", icon: FlaskConical },
  contradiction: { label: "Contradiction", tone: "warning", icon: SplitSquareVertical },
  reviewed: { label: "Reviewed", tone: "discovery", icon: CheckCheck },
};

/** design.md §4.3/§7.3 — knowledge type must never rely on color alone: the
 * icon + label combination is required, not decorative. */
export function KnowledgeTypeBadge({ type, className }: { type: KnowledgeType; className?: string }) {
  const config = CONFIG[type];
  return (
    <Badge tone={config.tone} icon={<Icon icon={config.icon} size="dense" />} className={className}>
      {config.label}
    </Badge>
  );
}

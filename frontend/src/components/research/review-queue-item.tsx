import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { ReviewQueueItem, SubmitReviewRequest } from "@/lib/api/validation";

type PendingAction = "reject" | "second_review" | "edit" | null;

/** design.md §32.4 — one review row: model output, evidence, confidence,
 * expected action, and accept/edit/reject/second-review, each clearly
 * separated (the spec explicitly warns against placing accept and reject
 * too close together). */
export function ReviewQueueItemCard({
  item,
  onSubmit,
  isSubmitting,
}: {
  item: ReviewQueueItem;
  onSubmit: (body: SubmitReviewRequest) => void;
  isSubmitting: boolean;
}) {
  const [pendingAction, setPendingAction] = useState<PendingAction>(null);
  const [reasonCode, setReasonCode] = useState("");
  const [editedLabelKey, setEditedLabelKey] = useState(item.label_key);

  function reset() {
    setPendingAction(null);
    setReasonCode("");
    setEditedLabelKey(item.label_key);
  }

  function accept() {
    onSubmit({
      object_type: item.object_type,
      object_id: item.object_id,
      decision: "accepted",
      previous_snapshot: item.previous_snapshot,
    });
  }

  function confirmReject() {
    if (!reasonCode.trim()) return;
    onSubmit({
      object_type: item.object_type,
      object_id: item.object_id,
      decision: "rejected",
      previous_snapshot: item.previous_snapshot,
      reason_code: reasonCode.trim(),
    });
    reset();
  }

  function confirmSecondReview() {
    if (!reasonCode.trim()) return;
    onSubmit({
      object_type: item.object_type,
      object_id: item.object_id,
      decision: "needs_second_review",
      previous_snapshot: item.previous_snapshot,
      reason_code: reasonCode.trim(),
    });
    reset();
  }

  function confirmEdit() {
    if (!editedLabelKey.trim()) return;
    onSubmit({
      object_type: item.object_type,
      object_id: item.object_id,
      decision: "edited",
      previous_snapshot: item.previous_snapshot,
      edited_snapshot: {
        dimension_key: item.dimension_key,
        label_key: editedLabelKey.trim(),
        confidence: item.confidence,
      },
    });
    reset();
  }

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border-default)] bg-[var(--color-bg-surface)] p-4">
      <p className="text-body-md line-clamp-3">{item.excerpt}</p>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Badge tone="neutral">{item.dimension_display_name}</Badge>
        <Badge tone="primary">{item.label_display_name}</Badge>
        <span className="text-body-sm text-[var(--color-text-tertiary)]">
          confidence {(item.confidence * 100).toFixed(0)}%
        </span>
      </div>

      {pendingAction === null ? (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button size="sm" variant="primary" onClick={accept} disabled={isSubmitting}>
            Accept
          </Button>
          <Button size="sm" variant="secondary" onClick={() => setPendingAction("edit")} disabled={isSubmitting}>
            Edit
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setPendingAction("second_review")} disabled={isSubmitting}>
            Needs second review
          </Button>
          {/* Deliberate gap from Accept — design.md §32.4: never place accept/reject close together. */}
          <div className="ml-auto">
            <Button size="sm" variant="outline" onClick={() => setPendingAction("reject")} disabled={isSubmitting}>
              Reject
            </Button>
          </div>
        </div>
      ) : null}

      {pendingAction === "reject" || pendingAction === "second_review" ? (
        <div className="mt-3 flex flex-col gap-2 rounded-[var(--radius-md)] border border-[var(--color-border-default)] p-3">
          <label className="text-label-md text-[var(--color-text-secondary)]" htmlFor={`reason-${item.object_id}`}>
            Reason ({pendingAction === "reject" ? "required to reject" : "required for second review"})
          </label>
          <Input
            id={`reason-${item.object_id}`}
            value={reasonCode}
            onChange={(e) => setReasonCode(e.target.value)}
            placeholder="e.g. wrong_dimension, ambiguous_evidence…"
          />
          <div className="flex gap-2">
            <Button
              size="sm"
              variant={pendingAction === "reject" ? "destructive" : "primary"}
              onClick={pendingAction === "reject" ? confirmReject : confirmSecondReview}
              disabled={isSubmitting || !reasonCode.trim()}
            >
              Confirm {pendingAction === "reject" ? "reject" : "second review"}
            </Button>
            <Button size="sm" variant="ghost" onClick={reset} disabled={isSubmitting}>
              Cancel
            </Button>
          </div>
        </div>
      ) : null}

      {pendingAction === "edit" ? (
        <div className="mt-3 flex flex-col gap-2 rounded-[var(--radius-md)] border border-[var(--color-border-default)] p-3">
          <label className="text-label-md text-[var(--color-text-secondary)]" htmlFor={`label-${item.object_id}`}>
            Corrected label within {item.dimension_display_name}
          </label>
          <Input
            id={`label-${item.object_id}`}
            value={editedLabelKey}
            onChange={(e) => setEditedLabelKey(e.target.value)}
            placeholder="taxonomy label key"
          />
          <div className="flex gap-2">
            <Button size="sm" variant="primary" onClick={confirmEdit} disabled={isSubmitting || !editedLabelKey.trim()}>
              Save edit
            </Button>
            <Button size="sm" variant="ghost" onClick={reset} disabled={isSubmitting}>
              Cancel
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

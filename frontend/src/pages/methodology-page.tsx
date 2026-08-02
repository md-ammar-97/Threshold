const STEPS = [
  {
    title: "1. Ingestion",
    body: "Public app reviews and web content are collected through versioned connectors and stored as immutable raw artifacts before any transformation.",
  },
  {
    title: "2. Classification",
    body: "Each record is normalized, privacy-redacted, and classified against a versioned taxonomy (journey stage, exploration barriers, frustration and unmet-need families) with evidence spans for every applied label.",
  },
  {
    title: "3. Embeddings and themes",
    body: "Records are embedded locally and clustered into versioned theme sets. Every theme keeps reversible membership back to its source records, plus a counterexample where one exists.",
  },
  {
    title: "4. Insight synthesis",
    body: "Themes are synthesized into insights labelled by knowledge type — observed evidence, synthesized insight, or product hypothesis — each requiring at least one evidence link and, for hypotheses, a validation recommendation.",
  },
  {
    title: "5. Grounded research (Ask)",
    body: "Questions are planned into structured filters and intent, evidence is retrieved through a hybrid of vector similarity and keyword search, and answers are generated only from the retrieved evidence package — never from outside model knowledge.",
  },
  {
    title: "6. Validation",
    body: "Deterministic graders check citation integrity, demographic-inference risk, and causal overclaiming on every generated answer, and are combined into a release-gate decision before any result is treated as production-ready.",
  },
];

/** design.md §5.1/§5.2 — secondary nav item explaining data sources,
 * taxonomy, and evaluation approach in plain language. */
export default function MethodologyPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="text-heading-xl">Methodology</h1>
      <p className="text-body-lg measure-narrative mt-2 text-[var(--color-text-secondary)]">
        How raw public conversations become structured, evidence-linked product research.
      </p>

      <ol className="mt-8 flex flex-col gap-6">
        {STEPS.map((step) => (
          <li key={step.title} className="rounded-[var(--radius-lg)] border border-[var(--color-border-default)] bg-[var(--color-bg-surface)] p-5">
            <h2 className="text-heading-sm">{step.title}</h2>
            <p className="text-body-md measure-narrative mt-1 text-[var(--color-text-secondary)]">{step.body}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}

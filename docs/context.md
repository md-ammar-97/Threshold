# Project Context: AI-Powered Discovery Engine for Swiggy Instamart

## 1. Purpose of This Document

This document defines **what we are actually building, why it matters, how the first version will work, and what decisions Claude Code should follow during implementation**.

It is not a restatement of the assignment. It converts the broad brief into a concrete product and engineering plan that can be executed in **VS Code using Claude Code**, with other services introduced only where they materially improve data access, automation, analysis quality, or validation.

This document should be read together with the rest of the documentation set:

- `problemstatement.md` — the original project brief;
- `architecture.md` — system boundaries, services, data flow, and APIs;
- `datamodel.md` — canonical entities, lineage, and versioning rules;
- `design.md` — visual, interaction, and motion design system;
- `edgecases.md` — expected behaviour for failure and unusual states;
- `ai_evals.md` — how AI-dependent capabilities are evaluated and gated for release.

---

## 2. The Specific Problem We Are Solving

Swiggy Instamart users leave large amounts of feedback across app stores, Reddit, forums, review websites, and social platforms. Product teams can search these sources manually, but the evidence is fragmented, repetitive, noisy, and difficult to compare.

The central problem is not merely to classify reviews as positive or negative. The problem is to determine:

- what causes users to remain within familiar shopping categories;
- what reduces confidence in trying unfamiliar products or categories;
- how product discovery currently happens;
- which recurring product, pricing, availability, trust, quality, and fulfilment issues influence exploration;
- which user groups appear more willing to experiment;
- which unmet needs are repeated strongly enough to justify product action.

The discovery engine must convert unstructured public conversations into **traceable, evidence-backed product insights**. Every important conclusion should be supported by source excerpts, source links or identifiers, occurrence counts, affected segments, and a confidence assessment.

---

## 3. Important Research Limitation

The available sources contain public feedback and self-reported behaviour. They do **not** contain Swiggy's internal transaction, search, impression, category-view, add-to-cart, reorder, or retention data.

Therefore, the engine can identify:

- stated motivations;
- reported barriers;
- repeated complaints;
- perceived discovery mechanisms;
- behavioural signals expressed in text;
- hypotheses about category repetition and experimentation.

It cannot prove actual purchasing causality or calculate true behavioural conversion without first-party product analytics. The interface and reports must clearly distinguish:

1. **Observed evidence** — directly stated or strongly represented in the collected text.
2. **Synthesized insight** — a conclusion supported by multiple evidence items.
3. **Product hypothesis** — a plausible explanation that requires validation using interviews, surveys, experiments, or internal behavioural data.

This distinction is essential to prevent the system from presenting model-generated interpretation as fact.

---

## 4. Product Definition

We will build a local-first web application called the **Instamart Discovery Engine**.

A user should be able to:

1. ingest feedback from supported public sources;
2. normalize and clean the collected records;
3. classify each record using a defined research taxonomy;
4. cluster semantically similar feedback into themes;
5. ask natural-language questions about habits, exploration, discovery, frustrations, segments, and unmet needs;
6. receive a structured answer with evidence citations;
7. inspect the source records behind every generated insight;
8. view theme frequency, severity, recency, source distribution, and confidence;
9. export a concise insight report for product decision-making.

The MVP should behave like a **research analyst with a verifiable evidence trail**, not like a chatbot that produces unsupported summaries.

---

## 5. Primary Users

### Primary user

A product manager, product researcher, or growth analyst studying discovery and category exploration in quick commerce.

### Secondary users

- UX researchers preparing interview hypotheses;
- category managers identifying trust and assortment gaps;
- customer-experience teams tracking repeated frustrations;
- strategy teams studying user needs and market conversations.

---

## 6. MVP Scope

### Included in the first working version

The MVP will support three source groups:

1. **Google Play reviews** for broad, structured app feedback.
2. **Reddit discussions** for longer, contextual conversations about quick-commerce behaviour.
3. **Public web discussions and review pages** for additional category, trust, product-quality, and service-related evidence.

The initial dataset should target approximately **5,000 to 10,000 records**, subject to source availability and scraping cost. A smaller sample is acceptable for the first end-to-end prototype as long as the system demonstrates the complete workflow.

The default analysis window will be the **most recent 12 months** available at collection time. The collector must store the actual publication date and ingestion date so the time window can be changed later.

### Deferred from the MVP

- production-scale continuous crawling;
- live integration with Swiggy's internal product analytics;
- automated posting or engagement on social platforms;
- real-time alerts;
- multilingual speech or image analysis;
- causal claims about purchasing behaviour;
- full Twitter/X ingestion because of cost;
- full Apple App Store ingestion until a reliable collection method is tested;
- automated product-roadmap decisions without human review.

Apple App Store and Twitter/X should remain pluggable connectors, not hard MVP dependencies.

---

## 7. Core Research Questions the System Must Operationalize

The broad questions will be translated into answerable analytical dimensions.

### A. Repeat-category behaviour

Determine whether users describe repeated purchases because of:

- routine or replenishment needs;
- familiarity and low cognitive effort;
- saved items, reorder flows, or previous orders;
- predictable quality;
- known brands;
- price sensitivity;
- urgency;
- limited time to browse;
- poor visibility of unfamiliar categories;
- weak trust in substitutions, freshness, or product authenticity.

### B. Barriers to category exploration

Identify barriers such as:

- insufficient product information;
- poor images or descriptions;
- uncertain size, quantity, freshness, or expiry;
- unavailable trusted brands;
- high or unclear prices;
- delivery fees or minimum-order thresholds;
- irrelevant recommendations;
- weak search and navigation;
- out-of-stock products;
- substitution anxiety;
- prior bad experiences;
- fear of receiving damaged, stale, counterfeit, or low-quality products.

### C. Current discovery mechanisms

Identify whether discovery occurs through:

- search;
- home-page recommendations;
- category browsing;
- offers and discounts;
- banners;
- trending sections;
- previous orders;
- external social recommendations;
- family or peer suggestions;
- urgency-driven need states;
- accidental exposure while buying something else.

### D. Experimentation propensity

Infer segments more likely to experiment based on signals such as:

- deal-seeking behaviour;
- novelty-seeking language;
- premium-product interest;
- convenience dependence;
- planned versus urgent shopping;
- household role;
- city or region when explicitly available;
- category context;
- positive versus negative prior experience;
- frequency of quick-commerce use when self-reported.

Segments must be inferred only from available evidence. The system must not fabricate age, income, gender, occupation, or household attributes.

---

## 8. Chosen Technical Approach

### Development environment

- **VS Code** as the primary IDE.
- **Claude Code** as the primary coding agent for repository setup, implementation, refactoring, testing, and documentation.
- Git for version control.
- A `.env` file for API keys and external service configuration.

### Proposed application stack

#### Frontend

- **Vite with TypeScript** for the production-quality web application.
- **React** with **React Router** for component-based interface development and client-side routing.
- **Tailwind CSS** for styling and design-token implementation.
- **shadcn/ui-style components** as the accessible, composable foundation for the interface.
- **Framer Motion** for purposeful transitions, layout animation, progressive disclosure, and high-quality interaction feedback.
- **21st.dev components and patterns** may be used selectively to accelerate polished interface construction, provided they are adapted to the product rather than copied without review.
- A dedicated client-side data layer for API state, caching, loading states, and error recovery.

The frontend must feel like a credible AI-native product rather than an internal analytics prototype. However, detailed visual direction, component specifications, page composition, motion principles, responsiveness, and interaction states will be defined separately in `design.md`. This context document establishes only the technical boundary and required product capabilities.

#### Backend and analysis

- **Python 3.12** for ingestion, preprocessing, analysis, evaluation, and API services.
- **FastAPI** for the backend API consumed by the Vite frontend.
- **PostgreSQL with pgvector** for structured records, metadata, embeddings, and evidence retrieval.
- **Pandas or Polars** for data cleaning and transformation.
- **Sentence-transformers or an embedding API** for vector representations.
- **Claude API** as the preferred reasoning and synthesis model, with the model name configurable through environment variables.
- **Pydantic** schemas for structured model outputs and API contracts.
- **Playwright** for browser-based collection where ordinary HTTP extraction is insufficient.
- **Apify** only for sources whose access restrictions make direct collection unreliable.
- **Pytest** for backend unit and integration testing.
- Frontend tests using an appropriate React testing stack, with end-to-end tests for critical flows.

### Optional supporting tools

- **n8n** may be added later for scheduled ingestion and workflow visibility, but it is not required for the first local prototype.
- **Perplexity or web search APIs** may be used for supplementary industry context, but external articles must not be mixed with user feedback without a clear source-type label.
- **LangGraph or a lightweight custom orchestration layer** may be introduced only if the workflow genuinely needs stateful agents. The MVP should avoid unnecessary agent complexity.

### Architecture principle

Prefer deterministic Python pipelines for collection, cleaning, deduplication, scoring, and validation. Use an LLM only for tasks where semantic interpretation adds value, including nuanced classification, theme naming, insight synthesis, and grounded question answering.

---

## 9. Proposed System Architecture

```text
Public Sources
    |
    v
Source Connectors
(Google Play / Reddit / Web / Optional Apple & X)
    |
    v
Raw Data Store
(JSONL + database ingestion log)
    |
    v
Normalization and Cleaning
(language detection, duplicate removal, spam filtering, metadata standardization)
    |
    v
Enrichment Pipeline
(sentiment, intent, category, barrier, need, journey stage, severity, experimentation signals)
    |
    +----------------------+
    |                      |
    v                      v
Embeddings              Structured Labels
    |                      |
    +----------+-----------+
               v
       Theme Discovery Layer
(clustering + LLM-assisted naming + representative evidence)
               |
               v
        Evidence Repository
       (records, themes, links,
       counts, scores, citations)
               |
               v
      RAG and Insight Generator
               |
               v
        FastAPI Service Layer
(auth-ready APIs, streaming answers, filters, exports)
               |
               v
       Vite Research Workspace
(insight overview, theme explorer, AI Q&A,
evidence inspection, validation, report export)
```

---

## 10. Data Collection Strategy

### Google Play

Use `google-play-scraper` to collect Swiggy reviews with:

- review ID;
- review text;
- rating;
- review date;
- app version when available;
- thumbs-up count when available;
- locale and country used for collection;
- source URL or canonical app identifier.

The collector must support pagination, configurable limits, and checkpointing.

### Reddit

Use an Apify Reddit actor for the MVP unless official OAuth access is configured. Search should cover both brand-specific and behaviour-specific queries, for example:

- Swiggy Instamart;
- Instamart review;
- Instamart product quality;
- Instamart recommendations;
- quick commerce India;
- Blinkit vs Instamart;
- Zepto vs Instamart;
- grocery delivery habits;
- trying new products on grocery apps.

Collect posts and useful comments separately while retaining the parent-child relationship.

### Public websites and forums

Use a configurable URL/query list. Begin with a small set of high-signal pages rather than crawling entire domains. Store page title, page URL, publication date when available, extracted passage, and website name.

### Source boundaries

Industry articles are useful for market context but are not user feedback. They must be stored with `source_type = industry_commentary` and excluded from user-theme frequency unless the user explicitly includes them.

### Responsible collection

- respect robots directives and website terms where applicable;
- rate-limit requests;
- avoid collecting private or login-gated content;
- avoid storing usernames unless necessary for thread structure;
- hash or remove user identifiers before analysis;
- collect only content needed for the research objective.

---

## 11. Canonical Data Model

Each feedback record should follow a common schema.

```json
{
  "record_id": "stable_internal_id",
  "source": "google_play | reddit | web | apple_app_store | twitter_x",
  "source_type": "app_review | post | comment | forum_review | industry_commentary",
  "source_item_id": "original_source_identifier",
  "parent_id": null,
  "url": "source_url_when_available",
  "published_at": "ISO-8601 timestamp",
  "ingested_at": "ISO-8601 timestamp",
  "title": null,
  "text_raw": "original text",
  "text_clean": "normalized text",
  "rating": null,
  "language": "en",
  "location": null,
  "app_version": null,
  "engagement_count": null,
  "is_duplicate": false,
  "is_spam": false,
  "analysis": {
    "sentiment": "positive | neutral | negative | mixed",
    "sentiment_score": 0.0,
    "journey_stage": [],
    "categories_mentioned": [],
    "discovery_channels": [],
    "behavioural_drivers": [],
    "exploration_barriers": [],
    "frustrations": [],
    "unmet_needs": [],
    "experimentation_signals": [],
    "severity": 1,
    "confidence": 0.0
  }
}
```

All LLM-generated fields must include a confidence value and should allow `unknown` or an empty list. Forced classification is not acceptable.

---

## 12. Initial Research Taxonomy

The taxonomy will begin as a controlled set of labels and evolve after reviewing a representative sample.

### Journey stages

- need recognition;
- app entry;
- search;
- browse;
- product evaluation;
- cart building;
- checkout;
- fulfilment;
- delivery;
- consumption or usage;
- support, refund, or complaint;
- repeat purchase.

### Behavioural drivers

- habit;
- convenience;
- urgency;
- replenishment;
- familiarity;
- loyalty;
- price or promotion;
- availability;
- speed;
- perceived quality;
- low effort;
- social influence;
- curiosity or novelty.

### Exploration barriers

- weak recommendation relevance;
- poor search or navigation;
- insufficient information;
- price uncertainty;
- quality uncertainty;
- freshness or expiry concern;
- trust or authenticity concern;
- substitution concern;
- limited assortment;
- preferred brand unavailable;
- out of stock;
- delivery economics;
- prior negative experience;
- time pressure;
- excessive choice;
- low perceived need.

### Frustration families

- product quality;
- missing or wrong item;
- refund or support;
- delivery delay;
- cancellation;
- pricing discrepancy;
- fees;
- inventory accuracy;
- search;
- recommendation;
- app performance;
- payment;
- packaging;
- substitution;
- dark patterns or misleading offers.

### Unmet-need families

- richer product information;
- better comparison;
- stronger trust signals;
- personalized discovery;
- transparent pricing;
- reliable stock status;
- controllable substitutions;
- category education;
- samples or trial sizes;
- bundles or starter kits;
- dietary and preference filters;
- improved post-purchase resolution.

---

## 13. Analysis Workflow

### Step 1: Clean and filter

- remove exact and near duplicates;
- remove empty, extremely short, promotional, or irrelevant records;
- detect language;
- retain code-mixed English/Hindi records where possible;
- redact direct personal identifiers;
- label competitor-only records separately.

### Step 2: Structured enrichment

Use an LLM with a strict Pydantic response schema to classify each record. The prompt must instruct the model to rely only on the supplied text and avoid demographic inference.

### Step 3: Embedding and semantic grouping

Generate embeddings for cleaned text. Use a clustering method such as HDBSCAN or agglomerative clustering. Do not choose the final theme name directly from cluster keywords alone.

### Step 4: Theme synthesis

For each cluster:

- select representative records;
- identify the common user problem or behaviour;
- generate a concise theme name;
- summarize what users are saying;
- calculate source, sentiment, recency, and category distribution;
- identify contradictory evidence;
- assign a confidence score;
- preserve supporting record IDs.

### Step 5: Insight generation

An insight is not the same as a theme. A valid insight must contain:

- a clear finding;
- the user behaviour or need it explains;
- quantified evidence from the dataset;
- at least three supporting records when available;
- source diversity where possible;
- affected segment or context;
- product implication;
- confidence level;
- validation recommendation.

### Step 6: Question answering through RAG

For a user question:

1. interpret the question into research dimensions and filters;
2. retrieve relevant themes and underlying records;
3. rerank evidence for relevance and source diversity;
4. generate an answer only from retrieved evidence;
5. cite record IDs and source links;
6. state data limitations and conflicting evidence;
7. separate conclusions from hypotheses.

---

## 14. Insight Prioritization

Each theme or opportunity should receive a transparent score rather than a model-generated arbitrary rank.

Recommended components:

- **Frequency:** number and share of relevant records;
- **Severity:** effect described by the user, from minor annoyance to abandonment, loss, or trust failure;
- **Recency:** whether the issue appears in recent records;
- **Source breadth:** number of independent source types in which it appears;
- **Confidence:** classifier and theme coherence confidence;
- **Discovery relevance:** how directly the issue affects exploration, evaluation, or repeat behaviour;
- **Actionability:** whether a product intervention can plausibly address it.

A configurable weighted score can be used for ordering, but the component values must remain visible.

---

## 15. Validation Plan

Quality validation is a first-class part of the product, not a final slide added after analysis.

### A. Gold-sample annotation

Randomly sample at least **200 records** across sources. Manually label the core taxonomy fields. Use this sample to estimate:

- precision and recall for multi-label classifications;
- sentiment accuracy;
- severity agreement;
- rate of unsupported labels;
- percentage of records correctly marked irrelevant.

### B. Inter-reviewer agreement

Where feasible, have two people independently label at least 50 records. Compare agreement and resolve ambiguous taxonomy definitions.

### C. Theme coherence

For each major theme, manually inspect at least 10 representative records and score whether they express the same underlying issue or behaviour.

### D. Evidence-grounding checks

For generated insights, verify:

- every citation actually supports the claim;
- counts match database queries;
- no unsupported demographic claim is made;
- opposing evidence is not omitted;
- the conclusion strength matches the evidence strength.

### E. Stability testing

Run the theme pipeline on different random samples or model runs. Major themes should remain reasonably stable. Highly unstable themes should be marked low confidence.

### F. Retrieval evaluation

Create 15 to 25 test questions. For each question, manually define relevant records or themes and evaluate retrieval precision before judging answer quality.

### G. Human acceptance review

A product reviewer should assess whether each top insight is:

- understandable;
- new or non-obvious;
- supported by evidence;
- relevant to discovery;
- actionable;
- appropriately caveated.

---

## 16. Frontend Product Surface for the MVP

The MVP will use a dedicated **Vite + React frontend**, not Streamlit. It should present the analysis as a polished AI research product with fast navigation, strong evidence visibility, responsive states, and intentional motion.

This document defines the required product surfaces. Exact visual language, typography, colors, spacing, component variants, layout grids, animation timings, responsive behaviour, and reusable design system rules will be specified later in `design.md`.

### 1. Research overview

- total analyzed records;
- records by source and time period;
- ingestion and processing status;
- high-level theme and sentiment distribution;
- top emerging insights;
- warnings about source coverage, evidence limitations, or low-confidence analysis.

### 2. Theme explorer

- ranked themes with frequency, severity, confidence, recency, and source breadth;
- filters by source, date, sentiment, category, journey stage, and exploration barrier;
- expandable representative excerpts;
- direct navigation from a theme to all supporting evidence;
- clear separation between observed theme, synthesized insight, and product hypothesis.

### 3. AI discovery workspace

- preset research-question prompts;
- free-text question input;
- streamed, evidence-grounded answers;
- inline source citations and expandable evidence cards;
- follow-up questions that preserve the active research context;
- visible caveats, contradictory evidence, and confidence indicators.

### 4. Evidence explorer

- fast search and multi-dimensional filtering;
- original text, source metadata, normalized labels, and source links;
- side-panel or detail-page inspection of individual records;
- traceability from record to theme and from theme to generated insight.

### 5. Validation workspace

- gold-sample classification metrics;
- theme-coherence review results;
- unsupported-claim and citation-grounding checks;
- retrieval evaluation results;
- low-confidence themes requiring human review.

### 6. Report builder and export

- select insights and themes for inclusion;
- preview an executive-ready report;
- export Markdown and a PDF-ready format;
- retain evidence references and caveats in exported output.

### Frontend engineering requirements

- consume backend functionality only through documented FastAPI contracts;
- support loading, empty, partial-data, degraded, and error states;
- use animation to clarify state changes, not merely decorate the interface;
- remain usable with motion reduction enabled;
- use reusable typed components rather than one-off page implementations;
- keep charts and visualizations linked to inspectable underlying evidence;
- avoid hiding confidence, methodology, or source limitations behind decorative UI.

---

## 17. Repository Structure

`architecture.md` (section 29) is the authoritative, current repository structure — it reflects the domain-oriented backend layout described in section 8.1 of that document and the `features/`-based frontend layout used throughout `design.md`. This section is intentionally kept high-level to avoid the two documents drifting out of sync.

```text
instamart-discovery-engine/
├── README.md
├── problemstatement.md
├── context.md
├── architecture.md
├── design.md
├── edgecases.md
├── ai_evals.md
├── docker-compose.yml
├── .env.example
├── frontend/        # Vite + React app; see architecture.md §7.2 and design.md §55
├── backend/          # FastAPI + domain modules; see architecture.md §8.1
├── prompts/           # versioned prompt templates; see architecture.md §12
├── data/               # raw, interim, processed, evaluation
├── scripts/             # ingest, analyze, evaluate, seed_demo
└── docs/                 # ADRs, API notes, evaluation reports
```

The frontend and backend should remain independently runnable, while `docker-compose.yml` provides a convenient full-stack development environment.

---

## 18. Implementation Phases

### Phase 1: Foundation and sample ingestion

- initialize the repository;
- define schemas and configuration;
- build Google Play collection;
- add one Reddit or web collection path;
- save raw and normalized records;
- create a reproducible sample dataset.

### Phase 2: Classification and taxonomy

- implement structured LLM classification;
- review 100 to 200 sample outputs;
- refine labels and prompt definitions;
- add confidence and unknown handling.

### Phase 3: Themes and evidence

- generate embeddings;
- cluster records;
- name and summarize themes;
- calculate theme metrics;
- build evidence traceability.

### Phase 4: RAG question answering

- index records and themes;
- implement retrieval and reranking;
- generate cited answers;
- add preset research questions.

### Phase 5: Validation

- create the gold dataset;
- calculate classification metrics;
- test retrieval;
- audit generated insights;
- expose validation results in the UI.

### Phase 6: Full-stack product experience

- build the Vite + React research workspace and connect it to the FastAPI service layer;
- implement core interaction, transition, loading, and evidence-inspection states;
- apply the design system and motion specifications defined in `design.md`;
- add critical frontend and end-to-end tests;
- prepare a stable demo dataset;
- generate the final insight report;
- document setup, limitations, and future extensions.

---

## 19. Definition of Done for the First Demonstrable Version

The MVP is complete when it can:

1. ingest at least two distinct public source types;
2. process at least 1,000 relevant feedback records end to end;
3. deduplicate and normalize the records;
4. classify records into the agreed research taxonomy;
5. identify and rank coherent themes;
6. answer the eight key research questions using retrieved evidence;
7. display supporting excerpts and source references for each answer;
8. distinguish evidence, insight, and hypothesis;
9. show at least one quantitative validation result for classification, retrieval, theme coherence, and grounding;
10. export a decision-ready insight report;
11. run locally from documented setup commands in VS Code;
12. provide a responsive, production-quality Vite + React interface with complete loading, empty, error, and evidence-inspection states.

---

## 20. Assumptions Adopted for Now

To avoid blocking implementation, the following defaults will be used unless changed later:

- The project is a demonstrable MVP, not a production Swiggy deployment.
- Public English and English-Hindi code-mixed content is in scope.
- The primary market is India.
- Competitor discussions may be retained when they reveal quick-commerce expectations, but must be labelled separately.
- Google Play, Reddit, and selected public web pages are sufficient for the MVP.
- Claude is the preferred LLM, but the provider must remain configurable.
- The user-facing MVP will use a dedicated Vite + React frontend; Streamlit is not part of the planned product interface.
- PostgreSQL with pgvector is the preferred persistent store; a local fallback may use SQLite and FAISS for easier demo setup.
- The final insights require human review before being treated as product recommendations.

---

## 21. Decisions That May Need User Input Later

These decisions do not block the initial repository setup, but they should be confirmed before final data collection and presentation:

1. Whether the deliverable is expected to be a working application, a prototype plus analysis, or both.
2. Whether paid services such as Apify and a hosted LLM API may be used, and the approximate budget.
3. Whether Apple App Store and Twitter/X are mandatory sources or optional extensions.
4. Whether the final demo must run fully locally or may depend on hosted services.
5. Whether Hindi and additional Indian languages must be analyzed in the first version.
6. Whether the final output should compare Swiggy Instamart against Blinkit and Zepto or remain brand-specific.
7. Whether the evaluator expects a live dashboard, a recorded walkthrough, a slide deck, a written report, or a combination.

Until clarified, implementation should follow the assumptions in the previous section.

---

## 22. Guidance for Claude Code

When using this file as implementation context, Claude Code should:

- preserve evidence traceability across every pipeline stage;
- avoid adding complex agent frameworks without a clear need;
- use typed schemas and deterministic processing wherever possible;
- write modular collectors so sources can be added or removed independently;
- include retries, logging, rate limiting, checkpointing, and error handling;
- never silently discard failed records;
- write tests alongside each module;
- keep model prompts versioned in the repository;
- make all model names, thresholds, weights, and API credentials configurable;
- ensure generated answers contain citations to stored evidence;
- clearly label low-confidence findings and hypotheses;
- treat the Vite + React frontend as a first-class product surface, not a thin wrapper around API responses;
- use shadcn-style primitives, Framer Motion, and selected 21st.dev patterns consistently rather than mixing unrelated component styles;
- defer detailed visual and motion decisions to `design.md` and keep implementation aligned with that document once it exists;
- update this context document when major architectural or scope decisions change.

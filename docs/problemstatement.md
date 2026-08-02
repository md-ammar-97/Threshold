# Problem Statement: AI-Powered Discovery Engine for Swiggy Instamart

## Objective

Build an AI-powered discovery engine that analyzes user feedback at scale to uncover behavioral patterns, recurring frustrations, unmet needs, and opportunities to improve category and product discovery on **Swiggy Instamart**.

The system should ingest feedback from multiple public sources, identify meaningful themes, generate evidence-backed insights, and help product teams understand why users do or do not explore new categories.

## Suggested AI-Native Stack

You may use any suitable AI-native tools or architecture, including:

- Claude Code
- GPTs
- AI agents
- Automated workflows
- Retrieval-Augmented Generation (RAG) systems
- n8n
- Zapier
- Perplexity
- Any other AI-native stack of your choice

## Data Sources to Analyze

The discovery engine should gather and analyze relevant user feedback from sources such as:

- Apple App Store reviews
- Google Play Store reviews
- Reddit discussions
- Community forums
- Social media conversations
- Product review platforms
- Quick-commerce discussions and industry commentary

## Key Research Questions

The system should help answer questions such as:

1. Why do users repeatedly buy from the same categories?
2. What prevents users from exploring new categories?
3. How do users discover products today?
4. What role do habits play in shopping behavior?
5. What information do users need before trying a new category?
6. Which frustrations emerge repeatedly?
7. Which user segments are more likely to experiment?
8. What unmet needs consistently emerge across discussions?

## Expected Demonstration

The final solution should clearly demonstrate:

1. **Data collection and ingestion**  
   How the workflow gathers feedback from multiple sources and prepares it for analysis.

2. **Theme identification**  
   How recurring topics, complaints, needs, behaviors, and motivations are detected and grouped.

3. **Insight generation**  
   How the system converts raw user feedback into actionable product insights.

4. **Quality validation**  
   How the accuracy, consistency, relevance, and reliability of the generated insights are evaluated.

## Data Source Access and Ingestion Options

| Source | Reality in Mid-2026 | Recommended Approach |
|---|---|---|
| Google Play reviews | Still open and does not require authentication | Use `google-play-scraper` through npm or PyPI |
| Apple App Store reviews | The old RSS feed is no longer reliable and may return empty results; Apple also throttles requests heavily per IP | Use an Apify actor that renders the live App Store page. Test on a small batch before committing. Fallback: use a Playwright headless browser against the rendered page |
| Reddit | The public `.json` API may return 403 errors following access changes introduced in May 2026 | Use an Apify Reddit actor that parses server-rendered HTML. Alternatively, register an official Reddit API application and access Reddit through OAuth using PRAW |
| Twitter/X | The official API v2 is expensive at meaningful volume | Use an Apify Twitter/X scraper sparingly and control collection volume because of cost |
| Forums and product-review sites | Platforms such as MouthShut, Quora, and PissedConsumer-style sites generally do not offer official APIs | Use Apify's generic Website Content Crawler or build a Playwright-based scraper with a proxy service such as Bright Data, ScraperAPI, or ScrapingBee |
| Quick-commerce industry commentary | Sources such as Entrackr, Inc42, YourStory, and Moneycontrol are ordinary public web pages | Use direct HTTP fetching, an RSS reader, or a lightweight web-crawling workflow |

## Desired Outcome

The final discovery engine should provide product teams with a scalable way to:

- Understand customer shopping habits
- Identify barriers to category exploration
- Detect recurring complaints and unmet needs
- Compare patterns across user segments and platforms
- Trace insights back to supporting user evidence
- Prioritize product opportunities based on frequency, severity, confidence, and potential impact

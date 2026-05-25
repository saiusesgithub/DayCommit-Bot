You are generating a realistic personal developer daily log summary.

Your job is to:
- organize the day clearly
- summarize technical progress
- estimate rough category/time allocation
- preserve realism
- avoid hallucinating or inventing context

STRICT RULES:
- Do NOT invent activities, emotions, motivations, or events not explicitly mentioned.
- Do NOT invent work that was not mentioned.
- Do NOT add fake productivity language or corporate-sounding wording.
- Keep the tone natural, grounded, and realistic.
- Use exact project/platform/tool names whenever available.
- Preserve technical names exactly as written.
- Only infer categories/time estimates conservatively from actual logs.
- Mention wasted time honestly but not harshly.
- If time ranges are unclear, estimate carefully.
- Do NOT exaggerate productivity.
- Do NOT generate fake timelines.
- Do NOT generate fake emotions.
- Do NOT generate todo lists.
- Do NOT rewrite or summarize the raw journal.
- Output ONLY valid Markdown.
- Follow the EXACT structure below.

# Required Output Format

## One-Line Summary
One concise natural sentence summarizing the day.

## Detailed Summary
2–5 short paragraphs maximum.

Focus on:
- what was worked on
- technical progress
- debugging/problems
- important decisions
- planning/ideas

Keep wording simple and realistic.

## Time Allocation

| Category | Estimated Time |
|---|---|

Allowed categories:
- Coding
- DSA
- DevOps / Deployment
- Learning / Research
- Open Source / Community
- Planning
- Entertainment / Timepass
- Personal

Only include categories actually present in the diary.

## Category Split

| Focus Area | Notes |
|---|---|

Example:
| DayCommit Bot | Azure deployment + AI provider debugging |
| OpenRouter | Model testing and fallback setup |

Use explicit project/tool/platform names whenever possible.

## Wins
- List meaningful wins from the day.
- Keep them realistic and directly based on the diary.

## Wasted Time / Distractions
- Mention distractions honestly.
- Keep wording neutral and realistic.
- If no clear wasted time is mentioned, write:
  "No major wasted time was clearly mentioned."

## Improvements For Tomorrow
- Give 2–3 practical suggestions.
- Suggestions must be directly connected to the diary.
- Keep them actionable and realistic.

IMPORTANT:
- The raw journal will be appended separately by backend code.
- Do NOT generate or rewrite the raw journal section.
- Your job is ONLY to generate the structured summary sections above.

Now summarize this diary:

{{DIARY_TEXT}}
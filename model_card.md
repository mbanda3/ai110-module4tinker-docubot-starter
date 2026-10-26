# DocuBot Model Card

This model card is a short reflection on your DocuBot system. Fill it out after you have implemented retrieval and experimented with all three modes:

1. Naive LLM over full docs  
2. Retrieval only  
3. RAG (retrieval plus LLM)

Use clear, honest descriptions. It is fine if your system is imperfect.

---

## 1. System Overview

**What is DocuBot trying to do?**  
Describe the overall goal in 2 to 3 sentences.

> _DocuBot is trying to combine both llm logic and force reading logic to act as a retrieval assistant for docs in a designated folder._ 

**What inputs does DocuBot take?**  
For example: user question, docs in folder, environment variables.

> _DocuBot takes a natural human question as input then also reads the text files in the docs folder as input to help with the output produced._ 

**What outputs does DocuBot produce?**

> _DocuBot then outputs either a free-roam generated text through mode 1 without any connection with any inputted text. The second mode utilizes a raw matching section of the text without llm usage. The last version utilizes both the text and the llm to produce an output._

---

## 2. Retrieval Design

**How does your retrieval system work?**  
Describe your choices for indexing and scoring.

- How do you turn documents into an index?
- How do you score relevance for a query?
- How do you choose top snippets?

> _The retrieval system works by reading each file as a whole then utilizing a method to split each document into blank-line delimited paragraphs.  The scoring works by tokenizing both query and text, dropping stopwords from the query, then scoring each section as 100 x the number of distinct query words it contains plus the total occurrences (so covering more of the query beats repeating one word). The snippets are retrieved based on the scores and it will drop zero-scores then sort in descending order._

**What tradeoffs did you make?**  
For example: speed vs precision, simplicity vs accuracy.

> _I chose simplicity over efficiency simply by utilizing a linear scan of every section per queury._

---

## 3. Use of the LLM (Gemini)

**When does DocuBot call the LLM and when does it not?**  
Briefly describe how each mode behaves.

- Naive LLM mode:
- Retrieval only mode:
- RAG mode:

> _DocuBoth calls the llm in both mode 1 and mode 3. The only difference is that in mode 3 we are utilizing both the document text and the llm to provide a much more effective answer hopefully._

**What instructions do you give the LLM to keep it grounded?**  
Summarize the rules from your prompt. For example: only use snippets, say "I do not know" when needed, cite files.

> _I keep the llm grounded by enabling DoucBoth to answer using only the provided snippets and never invent endpoints, functions, or config values. If the answer is unclear then the user simply is provided with an output of "I do not know based on the docs I have." which I believe helps in avoiding inaccuracy in responses._

---

## 4. Experiments and Comparisons

Run the **same set of queries** in all three modes. Fill in the table with short notes.

You can reuse or adapt the queries from `dataset.py`.

| Question | Naive LLM (Mode 1) | Retrieval only (Mode 2) | RAG (Mode 3) | Notes |
|---|---|---|---|---|
| Where is the auth token generated? | Asks for more context, then lists generic places tokens live (`auth.service.js`, `generateToken()`...). Nothing about this repo. | Correct: the `## Token Generation` section ranks first (`generate_access_token` in `auth_utils.py`), followed by two related AUTH.md snippets. | Correct and short: `generate_access_token` in `auth_utils.py`, cites AUTH.md. | RAG is the easiest to trust: same evidence as Mode 2, but as one cited sentence. |
| How do I connect to the database? | Generic "which DB/framework?" plus boilerplate `.env` advice. | "I do not know based on these docs." | "I do not know based on these docs." | Docs do cover this (DATABASE.md, SETUP.md `DATABASE_URL`). Both grounded modes wrongly refuse because the query says "connect" and the docs say "connection". |
| Which endpoint lists all users? | Lists GitHub, Slack, Okta, Auth0 endpoints and `GET /users`. None are this project's. | Correct: `### GET /api/users` ranks first, then `get_all_users()` and an API_REFERENCE intro. | Correct: "`GET /api/users`", cites API_REFERENCE.md. | Mode 1 is fluent but would send a developer to an endpoint that does not exist here. |
| How does a client refresh an access token? | Full OAuth2 `refresh_token` grant walkthrough (`POST /oauth/token`, `client_secret`...). The docs describe `POST /api/refresh` instead. | Returns 3 snippets, none mention `/api/refresh` (Token Generation, validation list, a JSON example). | "I do not know based on the docs I have." | The docs do answer this (AUTH.md line 57, API_REFERENCE.md `POST /api/refresh`). Retrieval missed it, so RAG refused. |
| What is the best pizza topping? (off-topic) | Confidently answers with a "Pizza Topping Selection Guide". | "I do not know based on these docs." | "I do not know based on these docs." | Only the grounded modes refuse. Mode 3's refusal comes from the retrieval guardrail, so the LLM is never called. |

**Evidence each mode uses and when it should refuse**

- Mode 1 (naive): uses no project evidence at all. The prompt ignores `all_text`, so it answers from general training data and never refuses.
- Mode 2 (retrieval only): uses the top 3 paragraph-sized sections, and refuses when the coverage guardrail fails (see section 5).
- Mode 3 (RAG): uses the same top 3 sections, so the guardrail runs first. The LLM then gets only those snippets plus the rule to reply "I do not know" if they are not enough. It should refuse when retrieval is empty or weak, or when the snippets don't actually contain the answer.

Note: Mode 1 and Mode 3 calls sometimes hit Gemini free-tier limits (429 at 5 requests/min, 503 under load). Those were re-run, not counted as answers.

**Example of each behavior requested**

- Naive generation, confident but weakly grounded: "Which endpoint lists all users?" and "How does a client refresh an access token?" Both answers sound authoritative and are wrong for this repo.
- Retrieval only, accurate but hard to read: "Where is the auth token generated?" returns three raw markdown snippets, and the user has to find the one sentence that answers it.
- RAG combining clarity and evidence: "Which endpoint lists all users?" gives one sentence naming `GET /api/users` and citing API_REFERENCE.md.
- RAG still failing: "How does a client refresh an access token?" The docs contain `/api/refresh`, but retrieval ranked other token sections higher, so the LLM only saw irrelevant snippets and correctly refused given what it was shown. The pipeline was wrong, not the LLM.

**What patterns did you notice?**  

- When does naive LLM look impressive but untrustworthy?  
- When is retrieval only clearly better?  
- When is RAG clearly better than both?

> _Naive mode is most impressive but untrustworthy when it substitutes real well-known API conventions. For retrieval only it is clearly better when the answer is one word for word sentence from the text. Then for mode 3 it is better than both when a question needs the retrieved fact turned into a direct cited sentence which depends on the retrieval semi working too._

> _Checkpoint takeaway: Mode 3 was easiest to trust on "Which endpoint lists all users?". Mode 1 named endpoints from other products, and Mode 2 had the right answer but buried it among three snippets. An LLM needs retrieval to stay grounded in project-specific facts. Retrieval alone isn't enough when the user wants a direct answer, and RAG can't fix a retrieval miss: the refresh-token question failed in Mode 3 because the right section never reached the model._

---

## 5. Failure Cases and Guardrails

**Describe at least two concrete failure cases you observed.**  
For each one, say:

- What was the question?  
- What did the system do?  
- What should have happened instead?

> _My question was "How do I connect to the database?" Which both retrieval only and mode 3 answered it does not know based on the docs even though I know it is explicitly stated in DATABASE.md and SETUP.md about the answer to the question. It should have surfaced this content instead of giving an idk response back._

> _I asked "Which endpoint lists all users?" In mode 2 I got the correct response but the gemini call itself returned an unavailable error. This should not have been the case._

**When should DocuBot say “I do not know based on the docs I have”?**  
Give at least two specific situations.

> _DocuBot should refuse when retrieval finds literally no section with any query-word overlap. It should also refuse when the only overlap is trivial or coincidental. Answering anyway risks a confident-sounding guess built on weak evidence._

**What guardrails did you implement?**  
Examples: refusal rules, thresholds, limits on snippets, safe defaults.

> _I implemented guardrails where we must have at least greater than or equal to 50% of sufficient evidence. I also implemented zero-snippet and empty-query short-circuits before every calling the llm._

---

## 6. Limitations and Future Improvements

**Current limitations**  
List at least three limitations of your DocuBot system.

1. _Exact-keyboard scoring has no stemming or synonym awareness, so paraphrased questions can be wrongly refused even when the docs cover the topic_
2. _The function build-index is built but never used and thus retrieval is a full linear scan per query which is inefficient and time costing_
3. _The heading-merge chunking heuristic assumes markdown-style # headings; it could misfire on non-markdown docs or unconventional formatting_

**Future improvements**  
List two or three changes that would most improve reliability or usefulness.

1. _Add lightweight normalization to close gaps like "connect" vs "connection"_
2. _Add retry/backoff in GeminiClient for transient 429 errors_
3. _Either wire self.index into retrieve() as a real candidate pre-fileter, or remove it. Currently it is unsused_

---

## 7. Responsible Use

**Where could this system cause real world harm if used carelessly?**  
Think about wrong answers, missing information, or over trusting the LLM.

> _The mode 1 has fluent-but-wrong answers which could lead a developer to implement against an endpoint that does not exist. False idk responses could make a developer wrongly conclude a topic is not documented at all when in reality it is._

**What instructions would you give real developers who want to use DocuBot safely?**  
Write 2 to 4 short bullet points.

- _Use retrieval-only or RAG for project-specific questions. Naive mode will ignore your docs entirely and answer based on general knowledge._
- _Treat a refusal as "try the exact terms used in the docs," not as proof that the topic is undocumented._
- _Do not treat DocuBot as authoritative beyond what is literally written inside the docs folder. It has no knowledge of the actual running code._

---

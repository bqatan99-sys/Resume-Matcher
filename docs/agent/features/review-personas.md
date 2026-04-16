# Review Personas

> Lightweight review lenses for resume tailoring work in Resume Matcher.

These are not runtime product roles or extra live LLM calls by default. They are a shared review framework for shaping better prompts, better UI, and more credible resume outputs.

## Review Order

Use the personas in this order when evaluating a change:

1. `Transferability Coach`
2. `UX/UI Reviewer`
3. `Hiring Manager`
4. `Recruiter Verifier`

## 1. Transferability Coach

**Purpose:** Help a candidate coming from another role or industry understand how to frame real experience as transferable skills without inventing anything.

**What it checks**

- Whether bullets are grounded in evidence from the master resume
- Whether the language highlights transferable skills instead of fake seniority
- Whether role changes are framed as adjacent growth, not exaggerated career identity shifts
- Whether the resume makes it easy to answer "why this person for this role?"

**What it must not do**

- Invent tools, titles, certifications, or metrics
- Rewrite the resume into a different profession
- Add keywords that are not supported by the source content

**Useful output**

- `supported`
- `risky`
- `unsupported`
- Suggested rewrite that keeps the claim truthful

## 2. UX/UI Reviewer

**Purpose:** Make the editing and preview flow feel obvious, calm, and easy to trust.

**What it checks**

- Whether the user can tell what is editable versus what is preview-only
- Whether template-backed preview/download states are unambiguous
- Whether links, badges, and error messages explain the state clearly
- Whether the resume output looks intentional on desktop and mobile

**What it must not do**

- Add visual noise just to expose features
- Hide important state behind vague labels
- Turn the interface into a settings dump

**Useful output**

- Friction points
- Confusing labels
- Missing affordances
- Layout or spacing issues that reduce trust

## 3. Hiring Manager

**Purpose:** Judge whether the resume reads like a credible, focused candidate for the role.

**What it checks**

- Whether the story is coherent and role-relevant
- Whether the strongest evidence is easy to spot quickly
- Whether bullets show ownership, scope, and outcomes
- Whether the resume feels like a person with judgment, not a keyword dump

**What it must not do**

- Reward padded buzzwords
- Overvalue decoration over substance
- Confuse polish with fit

**Useful output**

- Shortlist / no-shortlist verdict
- Most persuasive sections
- Missing evidence for the target role

## 4. Recruiter Verifier

**Purpose:** Final pass for ATS readability, shortlist confidence, and factual consistency.

**What it checks**

- Chronology, dates, and section order
- Readability in a fast scan
- Contact info and hyperlinks at the top
- Bullet punctuation, spacing, and formatting consistency
- Keyword alignment without stuffing
- Hallucination risk or awkward phrasing

**What it must not do**

- Approve outputs that look polished but break truthfulness
- Ignore formatting issues that could hurt screening
- Treat a high keyword score as proof of quality

**Useful output**

- `keep`
- `revise`
- `reject`
- Specific reasons tied to recruiter screening behavior

## Recommended Use

When a resume or tailoring change is being evaluated:

1. Run the `Transferability Coach` lens first to keep the content honest.
2. Run the `UX/UI Reviewer` lens to make sure the workflow is understandable.
3. Run the `Hiring Manager` lens to test relevance and credibility.
4. Run the `Recruiter Verifier` lens last to catch ATS and shortlist issues.

## Practical Rule

If a suggestion would make the candidate look better but would also make the story less truthful, the suggestion should be rejected.

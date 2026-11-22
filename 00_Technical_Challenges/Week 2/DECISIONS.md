# Decisions

One row, one decision. Week 1 was retrieval; this week is the agent and its boundary. By
Week 5 this file explains the decisions you made across the whole bootcamp.

## Agentic search, week 2

**What I changed**

> Real similarity scores (similarity_search_with_score).

**Why**

> For Confidence Filtering (Hallucination Prevention) so the weak matches are discardes based on a certain threshold before passing to LLM.

**What would change my mind**

> When granular visibility is not needed on how well each result actually matched the query. Or a lose requirement of not needing strong matching.

---

## Structured I/O: dataclass vs. Pydantic (answer this one too)

**The call:** the API contract in `schemas.py` is Pydantic, not a `@dataclass` like Week 1's `Hit`.

> In one or two lines: what does Pydantic give a FastAPI app that a dataclass does not, and
> where (if anywhere) would a plain dataclass still have been the right tool here?<br>
> ANSWER: Pydantic enforces types at runtime and has built in validation on data

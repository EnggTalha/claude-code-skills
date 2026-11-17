---
name: rag-pipeline-review
description: Review a retrieval-augmented generation (RAG) pipeline end to end, covering ingestion, chunking, embeddings, vector store, retrieval, reranking, prompt and evaluation, and return prioritised fixes with code. Use when the user's RAG bot gives wrong or hallucinated answers, misses documents it should find, is slow or expensive, or when they ask for a review of LangChain, LlamaIndex, Pinecone, Chroma, FAISS or MongoDB Atlas vector search code.
metadata:
  category: ai-llm
  added: "2026-11-18"
---

# RAG pipeline review

Most RAG quality problems come from retrieval, not from the LLM. This skill walks the pipeline in data-flow order, finds the weakest stage, and backs every recommendation with a quick experiment the user can run.

## When to use

- "My chatbot answers wrong / says it doesn't know / makes things up"
- "Retrieval misses obvious documents", "answers mix up two clients' data"
- Reviewing a new RAG codebase before production
- **Not for:** fine-tuning decisions or general prompt writing without retrieval

## Steps

1. **Map the pipeline.** Find each stage in the code and record its settings in a table:
   | Stage | Look for | Record |
   |---|---|---|
   | Loading | PDF/HTML loaders, OCR | text quality, tables lost? |
   | Chunking | `RecursiveCharacterTextSplitter`, `chunk_size`, `chunk_overlap` | size (tokens), overlap, splits on headings? |
   | Metadata | `metadata=` on documents | source, page, tenant/client id, date |
   | Embeddings | model name, dimension | same model at index and query time? |
   | Store | Pinecone/Chroma/FAISS/Atlas index | metric (cosine/dot), namespace per tenant |
   | Retrieval | `k`, `search_type`, filters, hybrid/BM25 | k, MMR, metadata filters |
   | Rerank | Cohere/cross-encoder | present? top-n |
   | Prompt | system prompt, context formatting | citations? "say I don't know" rule? |
   | Eval | test set, metrics | exists? |

2. **Check for the usual faults, in priority order:**
   1. **Embedding mismatch**: a different model or dimension at index and query time, or the model changed without re-indexing.
   2. **Bad text in**: scanned PDFs without OCR, headers and footers repeated on every chunk, tables flattened into nonsense. Print 3 random chunks and read them.
   3. **Chunking**: chunks above 1,000 tokens dilute the match, and chunks below 100 lose context. Start at 300–600 tokens with 10–15% overlap, splitting on headings for docs.
   4. **No metadata filtering**: multi-tenant data in one namespace with no `filter={"client_id": ...}`. This is how answers leak between clients.
   5. **k too small or too large**: k=2 misses facts, while k=20 floods the prompt. Retrieve 20, rerank, then keep 4–6.
   6. **Keyword-heavy queries** (IDs, product codes, Urdu/Arabic names): add hybrid BM25 + vector.
   7. **Prompt**: there's no instruction to answer only from the context and say "I don't know" otherwise, and no source citations.

3. **Run a quick retrieval probe.** Write 10–20 question → expected-source pairs from the user's own docs and measure hit rate before touching the LLM:
   ```python
   hits = 0
   for q, expected_source in TESTS:
       docs = retriever.invoke(q)
       hits += any(expected_source in d.metadata.get("source", "") for d in docs)
   print(f"hit@k = {hits}/{len(TESTS)}")
   ```
   If hit@k is under 80%, fix retrieval first. If it's high but answers are still bad, fix the prompt or the model.

4. **Recommend fixes** as a numbered list. Give each one its *evidence*, the *change* (code diff) and the *expected effect*. Limit to the top 5.

5. **Add an eval harness** if none exists: save the probe set as `evals/rag_cases.jsonl` and a script that prints hit@k plus answer faithfulness, so future changes can be measured.

## Examples

### Example 1: LangChain + Pinecone voice-bot knowledge base

Findings: `chunk_size=4000` characters, k=2, no reranker, and the PDFs had repeated headers. The probe gives hit@2 = 9/20. Fixes: chunk at 500 tokens on headings and strip headers, retrieve k=15 and rerank down to 5. The probe then gives 18/20.

### Example 2: two clients' data mixed

There's one Chroma collection with no `client_id` metadata. Fix: add `client_id` during ingestion, filter on it in the retriever, and add a test that client A's question never returns client B's sources.

## Pitfalls

- Don't recommend switching LLMs before measuring retrieval hit rate.
- Changing the embedding model means **re-indexing everything**. Say so.
- Don't judge chunking without printing real chunks.
- Keep eval questions out of the few-shot prompt, or the scores are meaningless.
- Never log full user documents or PII while debugging. Log ids and sources instead.

## Verification

- The pipeline table is filled in from the actual code, not from assumptions.
- Retrieval hit@k is measured before and after the changes, and both numbers are reported.
- Each recommended change maps to a specific file or line, with a diff.

# Repository-Aware AI Bug Localizer — Research Platform

> **Research Question:** Can repository-aware LLMs improve software bug localization compared with LLM-only and conventional techniques (keyword search, structural analysis)?

---

## What This Does

Given a GitHub repository URL and a natural-language bug report, the system:

1. Clones the repository and parses all source code (AST / tree-sitter)
2. Builds a dependency/call graph
3. Runs **four independent localization approaches** on the same input
4. Generates a root-cause explanation and a proposed fix
5. Optionally verifies the fix in a Docker sandbox
6. Computes research metrics (Top-1/3/5 accuracy, MRR, hallucination rate)

---

## Four Localization Approaches

| # | Approach | Method | LLM? | Retrieval? |
|---|---|---|---|---|
| A | **Keyword Search** | TF-IDF scoring on function names, files, source | No | No |
| B | **Structural Analysis** | Call-graph BFS from keyword-seeded functions | No | No |
| C | **LLM Only** | LLM reasons over a static source code sample | Yes | No |
| D | **RAG + LLM** | Issue embedded → FAISS retrieval → LLM with evidence | Yes | Yes (FAISS) |

The primary research comparison is **C vs D** — does retrieval-augmented context improve localization over direct LLM reasoning?

---

## Architecture

```
EshnaAiDevOps/
├── backend/                  FastAPI + Python 3.12
│   ├── api/                  REST endpoints + SSE streaming
│   ├── core/                 Repository ingestion, AST parsing, call graph
│   ├── localization/         Four approaches + file classifier + embeddings
│   ├── explanation/          Root-cause explanation (LLM)
│   ├── fix/                  Minimal fix generation (LLM)
│   ├── verification/         Docker sandbox testing
│   ├── evaluation/           Metrics engine + experiment runner
│   └── storage/              SQLite (analyses + experiments)
├── frontend/                 React 18 + Vite + Tailwind CSS
│   └── src/
│       ├── pages/            BugAnalysis, Evaluation
│       └── components/       Dashboard, ApproachComparison, LLMvsRAG, RAGEvidence...
└── shopbug/                  ShopBug benchmark (20 intentional bugs)
    └── BUG_DATASET.md        Ground-truth metadata
```

---

## Running the Project

### Prerequisites
- Python 3.12
- Node.js 18+
- [Ollama](https://ollama.ai) with `codellama:7b` pulled (`ollama pull codellama:7b`)

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
# Configure LLM in backend/.env (copy from .env.example)
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### Quick Check

```bash
curl http://localhost:8000/api/health
# {"status":"ok","llm_provider":"ollama","embedding_model":"nomic-embed-text"}
```

---

## Configuration (`backend/.env`)

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `openai` / `anthropic` / `ollama` |
| `LLM_MODEL` | `codellama:7b` | Model name |
| `LLM_API_KEY` | `ollama` | API key (empty for local Ollama) |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Falls back to `all-MiniLM-L6-v2` if not pulled |
| `RAG_TOP_K` | `5` | Retrieval top-K |
| `ENABLE_DOCKER_VERIFICATION` | `false` | Set `true` if Docker is available |

---

## Dashboard Sections

After clicking **Analyze Bug**:

1. **Issue + Repository** — input summary and pipeline diagram
2. **Repository Stats** — source files, functions, indexed chunks (real values)
3. **Approach Comparison** — 4 cards showing each approach's status, predictions, latency
4. **LLM Only vs RAG+LLM** — side-by-side pipeline with live step states
5. **LLM vs RAG Comparison** — all measurable metrics in one table (N/A shown honestly)
6. **RAG Evidence** — retrieved chunks with similarity scores and code previews
7. **Top-5 Ranking** — final ranked candidates (source files only, never test files)
8. **Root Cause** — explanation with dependency chain and supporting evidence
9. **Fix Proposal** — current vs proposed code, diff, safety notes
10. **Verification** — test results before/after fix (requires Docker)

---

## Evaluation Page

The **Evaluation** page (`/evaluation`) provides:

- Research question and experimental setup
- ShopBug benchmark summary (5 bugs used for quick eval, extendable to 20)
- Metric definitions (Top-1/3/5, MRR, hallucination rate, latency, tokens)
- **RUN FULL EXPERIMENT** — executes all approaches over the dataset and computes real metrics
- Results table showing Top-1/3/5 accuracy and MRR per approach
- Category / difficulty / issue-quality breakdown (populates after experiment run)

---

## ShopBug Benchmark

ShopBug is a controlled research benchmark with intentional bugs in a FastAPI e-commerce application.

- **Repository:** https://github.com/Eshna09/ShopBug
- **Dataset:** `backend/shopbug_dataset.json` (ground-truth JSON, never shown to localization models)
- **Ground truth separation:** Localization predictions are recorded before the evaluation module accesses ground truth

Bug categories: Calculation, Authentication, Cart/Checkout, Discount Logic, Product Service, Order Service, Database, Multi-file.

---

## Research Integrity

- Ground truth is **never** exposed to any localization model during prediction
- The same repository and same issue are submitted independently to all four approaches
- Hallucination rate = rejected predictions ÷ total LLM predictions (validated against real repo index)
- All displayed metrics come from actual execution — nothing is fabricated
- Test files are never ranked as primary root cause (demoted to supporting evidence)

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/repositories/analyze` | Full synchronous analysis |
| `POST` | `/api/repositories/analyze/stream` | SSE streaming analysis |
| `GET` | `/api/analysis/{id}` | Retrieve saved analysis |
| `GET` | `/api/history` | List recent analyses |
| `POST` | `/api/experiments/run` | Run full evaluation experiment |
| `GET` | `/api/evaluation/summary` | Evaluation summaries |

---

## Tech Stack

**Backend:** FastAPI 0.115 · Python 3.12 · SQLite · FAISS · sentence-transformers · tree-sitter · GitPython · psutil · Ollama / OpenAI / Anthropic

**Frontend:** React 18 · Vite 5 · TypeScript · Tailwind CSS · Lucide icons · Recharts · Axios

**LLM (local):** codellama:7b via Ollama (also supports gpt-4o, claude-3-5-sonnet)

**Embedding:** all-MiniLM-L6-v2 (sentence-transformers fallback) or nomic-embed-text (Ollama)

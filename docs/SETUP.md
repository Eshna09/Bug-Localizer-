# Setup Guide

## Prerequisites

- Python 3.11+
- Node.js 18+
- Git
- Docker (optional, for fix verification)
- An OpenAI or Anthropic API key

---

## 1. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env — set LLM_API_KEY, LLM_MODEL, etc.
```

### Required .env values

```env
LLM_PROVIDER=openai           # openai | anthropic | ollama
LLM_MODEL=gpt-4o              # model name for your provider
LLM_API_KEY=sk-...            # your API key

EMBEDDING_MODEL=all-MiniLM-L6-v2   # sentence-transformers model
RAG_TOP_K=5                         # top-K chunks for RAG retrieval

DATABASE_URL=sqlite:///./buglocalizer.db
WORKSPACE_DIR=./workspaces

ENABLE_DOCKER_VERIFICATION=true     # set false if Docker not available
```

### Start backend

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API available at: http://localhost:8000
Swagger docs:     http://localhost:8000/docs

---

## 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend available at: http://localhost:5173

---

## 3. Connect to ShopBug

In the Bug Analysis page, enter:

```
Repository URL:  https://github.com/your-username/shopbug
Issue:           When I apply a 20% discount to a ₹1000 order,
                 the final checkout amount is incorrect.
```

The system will:
1. Clone the repository
2. Parse all Python source files
3. Run keyword search, structural analysis, LLM-only, and RAG+LLM localization
4. Identify the most likely bug location
5. Generate a bug explanation
6. Propose a minimal fix
7. Verify the fix in Docker (if enabled)
8. Display the complete dashboard

---

## 4. Run a Research Experiment

Prepare a bug dataset JSON:

```json
[
  {
    "bug_id": "B001",
    "repo_url": "https://github.com/your-username/shopbug",
    "issue_description": "When I apply a 20% discount to a ₹1000 order, the final checkout amount is incorrect.",
    "ground_truth_file": "app/services/discount_service.py",
    "ground_truth_function": "calculate_discount",
    "category": "calculation",
    "difficulty": "easy",
    "issue_quality": "specific"
  }
]
```

Then run:

```bash
curl -X POST http://localhost:8000/api/experiments/run \
  -H "Content-Type: application/json" \
  -d '{
    "bug_dataset_path": "/path/to/dataset.json",
    "repo_url": "https://github.com/your-username/shopbug",
    "approaches": ["keyword", "structural", "llm_only", "rag_llm"],
    "top_k": 5
  }'
```

---

## 5. Direct API Usage

```bash
# Health check
curl http://localhost:8000/api/health

# Analyze a repository
curl -X POST http://localhost:8000/api/repositories/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/your-username/shopbug",
    "issue_description": "Discount calculation is wrong",
    "run_verification": false
  }'

# Get analysis by ID
curl http://localhost:8000/api/analysis/{analysis_id}

# List history
curl http://localhost:8000/api/history
```

---

## Security Notes

- Repository code is **never executed on the host** during localization
- Fix verification runs inside an isolated Docker container with:
  - No network access (`--network none`)
  - Memory limit (512MB)
  - CPU limit (1 core)
  - Temporary filesystem
- Only HTTPS GitHub URLs are accepted
- Ground truth files are excluded from localization input

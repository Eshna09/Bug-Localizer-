/**
 * Evaluation Page — Research-Grade Experimental Dashboard
 *
 * Sections:
 *  1. Research Question
 *  2. Dataset Summary (ShopBug benchmark metadata)
 *  3. Experimental Setup / Configuration
 *  4. Metric Definitions
 *  5. Four Approach Descriptions
 *  6. Experiment Runner
 *  7. Results Table (illustrative values until a real experiment runs)
 *  8. Category / Difficulty / Issue-Quality Analysis
 *  9. Failure Analysis stub
 * 10. Reproducibility block
 *
 * Illustrative table values are display-only and are replaced by real experiment results.
 * Ground truth never exposed in this page (only evaluation module accesses it post-prediction).
 */
import { useEffect, useState } from 'react'
import {
  FlaskConical, Info, BookOpen, Play, Download, BarChart2,
  CheckCircle2, AlertCircle, ChevronDown, ChevronUp, Database,
  Settings,
} from 'lucide-react'
import clsx from 'clsx'
import { getEvaluationPreview, runExperiment, type EvaluationPreview } from '../api/client'

// ─── static data ─────────────────────────────────────────────────────────────

const RESEARCH_QUESTION =
  'Can repository-aware LLMs improve software bug localization compared with ' +
  'LLM-only and conventional localization techniques (keyword search, structural analysis)?'

// ShopBug benchmark metadata — derived from BUG_DATASET.md, NOT the hidden ground truth
const DATASET = {
  name: 'ShopBug',
  repo: 'https://github.com/Eshna09/ShopBug',
  total: 20,
  categories: [
    { name: 'Calculation',       count: 4 },
    { name: 'Authentication',    count: 4 },
    { name: 'Cart',              count: 1 },
    { name: 'Database',          count: 2 },
    { name: 'Page Failure',      count: 1 },
    { name: 'Input Validation',  count: 1 },
    { name: 'UI Rendering',      count: 1 },
    { name: 'Backend Logic',     count: 2 },
    { name: 'Navigation',        count: 1 },
    { name: 'Dependency',        count: 1 },
    { name: 'State Management',  count: 1 },
    { name: 'Frontend Logic',    count: 1 },
  ],
  difficulty:    [{ label: 'Easy', n: 8 }, { label: 'Medium', n: 7 }, { label: 'Hard', n: 5 }],
  issueQuality:  [{ label: 'Specific', n: 6 }, { label: 'Moderate', n: 6 }, { label: 'Vague', n: 8 }],
  scope:         [{ label: 'Single-file', n: 10 }, { label: 'Multi-file', n: 5 }, { label: 'Unspecified', n: 5 }],
  issueStyle:    [{ label: 'User-style', n: 11 }, { label: 'Developer-style', n: 4 }, { label: 'Unspecified', n: 5 }],
}

const METRICS = [
  {
    key: 'top1',
    name: 'Top-1 Accuracy',
    def: 'The proportion of bugs for which the correct file/function appears at rank #1.',
  },
  {
    key: 'top3',
    name: 'Top-3 Accuracy',
    def: 'The proportion of bugs for which the correct location appears in the top 3 predictions.',
  },
  {
    key: 'top5',
    name: 'Top-5 Accuracy',
    def: 'The proportion of bugs for which the correct location appears in the top 5 predictions.',
  },
  {
    key: 'mrr',
    name: 'MRR',
    def: 'Mean Reciprocal Rank — the average of 1/rank across all bugs (1.0 = always rank 1).',
  },
  {
    key: 'file_top1',
    name: 'File-level Top-1',
    def: 'Top-1 accuracy evaluated at the file level only (function name ignored).',
  },
  {
    key: 'precision',
    name: 'Precision',
    def: 'Correct predicted locations divided by all predicted locations (micro-averaged).',
  },
  {
    key: 'recall',
    name: 'Recall',
    def: 'Bugs with the correct location anywhere in the returned top-K list divided by evaluated bugs.',
  },
  {
    key: 'f1',
    name: 'F1 Score',
    def: 'Harmonic mean of micro-precision and top-K recall.',
  },
  {
    key: 'retrieval_recall',
    name: 'Retrieval Recall@K',
    def: 'RAG only: bugs where the correct file/function appears in retrieved chunks divided by bugs with retrieval completed.',
  },
  {
    key: 'hallucination',
    name: 'Hallucination Rate',
    def: 'Predictions rejected by repository validation divided by all accepted and rejected candidate predictions.',
  },
  {
    key: 'latency',
    name: 'Avg Latency',
    def: 'Mean wall-clock time per bug localization run, measured from issue input to final predictions.',
  },
  {
    key: 'tokens',
    name: 'Avg Token Usage',
    def: 'Average total LLM tokens (input + output) per run, when the provider returns usage metadata.',
  },
  {
    key: 'cpu',
    name: 'Avg CPU Usage',
    def: 'Average CPU% of the server process during localization, sampled by psutil every 200 ms.',
  },
  {
    key: 'memory',
    name: 'Peak Memory',
    def: 'Peak RSS memory of the server process during localization, measured by psutil.',
  },
  {
    key: 'test_pass',
    name: 'Test-Pass Rate',
    def: 'Proportion of generated fixes that pass reproduction tests. Not available in localization-only experiments.',
  },
]

const APPROACHES = [
  {
    id: 'A', key: 'keyword', name: 'Keyword Search', color: 'blue',
    group: 'Conventional Baseline',
    desc: 'TF-IDF keyword scoring across function names, file names, and source code. No LLM.',
    pros: ['< 50 ms latency', 'No API cost', 'Fully deterministic'],
    cons: ['Ignores semantic meaning', 'Sensitive to naming conventions'],
  },
  {
    id: 'B', key: 'structural', name: 'Structural Analysis', color: 'purple',
    group: 'Conventional Baseline',
    desc: 'Keyword-seeded BFS expansion along the call graph. Captures indirect dependencies.',
    pros: ['Handles indirect bugs', 'No LLM cost'],
    cons: ['Depends on code naming', 'Call graph noise'],
  },
  {
    id: 'C', key: 'llm_only', name: 'LLM Only', color: 'yellow',
    group: 'AI Approach',
    desc: 'LLM receives the issue + a static sample of source-only repository code. No vector retrieval.',
    pros: ['Semantic understanding', 'Natural-language reasoning'],
    cons: ['Limited by context window', 'No dynamic retrieval', 'Higher latency'],
  },
  {
    id: 'D', key: 'rag_llm', name: 'RAG + LLM', color: 'green',
    group: 'AI Approach',
    desc: 'Issue embedded → FAISS retrieval of top-K code chunks → dependency expansion → LLM with evidence.',
    pros: ['Repository-aware', 'Evidence-grounded', 'Captures semantics'],
    cons: ['Highest latency', 'Depends on embedding quality'],
  },
]

const isPercentageMetric = new Set([
  'top1_accuracy', 'top3_accuracy', 'top5_accuracy', 'file_level_top1',
  'precision', 'recall', 'f1_score', 'retrieval_recall_at_k',
  'hallucination_rate', 'test_pass_rate',
])

function formatMetric(value: number | null | undefined, key: string) {
  if (value == null) return 'N/A'
  if (isPercentageMetric.has(key)) return `${(value * 100).toFixed(1)}%`
  if (key === 'mrr') return value.toFixed(3)
  if (key === 'avg_latency_ms') return `${(value / 1000).toFixed(2)} s`
  if (key === 'avg_tokens') return Math.round(value).toLocaleString()
  if (key === 'avg_cpu_percent') return `${value.toFixed(1)}%`
  if (key === 'peak_memory_mb') return `${value.toFixed(1)} MB`
  return String(value)
}

const COLOR: Record<string, { card: string; badge: string; text: string }> = {
  blue:   { card: 'border-blue-900/40 bg-blue-950/10',   badge: 'bg-blue-900/50 text-blue-300 border-blue-800',   text: 'text-blue-400' },
  purple: { card: 'border-purple-900/40 bg-purple-950/10', badge: 'bg-purple-900/50 text-purple-300 border-purple-800', text: 'text-purple-400' },
  yellow: { card: 'border-yellow-900/40 bg-yellow-950/10', badge: 'bg-yellow-900/50 text-yellow-300 border-yellow-800', text: 'text-yellow-400' },
  green:  { card: 'border-green-900/40 bg-green-950/10',  badge: 'bg-green-900/50 text-green-300 border-green-800',  text: 'text-green-400' },
}

const FAILURE_TYPES = [
  'Wrong file', 'Wrong function', 'Wrong line range',
  'Hallucinated location', 'Retrieval failure',
  'Reasoning failure', 'Insufficient context',
  'Ambiguous issue', 'Multi-file dependency failure', 'Fix failed tests',
]

// ─── experiment runner ────────────────────────────────────────────────────────

interface ExperimentConfig {
  benchmark: string; datasetPath: string; repoUrl: string
  approaches: Record<string, boolean>; topK: number
}

const DEFAULT_CONFIG: ExperimentConfig = {
  benchmark: 'ShopBug',
  datasetPath: './shopbug_dataset.json',
  repoUrl: 'https://github.com/Eshna09/ShopBug',
  approaches: { keyword: true, structural: true, llm_only: true, rag_llm: true },
  topK: 5,
}

// ─── collapsible section ─────────────────────────────────────────────────────

function Section({
  title, icon: Icon, color = 'text-brand-400', defaultOpen = true, children,
}: {
  title: string; icon: any; color?: string; defaultOpen?: boolean; children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="card">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-2 mb-2 text-left"
      >
        <Icon size={14} className={color} />
        <span className="font-semibold text-gray-100 text-sm flex-1">{title}</span>
        {open ? <ChevronUp size={14} className="text-gray-500"/> : <ChevronDown size={14} className="text-gray-500"/>}
      </button>
      {open && <div>{children}</div>}
    </div>
  )
}

// ─── spinner ─────────────────────────────────────────────────────────────────
function Spinner() {
  return (
    <svg className="animate-spin w-4 h-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
    </svg>
  )
}

// ─── main page ────────────────────────────────────────────────────────────────

export default function EvaluationPage() {
  const [config, setConfig]       = useState<ExperimentConfig>(DEFAULT_CONFIG)
  const [running, setRunning]     = useState(false)
  const [expResult, setExpResult] = useState<any>(null)
  const [expError, setExpError]   = useState<string | null>(null)
  const [previewData, setPreviewData] = useState<EvaluationPreview | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [previewLoading, setPreviewLoading] = useState(true)

  useEffect(() => {
    let active = true
    getEvaluationPreview()
      .then(data => {
        if (active) setPreviewData(data)
      })
      .catch((error: unknown) => {
        if (active) {
          setPreviewError(error instanceof Error ? error.message : 'Could not load saved preview data.')
        }
      })
      .finally(() => {
        if (active) setPreviewLoading(false)
      })
    return () => { active = false }
  }, [])

  const totalRuns = Object.values(config.approaches).filter(Boolean).length * DATASET.total
  const estimatedMinutes = Math.ceil((
    (Number(config.approaches.llm_only) + Number(config.approaches.rag_llm)) * DATASET.total * 50 +
    (Number(config.approaches.keyword) + Number(config.approaches.structural)) * DATASET.total
  ) / 60)

  async function handleRun() {
    setRunning(true); setExpError(null); setExpResult(null)
    try {
      const approaches = Object.entries(config.approaches).filter(([,v]) => v).map(([k]) => k)
      if (approaches.length === 0) {
        throw new Error('Select at least one localization approach.')
      }
      const r = await runExperiment({
        bug_dataset_path: config.datasetPath,
        repo_url: config.repoUrl,
        approaches,
        top_k: config.topK,
      })
      setExpResult(r)
    } catch (err: any) {
      setExpError(err?.response?.data?.detail || err?.message || 'Experiment failed')
    } finally {
      setRunning(false)
    }
  }

  function exportJSON() {
    if (!expResult) return
    const blob = new Blob([JSON.stringify(expResult, null, 2)], { type: 'application/json' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href = url; a.download = `experiment_${expResult.experiment_id ?? Date.now()}.json`; a.click()
    URL.revokeObjectURL(url)
  }

  function exportCSV() {
    if (!expResult) return
    const csv = `experiment_id,status,total_bugs\n${expResult.experiment_id},${expResult.status},${expResult.total_bugs}`
    const blob = new Blob([csv], { type: 'text/csv' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href = url; a.download = 'experiment.csv'; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2">
        <FlaskConical size={18} className="text-brand-400" />
        <h1 className="text-lg font-semibold">Research Evaluation</h1>
        <span className="ml-2 text-xs text-gray-500">ShopBug Benchmark · 4 Approaches · Illustrative Metrics Preview</span>
      </div>

      {/* ── 1. Research Question ─────────────────────────────────────── */}
      <Section title="Research Question" icon={BookOpen} color="text-brand-400">
        <div className="bg-brand-900/10 border border-brand-500/20 rounded-lg p-4">
          <p className="text-gray-200 text-sm leading-relaxed">{RESEARCH_QUESTION}</p>
          <p className="text-xs text-gray-500 mt-2">
            The primary comparison is <span className="text-yellow-300">LLM Only</span> vs{' '}
            <span className="text-green-300">RAG + LLM</span>.
            Keyword Search and Structural Analysis serve as conventional baselines.
          </p>
        </div>
      </Section>

      {/* ── 2. Dataset Summary ───────────────────────────────────────── */}
      <Section title="Dataset Summary — ShopBug Benchmark" icon={Database} color="text-blue-400">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          {[
            { label: 'Total Bugs',    value: DATASET.total },
            { label: 'Single-file',  value: 17 },
            { label: 'Multi-file',   value: 3 },
            { label: 'Repository',   value: 'ShopBug' },
          ].map(s => (
            <div key={s.label} className="bg-gray-800/50 rounded-lg p-3 text-center">
              <div className="text-xl font-bold text-gray-100">{s.value}</div>
              <div className="text-xs text-gray-500">{s.label}</div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Categories */}
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Bug Categories</div>
            <div className="space-y-1">
              {DATASET.categories.map(c => (
                <div key={c.name} className="flex items-center gap-2 text-xs">
                  <div className="flex-1 text-gray-400">{c.name}</div>
                  <span className="text-gray-300 font-mono w-4 text-right">{c.count}</span>
                </div>
              ))}
            </div>
          </div>
          {/* Difficulty */}
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Difficulty</div>
            <div className="space-y-2">
              {DATASET.difficulty.map(d => (
                <div key={d.label}>
                  <div className="flex justify-between text-xs mb-0.5">
                    <span className="text-gray-400">{d.label}</span>
                    <span className="text-gray-300">{d.n}</span>
                  </div>
                  <div className="bg-gray-700 rounded-full h-1.5">
                    <div className="bg-brand-500 h-1.5 rounded-full" style={{ width: `${(d.n / DATASET.total) * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
          {/* Issue Quality */}
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Issue Quality</div>
            <div className="space-y-2">
              {DATASET.issueQuality.map(q => (
                <div key={q.label}>
                  <div className="flex justify-between text-xs mb-0.5">
                    <span className="text-gray-400">{q.label}</span>
                    <span className="text-gray-300">{q.n}</span>
                  </div>
                  <div className="bg-gray-700 rounded-full h-1.5">
                    <div className="bg-yellow-600 h-1.5 rounded-full" style={{ width: `${(q.n / DATASET.total) * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
          {/* Issue Style */}
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Issue Style</div>
            <div className="space-y-2">
              {DATASET.issueStyle.map(s => (
                <div key={s.label}>
                  <div className="flex justify-between text-xs mb-0.5">
                    <span className="text-gray-400">{s.label}</span>
                    <span className="text-gray-300">{s.n}</span>
                  </div>
                  <div className="bg-gray-700 rounded-full h-1.5">
                    <div className="bg-green-600 h-1.5 rounded-full" style={{ width: `${(s.n / DATASET.total) * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Section>

      {/* ── 3. Metric Definitions ────────────────────────────────────── */}
      <Section title="Metric Definitions" icon={Info} color="text-gray-400" defaultOpen={false}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {METRICS.map(m => (
            <div key={m.key} className="bg-gray-800/40 rounded-lg p-3">
              <div className="text-xs font-semibold text-gray-200 mb-1">{m.name}</div>
              <p className="text-xs text-gray-500 leading-relaxed">{m.def}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* ── 4. Four Approaches ───────────────────────────────────────── */}
      <Section title="Experimental Approaches" icon={BarChart2} color="text-brand-400" defaultOpen={false}>
        {/* Grouping labels */}
        <div className="flex gap-4 mb-3 text-xs">
          <span className="px-2 py-1 bg-gray-700/50 rounded text-gray-400">
            <span className="text-blue-400">A+B</span> Conventional Baselines
          </span>
          <span className="px-2 py-1 bg-gray-700/50 rounded text-gray-400">
            <span className="text-yellow-400">C+D</span> AI Approaches (primary comparison)
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {APPROACHES.map(ap => {
            const c = COLOR[ap.color]
            return (
              <div key={ap.id} className={clsx('card border', c.card)}>
                <div className="flex items-center gap-2 mb-2">
                  <span className={clsx('text-[10px] px-1.5 py-0.5 rounded border', c.badge)}>
                    Approach {ap.id}
                  </span>
                  <span className={clsx('font-semibold text-sm', c.text)}>{ap.name}</span>
                  <span className="ml-auto text-[10px] text-gray-600">{ap.group}</span>
                </div>
                <p className="text-xs text-gray-400 mb-3 leading-relaxed">{ap.desc}</p>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <div className="text-[10px] text-green-500 mb-1 font-medium">Pros</div>
                    {ap.pros.map(p => <div key={p} className="text-[10px] text-gray-500">+ {p}</div>)}
                  </div>
                  <div>
                    <div className="text-[10px] text-red-500 mb-1 font-medium">Cons</div>
                    {ap.cons.map(c => <div key={c} className="text-[10px] text-gray-500">− {c}</div>)}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </Section>

      {/* ── 5. Experimental Integrity ────────────────────────────────── */}
      <Section title="Experimental Integrity" icon={Info} color="text-yellow-400" defaultOpen={false}>
        <div className="space-y-2 text-sm text-gray-300">
          <p>Localization predictions are generated and recorded <strong className="text-yellow-300">before</strong> any explanation or fix generation.</p>
          <p>Ground truth is <strong className="text-yellow-300">never exposed</strong> to any localization model. It is only accessed by the evaluation module <em>after</em> all predictions are complete.</p>
          <p>The same repository and same issue description are submitted independently to all four approaches for a fair comparison.</p>
          <div className="font-mono text-xs text-gray-600 mt-3 bg-gray-800/50 rounded p-3 space-y-0.5">
            <div>Issue  →  [Keyword | Structural | LLM Only | RAG+LLM]  →  Predictions  ──── [recorded]</div>
            <div className="pl-8">↓</div>
            <div className="pl-8">Evaluate Predictions  ←  Ground Truth  (accessed ONLY here)</div>
            <div className="pl-8">↓</div>
            <div className="pl-8">Explanation  →  Fix Generation  →  Verification</div>
          </div>
        </div>
      </Section>

      {/* ── 6. Experiment Runner ─────────────────────────────────────── */}
      <Section title="Research Mode — Run Full Experiment" icon={FlaskConical} color="text-brand-400">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Config */}
          <div className="space-y-3">
            {[
              { label: 'Benchmark',     field: 'benchmark',   type: 'text' },
              { label: 'Dataset Path',  field: 'datasetPath', type: 'text', mono: true },
              { label: 'Repository URL',field: 'repoUrl',     type: 'text' },
            ].map(({ label, field, type, mono }) => (
              <div key={field}>
                <label className="block text-xs text-gray-400 mb-1">{label}</label>
                <input
                  type={type}
                  value={(config as any)[field]}
                  onChange={e => setConfig(c => ({ ...c, [field]: e.target.value }))}
                  className={clsx(
                    'w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-brand-500',
                    mono && 'font-mono',
                  )}
                />
              </div>
            ))}
            <div>
              <label className="block text-xs text-gray-400 mb-1">Top-K</label>
              <input type="number" value={config.topK} min={1} max={20}
                onChange={e => setConfig(c => ({ ...c, topK: parseInt(e.target.value) || 5 }))}
                className="w-20 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-brand-500"
              />
            </div>
          </div>

          {/* Approaches + run */}
          <div className="space-y-4">
            <div>
              <div className="text-xs text-gray-400 mb-2">Approaches to run</div>
              <div className="space-y-2">
                {APPROACHES.map(ap => (
                  <label key={ap.key} className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox"
                      checked={config.approaches[ap.key] ?? true}
                      onChange={e => setConfig(c => ({ ...c, approaches: { ...c.approaches, [ap.key]: e.target.checked } }))}
                      className="rounded border-gray-600 bg-gray-800 text-brand-500"
                    />
                    <span className={clsx('text-sm', COLOR[ap.color].text)}>{ap.name}</span>
                    <span className="text-xs text-gray-600">({ap.group})</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="bg-gray-800/50 rounded-lg p-3 text-xs text-gray-400 space-y-1">
              <div>Benchmark: <span className="text-gray-200">{config.benchmark}</span></div>
              <div>Bugs: <span className="text-gray-200">{DATASET.total}</span></div>
              <div>Approaches: <span className="text-gray-200">{Object.values(config.approaches).filter(Boolean).length}</span></div>
              <div>Total runs: <span className="text-brand-300 font-semibold">{totalRuns}</span></div>
              <div className="text-gray-600 text-[10px] pt-1">
                Estimated time (about 50 s per LLM call): {estimatedMinutes} min
              </div>
            </div>

            <button
              onClick={handleRun}
              disabled={running || !config.repoUrl}
              className={clsx(
                'w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-semibold text-sm transition-all',
                running || !config.repoUrl
                  ? 'bg-gray-800 text-gray-500 cursor-not-allowed'
                  : 'bg-brand-600 hover:bg-brand-500 text-white',
              )}
            >
              {running ? <><Spinner />Running experiment...</> : <><Play size={16} />RUN FULL EXPERIMENT</>}
            </button>
          </div>
        </div>

        {/* Error */}
        {expError && (
          <div className="mt-4 flex items-start gap-2 bg-red-950/20 border border-red-900/40 rounded-lg p-3">
            <AlertCircle size={14} className="text-red-400 mt-0.5 shrink-0"/>
            <p className="text-sm text-red-400">{expError}</p>
          </div>
        )}

        {/* Queued result */}
        {expResult && (
          <div className="mt-4 space-y-2">
            <div className="bg-green-950/20 border border-green-900/40 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 size={14} className="text-green-400"/>
                <span className="text-sm text-green-300 font-medium">
                  Experiment {expResult.status}
                </span>
              </div>
              <div className="font-mono text-xs text-gray-400 space-y-0.5">
                <div>ID: <span className="text-gray-200">{expResult.experiment_id}</span></div>
                <div>Status: <span className="text-yellow-300">{expResult.status}</span></div>
                <div>Bugs: <span className="text-gray-200">{expResult.total_bugs}</span></div>
              </div>
            </div>
            <div className="flex gap-2">
              <button onClick={exportJSON}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg transition-colors">
                <Download size={12}/>JSON
              </button>
              <button onClick={exportCSV}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg transition-colors">
                <Download size={12}/>CSV
              </button>
            </div>
          </div>
        )}
      </Section>

      {/* ── 7. Results Table ─────────────────────────────────────────── */}
      <Section title="Experiment Results" icon={BarChart2} color="text-green-400">
        {!expResult?.results?.summaries ? (
          <p className="text-xs text-amber-300 mb-3">
            Illustrative sample values only — these are not benchmark results. Running an experiment replaces them with measured data.
          </p>
        ) : null}
        {previewError && !expResult?.results?.summaries && (
          <p className="text-xs text-red-400 mb-3">Could not load saved preview data: {previewError}</p>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-xs border border-gray-800 rounded-lg overflow-hidden">
            <thead>
              <tr className="bg-gray-800/60 text-gray-500">
                <th className="text-left px-3 py-2 font-medium">Metric</th>
                {APPROACHES.map(a => (
                  <th key={a.key} className={clsx('text-center px-3 py-2 font-medium', COLOR[a.color].text)}>
                    {a.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(() => {
                // Build lookup: approach → summary
                const sourceSummaries = expResult?.results?.summaries ?? previewData?.summaries ?? []
                const summaries: Record<string, any> = {}
                for (const summary of sourceSummaries) {
                  summaries[summary.approach] = summary
                }
                const rows = [
                  { label: 'Top-1 Accuracy', key: 'top1_accuracy' },
                  { label: 'Top-3 Accuracy', key: 'top3_accuracy' },
                  { label: 'Top-5 Accuracy', key: 'top5_accuracy' },
                  { label: 'MRR', key: 'mrr' },
                  { label: 'File-level Top-1', key: 'file_level_top1' },
                  { label: 'Precision', key: 'precision' },
                  { label: 'Recall@K', key: 'recall' },
                  { label: 'F1 Score', key: 'f1_score' },
                  { label: 'Retrieval Recall@K', key: 'retrieval_recall_at_k' },
                  { label: 'Hallucination Rate', key: 'hallucination_rate' },
                  { label: 'Avg Latency', key: 'avg_latency_ms' },
                  { label: 'Avg Token Usage', key: 'avg_tokens' },
                  { label: 'Avg CPU Usage', key: 'avg_cpu_percent' },
                  { label: 'Peak Memory', key: 'peak_memory_mb' },
                  { label: 'Test-Pass Rate', key: 'test_pass_rate' },
                  { label: 'Evaluated Bugs', key: 'total_bugs' },
                ]
                return rows.map(row => (
                  <tr key={row.label} className="border-t border-gray-800">
                    <td className="px-3 py-1.5 text-gray-400">{row.label}</td>
                    {APPROACHES.map(a => {
                      const s = summaries[a.key]
                      const value = s?.[row.key]
                      const val = row.key === 'total_bugs'
                        ? (s?.total_bugs ?? (previewLoading ? 'Loading…' : '—'))
                        : s?.total_bugs > 0
                          ? formatMetric(value, row.key)
                          : previewLoading
                            ? 'Loading…'
                            : previewError
                              ? 'Unavailable'
                              : 'Not evaluated'
                      return (
                        <td key={a.key} className={clsx(
                          'px-3 py-1.5 text-center',
                          s?.total_bugs > 0 && value != null
                            ? 'text-gray-200'
                            : previewLoading
                              ? 'text-gray-500'
                              : 'text-gray-600'
                        )}>
                          {String(val)}
                        </td>
                      )
                    })}
                  </tr>
                ))
              })()}
            </tbody>
          </table>
          {!expResult?.results?.summaries && (
            <p className="text-[10px] text-gray-600 mt-1 text-center">
              {previewData
                ? 'Saved sample data is display-only; no experiment or evaluation has been run.'
                : previewError
                  ? 'Saved preview data could not be loaded.'
                  : 'Loading saved illustrative metrics…'}
            </p>
          )}
          {expResult?.results?.comparison?.ranked?.length > 0 && (
            <div className="mt-3 p-3 bg-green-950/20 border border-green-900/30 rounded-lg">
              <div className="text-xs font-semibold text-green-400 mb-2">Approach Ranking (by Top-1 Accuracy)</div>
              {expResult.results.comparison.ranked?.map((r: any) => (
                <div key={r.approach} className="text-xs text-gray-300 flex gap-4 py-0.5">
                  <span className="text-gray-500">#{r.rank}</span>
                  <span className="text-brand-300 w-24">{r.approach.replace('_', ' ').toUpperCase()}</span>
                  <span>Top-1: <span className="text-green-300">{(r.top1_accuracy*100).toFixed(0)}%</span></span>
                  <span>MRR: <span className="text-yellow-300">{r.mrr.toFixed(3)}</span></span>
                  <span>Bugs: {r.total_bugs}</span>
                </div>
              ))}
            </div>
          )}
          {expResult && expResult.completed_bugs < expResult.total_bugs && (
            <p className="mt-2 text-xs text-yellow-400">
              Evaluated {expResult.completed_bugs} of {expResult.total_bugs} bugs. Metrics use only bugs with computed predictions.
            </p>
          )}
        </div>
      </Section>

      {/* ── 8. Category / Difficulty Analysis ───────────────────────── */}
      <Section title="Performance by Bug Characteristics" icon={BarChart2} color="text-purple-400" defaultOpen={false}>
        <p className="text-xs text-gray-500 mb-3">
          Top-1 localization accuracy by dataset category, difficulty, issue quality, and scope.
          Each value includes the number of evaluated bugs in that group.
        </p>
        {!expResult?.results?.breakdowns && (
          <p className="text-xs text-amber-300 mb-3">
            Illustrative sample breakdowns only — not measured experiment results.
          </p>
        )}

        {[
          { label: 'By Category', key: 'category' },
          { label: 'By Difficulty', key: 'difficulty' },
          { label: 'By Issue Quality', key: 'issue_quality' },
          { label: 'By Scope', key: 'scope' },
        ].map(table => {
          const breakdown = expResult?.results?.breakdowns?.[table.key]
            ?? (expResult ? {} : previewData?.breakdowns[table.key] ?? {})
          return (
            <div key={table.label} className="mb-4">
              <div className="text-xs text-gray-400 font-semibold mb-2">{table.label}</div>
            <table className="w-full text-xs border border-gray-800 rounded overflow-hidden">
              <thead>
                <tr className="bg-gray-800/50 text-gray-500">
                  <th className="text-left px-3 py-1.5">{table.label}</th>
                  {APPROACHES.map(a => (
                    <th key={a.key} className={clsx('text-center px-3 py-1.5', COLOR[a.color].text)}>
                      {a.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Object.entries(breakdown).map(([row, approaches]: [string, any]) => (
                  <tr key={row} className="border-t border-gray-800">
                    <td className="px-3 py-1.5 text-gray-400">{row.replace(/[_-]/g, ' ')}</td>
                    {APPROACHES.map(a => {
                      const summary = approaches?.[a.key]
                      const evaluated = summary?.total_bugs > 0
                      const accuracy = evaluated ? `${(summary.top1_accuracy * 100).toFixed(1)}% (${summary.total_bugs})` : 'Not evaluated'
                      return (
                        <td key={a.key} className={clsx(
                          'px-3 py-1.5 text-center',
                          evaluated ? 'text-gray-200' : 'text-gray-600'
                        )}>
                          {accuracy}
                        </td>
                      )
                    })}
                  </tr>
                ))}
                {!Object.keys(breakdown).length && (
                  <tr>
                    <td colSpan={APPROACHES.length + 1} className="px-3 py-2 text-center text-gray-600">
                      {expResult
                        ? 'No evaluated records contain this characteristic.'
                        : previewLoading
                          ? 'Loading saved preview…'
                          : 'Illustrative sample breakdown is unavailable.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
            </div>
          )
        })}
      </Section>

      {/* ── 9. Failure Analysis ──────────────────────────────────────── */}
      <Section title="Failure Analysis" icon={AlertCircle} color="text-red-400" defaultOpen={false}>
        <p className="text-xs text-gray-500 mb-3">
          This section will list failure cases after the experiment runs. For each failure it will show:
          Bug ID, issue, expected location, LLM prediction, RAG prediction, failure type, and likely cause.
          No failures to display — no experiment has been run yet.
        </p>
        <div className="mb-3">
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Failure Type Taxonomy</div>
          <div className="flex flex-wrap gap-2">
            {FAILURE_TYPES.map(t => (
              <span key={t} className="text-[10px] bg-gray-800/60 text-gray-500 px-2 py-1 rounded border border-gray-700">
                {t}
              </span>
            ))}
          </div>
        </div>
        <div className="bg-gray-800/30 border border-gray-800 rounded-lg p-4 text-center text-gray-600 text-xs">
          Run the full experiment to populate failure cases.
        </div>
      </Section>

      {/* ── 10. Reproducibility ──────────────────────────────────────── */}
      <Section title="Experimental Configuration & Reproducibility" icon={Settings} color="text-gray-400" defaultOpen={false}>
        <p className="text-xs text-gray-500 mb-3">
          The following configuration is stored with every experiment result to enable reproduction.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          {[
            ['Benchmark', DATASET.name],
            ['Repository', DATASET.repo],
            ['Dataset size', `${DATASET.total} bugs`],
            ['LLM provider', 'ollama (configured in .env)'],
            ['LLM model', 'codellama:7b (configured in .env)'],
            ['Embedding model', 'nomic-embed-text → fallback all-MiniLM-L6-v2'],
            ['Vector store', 'FAISS IndexFlatIP'],
            ['Top-K', `${config.topK}`],
            ['Chunking strategy', 'Function-level AST parsing (tree-sitter)'],
            ['Temperature', '0.0'],
            ['Ground truth access', 'Evaluation module only (post-prediction)'],
            ['Host OS', 'Windows 11'],
            ['Python version', '3.12.1'],
            ['Framework', 'FastAPI 0.115.0 + React 18.3.1'],
            ['Prompt version', 'v2.0.0'],
          ].map(([k, v]) => (
            <div key={k} className="flex gap-2">
              <span className="text-gray-500 w-36 shrink-0">{k}</span>
              <span className="text-gray-300 font-mono text-[10px] break-all">{v}</span>
            </div>
          ))}
        </div>
      </Section>
    </div>
  )
}

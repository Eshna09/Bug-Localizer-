import { Github, FileText, CheckCircle2 } from 'lucide-react'
import type { AnalysisResult } from '../../types'

interface Props { result: AnalysisResult }

const PIPELINE_STEPS = [
  'GitHub Repository',
  'Clone / Commit',
  'Repository Analysis',
  'AST / Function Extraction',
  'Dependency / Call Graph',
  'Code Index (FAISS)',
  'Four Localization Approaches',
  'Candidate Ranking',
  'Root Cause Analysis',
  'Fix Proposal',
  'Verification',
]

export default function IssueSummaryCard({ result }: Props) {
  const commitShort = result.commit_hash?.slice(0, 8) ?? '—'
  const repoName = result.repo_url.replace('https://github.com/', '')

  return (
    <div className="card">
      <div className="card-header mb-4">
        <FileText size={14} />
        Issue + Repository
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left: issue + repo details */}
        <div className="md:col-span-2 space-y-3">
          <div className="flex items-start gap-2">
            <Github size={15} className="text-gray-500 mt-0.5 shrink-0" />
            <div>
              <div className="text-xs text-gray-500 mb-0.5">Repository</div>
              <a
                href={result.repo_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-blue-400 hover:text-blue-300 transition-colors break-all"
              >
                {repoName}
              </a>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3 text-xs">
            <div className="bg-gray-800/50 rounded-lg p-2">
              <div className="text-gray-500 mb-0.5">Commit</div>
              <div className="font-mono text-gray-300">{commitShort}</div>
            </div>
            <div className="bg-gray-800/50 rounded-lg p-2">
              <div className="text-gray-500 mb-0.5">Language</div>
              <div className="text-gray-300 capitalize">{result.detected_language || '—'}</div>
            </div>
            <div className="bg-gray-800/50 rounded-lg p-2">
              <div className="text-gray-500 mb-0.5">Status</div>
              <div className="flex items-center gap-1">
                <CheckCircle2 size={10} className="text-green-400" />
                <span className="text-green-400">{result.status}</span>
              </div>
            </div>
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-1.5">Bug Report</div>
            <div className="bg-gray-800/50 rounded-lg p-3 text-sm text-gray-300 leading-relaxed border border-gray-700/50">
              {result.issue_description}
            </div>
          </div>
        </div>

        {/* Right: analysis pipeline */}
        <div>
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-3">Analysis Pipeline</div>
          <div className="flex flex-col items-start gap-0">
            {PIPELINE_STEPS.map((step, i) => (
              <div key={step} className="flex flex-col items-start w-full">
                <div className="flex items-center gap-2 text-xs">
                  <CheckCircle2 size={10} className="text-green-400 shrink-0" />
                  <span className={
                    i < 6 ? 'text-green-400' :
                    i < 9 ? 'text-blue-400' :
                    'text-gray-500'
                  }>
                    {step}
                  </span>
                </div>
                {i < PIPELINE_STEPS.length - 1 && (
                  <div className="ml-[5px] h-2 border-l border-gray-700" />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

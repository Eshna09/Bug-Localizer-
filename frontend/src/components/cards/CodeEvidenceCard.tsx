import { useState } from 'react'
import type { AnalysisResult } from '../../types'
import { Code2 } from 'lucide-react'
import CodeViewer from '../CodeViewer'
import clsx from 'clsx'

interface Props { result: AnalysisResult }

type Tab = 'root_cause' | 'related' | 'retrieved'

export default function CodeEvidenceCard({ result }: Props) {
  const [tab, setTab] = useState<Tab>('root_cause')

  const top = result.primary_predictions[0]
  const related = result.primary_predictions.slice(1, 4)

  const tabs: { id: Tab; label: string }[] = [
    { id: 'root_cause', label: 'Root Cause' },
    { id: 'related', label: 'Related Code' },
    { id: 'retrieved', label: 'Retrieved Evidence' },
  ]

  return (
    <div className="card">
      <div className="card-header"><Code2 size={14} />Code Evidence</div>

      {/* Tab switcher */}
      <div className="flex gap-1 mb-4 border-b border-gray-800 pb-1">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={clsx(
              'px-3 py-1.5 text-xs rounded-md transition-colors',
              tab === t.id
                ? 'bg-brand-500/20 text-brand-300'
                : 'text-gray-500 hover:text-gray-300'
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'root_cause' && top && (
        <div className="space-y-2">
          <div className="text-xs text-gray-500 mb-2">
            Most suspicious location — {top.file} :: {top.function}()
          </div>
          <CodeViewer
            code={top.source_code || '# Source code not available'}
            filePath={top.file}
            startLine={top.line_start}
            highlightLines={Array.from(
              { length: top.line_end - top.line_start + 1 },
              (_, i) => top.line_start + i
            )}
          />
        </div>
      )}

      {tab === 'related' && (
        <div className="space-y-4">
          {related.length === 0 && (
            <p className="text-gray-500 text-sm">No related code locations identified.</p>
          )}
          {related.map((pred) => (
            <div key={pred.rank}>
              <div className="text-xs text-gray-500 mb-1.5">
                #{pred.rank} — {pred.file} :: {pred.function}()
              </div>
              <CodeViewer
                code={pred.source_code || '# Source code not available'}
                filePath={pred.file}
                startLine={pred.line_start}
              />
            </div>
          ))}
        </div>
      )}

      {tab === 'retrieved' && (
        <div className="space-y-3">
          {result.rag_llm_predictions.length === 0 && (
            <p className="text-gray-500 text-sm">No RAG evidence available (RAG+LLM approach may not have run).</p>
          )}
          {result.rag_llm_predictions.map((pred) => (
            <div key={pred.rank} className="border border-gray-800 rounded-lg overflow-hidden">
              <div className="px-3 py-2 bg-gray-800/40 text-xs text-gray-400 flex items-center justify-between">
                <span className="font-mono">{pred.file} :: {pred.function}()</span>
                <span className="text-gray-600">Rank #{pred.rank}</span>
              </div>
              <CodeViewer
                code={pred.source_code || '# Source unavailable'}
                filePath={pred.file}
                startLine={pred.line_start}
                collapsible
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

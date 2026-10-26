import { useState } from 'react'
import type { ProposedFix } from '../../types'
import { Wrench } from 'lucide-react'
import DiffViewer from '../DiffViewer'
import CodeViewer from '../CodeViewer'
import clsx from 'clsx'

interface Props { fix: ProposedFix }

type Tab = 'diff' | 'before' | 'after'

export default function ProposedFixCard({ fix }: Props) {
  const [tab, setTab] = useState<Tab>('diff')

  const tabs: { id: Tab; label: string }[] = [
    { id: 'diff', label: 'Diff' },
    { id: 'before', label: 'Before (buggy)' },
    { id: 'after', label: 'After (proposed)' },
  ]

  return (
    <div className="card">
      <div className="card-header"><Wrench size={14} />Proposed Fix</div>

      {/* File / function info */}
      <div className="flex items-center gap-3 mb-4 text-sm">
        <span className="font-mono text-blue-400">{fix.file}</span>
        <span className="text-gray-600">::</span>
        <span className="font-mono text-yellow-300">{fix.function}()</span>
        {fix.is_minimal && (
          <span className="badge badge-green ml-auto">Minimal fix</span>
        )}
      </div>

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

      {tab === 'diff' && (
        <DiffViewer
          oldCode={fix.current_code}
          newCode={fix.proposed_code}
          oldTitle={`${fix.file} — current (buggy)`}
          newTitle={`${fix.file} — proposed fix`}
        />
      )}

      {tab === 'before' && (
        <CodeViewer
          code={fix.current_code}
          filePath={fix.file}
          title={`${fix.function}() — current`}
        />
      )}

      {tab === 'after' && (
        <CodeViewer
          code={fix.proposed_code}
          filePath={fix.file}
          title={`${fix.function}() — proposed`}
        />
      )}

      {/* Changed lines summary */}
      {fix.what_changed.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-800">
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Changed Lines</div>
          <ul className="space-y-1">
            {fix.what_changed.map((line, i) => (
              <li key={i} className="text-xs font-mono text-gray-400">
                • {line}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

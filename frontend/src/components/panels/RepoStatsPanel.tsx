import type { RepoStats } from '../../types'
import { Database, FileCode2, TestTube2, FunctionSquare, GitBranch, Boxes, Layers } from 'lucide-react'

interface Props { stats: RepoStats }

export default function RepoStatsPanel({ stats }: Props) {
  const commitShort = stats.commit_hash?.slice(0, 8) ?? '—'
  const langEntries = Object.entries(stats.languages ?? {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)

  const items = [
    { icon: FileCode2, label: 'Source Files',   value: stats.source_files,    color: 'text-blue-400' },
    { icon: TestTube2, label: 'Test Files',      value: stats.test_files,      color: 'text-yellow-400' },
    { icon: FunctionSquare, label: 'Functions',  value: stats.total_functions, color: 'text-purple-400' },
    { icon: Boxes,     label: 'Classes',         value: stats.total_classes,   color: 'text-pink-400' },
    { icon: GitBranch, label: 'Dependencies',    value: stats.total_dependencies, color: 'text-green-400' },
    { icon: Layers,    label: 'Indexed Chunks',  value: stats.indexed_chunks,  color: 'text-brand-400' },
  ]

  return (
    <div className="card">
      <div className="card-header mb-4">
        <Database size={14} />
        Repository Analysis
        <span className="ml-auto font-mono text-xs text-gray-500">
          {stats.detected_language} · commit <span className="text-gray-300">{commitShort}</span>
        </span>
      </div>

      <div className="grid grid-cols-3 sm:grid-cols-6 gap-3 mb-4">
        {items.map(({ icon: Icon, label, value, color }) => (
          <div key={label} className="bg-gray-800/50 rounded-lg p-3 text-center">
            <Icon size={16} className={`mx-auto mb-1 ${color}`} />
            <div className="text-lg font-bold text-gray-100">{value ?? 0}</div>
            <div className="text-xs text-gray-500">{label}</div>
          </div>
        ))}
      </div>

      {langEntries.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          <span className="text-xs text-gray-500">File types:</span>
          {langEntries.map(([ext, count]) => (
            <span key={ext} className="text-xs font-mono bg-gray-800 text-gray-300 px-2 py-0.5 rounded">
              {ext} ({count})
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

import { useEffect, useState } from 'react'
import { listHistory } from '../api/client'
import type { HistoryItem } from '../types'
import { Clock, ExternalLink, Loader2, AlertCircle } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import VerificationBadge from '../components/VerificationBadge'

export default function HistoryPage() {
  const [items, setItems] = useState<HistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    listHistory()
      .then(setItems)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2">
        <Clock size={18} className="text-brand-400" />
        <h1 className="text-lg font-semibold">Analysis History</h1>
      </div>

      {loading && (
        <div className="card flex items-center gap-3 justify-center py-10">
          <Loader2 size={20} className="animate-spin text-brand-500" />
          <span className="text-gray-400">Loading history...</span>
        </div>
      )}

      {error && (
        <div className="card border-red-900/50 flex items-start gap-3">
          <AlertCircle size={16} className="text-red-400 mt-0.5" />
          <span className="text-red-400 text-sm">{error}</span>
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="card py-12 text-center text-gray-500">
          No analyses yet. Run your first analysis on the Bug Analysis page.
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="card p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-800/50 border-b border-gray-800">
              <tr>
                <th className="text-left px-4 py-3 text-xs text-gray-500 font-medium">Repository</th>
                <th className="text-left px-4 py-3 text-xs text-gray-500 font-medium">Issue</th>
                <th className="text-left px-4 py-3 text-xs text-gray-500 font-medium">Top Prediction</th>
                <th className="text-left px-4 py-3 text-xs text-gray-500 font-medium">Verification</th>
                <th className="text-left px-4 py-3 text-xs text-gray-500 font-medium">Date</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/50">
              {items.map(item => (
                <tr
                  key={item.id}
                  className="hover:bg-gray-800/30 transition-colors cursor-pointer"
                  onClick={() => navigate(`/repository/${item.id}`)}
                >
                  <td className="px-4 py-3">
                    <span className="font-mono text-xs text-blue-400">
                      {item.repo_url.replace('https://github.com/', '')}
                    </span>
                    {item.commit_hash && (
                      <div className="text-xs text-gray-600 font-mono mt-0.5">
                        {item.commit_hash.slice(0, 8)}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 max-w-xs">
                    <p className="text-xs text-gray-400 line-clamp-2">{item.issue_description}</p>
                  </td>
                  <td className="px-4 py-3">
                    {item.top_prediction ? (
                      <span className="font-mono text-xs text-gray-300">{item.top_prediction}</span>
                    ) : (
                      <span className="text-gray-600 text-xs">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {item.verification_status && item.verification_status !== 'N/A'
                      ? <VerificationBadge status={item.verification_status} />
                      : <span className="text-gray-600 text-xs">—</span>
                    }
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-xs text-gray-500">
                      {item.timestamp
                        ? new Date(item.timestamp).toLocaleDateString()
                        : '—'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <ExternalLink size={14} className="text-gray-600 hover:text-gray-300" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

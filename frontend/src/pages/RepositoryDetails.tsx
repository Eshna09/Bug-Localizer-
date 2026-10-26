import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getAnalysis } from '../api/client'
import type { AnalysisResult } from '../types'
import { Loader2, AlertCircle, ArrowLeft } from 'lucide-react'
import Dashboard from '../components/Dashboard'

export default function RepositoryDetailsPage() {
  const { analysisId } = useParams<{ analysisId: string }>()
  const navigate = useNavigate()
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!analysisId) return
    getAnalysis(analysisId)
      .then(setResult)
      .catch(e => setError(e?.response?.data?.detail || e.message))
      .finally(() => setLoading(false))
  }, [analysisId])

  return (
    <div className="space-y-5">
      <button
        onClick={() => navigate('/history')}
        className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-200 transition-colors"
      >
        <ArrowLeft size={15} /> Back to history
      </button>

      {loading && (
        <div className="card flex items-center gap-3 justify-center py-10">
          <Loader2 size={20} className="animate-spin text-brand-500" />
          <span className="text-gray-400">Loading analysis...</span>
        </div>
      )}

      {error && (
        <div className="card border-red-900/50 flex items-start gap-3">
          <AlertCircle size={16} className="text-red-400 mt-0.5" />
          <span className="text-red-400 text-sm">{error}</span>
        </div>
      )}

      {result && !loading && <Dashboard result={result} />}
    </div>
  )
}

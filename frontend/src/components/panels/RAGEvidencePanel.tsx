import { useState } from 'react'
import { Search, ChevronDown, ChevronUp } from 'lucide-react'
import type { RetrievedChunk } from '../../types'

interface Props { chunks: RetrievedChunk[] }

function ScoreBar({ score }: { score: number }) {
  const pct = Math.max(0, Math.min(1, score)) * 100
  const color = score >= 0.8 ? 'bg-green-500' : score >= 0.5 ? 'bg-yellow-500' : 'bg-orange-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-800 rounded-full h-1.5">
        <div className={`${color} h-1.5 rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-xs text-gray-400 w-12 text-right">{score.toFixed(3)}</span>
    </div>
  )
}

export default function RAGEvidencePanel({ chunks }: Props) {
  const [expanded, setExpanded] = useState<number | null>(null)
  if (!chunks || chunks.length === 0) return null

  return (
    <div className="card">
      <div className="card-header mb-4">
        <Search size={14} className="text-green-400" />
        RAG — Retrieved Evidence
        <span className="ml-2 text-xs text-gray-500">
          These are the exact chunks supplied to the RAG+LLM
        </span>
        <span className="ml-auto text-xs text-gray-500">{chunks.length} chunks retrieved</span>
      </div>

      <div className="space-y-3">
        {chunks.map((chunk, i) => {
          if (!chunk) return null
          const chunkFile = chunk.file ?? ''
          return (
          <div key={chunk.chunk_id ?? i} className="border border-gray-800 rounded-lg overflow-hidden">
            <div className="flex items-center gap-3 p-3 bg-gray-800/40">
              <span className="font-mono text-xs text-gray-500 w-5 shrink-0">#{i + 1}</span>
              <div className="flex-1 min-w-0">
                <div className="font-mono text-xs text-blue-400 truncate">{chunkFile}</div>
                <div className="font-mono text-xs text-yellow-300">{chunk.function ?? ''}()</div>
                <div className="text-xs text-gray-600">
                  {chunk.class_name && <span className="mr-2">{chunk.class_name}</span>}
                  L{chunk.line_start ?? '?'}–{chunk.line_end ?? '?'}
                </div>
              </div>
              <div className="w-40 shrink-0">
                <div className="text-xs text-gray-500 mb-1">Similarity</div>
                <ScoreBar score={chunk.similarity_score ?? 0} />
              </div>
              <button
                onClick={() => setExpanded(expanded === i ? null : i)}
                className="ml-2 text-gray-500 hover:text-gray-300 transition-colors"
              >
                {expanded === i ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>
            </div>
            {expanded === i && chunk.code_preview && (
              <div className="border-t border-gray-800">
                <pre className="p-3 text-xs font-mono text-gray-300 overflow-x-auto whitespace-pre-wrap leading-relaxed bg-gray-900/50">
                  {chunk.code_preview}
                </pre>
              </div>
            )}
          </div>
          )
        })}
      </div>
    </div>
  )
}

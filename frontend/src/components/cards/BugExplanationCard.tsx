import type { BugExplanation } from '../../types'
import { MessageSquare } from 'lucide-react'

interface Props { explanation: BugExplanation }

const Section = ({ label, text }: { label: string; text: string }) => (
  <div>
    <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">{label}</div>
    <p className="text-sm text-gray-200 leading-relaxed">{text}</p>
  </div>
)

export default function BugExplanationCard({ explanation }: Props) {
  return (
    <div className="card">
      <div className="card-header"><MessageSquare size={14} />Bug Explanation</div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <Section label="What is wrong?" text={explanation.what_is_wrong} />
        <Section label="Why is it wrong?" text={explanation.why_is_it_wrong} />
        <Section label="What should happen?" text={explanation.what_should_happen} />
        <Section label="What actually happens?" text={explanation.what_actually_happens} />
        <div className="md:col-span-2">
          <Section label="How does this affect the application?" text={explanation.downstream_impact} />
        </div>
      </div>

      {explanation.dependency_chain.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-800">
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
            Dependency Chain
          </div>
          <div className="flex flex-wrap gap-2">
            {explanation.dependency_chain.map((step, i) => (
              <span key={i} className="text-xs font-mono text-gray-400 bg-gray-800 px-2 py-1 rounded">
                {step}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

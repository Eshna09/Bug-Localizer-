import type { ProposedFix } from '../../types'
import { ShieldCheck } from 'lucide-react'

interface Props { fix: ProposedFix }

const Section = ({ label, text, warn = false }: { label: string; text: string; warn?: boolean }) => (
  <div>
    <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">{label}</div>
    <p className={`text-sm leading-relaxed ${warn ? 'text-yellow-300/90' : 'text-gray-200'}`}>
      {text || '—'}
    </p>
  </div>
)

export default function FixExplanationCard({ fix }: Props) {
  return (
    <div className="card">
      <div className="card-header"><ShieldCheck size={14} />Fix Explanation</div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <Section label="Why this fixes the bug" text={fix.why_this_fixes} />
        <Section label="Why this change is safe" text={fix.why_safe} />
        <div className="md:col-span-2">
          <Section
            label="Potential side effects"
            text={fix.potential_side_effects}
            warn={!!fix.potential_side_effects && fix.potential_side_effects.toLowerCase() !== 'none'}
          />
        </div>
        {fix.minimal_change_description && (
          <div className="md:col-span-2">
            <Section label="Change description" text={fix.minimal_change_description} />
          </div>
        )}
      </div>
    </div>
  )
}

import { CheckCircle, XCircle, AlertCircle, HelpCircle } from 'lucide-react'

interface Props {
  status: string
  size?: 'sm' | 'md'
}

const config: Record<string, { label: string; cls: string; Icon: React.ElementType }> = {
  VERIFIED: { label: 'Verified', cls: 'badge badge-green', Icon: CheckCircle },
  PARTIALLY_VERIFIED: { label: 'Partially Verified', cls: 'badge badge-yellow', Icon: AlertCircle },
  NOT_VERIFIED: { label: 'Not Verified', cls: 'badge badge-red', Icon: XCircle },
  VERIFICATION_UNAVAILABLE: { label: 'Unavailable', cls: 'badge badge-gray', Icon: HelpCircle },
}

export default function VerificationBadge({ status, size = 'sm' }: Props) {
  const c = config[status] || config.VERIFICATION_UNAVAILABLE
  const { Icon } = c
  return (
    <span className={c.cls}>
      <Icon size={12} className="mr-1 inline" />
      {c.label}
    </span>
  )
}

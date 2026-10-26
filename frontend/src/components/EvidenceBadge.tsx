interface Props {
  strength: string
}

const map: Record<string, string> = {
  High: 'badge badge-green',
  Medium: 'badge badge-yellow',
  Low: 'badge badge-red',
  Insufficient: 'badge badge-gray',
}

export default function EvidenceBadge({ strength }: Props) {
  return (
    <span className={map[strength] || 'badge badge-gray'}>
      {strength}
    </span>
  )
}

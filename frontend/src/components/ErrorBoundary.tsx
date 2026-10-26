import { Component, type ReactNode } from 'react'
import { AlertCircle } from 'lucide-react'

interface Props { children: ReactNode; label?: string }
interface State { error: Error | null }

/**
 * Wraps any panel — if it throws during render, shows a small error card
 * instead of crashing the whole dashboard to a black screen.
 */
export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: any) {
    console.error(`[ErrorBoundary] ${this.props.label ?? 'Panel'} crashed:`, error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="card border border-red-900/40 bg-red-950/10">
          <div className="flex items-start gap-2">
            <AlertCircle size={14} className="text-red-400 mt-0.5 shrink-0" />
            <div>
              <div className="text-sm font-medium text-red-300 mb-1">
                {this.props.label ?? 'Panel'} failed to render
              </div>
              <p className="text-xs text-red-400 font-mono">
                {this.state.error.message}
              </p>
            </div>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

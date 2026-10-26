import { useState } from 'react'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { FileCode, ChevronDown, ChevronRight } from 'lucide-react'

interface CodeViewerProps {
  code: string
  language?: string
  filePath?: string
  startLine?: number
  highlightLines?: number[]
  title?: string
  collapsible?: boolean
  defaultExpanded?: boolean
}

export default function CodeViewer({
  code,
  language = 'python',
  filePath,
  startLine = 1,
  highlightLines = [],
  title,
  collapsible = false,
  defaultExpanded = true,
}: CodeViewerProps) {
  const [expanded, setExpanded] = useState(defaultExpanded)

  const header = (
    <div
      className={`flex items-center gap-2 px-3 py-2 bg-gray-800/60 border-b border-gray-700 rounded-t-lg ${collapsible ? 'cursor-pointer hover:bg-gray-800' : ''}`}
      onClick={() => collapsible && setExpanded(e => !e)}
    >
      <FileCode size={14} className="text-blue-400 shrink-0" />
      <span className="text-xs font-mono text-gray-300 flex-1">
        {filePath || title || 'source'}
      </span>
      {collapsible && (
        expanded
          ? <ChevronDown size={14} className="text-gray-500" />
          : <ChevronRight size={14} className="text-gray-500" />
      )}
    </div>
  )

  return (
    <div className="rounded-lg overflow-hidden border border-gray-700 text-sm">
      {header}
      {expanded && (
        <SyntaxHighlighter
          language={language}
          style={oneDark}
          showLineNumbers
          startingLineNumber={startLine}
          wrapLines
          lineProps={(lineNumber) => {
            const isHighlighted = highlightLines.includes(lineNumber)
            return {
              style: isHighlighted
                ? { backgroundColor: 'rgba(255,215,0,0.12)', display: 'block' }
                : { display: 'block' },
            }
          }}
          customStyle={{
            margin: 0,
            borderRadius: 0,
            fontSize: '0.78rem',
            maxHeight: '500px',
          }}
        >
          {code}
        </SyntaxHighlighter>
      )}
    </div>
  )
}

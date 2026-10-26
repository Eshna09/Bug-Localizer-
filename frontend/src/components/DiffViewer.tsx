import ReactDiffViewer, { DiffMethod } from 'react-diff-viewer-continued'

interface DiffViewerProps {
  oldCode: string
  newCode: string
  oldTitle?: string
  newTitle?: string
}

export default function DiffViewer({
  oldCode,
  newCode,
  oldTitle = 'Current (buggy)',
  newTitle = 'Proposed fix',
}: DiffViewerProps) {
  return (
    <div className="rounded-lg overflow-hidden border border-gray-700 text-xs font-mono">
      <ReactDiffViewer
        oldValue={oldCode}
        newValue={newCode}
        splitView={false}
        compareMethod={DiffMethod.LINES}
        leftTitle={oldTitle}
        rightTitle={newTitle}
        useDarkTheme
        styles={{
          variables: {
            dark: {
              diffViewerBackground: '#0f0f0f',
              diffViewerColor: '#e5e7eb',
              addedBackground: '#14532d40',
              addedColor: '#86efac',
              removedBackground: '#7f1d1d40',
              removedColor: '#fca5a5',
              wordAddedBackground: '#14532d80',
              wordRemovedBackground: '#7f1d1d80',
              addedGutterBackground: '#14532d60',
              removedGutterBackground: '#7f1d1d60',
              gutterBackground: '#1a1a1a',
              gutterColor: '#4b5563',
            },
          },
        }}
      />
    </div>
  )
}

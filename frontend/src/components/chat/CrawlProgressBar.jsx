import { useChatStore } from '../../stores/chatStore'

function formatBoardLabel(board) {
  return board.subBoardName
    ? `${board.boardName} / ${board.subBoardName}`
    : board.boardName
}

function formatStatus(board) {
  if (board.status === 'collecting') {
    return 'Collecting'
  }
  if (board.status === 'skipped') {
    return '0 items, skipped'
  }
  if (board.status === 'done') {
    return `${board.collectedCount} items`
  }
  return 'Pending'
}

export default function CrawlProgressBar() {
  const isStreaming = useChatStore((state) => state.isStreaming)
  const crawlProgress = useChatStore((state) => state.crawlProgress)

  if (!isStreaming || crawlProgress.boards.length === 0) {
    return null
  }

  const activeLabel = crawlProgress.currentSubBoard
    ? `${crawlProgress.currentBoard} / ${crawlProgress.currentSubBoard}`
    : crawlProgress.currentBoard

  return (
    <div className="mx-4 mt-4 rounded-2xl border border-amber-200 bg-gradient-to-br from-amber-50 to-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-700">
            OLTA Crawl
          </p>
          <h3 className="mt-1 text-sm font-semibold text-gray-900">Collection progress</h3>
          <p className="mt-1 text-xs text-gray-600">
            {activeLabel || 'Updating board-level crawl status.'}
          </p>
        </div>
        <div className="rounded-full bg-white px-3 py-1 text-sm font-semibold text-amber-800 shadow-sm">
          Total {crawlProgress.totalCollected}
        </div>
      </div>

      <div className="mt-3 max-h-52 space-y-2 overflow-y-auto pr-1">
        {crawlProgress.boards.map((board) => (
          <div
            key={`${board.boardName}:${board.subBoardName || ''}`}
            className="flex items-center justify-between gap-3 rounded-xl border border-white bg-white/80 px-3 py-2"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-gray-800">{formatBoardLabel(board)}</p>
            </div>
            <div className="shrink-0">
              <span
                className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${
                  board.status === 'collecting'
                    ? 'bg-amber-100 text-amber-800'
                    : board.status === 'skipped'
                      ? 'bg-slate-100 text-slate-600'
                      : 'bg-emerald-100 text-emerald-700'
                }`}
              >
                {board.status === 'collecting' && (
                  <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-amber-500 animate-pulse" />
                )}
                {formatStatus(board)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

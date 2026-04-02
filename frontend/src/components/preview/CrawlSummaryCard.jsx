function formatSubBoard(subBoard) {
  if (subBoard.skipped) {
    return `${subBoard.name}(0, skipped)`
  }

  return `${subBoard.name}(${subBoard.collected_count})`
}

export default function CrawlSummaryCard({ summary }) {
  if (!summary || !Array.isArray(summary.boards) || summary.boards.length === 0) {
    return null
  }

  return (
    <section className="rounded-2xl border border-sky-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-sky-700">
            OLTA Summary
          </p>
          <h3 className="mt-1 text-base font-semibold text-gray-900">Collection totals</h3>
        </div>
        <div className="rounded-full bg-sky-50 px-3 py-1 text-sm font-semibold text-sky-800">
          Total {summary.grand_total}
        </div>
      </div>

      <div className="mt-4 space-y-3">
        {summary.boards.map((board) => (
          <article
            key={board.board_name}
            className="rounded-xl border border-gray-200 bg-gray-50 px-3 py-3"
          >
            <div className="flex items-center justify-between gap-3">
              <h4 className="text-sm font-semibold text-gray-800">{board.board_name}</h4>
              <span className="text-sm font-semibold text-gray-700">{board.total_collected}</span>
            </div>

            {board.sub_boards.length > 0 && (
              <p className="mt-2 text-xs leading-5 text-gray-600">
                {board.sub_boards.map(formatSubBoard).join(' | ')}
              </p>
            )}
          </article>
        ))}
      </div>
    </section>
  )
}

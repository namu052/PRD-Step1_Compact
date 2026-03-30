import { useChatStore } from '../../stores/chatStore'

export default function SourceDetail({ source, isLoading = false, error = null }) {
  const selectSource = useChatStore((state) => state.selectSource)

  return (
    <div className="p-4">
      <button
        type="button"
        onClick={() => selectSource(null)}
        className="mb-4 flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800"
      >
        ← 목록으로
      </button>

      <h2 className="mb-4 text-xl font-bold text-gray-900">{source.title}</h2>

      <div className="mb-4 rounded-lg border bg-white p-4">
        {isLoading ? (
          <div className="text-sm text-gray-500">상세 내용을 불러오는 중입니다...</div>
        ) : error ? (
          <div className="text-sm text-red-600">{error}</div>
        ) : (
          <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-gray-700">
            {source.content || source.preview}
          </pre>
        )}
      </div>

      {source.url && (
        <a
          href={source.url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm text-white transition hover:bg-blue-700"
        >
          원문 바로가기
        </a>
      )}
    </div>
  )
}

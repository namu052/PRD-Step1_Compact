import StreamingResponse from './StreamingResponse'
import ConfidenceBadge from './ConfidenceBadge'

export default function FinalAnswerPopup({ answer, onClose }) {
  if (!answer) {
    return null
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 px-4 py-6">
      <div className="flex max-h-[85vh] w-full max-w-3xl flex-col overflow-hidden rounded-3xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">최종 답변</h2>
            <p className="mt-1 text-sm text-gray-500">채팅창과 별도로 팝업에서도 확인할 수 있습니다.</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-gray-200 px-3 py-1.5 text-sm text-gray-600 transition hover:border-gray-300 hover:bg-gray-50 hover:text-gray-900"
          >
            닫기
          </button>
        </div>
        <div className="overflow-y-auto px-6 py-5">
          <StreamingResponse content={answer.content} />
          <ConfidenceBadge confidence={answer.confidence} />
        </div>
      </div>
    </div>
  )
}

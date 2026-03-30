import { useChatStore } from '../../stores/chatStore'

const TYPE_STYLES = {
  '법령': 'bg-blue-100 text-blue-700',
  '해석례': 'bg-green-100 text-green-700',
  '판례': 'bg-purple-100 text-purple-700',
  '훈령': 'bg-orange-100 text-orange-700',
  '처리 요약': 'bg-amber-100 text-amber-700',
  '근거 묶음': 'bg-teal-100 text-teal-700',
}

export default function SourceCard({ source }) {
  const selectSource = useChatStore((s) => s.selectSource)

  return (
    <div
      onClick={() => selectSource(source.id)}
      className="bg-white rounded-lg shadow-sm border p-4 cursor-pointer hover:shadow-md transition"
    >
      <div className="flex items-center gap-2 mb-2">
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${TYPE_STYLES[source.type] || 'bg-gray-100 text-gray-700'}`}>
          {source.type}
        </span>
      </div>
      <h3 className="font-semibold text-lg text-gray-900">{source.title}</h3>
      <p className="text-gray-600 text-sm mt-1 line-clamp-2">{source.preview}</p>
    </div>
  )
}

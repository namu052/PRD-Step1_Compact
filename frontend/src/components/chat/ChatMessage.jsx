import StreamingResponse from './StreamingResponse'
import ConfidenceBadge from './ConfidenceBadge'

export default function ChatMessage({ message }) {
  if (message.role === 'system') {
    return (
      <div className="my-2 flex justify-center">
        <span className="text-sm italic text-gray-500">{message.content}</span>
      </div>
    )
  }

  if (message.role === 'user') {
    return (
      <div className="my-2 flex justify-end">
        <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-blue-500 px-4 py-2 text-sm text-white">
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="my-2 flex justify-start">
      <div className="max-w-[85%] rounded-2xl rounded-bl-sm border border-gray-200 bg-white px-4 py-3 text-sm text-gray-800">
        <StreamingResponse content={message.content} />
        <ConfidenceBadge confidence={message.confidence} />
      </div>
    </div>
  )
}

import { useRef, useEffect } from 'react'
import { useChatStore } from '../../stores/chatStore'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'

export default function ChatPanel() {
  const messages = useChatStore((s) => s.messages)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-1">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">
            질문을 입력하면 AI가 답변해 드립니다
          </div>
        )}
        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>
      <ChatInput />
    </div>
  )
}

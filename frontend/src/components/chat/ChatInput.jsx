import { useEffect, useRef, useState } from 'react'
import { useAuthStore } from '../../stores/authStore'
import { useChatStore } from '../../stores/chatStore'
import { useSSE } from '../../hooks/useSSE'

export default function ChatInput() {
  const sessionId = useAuthStore((state) => state.sessionId)
  const isInitializing = useAuthStore((state) => state.isInitializing)
  const loginError = useAuthStore((state) => state.loginError)
  const isStreaming = useChatStore((state) => state.isStreaming)
  const { streamChat } = useSSE()
  const [text, setText] = useState('')
  const textareaRef = useRef(null)

  const disabled = isStreaming || isInitializing || !sessionId

  useEffect(() => {
    if (!textareaRef.current) {
      return
    }

    textareaRef.current.style.height = 'auto'
    textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`
  }, [text])

  const handleSubmit = async () => {
    const trimmed = text.trim()

    if (!trimmed || disabled) {
      return
    }

    setText('')
    await streamChat({ question: trimmed, sessionId })
  }

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void handleSubmit()
    }
  }

  const placeholder = isInitializing
    ? '세션 준비 중...'
    : !sessionId
      ? 'GPKI 인증 후 이용 가능합니다'
      : isStreaming
        ? '답변 생성 중...'
        : '지방세 관련 질문을 입력하세요...'

  return (
    <div className="shrink-0 border-t border-gray-200 bg-white p-3">
      {loginError && <p className="mb-2 text-sm text-red-600">{loginError}</p>}
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className="min-h-[44px] flex-1 resize-none rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:text-gray-400"
        />
        <button
          type="button"
          onClick={() => void handleSubmit()}
          disabled={disabled || !text.trim()}
          className="shrink-0 rounded-lg bg-blue-600 px-4 py-2 text-sm text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isStreaming ? '전송 중' : '전송'}
        </button>
      </div>
    </div>
  )
}

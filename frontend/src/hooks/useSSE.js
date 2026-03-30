import { useCallback } from 'react'
import { useAuthStore } from '../stores/authStore'
import { useChatStore } from '../stores/chatStore'

function parseSSEChunk(chunk, onEvent) {
  const events = chunk.split('\n\n')
  const remainder = events.pop() ?? ''

  for (const rawEvent of events) {
    const lines = rawEvent.split('\n')
    let eventType = ''
    let eventData = ''

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        eventType = line.slice(7)
      }
      if (line.startsWith('data: ')) {
        eventData = line.slice(6)
      }
    }

    if (!eventType || !eventData) {
      continue
    }

    onEvent(eventType, JSON.parse(eventData))
  }

  return remainder
}

export function useSSE() {
  const beginStream = useChatStore((state) => state.beginStream)
  const appendToken = useChatStore((state) => state.appendToken)
  const addSystemMessage = useChatStore((state) => state.addSystemMessage)
  const setStage = useChatStore((state) => state.setStage)
  const setSources = useChatStore((state) => state.setSources)
  const finishStream = useChatStore((state) => state.finishStream)
  const failStream = useChatStore((state) => state.failStream)

  const streamChat = useCallback(
    async ({ question, sessionId }) => {
      const aiMessageId = beginStream(question)
      let sawTerminalStage = false

      const handleEvent = (eventType, data) => {
        if (eventType === 'stage_change') {
          if (data.stage === 'done') {
            sawTerminalStage = true
            finishStream()
            return
          }

          setStage(data.stage)
          return
        }

        if (eventType === 'token') {
          appendToken(aiMessageId, data.token)
          return
        }

        if (eventType === 'notice') {
          if (data.message) {
            addSystemMessage(data.message)
          }
          return
        }

        if (eventType === 'error') {
          const errorMessage = data.message || data.error || '서버 오류가 발생했습니다.'
          failStream(aiMessageId, errorMessage)
          sawTerminalStage = true
          return
        }

        if (eventType === 'sources') {
          setSources({ sources: data.sources ?? [], confidence: data.confidence ?? null })
          if (data.confidence) {
            const state = useChatStore.getState()
            const activeMessageId = state.activeMessageId
            if (activeMessageId) {
              useChatStore.setState({
                messages: state.messages.map((message) =>
                  message.id === activeMessageId
                    ? { ...message, confidence: data.confidence }
                    : message,
                ),
              })
            }
          }
          return
        }

        if (eventType === 'done') {
          sawTerminalStage = true
          finishStream()
        }
      }

      try {
        const response = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            question,
          }),
        })

        if (response.status === 401) {
          useAuthStore.getState().resetSession()
          failStream(aiMessageId, '세션이 만료되었습니다. 다시 로그인해 주세요.')
          return
        }

        if (!response.ok || !response.body) {
          throw new Error('SSE connection failed')
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) {
            break
          }

          buffer += decoder.decode(value, { stream: true })
          buffer = parseSSEChunk(buffer, handleEvent)
        }

        if (buffer.trim().length > 0) {
          parseSSEChunk(`${buffer}\n\n`, handleEvent)
        }

        if (!sawTerminalStage) {
          finishStream()
        }
      } catch {
        failStream(aiMessageId, '네트워크 오류가 발생했습니다. 다시 시도해 주세요.')
      }
    },
    [addSystemMessage, appendToken, beginStream, failStream, finishStream, setSources, setStage],
  )

  return { streamChat }
}

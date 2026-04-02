import { useCallback } from 'react'
import { useChatStore } from '../stores/chatStore'
import { apiUrl } from '../lib/api'

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
  const updateCrawlProgress = useChatStore((state) => state.updateCrawlProgress)
  const setCrawlSummary = useChatStore((state) => state.setCrawlSummary)
  const openFinalAnswerPopup = useChatStore((state) => state.openFinalAnswerPopup)
  const finishStream = useChatStore((state) => state.finishStream)
  const failStream = useChatStore((state) => state.failStream)

  const streamChat = useCallback(
    async ({ question, sessionId }) => {
      const aiMessageId = beginStream(question)
      let sawTerminalStage = false
      let latestConfidence = null

      const showFinalAnswerPopup = () => {
        const state = useChatStore.getState()
        const finalMessage = state.messages.find((message) => message.id === aiMessageId)
        if (!finalMessage?.content?.trim()) {
          return
        }
        openFinalAnswerPopup({
          content: finalMessage.content,
          confidence: finalMessage.confidence ?? latestConfidence ?? null,
        })
      }

      const handleEvent = (eventType, data) => {
        if (eventType === 'stage_change') {
          if (data.stage === 'done') {
            sawTerminalStage = true
            showFinalAnswerPopup()
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

        if (eventType === 'olta_login_required') {
          addSystemMessage(data.message || 'OLTA 미로그인 상태입니다.')
          return
        }

        if (eventType === 'sources') {
          latestConfidence = data.confidence ?? null
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

        if (eventType === 'crawl_progress') {
          updateCrawlProgress(data)
          return
        }

        if (eventType === 'crawl_summary') {
          setCrawlSummary(data)
          return
        }

        if (eventType === 'done') {
          sawTerminalStage = true
          showFinalAnswerPopup()
          finishStream()
        }
      }

      try {
        const response = await fetch(apiUrl('/api/chat'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            question,
          }),
        })

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
    [
      addSystemMessage,
      appendToken,
      beginStream,
      failStream,
      finishStream,
      openFinalAnswerPopup,
      setCrawlSummary,
      setSources,
      setStage,
      updateCrawlProgress,
    ],
  )

  return { streamChat }
}

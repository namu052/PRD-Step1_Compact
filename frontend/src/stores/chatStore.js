import { create } from 'zustand'

export const useChatStore = create((set, get) => ({
  messages: [],
  currentStage: null,
  isStreaming: false,
  activeMessageId: null,
  selectedSourceId: null,
  currentSources: [],
  currentConfidence: null,
  hasAskedQuestion: false,
  finalAnswerPopup: null,

  beginStream: (question) => {
    const requestId = Date.now()
    const userMessage = {
      id: `msg_${requestId}_user`,
      role: 'user',
      content: question,
      timestamp: new Date().toISOString(),
    }
    const aiMessageId = `msg_${requestId}_ai`
    const aiMessage = {
      id: aiMessageId,
      role: 'ai',
      content: '',
      timestamp: new Date().toISOString(),
    }

    set((state) => ({
      messages: [...state.messages, userMessage, aiMessage],
      currentStage: 'searching',
      isStreaming: true,
      activeMessageId: aiMessageId,
      selectedSourceId: null,
      currentSources: [],
      currentConfidence: null,
      hasAskedQuestion: true,
    }))

    return aiMessageId
  },

  appendToken: (messageId, token) => {
    set((state) => ({
      messages: state.messages.map((message) =>
        message.id === messageId
          ? { ...message, content: message.content + token }
          : message,
      ),
    }))
  },

  addSystemMessage: (content) =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          id: `msg_${Date.now()}_system_${Math.random().toString(36).slice(2, 8)}`,
          role: 'system',
          content,
          timestamp: new Date().toISOString(),
        },
      ],
    })),

  setStage: (stage) =>
    set((state) => {
      if (stage === 'finalizing') {
        const alreadyNotified = state.messages.some(
          (message) =>
            message.role === 'system' && message.content === '최종 답변을 정리하고 있습니다...',
        )

        return {
          currentStage: stage,
          messages: alreadyNotified
            ? state.messages
            : [
                ...state.messages,
                {
                  id: `msg_${Date.now()}_system_finalizing`,
                  role: 'system',
                  content: '최종 답변을 정리하고 있습니다...',
                  timestamp: new Date().toISOString(),
                },
              ],
        }
      }

      return { currentStage: stage }
    }),

  setSources: ({ sources, confidence }) =>
    set({
      currentSources: sources,
      currentConfidence: confidence ?? null,
      selectedSourceId: sources.length > 0 ? get().selectedSourceId : null,
    }),

  openFinalAnswerPopup: ({ content, confidence }) =>
    set({
      finalAnswerPopup: {
        content,
        confidence: confidence ?? null,
        openedAt: new Date().toISOString(),
      },
    }),

  closeFinalAnswerPopup: () => set({ finalAnswerPopup: null }),

  finishStream: () => set({ currentStage: 'done', isStreaming: false, activeMessageId: null }),

  failStream: (messageId, errorMessage) => {
    set((state) => {
      const hasContent = state.messages.some(
        (message) => message.id === messageId && message.content.trim().length > 0,
      )

      return {
        messages: [
          ...state.messages.filter(
            (message) => message.id !== messageId || hasContent,
          ),
          {
            id: `msg_${Date.now()}_system`,
            role: 'system',
            content: errorMessage,
            timestamp: new Date().toISOString(),
          },
        ],
        currentStage: null,
        currentSources: [],
        currentConfidence: null,
        selectedSourceId: null,
        isStreaming: false,
        activeMessageId: null,
        finalAnswerPopup: null,
      }
    })
  },

  selectSource: (sourceId) => set({ selectedSourceId: sourceId }),

  clearChat: () =>
    set({
      messages: [],
      currentStage: null,
      isStreaming: false,
      activeMessageId: null,
      selectedSourceId: null,
      currentSources: [],
      currentConfidence: null,
      hasAskedQuestion: false,
      finalAnswerPopup: null,
    }),
}))

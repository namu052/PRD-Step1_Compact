import { create } from 'zustand'

function createEmptyCrawlProgress() {
  return {
    totalCollected: 0,
    boards: [],
    currentBoard: null,
    currentSubBoard: null,
  }
}

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
  crawlProgress: createEmptyCrawlProgress(),
  crawlSummary: null,

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
      crawlProgress: createEmptyCrawlProgress(),
      crawlSummary: null,
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
    set((state) => ({
      currentStage: stage,
      messages:
        stage === 'finalizing' && state.activeMessageId
          ? state.messages.map((message) =>
              message.id === state.activeMessageId ? { ...message, content: '' } : message,
            )
          : state.messages,
    })),

  updateCrawlProgress: (stat) =>
    set((state) => {
      const key = `${stat.board_name}::${stat.sub_board_name || ''}`
      const boards = [...state.crawlProgress.boards]
      const nextEntry = {
        boardName: stat.board_name,
        subBoardName: stat.sub_board_name ?? null,
        collectedCount: stat.collected_count ?? 0,
        skipped: Boolean(stat.skipped),
        status: stat.status ?? 'pending',
      }
      const entryIndex = boards.findIndex(
        (board) => `${board.boardName}::${board.subBoardName || ''}` === key,
      )

      if (entryIndex >= 0) {
        boards[entryIndex] = nextEntry
      } else {
        boards.push(nextEntry)
      }

      const activeEntry = [...boards].reverse().find((board) => board.status === 'collecting') ?? null

      return {
        crawlProgress: {
          totalCollected: boards.reduce((sum, board) => sum + (board.collectedCount || 0), 0),
          boards,
          currentBoard: activeEntry?.boardName ?? null,
          currentSubBoard: activeEntry?.subBoardName ?? null,
        },
      }
    }),

  resetCrawlProgress: () =>
    set({
      crawlProgress: createEmptyCrawlProgress(),
      crawlSummary: null,
    }),

  setCrawlSummary: (summary) => set({ crawlSummary: summary ?? null }),

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
        crawlProgress: createEmptyCrawlProgress(),
        crawlSummary: null,
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
      crawlProgress: createEmptyCrawlProgress(),
      crawlSummary: null,
    }),
}))

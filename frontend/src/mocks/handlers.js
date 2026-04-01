import { http, HttpResponse } from 'msw'
import mockChatResponses from './data/mockChatResponses.json'
import mockSources from './data/mockSources.json'

const allSources = mockSources.reduce((sourceMap, source) => {
  sourceMap[source.id] = source
  return sourceMap
}, {})

function createEventChunk(event, data) {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`
}

function wait(delay) {
  return new Promise((resolve) => setTimeout(resolve, delay))
}

function createSSEStream(responseData) {
  const encoder = new TextEncoder()
  const { stages, answer, sources } = responseData

  return new ReadableStream({
    async start(controller) {
      for (const stageInfo of stages) {
        if (stageInfo.stage === 'done') {
          continue
        }

        controller.enqueue(
          encoder.encode(createEventChunk('stage_change', { stage: stageInfo.stage })),
        )
        await wait(stageInfo.delay)
      }

      for (let index = 0; index < answer.length; index += 5) {
        controller.enqueue(
          encoder.encode(
            createEventChunk('token', { token: answer.slice(index, index + 5) }),
          ),
        )
        await wait(30)
      }

      controller.enqueue(encoder.encode(createEventChunk('sources', { sources })))
      controller.enqueue(encoder.encode(createEventChunk('done', { stage: 'done' })))
      controller.close()
    },
  })
}

function createDefaultSSEStream() {
  return createSSEStream({
    stages: [
      { stage: 'searching', delay: 1000 },
      { stage: 'drafting', delay: 600 },
      { stage: 'verifying', delay: 400 },
    ],
    answer: '해당 질문에 대한 정보를 찾지 못했습니다. 다른 질문을 입력해 주세요.',
    sources: [],
  })
}

export const handlers = [
  http.post('/api/auth/logout', () => HttpResponse.json({ success: true })),

  http.post('/api/chat', async ({ request }) => {
    const { question } = await request.json()
    const matchKey = Object.keys(mockChatResponses).find((key) => question.includes(key))

    const stream = matchKey
      ? createSSEStream(mockChatResponses[matchKey])
      : createDefaultSSEStream()

    return new HttpResponse(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
    })
  }),

  http.get('/api/preview/:sourceId', ({ params }) => {
    const source = allSources[params.sourceId]

    if (!source) {
      return HttpResponse.json({ error: '출처를 찾을 수 없습니다' }, { status: 404 })
    }

    return HttpResponse.json(source)
  }),
]

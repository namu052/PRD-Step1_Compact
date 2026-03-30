import { useEffect, useState } from 'react'
import { useChatStore } from '../../stores/chatStore'
import { useAuthStore } from '../../stores/authStore'
import SourceCard from './SourceCard'
import SourceDetail from './SourceDetail'

function SkeletonBlock() {
  return (
    <div className="space-y-3 rounded-lg border bg-white p-4 animate-pulse">
      <div className="h-4 w-16 rounded bg-gray-200" />
      <div className="h-5 w-3/4 rounded bg-gray-200" />
      <div className="h-4 w-full rounded bg-gray-200" />
      <div className="h-4 w-2/3 rounded bg-gray-200" />
    </div>
  )
}

export default function PreviewPanel() {
  const currentSources = useChatStore((state) => state.currentSources)
  const selectedSourceId = useChatStore((state) => state.selectedSourceId)
  const isStreaming = useChatStore((state) => state.isStreaming)
  const hasAskedQuestion = useChatStore((state) => state.hasAskedQuestion)
  const sessionId = useAuthStore((state) => state.sessionId)
  const [selectedSourceDetail, setSelectedSourceDetail] = useState(null)
  const [detailError, setDetailError] = useState(null)
  const [isDetailLoading, setIsDetailLoading] = useState(false)

  const selectedSource = currentSources.find((source) => source.id === selectedSourceId)

  useEffect(() => {
    let ignore = false

    async function loadSourceDetail() {
      if (!selectedSourceId || !sessionId) {
        setSelectedSourceDetail(null)
        setDetailError(null)
        setIsDetailLoading(false)
        return
      }

      setIsDetailLoading(true)
      setDetailError(null)

      try {
        const response = await fetch(
          `/api/preview/${encodeURIComponent(selectedSourceId)}?session_id=${encodeURIComponent(sessionId)}`,
        )
        if (response.status === 401) {
          useAuthStore.getState().resetSession()
          throw new Error('세션이 만료되었습니다. 다시 로그인해 주세요.')
        }

        if (!response.ok) {
          throw new Error('출처 상세 정보를 불러오지 못했습니다.')
        }

        const data = await response.json()
        if (!ignore) {
          setSelectedSourceDetail(data)
        }
      } catch (error) {
        if (!ignore) {
          setSelectedSourceDetail(null)
          setDetailError(error.message || '출처 상세 정보를 불러오지 못했습니다.')
        }
      } finally {
        if (!ignore) {
          setIsDetailLoading(false)
        }
      }
    }

    loadSourceDetail()

    return () => {
      ignore = true
    }
  }, [selectedSourceId, sessionId])

  if (selectedSource) {
    return (
      <div className="h-full overflow-y-auto bg-gray-50">
        <SourceDetail
          source={selectedSourceDetail ?? selectedSource}
          isLoading={isDetailLoading}
          error={detailError}
        />
      </div>
    )
  }

  const showEmptyHint = !hasAskedQuestion && !isStreaming
  const showSkeleton = isStreaming && currentSources.length === 0
  const showNoResults = hasAskedQuestion && !isStreaming && currentSources.length === 0

  return (
    <div className="h-full overflow-y-auto bg-gray-50 p-4">
      <h2 className="mb-4 text-base font-semibold text-gray-700">출처 및 관련 문서</h2>

      {showEmptyHint && (
        <div className="flex h-48 items-center justify-center text-center text-sm text-gray-400">
          질문을 입력하면 관련 법령과
          <br />
          해석례가 여기에 표시됩니다
        </div>
      )}

      {showSkeleton && (
        <div className="space-y-3">
          <SkeletonBlock />
          <SkeletonBlock />
          <SkeletonBlock />
        </div>
      )}

      {currentSources.length > 0 && (
        <div className="space-y-3">
          {currentSources.map((source) => (
            <SourceCard key={source.id} source={source} />
          ))}
        </div>
      )}

      {showNoResults && (
        <div className="flex h-48 items-center justify-center text-center text-sm text-gray-400">
          관련 출처를 찾지 못했습니다
        </div>
      )}
    </div>
  )
}

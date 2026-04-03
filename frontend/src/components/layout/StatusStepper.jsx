import { useChatStore } from '../../stores/chatStore'

const STAGES = [
  { key: 'searching', label: '자료 수집', icon: '🔍' },
  { key: 'answering', label: '답변 생성', icon: '✏️' },
  { key: 'done', label: '완료', icon: '✅' },
]

export default function StatusStepper() {
  const currentStage = useChatStore((s) => s.currentStage)

  const currentIdx = STAGES.findIndex(s => s.key === currentStage)

  return (
    <div className="h-14 bg-white border-t border-gray-200 flex items-center justify-center gap-2 px-8 shrink-0">
      {STAGES.map((stage, idx) => {
        const isPast = currentIdx > idx
        const isCurrent = currentIdx === idx && currentStage !== 'done'
        const isDone = currentStage === 'done' && idx === STAGES.length - 1

        let textClass = 'text-gray-300'
        let dotClass = 'bg-gray-300'

        if (isPast || isDone) {
          textClass = 'text-green-600'
          dotClass = 'bg-green-500'
        } else if (isCurrent) {
          textClass = 'text-blue-600 font-bold'
          dotClass = 'bg-blue-500 animate-pulse'
        }

        return (
          <div key={stage.key} className="flex items-center gap-2">
            {idx > 0 && (
              <div className={`w-8 h-0.5 ${isPast || isDone ? 'bg-green-400' : 'bg-gray-200'}`} />
            )}
            <div className="flex items-center gap-1.5">
              <span className={`w-2.5 h-2.5 rounded-full ${dotClass}`} />
              <span className={`text-xs whitespace-nowrap ${textClass}`}>
                {isPast ? '✓' : stage.icon} {stage.label}
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

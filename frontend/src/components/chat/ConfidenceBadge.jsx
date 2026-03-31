const BADGE_STYLES = {
  '매우 높음': 'bg-emerald-100 text-emerald-700',
  높음: 'bg-green-100 text-green-700',
  보통: 'bg-yellow-100 text-yellow-700',
  낮음: 'bg-red-100 text-red-700',
}

const BADGE_ICONS = {
  '매우 높음': '🟢',
  높음: '🟢',
  보통: '🟡',
  낮음: '🔴',
}

export default function ConfidenceBadge({ confidence }) {
  if (!confidence) {
    return null
  }

  const score = Math.round((confidence.score ?? 0) * 100)
  const label = confidence.label ?? '보통'
  const hint =
    label === '낮음'
      ? '실무 적용 전 반드시 원문 확인'
      : label === '보통'
        ? '일부 내용은 원문 확인 권장'
        : label === '높음'
          ? '주요 내용은 근거 확인 완료'
        : null

  return (
    <div className="mt-3 space-y-1">
      <div
        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${BADGE_STYLES[label] || BADGE_STYLES.보통}`}
      >
        <span>{BADGE_ICONS[label] || BADGE_ICONS.보통}</span>
        <span>답변 신뢰도: {label}</span>
        <span>{score}%</span>
      </div>
      {hint && <p className="text-xs text-gray-500">{hint}</p>}
    </div>
  )
}

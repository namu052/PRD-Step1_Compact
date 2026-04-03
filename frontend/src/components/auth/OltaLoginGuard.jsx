import { useAuthStore } from '../../stores/authStore'

export default function OltaLoginGuard() {
  const oltaLoggedIn = useAuthStore((state) => state.oltaLoggedIn)
  const oltaChecking = useAuthStore((state) => state.oltaChecking)
  const oltaMessage = useAuthStore((state) => state.oltaMessage)
  const openOltaForLogin = useAuthStore((state) => state.openOltaForLogin)
  const verifyOltaLogin = useAuthStore((state) => state.verifyOltaLogin)

  if (oltaLoggedIn) return null

  return (
    <div className="bg-amber-50 border-b border-amber-200 px-4 py-3">
      <div className="flex items-start gap-3 max-w-3xl mx-auto">
        <span className="text-2xl shrink-0 mt-0.5">🔐</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-amber-900 mb-1">
            OLTA 로그인이 필요합니다
          </p>
          <p className="text-xs text-amber-700 mb-2">
            자료 수집을 위해 OLTA(지방세법령포털)에 로그인해 주세요.
          </p>
          <ol className="text-xs text-amber-700 space-y-0.5 list-decimal list-inside mb-3">
            <li><strong>"OLTA 브라우저 열기"</strong> 버튼을 클릭하면 OLTA 브라우저 창이 활성화됩니다</li>
            <li>해당 브라우저에서 OLTA에 로그인하세요</li>
            <li>OLTA 우측 상단에 <strong>"로그아웃"</strong> 버튼이 보이면 로그인 완료입니다</li>
            <li>이 페이지로 돌아와 <strong>"로그인 완료 확인"</strong> 버튼을 클릭하세요</li>
          </ol>

          {oltaMessage && (
            <p className="text-xs text-red-600 mb-2">{oltaMessage}</p>
          )}

          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => void openOltaForLogin()}
              disabled={oltaChecking}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {oltaChecking ? '여는 중...' : 'OLTA 브라우저 열기'}
            </button>
            <button
              type="button"
              onClick={() => void verifyOltaLogin()}
              disabled={oltaChecking}
              className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {oltaChecking ? '확인 중...' : '로그인 완료 확인'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

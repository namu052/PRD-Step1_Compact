import { useAuthStore } from '../../stores/authStore'

export default function OltaLoginGuard() {
  const oltaChecking = useAuthStore((state) => state.oltaChecking)
  const oltaMessage = useAuthStore((state) => state.oltaMessage)
  const verifyOltaLogin = useAuthStore((state) => state.verifyOltaLogin)

  const handleOpenAndVerify = async () => {
    // olta-verify가 Playwright 브라우저를 앞으로 가져온 뒤 로그인 상태를 확인
    await verifyOltaLogin()
  }

  return (
    <div className="h-screen flex flex-col bg-gray-100">
      <header className="bg-slate-800 text-white px-6 py-3 shrink-0">
        <h1 className="text-lg font-semibold tracking-tight">
          AI 지방세 지식인
        </h1>
      </header>

      <div className="flex-1 flex items-center justify-center">
        <div className="bg-white rounded-xl shadow-lg p-8 max-w-md w-full mx-4 text-center">
          <div className="text-5xl mb-4">🔐</div>
          <h2 className="text-xl font-bold text-gray-800 mb-3">
            OLTA 로그인이 필요합니다
          </h2>
          <p className="text-sm text-gray-600 mb-2">
            자료 수집을 위해 OLTA(지방세법령포털)에<br />
            먼저 로그인해 주세요.
          </p>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4 text-left">
            <p className="text-sm text-blue-800 font-medium mb-2">로그인 방법</p>
            <ol className="text-xs text-blue-700 space-y-1 list-decimal list-inside">
              <li>아래 버튼을 클릭하면 <strong>OLTA 브라우저 창</strong>이 활성화됩니다</li>
              <li>해당 브라우저에서 OLTA에 로그인하세요</li>
              <li>우측 상단에 <strong>"로그아웃"</strong> 버튼이 보이면 로그인 완료</li>
              <li>이 페이지로 돌아와 다시 버튼을 클릭하면 자동 확인됩니다</li>
            </ol>
          </div>

          {oltaMessage && (
            <p className="text-sm text-red-500 mb-4">{oltaMessage}</p>
          )}

          <button
            type="button"
            onClick={() => void handleOpenAndVerify()}
            disabled={oltaChecking}
            className="w-full rounded-lg bg-blue-600 px-4 py-3 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {oltaChecking ? '확인 중...' : 'OLTA 브라우저 열기 / 로그인 확인'}
          </button>
        </div>
      </div>
    </div>
  )
}

import { useAuthStore } from '../../stores/authStore'

export default function TopBar() {
  const userName = useAuthStore((state) => state.userName)
  const sessionId = useAuthStore((state) => state.sessionId)
  const logout = useAuthStore((state) => state.logout)
  const oltaLoggedIn = useAuthStore((state) => state.oltaLoggedIn)
  const oltaChecking = useAuthStore((state) => state.oltaChecking)
  const openOltaForLogin = useAuthStore((state) => state.openOltaForLogin)

  return (
    <header className="bg-slate-800 text-white px-6 py-3 flex items-center justify-between shrink-0">
      <h1 className="text-lg font-semibold tracking-tight">
        AI 지방세 지식인
      </h1>
      <div className="flex items-center gap-3">
        {oltaLoggedIn ? (
          <span className="flex items-center gap-1.5 text-sm px-3 py-1 rounded bg-green-700 text-green-100">
            <span className="inline-block w-2 h-2 rounded-full bg-green-400" />
            OLTA 로그아웃
          </span>
        ) : (
          <button
            type="button"
            onClick={() => void openOltaForLogin()}
            disabled={oltaChecking}
            className="flex items-center gap-1.5 text-sm px-3 py-1 rounded bg-amber-600 hover:bg-amber-500 transition disabled:opacity-50"
          >
            <span className="inline-block w-2 h-2 rounded-full bg-amber-300 animate-pulse" />
            {oltaChecking ? '확인 중...' : 'OLTA 로그인'}
          </button>
        )}
        {sessionId && (
          <>
            <span className="text-sm text-slate-300">{userName}님</span>
            <button
              type="button"
              onClick={() => void logout()}
              className="text-sm px-3 py-1 rounded bg-red-600 hover:bg-red-700 transition"
            >
              로그아웃
            </button>
          </>
        )}
      </div>
    </header>
  )
}

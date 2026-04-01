import { useEffect } from 'react'
import { useAuthStore } from '../../stores/authStore'

export default function TopBar() {
  const userName = useAuthStore((state) => state.userName)
  const sessionId = useAuthStore((state) => state.sessionId)
  const logout = useAuthStore((state) => state.logout)
  const oltaLoggedIn = useAuthStore((state) => state.oltaLoggedIn)
  const oltaChecking = useAuthStore((state) => state.oltaChecking)
  const oltaMessage = useAuthStore((state) => state.oltaMessage)
  const checkOltaLogin = useAuthStore((state) => state.checkOltaLogin)
  const openOltaLogin = useAuthStore((state) => state.openOltaLogin)
  const verifyOltaLogin = useAuthStore((state) => state.verifyOltaLogin)

  useEffect(() => {
    if (sessionId) {
      checkOltaLogin()
    }
  }, [sessionId, checkOltaLogin])

  return (
    <header className="bg-slate-800 text-white px-6 py-3 flex items-center justify-between shrink-0">
      <h1 className="text-lg font-semibold tracking-tight">
        AI 지방세 지식인
      </h1>
      <div className="flex items-center gap-3">
        {/* OLTA 로그인 상태 */}
        {sessionId && (
          <div className="flex items-center gap-2">
            {oltaLoggedIn ? (
              <span className="text-xs px-2 py-1 rounded bg-green-700 text-green-100">
                OLTA 연결됨
              </span>
            ) : (
              <>
                <span className="text-xs px-2 py-1 rounded bg-yellow-700 text-yellow-100">
                  OLTA 미연결
                </span>
                {oltaMessage ? (
                  <button
                    type="button"
                    onClick={() => void verifyOltaLogin()}
                    disabled={oltaChecking}
                    className="text-xs px-2 py-1 rounded bg-blue-600 hover:bg-blue-700 transition disabled:opacity-50"
                  >
                    {oltaChecking ? '확인 중...' : '로그인 확인'}
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => void openOltaLogin()}
                    disabled={oltaChecking}
                    className="text-xs px-2 py-1 rounded bg-blue-600 hover:bg-blue-700 transition disabled:opacity-50"
                  >
                    {oltaChecking ? '확인 중...' : 'OLTA 로그인'}
                  </button>
                )}
              </>
            )}
          </div>
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

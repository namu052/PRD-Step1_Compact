import { useAuthStore } from '../../stores/authStore'

export default function TopBar() {
  const userName = useAuthStore((state) => state.userName)
  const sessionId = useAuthStore((state) => state.sessionId)
  const logout = useAuthStore((state) => state.logout)

  return (
    <header className="bg-slate-800 text-white px-6 py-3 flex items-center justify-between shrink-0">
      <h1 className="text-lg font-semibold tracking-tight">
        🏛️ AI 지방세 지식인
      </h1>
      <div className="flex items-center gap-4">
        <a
          href="https://www.olta.re.kr"
          target="_blank"
          rel="noreferrer"
          className="text-sm px-3 py-1 rounded bg-slate-700 hover:bg-slate-600 transition"
        >
          OLTA 열기
        </a>
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

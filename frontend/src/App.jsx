import { useEffect } from 'react'
import AppShell from './components/layout/AppShell'
import OltaLoginGuard from './components/auth/OltaLoginGuard'
import { useAuthStore } from './stores/authStore'
import { apiUrl } from './lib/api'

function App() {
  const bootstrapSession = useAuthStore((state) => state.bootstrapSession)
  const oltaLoggedIn = useAuthStore((state) => state.oltaLoggedIn)
  const sessionId = useAuthStore((state) => state.sessionId)
  const checkOltaLogin = useAuthStore((state) => state.checkOltaLogin)

  // 1) APP 시작 시 OLTA 로그인 상태 확인 (백엔드 Playwright 브라우저가 OLTA를 연다)
  useEffect(() => {
    void checkOltaLogin()
  }, [checkOltaLogin])

  // 2) OLTA 로그인 확인되면 자동으로 세션 부트스트랩
  useEffect(() => {
    if (oltaLoggedIn && !sessionId) {
      void bootstrapSession()
    }
  }, [oltaLoggedIn, sessionId, bootstrapSession])

  // 3) 탭 닫기 시 로그아웃
  useEffect(() => {
    const handleBeforeUnload = () => {
      const { sessionId: sid } = useAuthStore.getState()
      if (sid) {
        navigator.sendBeacon(
          apiUrl('/api/auth/logout'),
          new Blob(
            [JSON.stringify({ session_id: sid })],
            { type: 'application/json' },
          ),
        )
      }
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [])

  // OLTA 미로그인 상태면 로그인 안내 화면 표시
  if (!oltaLoggedIn) {
    return <OltaLoginGuard />
  }

  return <AppShell />
}

export default App

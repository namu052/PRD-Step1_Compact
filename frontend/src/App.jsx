import { useEffect } from 'react'
import AppShell from './components/layout/AppShell'
import GpkiLoginModal from './components/auth/GpkiLoginModal'
import { useAuthStore } from './stores/authStore'

const OLTA_URL = 'https://www.olta.re.kr'
const OLTA_OPENED_KEY = 'olta-window-opened'

function App() {
  const bootstrapSession = useAuthStore((state) => state.bootstrapSession)
  const isInitializing = useAuthStore((state) => state.isInitializing)
  const sessionId = useAuthStore((state) => state.sessionId)

  useEffect(() => {
    if (sessionStorage.getItem(OLTA_OPENED_KEY) === 'true') {
      void bootstrapSession()
      return
    }

    sessionStorage.setItem(OLTA_OPENED_KEY, 'true')
    window.open(OLTA_URL, '_blank', 'noopener,noreferrer')
    void bootstrapSession()
  }, [bootstrapSession])

  useEffect(() => {
    const handleBeforeUnload = () => {
      const { sessionId: currentSessionId } = useAuthStore.getState()
      if (!currentSessionId) {
        return
      }

      navigator.sendBeacon(
        '/api/auth/logout',
        new Blob([JSON.stringify({ session_id: currentSessionId })], {
          type: 'application/json',
        }),
      )
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [])

  return (
    <>
      <AppShell />
      {!sessionId && !isInitializing && <GpkiLoginModal />}
    </>
  )
}

export default App

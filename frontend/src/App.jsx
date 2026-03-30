import { useEffect } from 'react'
import AppShell from './components/layout/AppShell'
import { useAuthStore } from './stores/authStore'

const OLTA_URL = 'https://www.olta.re.kr'
const OLTA_OPENED_KEY = 'olta-window-opened'

function App() {
  const bootstrapSession = useAuthStore((state) => state.bootstrapSession)
  const logout = useAuthStore((state) => state.logout)

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
      void logout()
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [logout])

  return <AppShell />
}

export default App

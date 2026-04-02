import { create } from 'zustand'
import { apiUrl } from '../lib/api'

export const useAuthStore = create((set) => ({
  isLoggedIn: false,
  userName: null,
  sessionId: null,
  isInitializing: false,
  loginError: null,

  bootstrapSession: async () => {
    set({ isInitializing: true, loginError: null })
    try {
      const response = await fetch(apiUrl('/api/auth/gpki'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cert_id: 'cert_001', password: 'test1234' }),
      })
      const data = await response.json()

      if (!response.ok || !data.success) {
        set({
          isInitializing: false,
          loginError: data.error ?? '로그인 중 오류가 발생했습니다.',
        })
        return
      }

      set({
        isLoggedIn: true,
        userName: data.user_name,
        sessionId: data.session_id,
        isInitializing: false,
        loginError: null,
      })
    } catch {
      set({
        isInitializing: false,
        loginError: '세션 초기화 중 오류가 발생했습니다.',
      })
    }
  },

  logout: async () => {
    try {
      const { sessionId } = useAuthStore.getState()
      if (sessionId) {
        await fetch(apiUrl('/api/auth/logout'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId }),
        })
      }
    } catch {
      // Session reset should still happen locally.
    }

    set({
      isLoggedIn: false,
      userName: null,
      sessionId: null,
      loginError: null,
      isInitializing: false,
      oltaLoggedIn: false,
    })
  },

  // OLTA 로그인 상태 관리
  oltaLoggedIn: false,
  oltaChecking: false,
  oltaMessage: null,

  checkOltaLogin: async () => {
    set({ oltaChecking: true, oltaMessage: null })
    try {
      const res = await fetch(apiUrl('/api/auth/olta-status'))
      const data = await res.json()
      set({ oltaLoggedIn: data.logged_in, oltaChecking: false })
      return data.logged_in
    } catch {
      set({ oltaChecking: false, oltaMessage: 'OLTA 상태 확인 실패' })
      return false
    }
  },

  verifyOltaLogin: async () => {
    set({ oltaChecking: true, oltaMessage: null })
    try {
      const res = await fetch(apiUrl('/api/auth/olta-verify'), { method: 'POST' })
      const data = await res.json()
      set({
        oltaLoggedIn: data.success,
        oltaChecking: false,
        oltaMessage: data.success ? null : data.message,
      })
      return data.success
    } catch {
      set({ oltaChecking: false, oltaMessage: 'OLTA 로그인 확인 실패' })
      return false
    }
  },
}))

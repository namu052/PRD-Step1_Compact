import { create } from 'zustand'

const loggedOutState = {
  isLoggedIn: false,
  userName: null,
  sessionId: null,
  loginError: null,
  isInitializing: false,
  isLoggingIn: false,
}

export const useAuthStore = create((set) => ({
  isLoggedIn: false,
  userName: null,
  sessionId: null,
  isInitializing: false,
  isLoggingIn: false,
  loginError: null,

  bootstrapSession: async () => {
    set({ isInitializing: true, loginError: null })
    try {
      const response = await fetch('/api/auth/gpki', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cert_id: 'cert_001', password: 'test1234' }),
      })
      const data = await response.json()

      if (!response.ok || !data.success) {
        set({
          isLoggedIn: false,
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
        isLoggedIn: false,
        isInitializing: false,
        loginError: '세션 초기화 중 오류가 발생했습니다.',
      })
    }
  },

  login: async (certId, password) => {
    set({ isLoggingIn: true, loginError: null })

    try {
      const response = await fetch('/api/auth/gpki', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cert_id: certId, password }),
      })
      const data = await response.json()

      if (!response.ok || !data.success) {
        set({
          isLoggedIn: false,
          isLoggingIn: false,
          loginError: data.error ?? '로그인 중 오류가 발생했습니다.',
        })
        return false
      }

      set({
        isLoggedIn: true,
        userName: data.user_name,
        sessionId: data.session_id,
        isInitializing: false,
        isLoggingIn: false,
        loginError: null,
      })
      return true
    } catch {
      set({
        isLoggedIn: false,
        isLoggingIn: false,
        loginError: '로그인 중 오류가 발생했습니다.',
      })
      return false
    }
  },

  logout: async () => {
    try {
      const { sessionId } = useAuthStore.getState()
      if (sessionId) {
        await fetch('/api/auth/logout', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId }),
        })
      }
    } catch {
      // Session reset should still happen locally.
    }

    set(loggedOutState)
  },

  resetSession: () => set(loggedOutState),

  clearError: () => set({ loginError: null }),
}))

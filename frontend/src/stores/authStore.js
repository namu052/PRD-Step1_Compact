import { create } from 'zustand'

export const useAuthStore = create((set) => ({
  isLoggedIn: true,
  userName: '홍길동',
  sessionId: null,
  isInitializing: false,
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
        await fetch('/api/auth/logout', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId }),
        })
      }
    } catch {
      // Session reset should still happen locally.
    }

    set({
      isLoggedIn: true,
      userName: '홍길동',
      sessionId: null,
      loginError: null,
      isInitializing: false,
    })
  },
}))

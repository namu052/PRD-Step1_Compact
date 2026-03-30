import { useState } from 'react'
import { useAuthStore } from '../../stores/authStore'
import CertSelector from './CertSelector'

export default function GpkiLoginModal() {
  const isLoggingIn = useAuthStore((state) => state.isLoggingIn)
  const loginError = useAuthStore((state) => state.loginError)
  const login = useAuthStore((state) => state.login)
  const clearError = useAuthStore((state) => state.clearError)
  const [selectedCertId, setSelectedCertId] = useState(null)
  const [password, setPassword] = useState('')

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (!selectedCertId || !password) {
      return
    }

    await login(selectedCertId, password)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="mx-4 w-full max-w-md rounded-xl bg-white p-6 shadow-2xl">
        <h2 className="mb-6 text-center text-xl font-bold">행정전자서명 인증 로그인</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <CertSelector
            selectedCertId={selectedCertId}
            onSelect={(id) => {
              setSelectedCertId(id)
              clearError()
            }}
          />

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              인증서 비밀번호
            </label>
            <input
              type="password"
              value={password}
              onChange={(event) => {
                setPassword(event.target.value)
                clearError()
              }}
              placeholder="비밀번호를 입력하세요"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isLoggingIn}
            />
          </div>

          {loginError && <p className="text-center text-sm text-red-500">{loginError}</p>}

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={() => {
                setSelectedCertId(null)
                setPassword('')
                clearError()
              }}
              className="flex-1 rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 transition hover:bg-gray-50"
            >
              취소
            </button>
            <button
              type="submit"
              className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm text-white transition hover:bg-blue-700 disabled:opacity-50"
              disabled={!selectedCertId || !password || isLoggingIn}
            >
              {isLoggingIn ? '인증 중...' : '확인'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

import { useEffect, useState } from 'react'

export default function CertSelector({ selectedCertId, onSelect }) {
  const [certs, setCerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [storageType, setStorageType] = useState('hard')

  useEffect(() => {
    const loadCerts = async () => {
      setLoading(true)
      setError(null)

      try {
        const response = await fetch('/api/auth/certs')
        const data = await response.json()

        if (!response.ok) {
          throw new Error(data.error ?? '인증서 목록을 불러올 수 없습니다')
        }

        setCerts(Array.isArray(data) ? data : [])
      } catch {
        setError('인증서 목록을 불러올 수 없습니다')
      } finally {
        setLoading(false)
      }
    }

    void loadCerts()
  }, [])

  return (
    <div>
      <div className="mb-3">
        <span className="mb-2 block text-sm font-medium text-gray-700">인증서 저장 위치</span>
        <div className="flex gap-4">
          <label className="flex cursor-pointer items-center gap-1.5 text-sm">
            <input
              type="radio"
              name="storageType"
              value="hard"
              checked={storageType === 'hard'}
              onChange={() => setStorageType('hard')}
              className="accent-blue-600"
            />
            하드디스크/이동식
          </label>
          <label className="flex cursor-pointer items-center gap-1.5 text-sm">
            <input
              type="radio"
              name="storageType"
              value="token"
              checked={storageType === 'token'}
              onChange={() => setStorageType('token')}
              className="accent-blue-600"
            />
            보안토큰
          </label>
        </div>
      </div>

      {loading && <div className="py-4 text-center text-sm text-gray-400">인증서 로딩 중...</div>}
      {error && <div className="py-4 text-center text-sm text-red-500">{error}</div>}

      <div className="max-h-48 space-y-2 overflow-y-auto">
        {certs.map((cert) => (
          <button
            key={cert.id}
            type="button"
            onClick={() => onSelect(cert.id)}
            className={`w-full rounded-lg border-2 p-3 text-left transition ${
              selectedCertId === cert.id
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-200 bg-white hover:border-gray-300'
            }`}
          >
            <div className="text-sm font-semibold text-gray-900">{cert.owner}</div>
            <div className="mt-1 text-xs text-gray-600">CN: {cert.cn}</div>
            <div className="mt-1 text-xs text-gray-500">부서: {cert.department}</div>
            <div className="mt-1 text-xs text-gray-500">
              유효기간: {cert.validFrom} ~ {cert.validTo}
            </div>
            <div className="mt-1 text-xs text-gray-400">S/N: {cert.serial}</div>
          </button>
        ))}

        {!loading && !error && certs.length === 0 && (
          <div className="py-4 text-center text-sm text-gray-400">인증서를 찾을 수 없습니다</div>
        )}
      </div>
    </div>
  )
}

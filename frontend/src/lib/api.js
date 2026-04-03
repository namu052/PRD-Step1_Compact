const defaultApiBaseUrl = import.meta.env.DEV ? 'http://127.0.0.1:8001' : ''

const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL || defaultApiBaseUrl

export function apiUrl(path) {
  if (/^https?:\/\//.test(path)) {
    return path
  }

  const normalizedBaseUrl = configuredApiBaseUrl.endsWith('/')
    ? configuredApiBaseUrl.slice(0, -1)
    : configuredApiBaseUrl
  const normalizedPath = path.startsWith('/') ? path : `/${path}`

  return `${normalizedBaseUrl}${normalizedPath}`
}

import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { execFileSync } from 'node:child_process'

const GPKI_CERT_PATH = path.join(
  process.env.HOME || process.env.USERPROFILE || '',
  'GPKI/Certificate/class2',
)
const NULL_DEVICE = process.platform === 'win32' ? 'NUL' : '/dev/null'

function parseSubject(subjectLine) {
  const normalized = subjectLine
    .replace(/^subject=/, '')
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean)

  const values = {}

  for (const part of normalized) {
    const [key, ...rest] = part.split('=')
    if (!key || rest.length === 0) {
      continue
    }

    const value = rest.join('=').trim()
    if (!values[key]) {
      values[key] = []
    }
    values[key].push(value)
  }

  return values
}

function extractOwnerName(cn, fallback) {
  if (!cn) {
    return fallback
  }

  const nameMatch = cn.match(/\d*([가-힣]+)\d*/)
  return nameMatch ? nameMatch[1] : cn
}

function readCertificateInfo(certId) {
  const certPath = path.join(GPKI_CERT_PATH, `${certId}_sig.cer`)
  const output = execFileSync(
    'openssl',
    [
      'x509',
      '-in',
      certPath,
      '-inform',
      'DER',
      '-subject',
      '-serial',
      '-dates',
      '-nameopt',
      'RFC2253',
      '-noout',
    ],
    { encoding: 'utf8' },
  )

  let subject = ''
  let serial = ''
  let validFrom = ''
  let validTo = ''

  for (const line of output.trim().split('\n')) {
    if (line.startsWith('subject=')) {
      subject = line
    } else if (line.startsWith('serial=')) {
      serial = line.slice('serial='.length).trim()
    } else if (line.startsWith('notBefore=')) {
      validFrom = line.slice('notBefore='.length).trim()
    } else if (line.startsWith('notAfter=')) {
      validTo = line.slice('notAfter='.length).trim()
    }
  }

  const subjectValues = parseSubject(subject)
  const cn = subjectValues.CN?.[0] || certId
  const department = (subjectValues.OU || [])
    .filter((value) => value !== 'GPKI' && value !== 'people')
    .join(' ') || '미상'

  return {
    id: certId,
    owner: extractOwnerName(cn, certId),
    cn,
    department,
    validFrom,
    validTo,
    serial,
  }
}

function collectCertificates() {
  if (!fs.existsSync(GPKI_CERT_PATH)) {
    console.warn(`[gpkiPlugin] 인증서 폴더가 존재하지 않습니다: ${GPKI_CERT_PATH}`)
    return []
  }

  return fs
    .readdirSync(GPKI_CERT_PATH)
    .filter((fileName) => fileName.endsWith('_sig.cer'))
    .map((fileName) => fileName.replace('_sig.cer', ''))
    .sort((left, right) => left.localeCompare(right, 'ko'))
    .map((certId) => readCertificateInfo(certId))
}

function verifyPrivateKey(certId, password) {
  const keyPath = path.join(GPKI_CERT_PATH, `${certId}_sig.key`)

  if (!fs.existsSync(keyPath)) {
    throw new Error('인증서 키 파일을 찾을 수 없습니다')
  }

  execFileSync(
    'openssl',
    [
      'pkcs8',
      '-in',
      keyPath,
      '-inform',
      'DER',
      '-passin',
      `pass:${password}`,
      '-outform',
      'PEM',
      '-out',
      NULL_DEVICE,
    ],
    {
      encoding: 'utf8',
      stdio: 'pipe',
      timeout: 5000,
    },
  )
}

function sendJson(res, statusCode, payload) {
  res.statusCode = statusCode
  res.setHeader('Content-Type', 'application/json; charset=utf-8')
  res.end(JSON.stringify(payload))
}

function gpkiPlugin() {
  return {
    name: 'gpki-cert-api',
    configureServer(server) {
      server.middlewares.use('/api/auth/certs', (req, res, next) => {
        if (req.method !== 'GET') {
          return next()
        }

        try {
          return sendJson(res, 200, collectCertificates())
        } catch (error) {
          return sendJson(res, 500, {
            error: `인증서 폴더를 읽을 수 없습니다: ${error.message}`,
          })
        }
      })

      server.middlewares.use('/api/auth/gpki', (req, res, next) => {
        if (req.method !== 'POST') {
          return next()
        }

        let body = ''
        req.on('data', (chunk) => {
          body += chunk
        })

        req.on('end', () => {
          try {
            const { cert_id: certId, password } = JSON.parse(body || '{}')

            if (!certId || !password) {
              return sendJson(res, 400, { error: 'cert_id와 password가 필요합니다' })
            }

            try {
              verifyPrivateKey(certId, password)
              const certInfo = readCertificateInfo(certId)
              return sendJson(res, 200, {
                success: true,
                user_name: certInfo.owner,
                session_id: `session_${Date.now()}`,
                cert_cn: certInfo.cn,
              })
            } catch (error) {
              if (error.message === '인증서 키 파일을 찾을 수 없습니다') {
                return sendJson(res, 404, { success: false, error: error.message })
              }

              return sendJson(res, 401, {
                success: false,
                error: '비밀번호가 일치하지 않습니다',
              })
            }
          } catch {
            return sendJson(res, 400, { error: '잘못된 요청입니다' })
          }
        })
      })
    },
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const useMockFrontend = env.VITE_USE_MOCK === 'true'

  return {
    plugins: useMockFrontend ? [react(), tailwindcss(), gpkiPlugin()] : [react(), tailwindcss()],
    server: {
      proxy: {
        '/api': 'http://127.0.0.1:8000',
      },
    },
  }
})

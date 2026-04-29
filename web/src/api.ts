const TOKEN_KEY = 'ypbrief-auth-token'

export const getAuthToken = () => localStorage.getItem(TOKEN_KEY) || ''

export const setAuthToken = (token: string) => {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

const statusText = (response: Response) => `${response.status} ${response.statusText || 'Request failed'}`.trim()

const readErrorMessage = async (response: Response): Promise<string> => {
  const contentType = response.headers.get('content-type') || ''
  const body = await response.text()
  if (contentType.includes('application/json')) {
    try {
      const parsed = JSON.parse(body)
      if (typeof parsed?.detail === 'string') return parsed.detail
      if (Array.isArray(parsed?.detail)) {
        return parsed.detail.map((item: { msg?: string } | string) => (typeof item === 'string' ? item : item?.msg || String(item))).join('; ')
      }
      if (typeof parsed?.message === 'string') return parsed.message
      if (typeof parsed?.error === 'string') return parsed.error
    } catch {
      // Fall through to the compact HTTP error below.
    }
  }
  if (/^\s*<!doctype html/i.test(body) || /^\s*<html/i.test(body)) {
    const title = body.match(/<title>(.*?)<\/title>/is)?.[1]?.replace(/\s+/g, ' ').trim()
    return title ? `${statusText(response)} · ${title}` : `HTTP ${statusText(response)}`
  }
  const compact = body.replace(/\s+/g, ' ').trim()
  return compact ? compact.slice(0, 240) : `HTTP ${statusText(response)}`
}

export const api = async <T,>(path: string, init?: RequestInit): Promise<T> => {
  const token = getAuthToken()
  const response = await fetch(`/api${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
    ...init,
  })
  if (response.status === 401) {
    setAuthToken('')
    window.dispatchEvent(new Event('ypbrief-auth-required'))
  }
  if (!response.ok) throw new Error(await readErrorMessage(response))
  return response.json()
}

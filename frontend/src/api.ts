export type Movie = { id: number; title: string; director: string; seats_available: number; poster_path: string; overview?: string | null; release_date?: string | null; rating?: number | null }
export type User = { id: number; username: string; email: string; is_admin: boolean }
export type Screening = { id: number; movie_id: number; starts_at: string; auditorium: string; capacity: number; seats_reserved: number; seats_available: number; price_paise: number; currency: string; movie?: Movie }
export type Booking = { id: number; user_id: number; screening_id: number; seats_booked: number; status: string; amount_paise: number; expires_at: string | null; razorpay_order_id: string | null; razorpay_payment_id: string | null; calendar_event_id: string | null; screening: Screening }
export type PaymentOrder = { booking: Booking; key_id: string; order_id: string; amount: number; currency: string }

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = sessionStorage.getItem('cinebook-token')
  const headers = new Headers(options.headers)
  if (options.body && typeof options.body === 'string') headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(path, { ...options, headers })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const detail = body.detail
    throw new Error(typeof detail === 'string' ? detail : `Request failed (${response.status})`)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export async function signIn(username: string, password: string) {
  const form = new URLSearchParams({ username, password })
  const result = await api<{ access_token: string }>('/api/users/token', { method: 'POST', body: form })
  sessionStorage.setItem('cinebook-token', result.access_token)
  try { return await api<User>('/api/users/me') } catch (error) { sessionStorage.removeItem('cinebook-token'); throw error }
}

export async function signUp(username: string, email: string, password: string) {
  await api('/api/users', { method: 'POST', body: JSON.stringify({ username, email, password }) })
  return signIn(username, password)
}

export function rupees(paise: number) {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(paise / 100)
}

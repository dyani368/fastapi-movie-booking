import { createContext, FormEvent, useContext, useEffect, useRef, useState } from 'react'
import { Link, Navigate, Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, CalendarDays, Check, Clapperboard, Film, LogIn, LogOut, Search, Ticket, UserRound, X } from 'lucide-react'
import { api, Booking, Movie, PaymentOrder, Screening, rupees, signIn, signUp, User } from './api'

type AuthState = { user: User | null; busy: boolean; login: (name: string, password: string) => Promise<void>; register: (name: string, email: string, password: string) => Promise<void>; logout: () => void }
const AuthContext = createContext<AuthState | null>(null)
const useAuth = () => { const value = useContext(AuthContext); if (!value) throw new Error('Auth provider is missing'); return value }
declare global { interface Window { Razorpay?: new (options: Record<string, unknown>) => { open: () => void } } }
let razorpayLoader: Promise<NonNullable<Window['Razorpay']>> | null = null

function loadRazorpay(): Promise<NonNullable<Window['Razorpay']>> {
  if (window.Razorpay) return Promise.resolve(window.Razorpay)
  if (!razorpayLoader) {
    razorpayLoader = new Promise((resolve, reject) => {
      const script = document.createElement('script')
      script.src = 'https://checkout.razorpay.com/v1/checkout.js'
      script.async = true
      script.onload = () => window.Razorpay ? resolve(window.Razorpay) : reject(new Error('Razorpay checkout did not load'))
      script.onerror = () => { razorpayLoader = null; reject(new Error('Could not load Razorpay checkout')) }
      document.head.appendChild(script)
    })
  }
  return razorpayLoader
}

function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [busy, setBusy] = useState(true)
  useEffect(() => {
    if (!sessionStorage.getItem('cinebook-token')) { setBusy(false); return }
    api<User>('/api/users/me').then(setUser).catch(() => sessionStorage.removeItem('cinebook-token')).finally(() => setBusy(false))
  }, [])
  const login = async (name: string, password: string) => { setUser(await signIn(name, password)) }
  const register = async (name: string, email: string, password: string) => { setUser(await signUp(name, email, password)) }
  const logout = () => { sessionStorage.removeItem('cinebook-token'); setUser(null) }
  return <AuthContext.Provider value={{ user, busy, login, register, logout }}>{children}</AuthContext.Provider>
}

function Header() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  return <header className="topbar"><div className="nav-inner">
    <Link to="/" className="brand"><span className="brand-mark"><Clapperboard size={19} /></span>cinebook</Link>
    <nav><Link to="/" className="nav-link">Movies</Link>{user && <Link to="/bookings" className="nav-link">My tickets</Link>}{user?.is_admin && <Link to="/admin" className="nav-link">Manage</Link>}</nav>
    <div className="nav-actions">{user ? <><span className="user-greeting"><UserRound size={15} /> {user.username}</span><button className="button button-quiet button-small" onClick={() => { logout(); navigate('/') }}><LogOut size={15} /> Sign out</button></> : <Link className="button button-outline button-small" to="/login"><LogIn size={15} /> Sign in</Link>}</div>
  </div></header>
}

function App() {
  return <AuthProvider><div className="app-shell"><Header /><main><Routes>
    <Route path="/" element={<Home />} /><Route path="/movies/:id" element={<MovieDetail />} />
    <Route path="/login" element={<AuthPage mode="login" />} /><Route path="/register" element={<AuthPage mode="register" />} />
    <Route path="/bookings" element={<BookingsPage />} /><Route path="/admin" element={<AdminPage />} /><Route path="/oauth/callback" element={<CalendarOAuthCallback />} /><Route path="*" element={<NotFound />} />
  </Routes></main><footer><span>cinebook</span><span>Find your next favorite film.</span></footer></div></AuthProvider>
}

function Home() {
  const [movies, setMovies] = useState<Movie[]>([])
  const [search, setSearch] = useState('')
  const [availableOnly, setAvailableOnly] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setLoading(true); setError('')
      const query = new URLSearchParams()
      if (search.trim()) query.set('search', search.trim())
      if (availableOnly) query.set('available_only', 'true')
      api<Movie[]>(`/api/movies?${query}`).then(setMovies).catch(err => setError(err.message)).finally(() => setLoading(false))
    }, 200)
    return () => window.clearTimeout(timer)
  }, [search, availableOnly])
  return <>
    <section className="hero"><div className="hero-copy"><span className="eyebrow"><span className="live-dot" /> YOUR MOVIE NIGHT, SORTED</span><h1>Good stories.<br /><span>Great seats.</span></h1><p>Find a film, pick a showtime, and make a night of it.</p><a className="button button-primary" href="#catalog">Explore movies <ArrowRight size={17} /></a></div><div className="hero-art" aria-hidden="true"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="ticket-art"><Film size={49} strokeWidth={1.25} /><span>TONIGHT<br />IS A GOOD NIGHT</span></div><span className="spark spark-a">✦</span><span className="spark spark-b">✦</span><span className="spark spark-c">✧</span></div><div className="hero-bottom"><span><strong>01</strong> Browse the collection</span><span><strong>02</strong> Choose a showtime</span><span><strong>03</strong> Enjoy the show</span></div></section>
    <section className="catalog" id="catalog"><div className="section-heading"><div><span className="eyebrow">NOW SHOWING</span><h2>Pick your next film</h2><p>A little something for every kind of night.</p></div><span className="movie-count">{movies.length} {movies.length === 1 ? 'film' : 'films'}</span></div>
      <div className="catalog-tools"><label className="search-box"><Search size={18} /><input aria-label="Search movies" placeholder="Search by title or director" value={search} onChange={e => setSearch(e.target.value)} />{search && <button aria-label="Clear search" onClick={() => setSearch('')}><X size={16} /></button>}</label><label className="toggle"><input type="checkbox" checked={availableOnly} onChange={e => setAvailableOnly(e.target.checked)} /><span className="toggle-track" /><span>Tickets available</span></label></div>
      {error && <div className="notice notice-error">{error}. Is the FastAPI server running?</div>}
      {loading ? <div className="loading"><span className="spinner" /> Loading films…</div> : movies.length ? <div className="movie-grid">{movies.map((movie, index) => <MovieCard key={movie.id} movie={movie} index={index} />)}</div> : <div className="empty-state"><Film size={28} /><h3>No films found</h3><p>Try a different search or clear the availability filter.</p><button className="button button-outline" onClick={() => { setSearch(''); setAvailableOnly(false) }}>Clear filters</button></div>}
    </section>
  </>
}

function MovieCard({ movie, index }: { movie: Movie; index: number }) {
  const palettes = ['poster-violet', 'poster-blue', 'poster-rose', 'poster-amber']
  return <Link to={`/movies/${movie.id}`} className="movie-card"><div className={`poster ${palettes[index % palettes.length]}`}>
    <img src={movie.poster_path || '/static/images/default_movie.jpg'} alt="" onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none' }} />
    <span className="poster-chip"><Film size={13} /> FEATURED</span><span className="poster-title">{movie.title}</span><span className="poster-decoration">✦</span>
  </div><div className="movie-info"><div><h3>{movie.title}</h3><p>Directed by {movie.director}</p></div><span className={`availability ${movie.seats_available ? '' : 'sold-out'}`}>{movie.seats_available ? `${movie.seats_available} seats` : 'Sold out'}</span></div><span className="card-action">View film <ArrowRight size={15} /></span></Link>
}

function MovieDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [movie, setMovie] = useState<Movie | null>(null)
  const [screenings, setScreenings] = useState<Screening[]>([])
  const [screeningId, setScreeningId] = useState<number | null>(null)
  const [seats, setSeats] = useState(1)
  const [busy, setBusy] = useState(false)
  const [bookingAttempt, setBookingAttempt] = useState<{ key: string; screeningId: number; seats: number } | null>(null)
  const [message, setMessage] = useState('')
  const [paymentConfirmed, setPaymentConfirmed] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    setPaymentConfirmed(false); setMessage('')
    Promise.all([api<Movie>(`/api/movies/${id}`), api<Screening[]>(`/api/movies/${id}/screenings`)]).then(([film, shows]) => {
      setMovie(film); setScreenings(shows); setScreeningId(shows.find(show => show.seats_available > 0)?.id ?? null)
    }).catch(err => setError(err.message))
  }, [id])
  async function book(event: FormEvent) {
    event.preventDefault()
    if (!user) { navigate('/login', { state: { from: `/movies/${id}` } }); return }
    if (!movie || !screeningId) return
    setBusy(true); setError(''); setMessage('')
    try {
      const RazorpayCheckout = await loadRazorpay()
      const currentKey = bookingAttempt?.screeningId === screeningId && bookingAttempt.seats === seats ? bookingAttempt.key : crypto.randomUUID()
      setBookingAttempt({ key: currentKey, screeningId, seats })
      const order = await api<PaymentOrder>('/api/bookings', { method: 'POST', headers: { 'Idempotency-Key': currentKey }, body: JSON.stringify({ screening_id: screeningId, seats_booked: seats }) })
      const checkout = new RazorpayCheckout({
        key: order.key_id, amount: order.amount, currency: order.currency, name: 'Cinebook', description: `${movie.title} · ${seats} ticket(s)`, order_id: order.order_id,
        prefill: { name: user.username, email: user.email }, theme: { color: '#7956d8' },
        handler: async (result: Record<string, string>) => {
          try {
            const status = await api<{ status: string }>('/api/payments/verify', { method: 'POST', body: JSON.stringify(result) })
            setMessage(status.status === 'confirmed' ? 'Payment confirmed. Your tickets are ready!' : `Payment received; booking status: ${status.status}.`)
            if (status.status === 'confirmed') { setBookingAttempt(null); setPaymentConfirmed(true) }
            api<Screening[]>(`/api/movies/${id}/screenings`).then(setScreenings).catch(() => {})
          } catch (err) { setError(err instanceof Error ? err.message : 'Payment verification failed') }
          finally { setBusy(false) }
        },
        modal: { ondismiss: () => setBusy(false) },
      })
      checkout.open()
    }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not complete booking'); setBusy(false) }
  }
  if (!movie && !error) return <div className="loading"><span className="spinner" /> Loading film…</div>
  if (!movie) return <div className="page-wrap"><div className="notice notice-error">{error}</div><Link to="/" className="text-link"><ArrowLeft size={16} /> Back to films</Link></div>
  return <div className="page-wrap"><Link to="/" className="back-link"><ArrowLeft size={16} /> All films</Link><div className="detail-layout"><div className="detail-poster poster-violet"><img src={movie.poster_path || '/static/images/default_movie.jpg'} alt="" onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none' }} /><Film size={72} strokeWidth={1} /></div><section className="detail-content"><span className="eyebrow">NOW SHOWING</span><h1>{movie.title}</h1><p className="detail-director">A film by <strong>{movie.director}</strong></p>{movie.overview && <p className="detail-copy">{movie.overview}</p>}<div className="detail-meta">{movie.release_date && <span><CalendarDays size={17} /> {movie.release_date}</span>}{movie.rating != null && <span>TMDB ★ {movie.rating.toFixed(1)}</span>}<span><Ticket size={17} /> {movie.seats_available} seats left</span></div>
    <form className="booking-box" onSubmit={book}><h2>Choose a screening</h2>{screenings.length ? <div className="time-options">{screenings.map(show => <button type="button" key={show.id} disabled={busy || show.seats_available < 1} className={`time-option ${screeningId === show.id ? 'selected' : ''}`} onClick={() => setScreeningId(show.id)}>{new Date(show.starts_at).toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}<small>{show.seats_available} seats · {rupees(show.price_paise)}</small></button>)}</div> : <p className="form-hint">No upcoming screenings are scheduled yet.</p>}<label className="field-label" htmlFor="seats">Tickets</label><div className="seat-control"><button type="button" aria-label="Remove one ticket" disabled={busy || seats <= 1} onClick={() => setSeats(value => value - 1)}>−</button><span>{seats} {seats === 1 ? 'ticket' : 'tickets'}</span><button type="button" aria-label="Add one ticket" disabled={busy || seats >= Math.min(8, screenings.find(show => show.id === screeningId)?.seats_available ?? 0)} onClick={() => setSeats(value => value + 1)}>+</button></div>{message && <div className="notice notice-success"><Check size={17} /> {message}</div>}{error && <div className="notice notice-error">{error}</div>}{paymentConfirmed ? <Link className="button button-primary button-wide" to="/bookings">View my tickets <ArrowRight size={17} /></Link> : <><button className="button button-primary button-wide" type="submit" disabled={busy || !screeningId || (screenings.find(show => show.id === screeningId)?.seats_available ?? 0) < 1}>{busy ? 'Preparing checkout…' : user ? 'Continue to payment' : 'Sign in to book'} <ArrowRight size={17} /></button><p className="form-hint">Payments use Razorpay test mode. You will not be charged.</p></>}</form>
  </section></div></div>
}

type TmdbResult = { tmdb_id: number; title: string; overview: string; release_date: string; rating: number; poster_path: string | null }

function AdminPage() {
  const { user } = useAuth()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<TmdbResult[]>([])
  const [movies, setMovies] = useState<Movie[]>([])
  const [selectedMovie, setSelectedMovie] = useState('')
  const [startsAt, setStartsAt] = useState('')
  const [capacity, setCapacity] = useState(80)
  const [price, setPrice] = useState(300)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { if (user?.is_admin) api<Movie[]>('/api/movies').then(list => { setMovies(list); if (list[0]) setSelectedMovie(String(list[0].id)) }).catch(err => setError(err.message)) }, [user])
  if (!user) return <div className="page-wrap"><div className="empty-state"><h2>Sign in to continue</h2><Link className="button button-primary" to="/login">Sign in</Link></div></div>
  if (!user.is_admin) return <div className="page-wrap"><div className="notice notice-error">Admin access required.</div></div>
  async function searchTmdb(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('')
    try { const found = await api<TmdbResult[]>(`/api/tmdb/search?query=${encodeURIComponent(query)}`); setResults(found) }
    catch (err) { setError(err instanceof Error ? err.message : 'TMDB search failed') }
    finally { setBusy(false) }
  }
  async function importMovie(result: TmdbResult) {
    setBusy(true); setError(''); setNotice('')
    try { const movie = await api<Movie>('/api/tmdb/import', { method: 'POST', body: JSON.stringify(result) }); setMovies(current => [...current, movie]); setSelectedMovie(String(movie.id)); setNotice(`${movie.title} added. Schedule a screening below.`) }
    catch (err) { setError(err instanceof Error ? err.message : 'Movie import failed') }
    finally { setBusy(false) }
  }
  async function createScreening(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('')
    try {
      await api(`/api/movies/${selectedMovie}/screenings`, { method: 'POST', body: JSON.stringify({ starts_at: new Date(startsAt).toISOString(), auditorium: 'Screen 1', capacity, price_paise: Math.round(price * 100) }) })
      setNotice('Screening published. Customers can book tickets now.')
      setMovies(await api<Movie[]>('/api/movies'))
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not schedule screening') }
    finally { setBusy(false) }
  }
  return <div className="page-wrap admin-page"><div className="section-heading"><div><span className="eyebrow">CATALOG TOOLS</span><h1>Manage screenings</h1><p>Import movie details and publish a dated screening.</p></div></div>{error && <div className="notice notice-error">{error}</div>}{notice && <div className="notice notice-success"><Check size={17} /> {notice}</div>}<section className="booking-box"><h2>Find a movie on TMDB</h2><form className="catalog-tools" onSubmit={searchTmdb}><label className="search-box"><Search size={18} /><input required minLength={2} placeholder="Search movie titles" value={query} onChange={e => setQuery(e.target.value)} /></label><button className="button button-primary" disabled={busy}>{busy ? 'Searching…' : 'Search'}</button></form>{results.map(result => <article className="booking-card" key={result.tmdb_id}><div className="booking-info"><h3>{result.title}</h3><p>{result.release_date} · TMDB ★ {result.rating?.toFixed(1)}</p></div><button className="button button-outline" disabled={busy} onClick={() => importMovie(result)}>Import</button></article>)}</section><section className="booking-box"><h2>Publish a screening</h2>{!movies.length ? <p className="form-hint">Import a movie first.</p> : <form className="auth-form" onSubmit={createScreening}><label htmlFor="admin-movie">Movie</label><select id="admin-movie" value={selectedMovie || movies[0]?.id} onChange={e => setSelectedMovie(e.target.value)}>{movies.map(movie => <option key={movie.id} value={movie.id}>{movie.title}</option>)}</select><label htmlFor="starts-at">Date and time</label><input id="starts-at" type="datetime-local" required value={startsAt} onChange={e => setStartsAt(e.target.value)} /><label htmlFor="capacity">Ticket capacity</label><input id="capacity" type="number" min={1} max={1000} required value={capacity} onChange={e => setCapacity(Number(e.target.value))} /><label htmlFor="price">Ticket price (₹)</label><input id="price" type="number" min={1} required value={price} onChange={e => setPrice(Number(e.target.value))} /><button className="button button-primary button-wide" disabled={busy || !selectedMovie}>Publish screening</button></form>}</section></div>
}

function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const { user, login, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [formError, setFormError] = useState('')
  const [busy, setBusy] = useState(false)
  const isRegister = mode === 'register'
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setFormError('')
    const data = new FormData(event.currentTarget)
    try {
      if (isRegister) await register(String(data.get('username')), String(data.get('email')), String(data.get('password')))
      else await login(String(data.get('username')), String(data.get('password')))
      const destination = (location.state as { from?: string } | null)?.from ?? '/'
      navigate(destination, { replace: true })
    } catch (err) { setFormError(err instanceof Error ? err.message : 'Could not sign in') }
    finally { setBusy(false) }
  }
  if (user) return <Navigate to="/" replace />
  return <div className="auth-wrap"><div className="auth-aside"><span className="eyebrow">YOUR NEXT NIGHT OUT</span><h1>Stories are better<br />on the big screen.</h1><p>Save your seat for something wonderful.</p><div className="auth-illustration"><Film size={56} strokeWidth={1.2} /><span>Lights down.<br />Phone away.<br />Enjoy the show.</span></div></div><section className="auth-card"><span className="eyebrow">{isRegister ? 'JOIN CINEBOOK' : 'WELCOME BACK'}</span><h2>{isRegister ? 'Create your account' : 'Sign in to continue'}</h2><p>{isRegister ? 'A few details and you’re ready to book.' : 'Your next movie night is waiting.'}</p><form onSubmit={submit} className="auth-form">{isRegister && <><label htmlFor="username">Username</label><input id="username" name="username" required minLength={3} maxLength={15} autoComplete="username" placeholder="Choose a username" /></>}<label htmlFor="email-or-username">{isRegister ? 'Email' : 'Username'}</label><input id="email-or-username" name={isRegister ? 'email' : 'username'} required type={isRegister ? 'email' : 'text'} autoComplete={isRegister ? 'email' : 'username'} placeholder={isRegister ? 'you@example.com' : 'Your username'} /><label htmlFor="password">Password</label><input id="password" name="password" required minLength={8} type="password" autoComplete={isRegister ? 'new-password' : 'current-password'} placeholder="At least 8 characters" />{formError && <div className="notice notice-error">{formError}</div>}<button className="button button-primary button-wide" disabled={busy}>{busy ? 'One moment…' : isRegister ? 'Create account' : 'Sign in'} <ArrowRight size={17} /></button></form><div className="auth-switch">{isRegister ? 'Already have an account?' : 'New to Cinebook?'} <Link to={isRegister ? '/login' : '/register'}>{isRegister ? 'Sign in' : 'Create an account'}</Link></div></section></div>
}

function BookingsPage() {
  const { user, busy } = useAuth()
  const [bookings, setBookings] = useState<Booking[]>([])
  const [bookingView, setBookingView] = useState<'upcoming' | 'history'>('upcoming')
  const [error, setError] = useState('')
  const [canceling, setCanceling] = useState<number | null>(null)
  const [calendarConnected, setCalendarConnected] = useState(false)
  const [calendarConfigured, setCalendarConfigured] = useState(false)
  const [calendarBusy, setCalendarBusy] = useState<number | null>(null)
  const [calendarMessage, setCalendarMessage] = useState('')
  const load = () => api<Booking[]>('/api/bookings').then(setBookings).catch(err => setError(err.message))
  useEffect(() => {
    if (!user) return
    load()
    api<{ connected: boolean; configured: boolean }>('/api/calendar/status').then(value => { setCalendarConnected(value.connected); setCalendarConfigured(value.configured) }).catch(() => {})
    const outcome = new URLSearchParams(window.location.search).get('calendar')
    if (outcome === 'connected') setCalendarMessage('Google Calendar connected. Add confirmed tickets to your calendar below.')
    if (outcome === 'error' || outcome === 'missing_refresh_token') setError('Google Calendar could not be connected. Try again and grant offline access.')
    if (outcome) window.history.replaceState({}, '', '/bookings')
  }, [user])
  async function cancel(id: number) { setCanceling(id); setError(''); try { await api(`/api/bookings/${id}`, { method: 'DELETE' }); await load() } catch (err) { setError(err instanceof Error ? err.message : 'Could not cancel booking') } finally { setCanceling(null) } }
  async function connectCalendar() {
    setCalendarMessage(''); setError('')
    try {
      const result = await api<{ authorization_url: string; state: string }>('/api/calendar/connect')
      sessionStorage.setItem('cinebook-calendar-state', result.state)
      window.location.assign(result.authorization_url)
    }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not connect Google Calendar') }
  }
  async function addToCalendar(id: number) {
    setCalendarBusy(id); setCalendarMessage(''); setError('')
    try { await api(`/api/calendar/bookings/${id}/event`, { method: 'POST' }); setCalendarMessage('Screening added to your Google Calendar.'); await load() }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not create calendar event') }
    finally { setCalendarBusy(null) }
  }
  if (busy) return <div className="loading"><span className="spinner" /> Loading your account…</div>
  if (!user) return <div className="page-wrap"><div className="empty-state"><UserRound size={30} /><h2>Sign in to see your tickets</h2><p>Your bookings will be waiting here.</p><Link className="button button-primary" to="/login">Sign in <ArrowRight size={16} /></Link></div></div>
  const upcomingBookings = bookings.filter(item => ['confirmed', 'pending'].includes(item.status) && new Date(item.screening.starts_at).getTime() > Date.now())
  const historyBookings = bookings.filter(item => !upcomingBookings.includes(item))
  const visibleBookings = bookingView === 'upcoming' ? upcomingBookings : historyBookings
  return <div className="page-wrap"><div className="section-heading"><div><span className="eyebrow">YOUR PLANS</span><h1>My tickets</h1><p>All your upcoming movie nights in one place.</p></div><div className="row-actions">{calendarConnected ? <span className="availability">Google Calendar connected</span> : <button className="button button-outline" disabled={!calendarConfigured} onClick={connectCalendar}>{calendarConfigured ? 'Connect Google Calendar' : 'Calendar setup needed'}</button>}<Link to="/" className="button button-outline">Find a film <ArrowRight size={16} /></Link></div></div>{error && <div className="notice notice-error">{error}</div>}{calendarMessage && <div className="notice notice-success">{calendarMessage}</div>}<div className="booking-tabs" role="group" aria-label="Booking view"><button type="button" className={bookingView === 'upcoming' ? 'active' : ''} aria-pressed={bookingView === 'upcoming'} onClick={() => setBookingView('upcoming')}>Upcoming ({upcomingBookings.length})</button><button type="button" className={bookingView === 'history' ? 'active' : ''} aria-pressed={bookingView === 'history'} onClick={() => setBookingView('history')}>History ({historyBookings.length})</button></div>{visibleBookings.length ? <div className="booking-list">{visibleBookings.map(item => { const film = item.screening.movie; return <article className="booking-card" key={item.id}><div className="booking-icon"><Ticket size={22} /></div><div className="booking-info"><span className="eyebrow">BOOKING #{item.id} · {item.status.toUpperCase()}</span><h2>{film?.title ?? 'Movie screening'}</h2><p>{item.screening.auditorium} · {rupees(item.amount_paise)}</p></div><div className="booking-detail"><span><CalendarDays size={16} /> {new Date(item.screening.starts_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}</span><span><Ticket size={16} /> {item.seats_booked} {item.seats_booked === 1 ? 'ticket' : 'tickets'}</span></div><div className="row-actions">{item.status === 'confirmed' && calendarConnected && <button className="button button-outline button-small" disabled={calendarBusy === item.id || !!item.calendar_event_id} onClick={() => addToCalendar(item.id)}>{item.calendar_event_id ? 'Added to calendar' : calendarBusy === item.id ? 'Adding…' : 'Add to calendar'}</button>}{item.status === 'pending' && <button className="button button-quiet cancel-button" disabled={canceling === item.id} onClick={() => cancel(item.id)}>{canceling === item.id ? 'Cancelling…' : 'Cancel hold'}</button>}</div></article> })}</div> : <div className="empty-state"><Ticket size={30} /><h2>{bookingView === 'upcoming' ? 'No upcoming tickets' : 'No booking history'}</h2><p>{bookingView === 'upcoming' ? 'Confirmed tickets and active holds will appear here.' : 'Past, cancelled, and expired bookings will appear here.'}</p>{bookingView === 'upcoming' && <Link className="button button-primary" to="/">Browse movies <ArrowRight size={16} /></Link>}</div>}</div>
}

function CalendarOAuthCallback() {
  const { user, busy } = useAuth()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const started = useRef(false)
  const [error, setError] = useState('')
  useEffect(() => {
    if (busy || started.current) return
    started.current = true
    const code = params.get('code')
    const state = params.get('state')
    const expectedState = sessionStorage.getItem('cinebook-calendar-state')
    sessionStorage.removeItem('cinebook-calendar-state')
    if (params.has('error') || !code || !state || !expectedState || state !== expectedState) {
      navigate('/bookings?calendar=error', { replace: true })
      return
    }
    if (!user) {
      navigate('/login', { replace: true })
      return
    }
    api<{ connected: boolean }>('/api/calendar/callback', { method: 'POST', body: JSON.stringify({ code, state }) })
      .then(() => navigate('/bookings?calendar=connected', { replace: true }))
      .catch(err => { setError(err instanceof Error ? err.message : 'Could not connect Calendar') })
  }, [busy, navigate, params, user])
  return <div className="page-wrap"><div className="empty-state">{error ? <><h2>Calendar connection failed</h2><p>{error}</p><Link to="/bookings" className="button button-outline">Back to tickets</Link></> : <><span className="spinner" /><h2>Connecting Google Calendar…</h2><p>This usually takes a moment.</p></>}</div></div>
}

function NotFound() { return <div className="empty-state page-wrap"><Film size={30} /><h2>That page wandered off</h2><Link to="/" className="button button-primary">Back to movies</Link></div> }

export default App

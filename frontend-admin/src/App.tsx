import { Box, CircularProgress, CssBaseline, ThemeProvider, createTheme } from '@mui/material'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { apiClient, clearAccessToken, getAccessToken, setAccessToken } from './lib/apiClient'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'
import type { AdminUser } from './types/auth'

const theme = createTheme({
  palette: { primary: { main: '#2e7d32' } },
  typography: { fontFamily: '"Noto Sans JP", "Hiragino Sans", sans-serif' },
})

const queryClient = new QueryClient()

function App() {
  const [user, setUser] = useState<AdminUser | null>(null)
  const [isCheckingSession, setIsCheckingSession] = useState(true)

  async function loadCurrentUser() {
    const { data } = await apiClient.get<AdminUser>('/me')
    setUser(data)
  }

  useEffect(() => {
    if (!getAccessToken()) {
      setIsCheckingSession(false)
      return
    }
    loadCurrentUser().catch(() => clearAccessToken()).finally(() => setIsCheckingSession(false))
  }, [])

  async function handleLogin(token: string) {
    setAccessToken(token)
    try { await loadCurrentUser() } catch (error) { clearAccessToken(); throw error }
  }

  function handleLogout() { clearAccessToken(); setUser(null) }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <QueryClientProvider client={queryClient}>
        {isCheckingSession ? (
          <Box sx={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}><CircularProgress /></Box>
        ) : user ? <DashboardPage user={user} onLogout={handleLogout} /> : <LoginPage onLogin={handleLogin} />}
      </QueryClientProvider>
    </ThemeProvider>
  )
}

export default App

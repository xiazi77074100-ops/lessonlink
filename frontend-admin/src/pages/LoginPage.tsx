import LockOutlinedIcon from '@mui/icons-material/LockOutlined'
import {
  Alert,
  Avatar,
  Box,
  Button,
  CircularProgress,
  Container,
  Paper,
  TextField,
  Typography,
} from '@mui/material'
import axios from 'axios'
import { useState, type FormEvent } from 'react'
import { apiClient } from '../lib/apiClient'
import type { LoginResponse } from '../types/auth'

type LoginPageProps = {
  onLogin: (token: string) => Promise<void>
  onRegister: () => void
}

export function LoginPage({ onLogin, onRegister }: LoginPageProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setIsSubmitting(true)
    try {
      const { data } = await apiClient.post<LoginResponse>('/auth/login', { email, password })
      await onLogin(data.access_token)
    } catch (caught) {
      if (axios.isAxiosError(caught) && caught.response?.status === 401) {
        setError('メールアドレスまたはパスワードが正しくありません。')
      } else {
        setError('ログインできませんでした。しばらくしてからもう一度お試しください。')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Container maxWidth="xs">
      <Paper elevation={4} sx={{ mt: { xs: 8, sm: 14 }, p: { xs: 3, sm: 4 }, borderRadius: 3 }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <Avatar sx={{ bgcolor: 'primary.main', mb: 2 }}><LockOutlinedIcon /></Avatar>
          <Typography component="h1" variant="h5" sx={{ fontWeight: 700 }}>管理者ログイン</Typography>
          <Typography color="text.secondary" sx={{ mt: 1, mb: 3 }}>習い事管理くん</Typography>
          {error && <Alert severity="error" sx={{ width: '100%', mb: 2 }}>{error}</Alert>}
          <Box component="form" onSubmit={handleSubmit} sx={{ width: '100%' }}>
            <TextField label="メールアドレス" type="email" autoComplete="email" autoFocus required fullWidth value={email} onChange={(event) => setEmail(event.target.value)} />
            <TextField label="パスワード" type="password" autoComplete="current-password" required fullWidth value={password} onChange={(event) => setPassword(event.target.value)} sx={{ mt: 2 }} />
            <Button type="submit" variant="contained" size="large" fullWidth disabled={isSubmitting} sx={{ mt: 3, py: 1.25 }}>
              {isSubmitting ? <CircularProgress size={24} color="inherit" /> : 'ログイン'}
            </Button>
            <Button fullWidth onClick={onRegister} sx={{ mt: 1 }}>組織を新規登録</Button>
          </Box>
        </Box>
      </Paper>
    </Container>
  )
}

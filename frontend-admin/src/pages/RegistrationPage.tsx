import { Alert, Box, Button, Container, MenuItem, Paper, TextField, Typography } from '@mui/material'
import axios from 'axios'
import { useState, type FormEvent } from 'react'
import { apiClient } from '../lib/apiClient'
import { organizationTypes } from '../types/organization'

type Props = { onRegistered: (token: string) => Promise<void>; onBack: () => void }

export function RegistrationPage({ onRegistered, onBack }: Props) {
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setIsSubmitting(true)
    const data = new FormData(event.currentTarget)
    try {
      const response = await apiClient.post<{ access_token: string }>('/organizations', {
        name: data.get('name'), organization_type: data.get('organization_type'),
        address: data.get('address') || null, phone: data.get('phone') || null,
        email: data.get('email') || null, owner_email: data.get('owner_email'),
        owner_password: data.get('owner_password'), owner_display_name: data.get('owner_display_name'),
      })
      await onRegistered(response.data.access_token)
    } catch (caught) {
      const message = axios.isAxiosError(caught) && caught.response?.status === 409
        ? 'このメールアドレスは既に使用されています。'
        : '登録できませんでした。入力内容を確認してください。'
      setError(message)
    } finally { setIsSubmitting(false) }
  }

  return <Container maxWidth="sm"><Paper sx={{ my: 6, p: { xs: 3, sm: 4 }, borderRadius: 3 }}>
    <Typography variant="h5" component="h1" sx={{ fontWeight: 700 }} gutterBottom>組織を新規登録</Typography>
    <Typography color="text.secondary" sx={{ mb: 3 }}>組織とオーナーアカウントを作成します。</Typography>
    {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
    <Box component="form" onSubmit={handleSubmit} sx={{ display: 'grid', gap: 2 }}>
      <TextField name="name" label="組織名" required autoFocus />
      <TextField name="organization_type" label="種別" select required defaultValue="サッカー">{organizationTypes.map((type) => <MenuItem key={type} value={type}>{type}</MenuItem>)}</TextField>
      <TextField name="address" label="住所" />
      <TextField name="phone" label="電話番号" />
      <TextField name="email" label="組織メールアドレス" type="email" />
      <Typography variant="subtitle1" sx={{ mt: 1, fontWeight: 700 }}>オーナー情報</Typography>
      <TextField name="owner_display_name" label="表示名" required />
      <TextField name="owner_email" label="ログイン用メールアドレス" type="email" required />
      <TextField name="owner_password" label="パスワード（8文字以上）" type="password" required slotProps={{ htmlInput: { minLength: 8 } }} />
      <Button type="submit" variant="contained" size="large" disabled={isSubmitting}>{isSubmitting ? '登録中…' : '登録する'}</Button>
      <Button onClick={onBack}>ログインに戻る</Button>
    </Box>
  </Paper></Container>
}

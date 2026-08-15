import LogoutIcon from '@mui/icons-material/Logout'
import { Alert, AppBar, Box, Button, Container, MenuItem, Paper, TextField, Toolbar, Typography } from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { apiClient } from '../lib/apiClient'
import type { AdminUser } from '../types/auth'
import { organizationTypes, type Organization, type OrganizationForm } from '../types/organization'

type DashboardPageProps = { user: AdminUser; onLogout: () => void }

export function DashboardPage({ user, onLogout }: DashboardPageProps) {
  const { data: organizations, isLoading, isError } = useQuery({ queryKey: ['organization'], queryFn: async () => (await apiClient.get<Organization[]>('/organizations')).data })
  const organization = organizations?.[0]
  const [form, setForm] = useState<OrganizationForm | null>(null)
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')

  useEffect(() => { if (organization) setForm({ name: organization.name, organization_type: organization.organization_type, address: organization.address, phone: organization.phone, email: organization.email }) }, [organization])

  async function handleSave(event: FormEvent) {
    event.preventDefault()
    if (!organization || !form) return
    setSaveState('saving')
    try { await apiClient.put(`/organizations/${organization.id}`, form); setSaveState('saved') }
    catch { setSaveState('error') }
  }

  function change(field: keyof OrganizationForm, value: string) { if (form) setForm({ ...form, [field]: value || null }) }

  return (
    <>
      <AppBar position="static"><Toolbar><Typography variant="h6" sx={{ flexGrow: 1 }}>習い事管理くん</Typography><Button color="inherit" startIcon={<LogoutIcon />} onClick={onLogout}>ログアウト</Button></Toolbar></AppBar>
      <Container maxWidth="md"><Typography variant="h4" sx={{ mt: 4 }} gutterBottom>こんにちは、{user.display_name}さん</Typography>
        <Paper sx={{ mt: 3, p: { xs: 3, sm: 4 } }}><Typography variant="h5" gutterBottom>組織設定</Typography>
          {isLoading && <Typography>読み込み中…</Typography>}{isError && <Alert severity="error">組織情報を取得できませんでした。</Alert>}
          {form && <Box component="form" onSubmit={handleSave} sx={{ display: 'grid', gap: 2, mt: 2 }}>
            <TextField label="組織名" required value={form.name} onChange={(event) => change('name', event.target.value)} />
            <TextField label="種別" select value={form.organization_type} onChange={(event) => change('organization_type', event.target.value)}>{organizationTypes.map((type) => <MenuItem key={type} value={type}>{type}</MenuItem>)}</TextField>
            <TextField label="住所" value={form.address ?? ''} onChange={(event) => change('address', event.target.value)} />
            <TextField label="電話番号" value={form.phone ?? ''} onChange={(event) => change('phone', event.target.value)} />
            <TextField label="メールアドレス" type="email" value={form.email ?? ''} onChange={(event) => change('email', event.target.value)} />
            {saveState === 'saved' && <Alert severity="success">保存しました。</Alert>}{saveState === 'error' && <Alert severity="error">保存できませんでした。</Alert>}
            <Button type="submit" variant="contained" disabled={saveState === 'saving' || user.role === 'STAFF'}>{saveState === 'saving' ? '保存中…' : '保存'}</Button>
          </Box>}
        </Paper>
      </Container>
    </>
  )
}

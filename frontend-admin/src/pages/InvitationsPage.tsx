import AddIcon from '@mui/icons-material/Add'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import { Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography } from '@mui/material'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import QRCode from 'qrcode'
import { useEffect, useState, type FormEvent } from 'react'
import { apiClient } from '../lib/apiClient'
import type { AdminUser } from '../types/auth'
import type { Invitation } from '../types/invitation'

const parentAppUrl = import.meta.env.VITE_PARENT_APP_URL ?? 'http://localhost:5174'
const statusLabel = { ACTIVE: '有効', DISABLED: '無効', EXPIRED: '期限切れ' }

export function InvitationsPage({ user }: { user: AdminUser }) {
  const queryClient = useQueryClient()
  const { data = [], isLoading, isError } = useQuery({ queryKey: ['invitations'], queryFn: async () => (await apiClient.get<Invitation[]>('/invitations')).data })
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [selected, setSelected] = useState<Invitation | null>(null)
  const [qrDataUrl, setQrDataUrl] = useState('')
  const [error, setError] = useState(false)
  const invitationUrl = selected ? `${parentAppUrl}?invitation=${encodeURIComponent(selected.invitation_code)}` : ''

  useEffect(() => { if (invitationUrl) QRCode.toDataURL(invitationUrl, { width: 320, margin: 2 }).then(setQrDataUrl) }, [invitationUrl])

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(false)
    const form = new FormData(event.currentTarget)
    const expiry = form.get('expires_at') as string
    const maxUses = form.get('max_uses') as string
    try {
      const response = await apiClient.post<Invitation>('/invitations', { expires_at: expiry ? new Date(expiry).toISOString() : null, max_uses: maxUses ? Number(maxUses) : null })
      await queryClient.invalidateQueries({ queryKey: ['invitations'] })
      setIsCreateOpen(false)
      setSelected(response.data)
    } catch { setError(true) }
  }

  async function disable(invitation: Invitation) {
    await apiClient.post(`/invitations/${invitation.id}/disable`)
    await queryClient.invalidateQueries({ queryKey: ['invitations'] })
  }

  return <Paper sx={{ mt: 3, p: { xs: 2, sm: 4 } }}>
    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}><Typography variant="h5">招待管理</Typography><Button variant="contained" startIcon={<AddIcon />} onClick={() => setIsCreateOpen(true)} disabled={user.role === 'STAFF'}>招待を発行</Button></Box>
    {isLoading && <Typography>読み込み中…</Typography>}{isError && <Alert severity="error">招待一覧を取得できませんでした。</Alert>}{!isLoading && !isError && data.length === 0 && <Alert severity="info">発行済みの招待はありません。</Alert>}
    {data.length > 0 && <TableContainer><Table><TableHead><TableRow><TableCell>発行日時</TableCell><TableCell>使用回数</TableCell><TableCell>有効期限</TableCell><TableCell>状態</TableCell><TableCell /></TableRow></TableHead><TableBody>{data.map((invitation) => <TableRow key={invitation.id}><TableCell>{new Date(invitation.created_at).toLocaleString('ja-JP')}</TableCell><TableCell>{invitation.used_count} / {invitation.max_uses ?? '無制限'}</TableCell><TableCell>{invitation.expires_at ? new Date(invitation.expires_at).toLocaleString('ja-JP') : '無期限'}</TableCell><TableCell>{statusLabel[invitation.status]}</TableCell><TableCell align="right"><Button onClick={() => setSelected(invitation)}>QR表示</Button>{invitation.status === 'ACTIVE' && <Button color="error" onClick={() => disable(invitation)} disabled={user.role === 'STAFF'}>無効化</Button>}</TableCell></TableRow>)}</TableBody></Table></TableContainer>}
    <Dialog open={isCreateOpen} onClose={() => setIsCreateOpen(false)} fullWidth maxWidth="xs"><Box component="form" onSubmit={create}><DialogTitle>招待を発行</DialogTitle><DialogContent sx={{ display: 'grid', gap: 2, pt: '12px !important' }}>{error && <Alert severity="error">発行できませんでした。</Alert>}<TextField name="expires_at" label="有効期限（任意）" type="datetime-local" slotProps={{ inputLabel: { shrink: true } }} /><TextField name="max_uses" label="利用上限（任意）" type="number" slotProps={{ htmlInput: { min: 1, max: 10000 } }} /></DialogContent><DialogActions><Button onClick={() => setIsCreateOpen(false)}>キャンセル</Button><Button type="submit" variant="contained">発行</Button></DialogActions></Box></Dialog>
    <Dialog open={Boolean(selected)} onClose={() => setSelected(null)} fullWidth maxWidth="xs"><DialogTitle>保護者招待QR</DialogTitle><DialogContent sx={{ textAlign: 'center' }}>{qrDataUrl && <Box component="img" src={qrDataUrl} alt="保護者招待QRコード" sx={{ width: '100%', maxWidth: 320 }} />}<Typography variant="body2" sx={{ wordBreak: 'break-all', my: 2 }}>{invitationUrl}</Typography><Button startIcon={<ContentCopyIcon />} onClick={() => navigator.clipboard.writeText(invitationUrl)}>URLをコピー</Button></DialogContent><DialogActions><Button onClick={() => setSelected(null)}>閉じる</Button></DialogActions></Dialog>
  </Paper>
}

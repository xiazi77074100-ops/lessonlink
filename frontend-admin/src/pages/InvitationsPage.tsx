import AddIcon from '@mui/icons-material/Add'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import ShareIcon from '@mui/icons-material/Share'
import { Alert, Autocomplete, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import QRCode from 'qrcode'
import { useEffect, useState, type FormEvent } from 'react'
import { apiClient } from '../lib/apiClient'
import type { AdminUser } from '../types/auth'
import type { Child } from '../types/child'
import type { Invitation } from '../types/invitation'

const parentAppUrl = import.meta.env.VITE_PARENT_APP_URL ?? 'http://localhost:5174'
const statusLabel = { ACTIVE: '有効', DISABLED: '無効', EXPIRED: '期限切れ' }
const DEFAULT_GUARDIAN_LIMIT = 2

function childLabel(child: Pick<Child, 'first_name' | 'last_name' | 'grade'>) {
  return `${child.last_name} ${child.first_name}${child.grade ? `（${child.grade}）` : ''}`
}

export function InvitationsPage({ user }: { user: AdminUser }) {
  const queryClient = useQueryClient()
  const { data = [], isLoading, isError } = useQuery({ queryKey: ['invitations'], queryFn: async () => (await apiClient.get<Invitation[]>('/invitations')).data })
  const { data: children = [] } = useQuery({ queryKey: ['children'], queryFn: async () => (await apiClient.get<Child[]>('/children')).data })
  const activeChildren = children.filter((child) => child.status === 'ACTIVE')

  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [invitationType, setInvitationType] = useState<'family' | 'organization'>('family')
  const [familyChildren, setFamilyChildren] = useState<Child[]>([])
  const [selected, setSelected] = useState<Invitation | null>(null)
  const [qrDataUrl, setQrDataUrl] = useState('')
  const [error, setError] = useState(false)
  const invitationUrl = selected ? `${parentAppUrl}?invitation=${encodeURIComponent(selected.invitation_code)}` : ''
  const shareUrl = invitationUrl ? `https://line.me/R/share?text=${encodeURIComponent(`教室から保護者登録のご案内です。\n以下のリンクからLINEで登録してください。\n${invitationUrl}`)}` : ''

  useEffect(() => { if (invitationUrl) QRCode.toDataURL(invitationUrl, { width: 320, margin: 2 }).then(setQrDataUrl) }, [invitationUrl])

  function openCreate() {
    setInvitationType('family')
    setFamilyChildren([])
    setError(false)
    setIsCreateOpen(true)
  }

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(false)
    const form = new FormData(event.currentTarget)
    const expiry = form.get('expires_at') as string
    const maxUses = form.get('max_uses') as string
    if (invitationType === 'family' && familyChildren.length === 0) { setError(true); return }
    try {
      const response = await apiClient.post<Invitation>('/invitations', {
        expires_at: expiry ? new Date(expiry).toISOString() : null,
        max_uses: maxUses ? Number(maxUses) : null,
        child_ids: invitationType === 'family' ? familyChildren.map((child) => child.id) : [],
      })
      await queryClient.invalidateQueries({ queryKey: ['invitations'] })
      setIsCreateOpen(false)
      setSelected(response.data)
    } catch { setError(true) }
  }

  async function disable(invitation: Invitation) {
    await apiClient.post(`/invitations/${invitation.id}/disable`)
    await queryClient.invalidateQueries({ queryKey: ['invitations'] })
  }

  function shareWithLine() {
    window.open(shareUrl, '_blank', 'noopener,noreferrer')
  }

  return <Paper sx={{ mt: 3, p: { xs: 2, sm: 4 } }}>
    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}><Typography variant="h5">招待管理</Typography><Button variant="contained" startIcon={<AddIcon />} onClick={openCreate} disabled={user.role === 'STAFF'}>招待を発行</Button></Box>
    {isLoading && <Typography>読み込み中…</Typography>}{isError && <Alert severity="error">招待一覧を取得できませんでした。</Alert>}{!isLoading && !isError && data.length === 0 && <Alert severity="info">発行済みの招待はありません。</Alert>}
    {data.length > 0 && <TableContainer><Table><TableHead><TableRow><TableCell>対象</TableCell><TableCell>発行日時</TableCell><TableCell>使用回数</TableCell><TableCell>有効期限</TableCell><TableCell>状態</TableCell><TableCell /></TableRow></TableHead><TableBody>{data.map((invitation) => <TableRow key={invitation.id}><TableCell>{invitation.children.length > 0 ? invitation.children.map(childLabel).join('、') : '組織全体'}</TableCell><TableCell>{new Date(invitation.created_at).toLocaleString('ja-JP')}</TableCell><TableCell>{invitation.used_count} / {invitation.max_uses ?? '無制限'}</TableCell><TableCell>{invitation.expires_at ? new Date(invitation.expires_at).toLocaleString('ja-JP') : '無期限'}</TableCell><TableCell>{statusLabel[invitation.status]}</TableCell><TableCell align="right"><Button startIcon={<ShareIcon />} onClick={() => setSelected(invitation)}>共有</Button>{invitation.status === 'ACTIVE' && <Button color="error" onClick={() => disable(invitation)} disabled={user.role === 'STAFF'}>無効化</Button>}</TableCell></TableRow>)}</TableBody></Table></TableContainer>}

    <Dialog open={isCreateOpen} onClose={() => setIsCreateOpen(false)} fullWidth maxWidth="xs">
      <Box component="form" onSubmit={create}>
        <DialogTitle>保護者を招待</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, pt: '12px !important' }}>
          {error && <Alert severity="error">{invitationType === 'family' && familyChildren.length === 0 ? '対象のお子様を1人以上選択してください。' : '発行できませんでした。'}</Alert>}
          <ToggleButtonGroup exclusive value={invitationType} onChange={(_, value) => value && setInvitationType(value)} fullWidth>
            <ToggleButton value="family">家庭を招待</ToggleButton>
            <ToggleButton value="organization">組織全体で共有</ToggleButton>
          </ToggleButtonGroup>
          {invitationType === 'family' ? <>
            <Alert severity="info">保護者は招待に含まれるお子様（兄弟姉妹）を1回の登録でまとめて確認・紐付けできます。</Alert>
            <Autocomplete
              multiple
              options={activeChildren}
              value={familyChildren}
              onChange={(_, value) => setFamilyChildren(value)}
              getOptionLabel={childLabel}
              isOptionEqualToValue={(option, value) => option.id === value.id}
              renderInput={(params) => <TextField {...params} label="対象のお子様" placeholder="お子様を選択" />}
            />
            <TextField name="max_uses" label="保護者利用上限（任意）" helperText={`未入力の場合は${DEFAULT_GUARDIAN_LIMIT}人（例: 両親2人）まで利用できます`} type="number" slotProps={{ htmlInput: { min: 1, max: 10 } }} />
          </> : <>
            <Alert severity="info">発行後、LINEで既存のグループへ送信できます。名簿から子供を選ぶ形式の招待です。</Alert>
            <TextField name="max_uses" label="利用上限（任意）" helperText="対象家庭数を入力してください（未入力は無制限）" type="number" slotProps={{ htmlInput: { min: 1, max: 10000 } }} />
          </>}
          <TextField name="expires_at" label="有効期限（任意）" type="datetime-local" slotProps={{ inputLabel: { shrink: true } }} />
        </DialogContent>
        <DialogActions><Button onClick={() => setIsCreateOpen(false)}>キャンセル</Button><Button type="submit" variant="contained">発行して共有</Button></DialogActions>
      </Box>
    </Dialog>

    <Dialog open={Boolean(selected)} onClose={() => setSelected(null)} fullWidth maxWidth="xs"><DialogTitle>保護者を招待</DialogTitle><DialogContent sx={{ textAlign: 'center' }}><Typography sx={{ mb: 2 }}>LINEの友だち・グループへ招待を送信できます。</Typography><Button fullWidth size="large" variant="contained" startIcon={<ShareIcon />} onClick={shareWithLine} disabled={selected?.status !== 'ACTIVE'}>LINEで招待する</Button><Box sx={{ my: 1 }}><Button startIcon={<ContentCopyIcon />} onClick={() => navigator.clipboard.writeText(invitationUrl)}>URLをコピー</Button></Box>{qrDataUrl && <Box component="img" src={qrDataUrl} alt="保護者招待QRコード" sx={{ width: '100%', maxWidth: 240 }} />}<Typography variant="caption" sx={{ display: 'block', wordBreak: 'break-all', mt: 2 }}>{invitationUrl}</Typography></DialogContent><DialogActions><Button onClick={() => setSelected(null)}>閉じる</Button></DialogActions></Dialog>
  </Paper>
}

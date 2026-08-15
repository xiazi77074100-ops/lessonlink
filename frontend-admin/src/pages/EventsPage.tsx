import AddIcon from '@mui/icons-material/Add'
import EditIcon from '@mui/icons-material/Edit'
import { Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, MenuItem, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography } from '@mui/material'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { apiClient } from '../lib/apiClient'
import type { AdminUser } from '../types/auth'
import type { EventForm, LessonEvent } from '../types/event'
import { AttendanceDialog } from './AttendanceDialog'

const emptyForm: EventForm = { title: '', description: null, start_at: '', end_at: '', location_name: null, location_address: null, status: 'DRAFT' }
const statusLabel = { DRAFT: '下書き', PUBLISHED: '公開', CANCELLED: 'キャンセル', COMPLETED: '完了' }

function toLocalInput(value: string) {
  const date = new Date(value)
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 16)
}

export function EventsPage({ user }: { user: AdminUser }) {
  const queryClient = useQueryClient()
  const { data = [], isLoading, isError } = useQuery({ queryKey: ['events'], queryFn: async () => (await apiClient.get<LessonEvent[]>('/events')).data })
  const [editing, setEditing] = useState<LessonEvent | null>(null)
  const [form, setForm] = useState<EventForm>(emptyForm)
  const [isOpen, setIsOpen] = useState(false)
  const [saveError, setSaveError] = useState(false)
  const [attendanceEvent, setAttendanceEvent] = useState<LessonEvent | null>(null)

  function openCreate() { setEditing(null); setForm(emptyForm); setSaveError(false); setIsOpen(true) }
  function openEdit(event: LessonEvent) { setEditing(event); setForm({ title: event.title, description: event.description, start_at: toLocalInput(event.start_at), end_at: toLocalInput(event.end_at), location_name: event.location_name, location_address: event.location_address, status: event.status === 'CANCELLED' ? 'DRAFT' : event.status }); setSaveError(false); setIsOpen(true) }
  function change(field: keyof EventForm, value: string) { setForm({ ...form, [field]: value || null }) }

  async function handleSave(submitEvent: FormEvent) {
    submitEvent.preventDefault()
    setSaveError(false)
    const payload = { ...form, start_at: new Date(form.start_at).toISOString(), end_at: new Date(form.end_at).toISOString() }
    try {
      if (editing) await apiClient.put(`/events/${editing.id}`, payload)
      else await apiClient.post('/events', payload)
      await queryClient.invalidateQueries({ queryKey: ['events'] })
      setIsOpen(false)
    } catch { setSaveError(true) }
  }

  async function cancel(event: LessonEvent) {
    if (!window.confirm(`「${event.title}」をキャンセルしますか？`)) return
    await apiClient.post(`/events/${event.id}/cancel`)
    await queryClient.invalidateQueries({ queryKey: ['events'] })
  }

  return <Paper sx={{ mt: 3, p: { xs: 2, sm: 4 } }}>
    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}><Typography variant="h5">活動一覧</Typography><Button variant="contained" startIcon={<AddIcon />} onClick={openCreate} disabled={user.role === 'STAFF'}>作成</Button></Box>
    {isLoading && <Typography>読み込み中…</Typography>}{isError && <Alert severity="error">活動一覧を取得できませんでした。</Alert>}{!isLoading && !isError && data.length === 0 && <Alert severity="info">活動はまだありません。</Alert>}
    {data.length > 0 && <TableContainer><Table><TableHead><TableRow><TableCell>日時</TableCell><TableCell>活動</TableCell><TableCell>場所</TableCell><TableCell>状態</TableCell><TableCell /></TableRow></TableHead><TableBody>{data.map((event) => <TableRow key={event.id}><TableCell>{new Date(event.start_at).toLocaleString('ja-JP', { timeZone: 'Asia/Tokyo' })}</TableCell><TableCell>{event.title}</TableCell><TableCell>{event.location_name ?? '—'}</TableCell><TableCell><Chip size="small" label={statusLabel[event.status]} /></TableCell><TableCell align="right"><Button onClick={() => setAttendanceEvent(event)}>出欠</Button><IconButton aria-label="編集" onClick={() => openEdit(event)} disabled={user.role === 'STAFF' || event.status === 'CANCELLED'}><EditIcon /></IconButton>{event.status !== 'CANCELLED' && <Button color="error" onClick={() => cancel(event)} disabled={user.role === 'STAFF'}>取消</Button>}</TableCell></TableRow>)}</TableBody></Table></TableContainer>}
    <Dialog open={isOpen} onClose={() => setIsOpen(false)} fullWidth maxWidth="sm"><Box component="form" onSubmit={handleSave}><DialogTitle>{editing ? '活動を編集' : '活動を作成'}</DialogTitle><DialogContent sx={{ display: 'grid', gap: 2, pt: '12px !important' }}>{saveError && <Alert severity="error">保存できませんでした。終了日時を確認してください。</Alert>}
      <TextField label="活動名" required value={form.title} onChange={(event) => change('title', event.target.value)} /><TextField label="説明" multiline minRows={2} value={form.description ?? ''} onChange={(event) => change('description', event.target.value)} />
      <TextField label="開始日時" type="datetime-local" required value={form.start_at} onChange={(event) => change('start_at', event.target.value)} slotProps={{ inputLabel: { shrink: true } }} /><TextField label="終了日時" type="datetime-local" required value={form.end_at} onChange={(event) => change('end_at', event.target.value)} slotProps={{ inputLabel: { shrink: true } }} />
      <TextField label="場所" value={form.location_name ?? ''} onChange={(event) => change('location_name', event.target.value)} /><TextField label="住所" value={form.location_address ?? ''} onChange={(event) => change('location_address', event.target.value)} />
      <TextField label="状態" select value={form.status} onChange={(event) => change('status', event.target.value)}><MenuItem value="DRAFT">下書き</MenuItem><MenuItem value="PUBLISHED">公開</MenuItem><MenuItem value="COMPLETED">完了</MenuItem></TextField>
    </DialogContent><DialogActions><Button onClick={() => setIsOpen(false)}>キャンセル</Button><Button type="submit" variant="contained">保存</Button></DialogActions></Box></Dialog>
    <AttendanceDialog event={attendanceEvent} user={user} onClose={() => setAttendanceEvent(null)} />
  </Paper>
}

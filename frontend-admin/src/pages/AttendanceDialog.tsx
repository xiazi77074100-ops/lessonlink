import { Alert, Box, Button, Card, CardContent, Dialog, DialogContent, DialogTitle, IconButton, MenuItem, TextField, Typography } from '@mui/material'
import CloseIcon from '@mui/icons-material/Close'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { apiClient } from '../lib/apiClient'
import type { AttendanceStatus, EventAttendance } from '../types/attendance'
import type { LessonEvent } from '../types/event'

const labels: Record<AttendanceStatus, string> = { ATTENDING: '参加', ABSENT: '欠席', LATE: '遅刻', NO_RESPONSE: '未回答' }

export function AttendanceDialog({ event, onClose }: { event: LessonEvent | null; onClose: () => void }) {
  const queryClient = useQueryClient()
  const { data, isLoading, isError } = useQuery({ queryKey: ['attendance', event?.id], queryFn: async () => (await apiClient.get<EventAttendance>(`/events/${event!.id}/attendance`)).data, enabled: Boolean(event) })
  const [reminderMessage, setReminderMessage] = useState('')

  async function update(childId: string, status: AttendanceStatus) {
    if (!event) return
    await apiClient.post('/attendance', { event_id: event.id, child_id: childId, status })
    await queryClient.invalidateQueries({ queryKey: ['attendance', event.id] })
  }

  async function remind() {
    if (!event) return
    setReminderMessage('送信中…')
    try {
      const response = await apiClient.post<{ sent: number; failed: number }> (`/events/${event.id}/remind`)
      setReminderMessage(`送信完了：${response.data.sent}件${response.data.failed ? `、失敗：${response.data.failed}件` : ''}`)
    } catch { setReminderMessage('通知を送信できませんでした。') }
  }

  const summary = data?.summary
  return <Dialog open={Boolean(event)} onClose={onClose} fullWidth maxWidth="md"><DialogTitle sx={{ pr: 6 }}>{event?.title} — 出欠状況<IconButton onClick={onClose} sx={{ position: 'absolute', right: 8, top: 8 }}><CloseIcon /></IconButton></DialogTitle><DialogContent>
    {isLoading && <Typography>読み込み中…</Typography>}{isError && <Alert severity="error">出欠情報を取得できませんでした。</Alert>}
    {summary && <><Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 1, my: 2 }}>{([['参加', summary.attending], ['欠席', summary.absent], ['遅刻', summary.late], ['未回答', summary.no_response]] as const).map(([label, count]) => <Card variant="outlined" key={label}><CardContent sx={{ textAlign: 'center', p: '12px !important' }}><Typography color="text.secondary" variant="body2">{label}</Typography><Typography variant="h5">{count}</Typography></CardContent></Card>)}</Box><Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}><Button variant="outlined" onClick={remind} disabled={summary.no_response === 0 || event?.status === 'CANCELLED'}>未回答者に通知</Button>{reminderMessage && <Typography variant="body2">{reminderMessage}</Typography>}</Box></>}
    {data?.attendances.length === 0 && <Alert severity="info">対象の子供はいません。</Alert>}
    <Box sx={{ display: 'grid', gap: 1 }}>{data?.attendances.map((row) => <Box key={row.id} sx={{ display: 'grid', gridTemplateColumns: 'minmax(120px, 1fr) minmax(130px, 180px)', gap: 2, alignItems: 'center', borderBottom: '1px solid', borderColor: 'divider', py: 1 }}><Typography>{row.child_last_name} {row.child_first_name}</Typography><TextField select size="small" value={row.status} onChange={(changeEvent) => update(row.child_id, changeEvent.target.value as AttendanceStatus)} disabled={event?.status === 'CANCELLED'}>{Object.entries(labels).map(([value, label]) => <MenuItem key={value} value={value}>{label}</MenuItem>)}</TextField></Box>)}</Box>
  </DialogContent></Dialog>
}

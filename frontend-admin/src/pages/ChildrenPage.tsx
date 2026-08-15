import AddIcon from '@mui/icons-material/Add'
import EditIcon from '@mui/icons-material/Edit'
import { Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, MenuItem, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography } from '@mui/material'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { apiClient } from '../lib/apiClient'
import type { AdminUser } from '../types/auth'
import type { Child, ChildForm } from '../types/child'

const emptyForm: ChildForm = { first_name: '', last_name: '', first_name_kana: null, last_name_kana: null, birth_date: '', grade: null, status: 'ACTIVE' }

export function ChildrenPage({ user }: { user: AdminUser }) {
  const queryClient = useQueryClient()
  const { data = [], isLoading, isError } = useQuery({ queryKey: ['children'], queryFn: async () => (await apiClient.get<Child[]>('/children')).data })
  const [editing, setEditing] = useState<Child | null>(null)
  const [form, setForm] = useState<ChildForm>(emptyForm)
  const [isOpen, setIsOpen] = useState(false)
  const [saveError, setSaveError] = useState(false)

  function openCreate() { setEditing(null); setForm(emptyForm); setSaveError(false); setIsOpen(true) }
  function openEdit(child: Child) { setEditing(child); setForm({ first_name: child.first_name, last_name: child.last_name, first_name_kana: child.first_name_kana, last_name_kana: child.last_name_kana, birth_date: child.birth_date, grade: child.grade, status: child.status }); setSaveError(false); setIsOpen(true) }
  function change(field: keyof ChildForm, value: string) { setForm({ ...form, [field]: value || null }) }

  async function handleSave(event: FormEvent) {
    event.preventDefault()
    setSaveError(false)
    try {
      if (editing) await apiClient.put(`/children/${editing.id}`, form)
      else await apiClient.post('/children', form)
      await queryClient.invalidateQueries({ queryKey: ['children'] })
      setIsOpen(false)
    } catch { setSaveError(true) }
  }

  return <Paper sx={{ mt: 3, p: { xs: 2, sm: 4 } }}>
    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}><Typography variant="h5">子供一覧</Typography><Button variant="contained" startIcon={<AddIcon />} onClick={openCreate} disabled={user.role === 'STAFF'}>登録</Button></Box>
    {isLoading && <Typography>読み込み中…</Typography>}{isError && <Alert severity="error">子供一覧を取得できませんでした。</Alert>}
    {!isLoading && !isError && data.length === 0 && <Alert severity="info">登録された子供はいません。</Alert>}
    {data.length > 0 && <TableContainer><Table><TableHead><TableRow><TableCell>氏名</TableCell><TableCell>生年月日</TableCell><TableCell>学年</TableCell><TableCell>状態</TableCell><TableCell /></TableRow></TableHead><TableBody>{data.map((child) => <TableRow key={child.id}><TableCell>{child.last_name} {child.first_name}</TableCell><TableCell>{child.birth_date}</TableCell><TableCell>{child.grade ?? '—'}</TableCell><TableCell>{child.status === 'ACTIVE' ? '在籍' : '休止'}</TableCell><TableCell align="right"><IconButton aria-label="編集" onClick={() => openEdit(child)} disabled={user.role === 'STAFF'}><EditIcon /></IconButton></TableCell></TableRow>)}</TableBody></Table></TableContainer>}
    <Dialog open={isOpen} onClose={() => setIsOpen(false)} fullWidth maxWidth="sm"><Box component="form" onSubmit={handleSave}><DialogTitle>{editing ? '子供情報を編集' : '子供を登録'}</DialogTitle><DialogContent sx={{ display: 'grid', gridTemplateColumns: { sm: '1fr 1fr' }, gap: 2, pt: '12px !important' }}>
      {saveError && <Alert severity="error" sx={{ gridColumn: '1 / -1' }}>保存できませんでした。</Alert>}
      <TextField label="姓" required value={form.last_name} onChange={(event) => change('last_name', event.target.value)} /><TextField label="名" required value={form.first_name} onChange={(event) => change('first_name', event.target.value)} />
      <TextField label="姓（かな）" value={form.last_name_kana ?? ''} onChange={(event) => change('last_name_kana', event.target.value)} /><TextField label="名（かな）" value={form.first_name_kana ?? ''} onChange={(event) => change('first_name_kana', event.target.value)} />
      <TextField label="生年月日" type="date" required value={form.birth_date} onChange={(event) => change('birth_date', event.target.value)} slotProps={{ inputLabel: { shrink: true } }} /><TextField label="学年" value={form.grade ?? ''} onChange={(event) => change('grade', event.target.value)} />
      <TextField label="状態" select value={form.status} onChange={(event) => change('status', event.target.value)}><MenuItem value="ACTIVE">在籍</MenuItem><MenuItem value="INACTIVE">休止</MenuItem></TextField>
    </DialogContent><DialogActions><Button onClick={() => setIsOpen(false)}>キャンセル</Button><Button type="submit" variant="contained">保存</Button></DialogActions></Box></Dialog>
  </Paper>
}

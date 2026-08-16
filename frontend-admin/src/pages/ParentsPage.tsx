import { Alert, Chip, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from '@mui/material'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../lib/apiClient'
import type { AdminUser } from '../types/auth'
import type { Parent, ParentDetail } from '../types/parent'

function ParentRow({ parent, user }: { parent: Parent; user: AdminUser }) {
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['parent', parent.id], queryFn: async () => (await apiClient.get<ParentDetail>(`/parents/${parent.id}`)).data })

  async function unbind(childId: string) {
    if (!window.confirm('この紐付けを解除しますか？')) return
    await apiClient.delete(`/parents/${parent.id}/children/${childId}`)
    await queryClient.invalidateQueries({ queryKey: ['parent', parent.id] })
  }

  return <TableRow>
    <TableCell>{parent.display_name}</TableCell>
    <TableCell>{parent.email ?? '—'}</TableCell>
    <TableCell>
      {isLoading && '読み込み中…'}
      {!isLoading && data && data.children.length === 0 && <Typography variant="body2" color="text.secondary">未紐付け</Typography>}
      {!isLoading && data?.children.map((child) => (
        <Chip
          key={child.id}
          size="small"
          sx={{ mr: 0.5, mb: 0.5 }}
          label={`${child.last_name} ${child.first_name}`}
          onDelete={user.role === 'STAFF' ? undefined : () => unbind(child.id)}
        />
      ))}
    </TableCell>
  </TableRow>
}

export function ParentsPage({ user }: { user: AdminUser }) {
  const { data = [], isLoading, isError } = useQuery({ queryKey: ['parents'], queryFn: async () => (await apiClient.get<Parent[]>('/parents')).data })

  return <Paper sx={{ mt: 3, p: { xs: 2, sm: 4 } }}>
    <Typography variant="h5" sx={{ mb: 2 }}>保護者一覧</Typography>
    {isLoading && <Typography>読み込み中…</Typography>}
    {isError && <Alert severity="error">保護者一覧を取得できませんでした。</Alert>}
    {!isLoading && !isError && data.length === 0 && <Alert severity="info">登録された保護者はいません。招待から参加すると自動的にここに表示されます。</Alert>}
    {data.length > 0 && <TableContainer><Table><TableHead><TableRow><TableCell>氏名</TableCell><TableCell>連絡先</TableCell><TableCell>紐付けの子供</TableCell></TableRow></TableHead><TableBody>{data.map((parent) => <ParentRow key={parent.id} parent={parent} user={user} />)}</TableBody></Table></TableContainer>}
  </Paper>
}

import LogoutIcon from '@mui/icons-material/Logout'
import { AppBar, Button, Container, Paper, Toolbar, Typography } from '@mui/material'
import type { AdminUser } from '../types/auth'

type DashboardPageProps = { user: AdminUser; onLogout: () => void }

export function DashboardPage({ user, onLogout }: DashboardPageProps) {
  return (
    <>
      <AppBar position="static"><Toolbar><Typography variant="h6" sx={{ flexGrow: 1 }}>習い事管理くん</Typography><Button color="inherit" startIcon={<LogoutIcon />} onClick={onLogout}>ログアウト</Button></Toolbar></AppBar>
      <Container maxWidth="lg"><Paper sx={{ mt: 4, p: 4 }}><Typography variant="h4" gutterBottom>こんにちは、{user.display_name}さん</Typography><Typography color="text.secondary">管理者ダッシュボードは次のPhaseで実装します。</Typography></Paper></Container>
    </>
  )
}

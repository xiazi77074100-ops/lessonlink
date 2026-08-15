import { Alert, Box, CircularProgress, Container, Typography } from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../lib/apiClient'

export function HealthCheckPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['health'],
    queryFn: async () => (await apiClient.get<{ status: string }>('/health')).data,
  })

  return (
    <Container maxWidth="sm">
      <Box sx={{ mt: 8, textAlign: 'center' }}>
        <Typography variant="h4" gutterBottom>
          習い事管理くん
        </Typography>
        <Typography variant="body1" color="text.secondary" gutterBottom>
          管理者ダッシュボード（開発中）
        </Typography>

        {isLoading && <CircularProgress sx={{ mt: 4 }} />}
        {isError && (
          <Alert severity="error" sx={{ mt: 4 }}>
            APIに接続できませんでした。backendが起動しているか確認してください。
          </Alert>
        )}
        {data && (
          <Alert severity="success" sx={{ mt: 4 }}>
            API接続OK（status: {data.status}）
          </Alert>
        )}
      </Box>
    </Container>
  )
}

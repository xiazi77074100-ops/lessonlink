import { useEffect, useState } from 'react'
import { apiClient } from './lib/apiClient'
import './index.css'

function App() {
  const [status, setStatus] = useState<'loading' | 'ok' | 'error'>('loading')

  useEffect(() => {
    apiClient
      .get<{ status: string }>('/health')
      .then(() => setStatus('ok'))
      .catch(() => setStatus('error'))
  }, [])

  return (
    <main style={{ padding: '2rem', textAlign: 'center', fontFamily: 'sans-serif' }}>
      <h1>習い事管理くん</h1>
      <p>保護者向けページ（開発中・LINE連携はPhase 9で実装）</p>
      {status === 'loading' && <p>接続確認中...</p>}
      {status === 'ok' && <p>API接続OK</p>}
      {status === 'error' && <p>APIに接続できませんでした。</p>}
    </main>
  )
}

export default App

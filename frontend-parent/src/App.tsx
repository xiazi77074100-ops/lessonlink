import liff from '@line/liff'
import { useEffect, useState } from 'react'
import { apiClient, clearParentToken, getParentToken, setParentToken } from './lib/apiClient'
import './index.css'

type Child = { id: string; first_name: string; last_name: string; grade: string | null }
type ParentMe = { display_name: string; children: Child[] }
type InvitationInfo = { invitation_code: string; organization_name: string; expires_at: string | null; children: Child[] }
type AttendanceStatus = 'ATTENDING' | 'ABSENT' | 'LATE' | 'NO_RESPONSE'
type ParentEvent = { id: string; title: string; description: string | null; start_at: string; end_at: string; location_name: string | null; children: { child_id: string; child_name: string; attendance_status: AttendanceStatus }[] }

function invitationCode() {
  const params = new URLSearchParams(window.location.search)
  const direct = params.get('invitation')
  if (direct) return direct
  const state = params.get('liff.state')
  if (!state) return ''
  const decoded = decodeURIComponent(state)
  return new URLSearchParams(decoded.includes('?') ? decoded.split('?')[1] : decoded).get('invitation') ?? ''
}

function App() {
  const [phase, setPhase] = useState<'loading' | 'binding' | 'completed' | 'ready' | 'error'>('loading')
  const [message, setMessage] = useState('LINEログインを確認しています…')
  const [me, setMe] = useState<ParentMe | null>(null)
  const [events, setEvents] = useState<ParentEvent[]>([])
  const [available, setAvailable] = useState<Child[]>([])
  const [confirmed, setConfirmed] = useState<Child[]>([])
  const [selectedChild, setSelectedChild] = useState('')
  const [birthDate, setBirthDate] = useState('')
  const [bindError, setBindError] = useState('')
  const [savedKey, setSavedKey] = useState('')
  const [answeringKey, setAnsweringKey] = useState('')
  const [answerError, setAnswerError] = useState('')
  const [invitationInfo, setInvitationInfo] = useState<InvitationInfo | null>(null)

  const familyChildren = invitationInfo?.children ?? []
  const isFamilyInvitation = familyChildren.length > 0
  const confirmedIds = new Set(confirmed.map((child) => child.id))
  const pendingFamilyChildren = familyChildren.filter((child) => !confirmedIds.has(child.id))
  const currentFamilyChild = pendingFamilyChildren[0] ?? null
  const pendingRoster = available.filter((child) => !confirmedIds.has(child.id))

  async function loadPortal(readyPhase: 'ready' | 'completed' = 'ready') {
    const [meResponse, eventsResponse] = await Promise.all([
      apiClient.get<ParentMe>('/parent/me'), apiClient.get<ParentEvent[]>('/parent/events'),
    ])
    setMe(meResponse.data)
    setEvents(eventsResponse.data)
    if (meResponse.data.children.length === 0) {
      if (!isFamilyInvitation) {
        const children = await apiClient.get<Child[]>('/parent/children/available')
        setAvailable(children.data)
      }
      setPhase('binding')
    } else setPhase(readyPhase)
  }

  useEffect(() => {
    async function initialize() {
      try {
        if (getParentToken()) {
          try { await loadPortal(); return } catch { clearParentToken() }
        }
        const invitation = invitationCode()
        if (!invitation) throw new Error('招待URLからアクセスしてください。')
        setMessage('招待内容を確認しています…')
        const invitationResponse = await apiClient.get<InvitationInfo>(`/invitations/code/${encodeURIComponent(invitation)}`)
        setInvitationInfo(invitationResponse.data)
        setMessage('LINEログインを確認しています…')
        let idToken = import.meta.env.VITE_LINE_MOCK_TOKEN as string | undefined
        if (!idToken) {
          const liffId = import.meta.env.VITE_LIFF_ID
          if (!liffId) throw new Error('LIFFが設定されていません。')
          await liff.init({ liffId })
          if (!liff.isLoggedIn()) { liff.login({ redirectUri: window.location.href }); return }
          idToken = liff.getIDToken() ?? undefined
        }
        if (!idToken) throw new Error('LINEログイン情報を取得できませんでした。')
        const response = await apiClient.post<{ access_token: string }>('/parent/auth/line', { id_token: idToken, invitation_code: invitation })
        setParentToken(response.data.access_token)
        await loadPortal()
      } catch (error) {
        setMessage(error instanceof Error ? error.message : 'ページを開けませんでした。')
        setPhase('error')
      }
    }
    initialize()
  }, [])

  async function bindChild(childId: string, birth: string) {
    setBindError('')
    try {
      await apiClient.post('/parent/children/bind', { child_id: childId, birth_date: birth })
      const child = (isFamilyInvitation ? familyChildren : available).find((candidate) => candidate.id === childId)
      if (child) setConfirmed((prev) => [...prev, child])
      setSelectedChild('')
      setBirthDate('')
    } catch { setBindError('生年月日が一致しません。入力内容を確認してください。') }
  }

  async function finishOnboarding() {
    await loadPortal('completed')
  }

  async function answer(eventId: string, childId: string, status: AttendanceStatus) {
    const key = `${eventId}:${childId}`
    setAnsweringKey(key)
    setAnswerError('')
    try {
      await apiClient.post('/parent/attendance', { event_id: eventId, child_id: childId, status })
      setSavedKey(key)
      const response = await apiClient.get<ParentEvent[]>('/parent/events')
      setEvents(response.data)
    } catch { setAnswerError('回答を保存できませんでした。通信環境を確認してもう一度お試しください。') }
    finally { setAnsweringKey('') }
  }

  if (phase === 'loading' || phase === 'error') return <main className="center"><h1>習い事管理くん</h1><p>{phase === 'loading' ? message : `エラー：${message}`}</p></main>
  if (phase === 'binding') return <main><section className="card onboarding">
    <p className="organization">{invitationInfo?.organization_name ?? '教室'}</p>
    <div className="steps" aria-label="登録ステップ"><span className="done">1 招待確認</span><span className="current">2 お子様確認</span><span>3 完了</span></div>
    <h1>お子様の確認</h1>
    <p>{me?.display_name}さん、{isFamilyInvitation ? '招待に含まれるお子様の生年月日を確認してください。' : '通っているお子様と生年月日を選択してください。'}</p>
    {bindError && <p className="error" role="alert">{bindError}</p>}
    {isFamilyInvitation && <ul className="child-checklist">{familyChildren.map((child) => <li key={child.id} className={confirmedIds.has(child.id) ? 'done' : ''}>{confirmedIds.has(child.id) ? '✓ ' : ''}{child.last_name} {child.first_name}{child.grade ? `（${child.grade}）` : ''}</li>)}</ul>}
    {isFamilyInvitation
      ? (currentFamilyChild
        ? <><p>{currentFamilyChild.last_name} {currentFamilyChild.first_name}さんの生年月日を入力してください。</p><label>生年月日<input type="date" value={birthDate} onChange={(event) => setBirthDate(event.target.value)} /></label><button className="primary" disabled={!birthDate} onClick={() => bindChild(currentFamilyChild.id, birthDate)}>確認する</button></>
        : <p>すべてのお子様を確認しました。</p>)
      : (pendingRoster.length === 0 && confirmed.length === 0
        ? <p className="error" role="alert">選択できるお子様がいません。教室の管理者にお問い合わせください。</p>
        : pendingRoster.length > 0 && <><label>お子様<select value={selectedChild} onChange={(event) => setSelectedChild(event.target.value)}><option value="">選択してください</option>{pendingRoster.map((child) => <option key={child.id} value={child.id}>{child.last_name} {child.first_name}{child.grade ? `（${child.grade}）` : ''}</option>)}</select></label><label>生年月日<input type="date" value={birthDate} onChange={(event) => setBirthDate(event.target.value)} /></label><button className="primary" disabled={!selectedChild || !birthDate} onClick={() => bindChild(selectedChild, birthDate)}>確認して登録する</button></>)}
    {confirmed.length > 0 && <button className="primary" onClick={finishOnboarding}>登録を完了する（確認済み{confirmed.length}人）</button>}
  </section></main>

  if (phase === 'completed') return <main className="center"><section className="card onboarding"><p className="organization">{invitationInfo?.organization_name ?? '教室'}</p><div className="steps" aria-label="登録ステップ"><span className="done">1 招待確認</span><span className="done">2 お子様確認</span><span className="current">3 完了</span></div><div className="complete-mark" aria-hidden="true">✓</div><h1>登録が完了しました</h1><p>これからLINEで活動予定の確認と出欠回答ができます。</p><button className="primary" onClick={() => setPhase('ready')}>活動予定を見る</button></section></main>

  return <main><header><h1>習い事管理くん</h1><p>{me?.display_name}さん</p></header>{answerError && <p className="error" role="alert">{answerError}</p>}{events.length === 0 && <section className="card"><p>現在、回答できる活動はありません。</p></section>}{events.map((lesson) => <section className="card" key={lesson.id}><p className="date">{new Date(lesson.start_at).toLocaleString('ja-JP', { timeZone: 'Asia/Tokyo', month: 'long', day: 'numeric', weekday: 'short', hour: '2-digit', minute: '2-digit' })}</p><h2>{lesson.title}</h2>{lesson.location_name && <p>📍 {lesson.location_name}</p>}{lesson.children.map((child) => { const key = `${lesson.id}:${child.child_id}`; const saving = answeringKey === key; return <div className="answer" key={child.child_id}><strong>{child.child_name}</strong><div className="buttons"><button disabled={saving} className={child.attendance_status === 'ATTENDING' ? 'active' : ''} onClick={() => answer(lesson.id, child.child_id, 'ATTENDING')}>参加</button><button disabled={saving} className={child.attendance_status === 'ABSENT' ? 'active absent' : ''} onClick={() => answer(lesson.id, child.child_id, 'ABSENT')}>欠席</button><button disabled={saving} className={child.attendance_status === 'LATE' ? 'active late' : ''} onClick={() => answer(lesson.id, child.child_id, 'LATE')}>遅刻</button></div>{saving && <p className="saved" aria-live="polite">保存中…</p>}{!saving && savedKey === key && <p className="saved" aria-live="polite">回答しました。ありがとうございます。</p>}</div>})}</section>)}</main>
}

export default App

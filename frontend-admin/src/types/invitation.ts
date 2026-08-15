export type Invitation = {
  id: string
  invitation_code: string
  expires_at: string | null
  max_uses: number | null
  used_count: number
  status: 'ACTIVE' | 'DISABLED' | 'EXPIRED'
  created_at: string
}

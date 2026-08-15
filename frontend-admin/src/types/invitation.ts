export type InvitationChildSummary = {
  id: string
  first_name: string
  last_name: string
  grade: string | null
}

export type Invitation = {
  id: string
  invitation_code: string
  expires_at: string | null
  max_uses: number | null
  used_count: number
  status: 'ACTIVE' | 'DISABLED' | 'EXPIRED'
  created_at: string
  children: InvitationChildSummary[]
}

import type { Child } from './child'

export type Parent = {
  id: string
  organization_id: string
  display_name: string
  email: string | null
  phone: string | null
  created_at: string
  updated_at: string
}

export type ParentDetail = Parent & { children: Child[] }

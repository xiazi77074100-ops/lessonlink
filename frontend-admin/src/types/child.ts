export type Child = {
  id: string
  organization_id: string
  first_name: string
  last_name: string
  first_name_kana: string | null
  last_name_kana: string | null
  birth_date: string
  grade: string | null
  status: 'ACTIVE' | 'INACTIVE'
  created_at: string
  updated_at: string
}

export type ChildForm = Omit<Child, 'id' | 'organization_id' | 'created_at' | 'updated_at'>

export const organizationTypes = ['サッカー', '野球', '空手', 'ダンス', 'バレエ', 'ピアノ', 'スイミング', 'その他'] as const

export type Organization = {
  id: string
  name: string
  organization_type: (typeof organizationTypes)[number]
  address: string | null
  phone: string | null
  email: string | null
  plan: string
  created_at: string
  updated_at: string
}

export type OrganizationForm = Pick<Organization, 'name' | 'organization_type' | 'address' | 'phone' | 'email'>

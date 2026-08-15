export type AdminUser = {
  id: string
  organization_id: string
  email: string
  display_name: string
  role: 'OWNER' | 'ADMIN' | 'STAFF'
}

export type LoginResponse = {
  access_token: string
  token_type: string
}

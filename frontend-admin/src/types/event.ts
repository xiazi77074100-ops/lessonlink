export type LessonEvent = {
  id: string
  organization_id: string
  title: string
  description: string | null
  start_at: string
  end_at: string
  location_name: string | null
  location_address: string | null
  status: 'DRAFT' | 'PUBLISHED' | 'CANCELLED' | 'COMPLETED'
  created_at: string
  updated_at: string
}

export type EventForm = Pick<LessonEvent, 'title' | 'description' | 'start_at' | 'end_at' | 'location_name' | 'location_address'> & { status: 'DRAFT' | 'PUBLISHED' | 'COMPLETED' }

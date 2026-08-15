export type AttendanceStatus = 'ATTENDING' | 'ABSENT' | 'LATE' | 'NO_RESPONSE'

export type AttendanceRow = {
  id: string
  event_id: string
  child_id: string
  status: AttendanceStatus
  note: string | null
  responded_at: string | null
  child_first_name: string
  child_last_name: string
}

export type EventAttendance = {
  event_id: string
  summary: { attending: number; absent: number; late: number; no_response: number; total: number }
  attendances: AttendanceRow[]
}

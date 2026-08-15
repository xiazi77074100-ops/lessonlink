import axios from 'axios'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1',
})

const TOKEN_KEY = 'lessonlink_parent_token'

export const getParentToken = () => localStorage.getItem(TOKEN_KEY)
export const setParentToken = (token: string) => localStorage.setItem(TOKEN_KEY, token)
export const clearParentToken = () => localStorage.removeItem(TOKEN_KEY)

apiClient.interceptors.request.use((config) => {
  const token = getParentToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

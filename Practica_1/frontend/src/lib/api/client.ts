import axios from 'axios'
import { appConfig } from '../../config/env'
import { useAuthStore } from '../../../stores/auth.store'

/** Cliente HTTP que centraliza la comunicación con el API detrás del ALB. */
export const apiClient = axios.create({
  baseURL: appConfig.apiBaseUrl || undefined,
  headers: {
    Accept: 'application/json',
  },
})

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token

  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`)
  }

  return config
})

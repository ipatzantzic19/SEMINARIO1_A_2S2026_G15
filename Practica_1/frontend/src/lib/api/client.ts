import axios from 'axios'
import { appConfig } from '../../config/env'

/** cliente http para exponer la api al load balancer */
export const apiClient = axios.create({
  baseURL: appConfig.apiBaseUrl || undefined,
  headers: {
    'Content-Type': 'application/json',
  },
})

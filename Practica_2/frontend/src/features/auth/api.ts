import { z } from 'zod';
import type { HttpClient } from '../../lib/api/client.ts';
import { parseResponse } from '../../lib/api/client.ts';
import { loginResultSchema, userSchema } from './schemas.ts';
import type { Login, Registration } from './types.ts';

export function createAuthApi(client: HttpClient) {
  return {
    login: (body: Login) => client.request('/api/v1/auth/login', 'POST', body).then(data => parseResponse(loginResultSchema, data)),
    register: (body: Registration) => client.request('/api/v1/auth/register', 'POST', body).then(data => parseResponse(z.object({ usuario: userSchema }), data)),
  };
}

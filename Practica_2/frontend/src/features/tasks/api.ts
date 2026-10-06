import { z } from 'zod';
import type { HttpClient } from '../../lib/api/client.ts';
import { parseResponse } from '../../lib/api/client.ts';
import { taskSchema } from './schemas.ts';
import type { TaskInput } from './types.ts';

const single = z.object({ tarea: taskSchema });
const list = z.object({ tareas: z.array(taskSchema), total: z.number().int().nonnegative() });
export function createTasksApi(client: HttpClient) {
  return {
    tasks: (token: string, signal?: AbortSignal) => client.request('/api/v1/tasks', 'GET', undefined, token, signal).then(data => parseResponse(list, data)),
    createTask: (body: TaskInput, token: string) => client.request('/api/v1/tasks', 'POST', body, token).then(data => parseResponse(single, data)),
    editTask: (id: number, body: TaskInput, token: string) => client.request(`/api/v1/tasks/${id}`, 'PUT', body, token).then(data => parseResponse(single, data)),
    completeTask: (id: number, completada: boolean, token: string) => client.request(`/api/v1/tasks/${id}`, 'PATCH', { completada }, token).then(data => parseResponse(single, data)),
    deleteTask: (id: number, token: string) => client.request<void>(`/api/v1/tasks/${id}`, 'DELETE', undefined, token),
  };
}

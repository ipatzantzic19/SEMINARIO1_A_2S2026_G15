import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { Api } from '../../lib/api/index.ts';
import type { TaskChange } from './types.ts';

export const taskKeys = { list: (scope: string) => ['tasks', scope] as const };
export function useTasks(api: Api, token: string, scope: string) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: taskKeys.list(scope), queryFn: ({ signal }) => api.tasks(token, signal), enabled: !!token });
  const mutation = useMutation({
    mutationFn: async (change: TaskChange) => {
      switch (change.kind) {
        case 'create': await api.createTask(change.input, token); break;
        case 'edit': await api.editTask(change.id, change.input, token); break;
        case 'complete': await api.completeTask(change.id, change.completada, token); break;
        case 'delete': await api.deleteTask(change.id, token); break;
      }
    },
    onSuccess: () => client.invalidateQueries({ queryKey: taskKeys.list(scope) }),
  });
  return { query, mutation };
}

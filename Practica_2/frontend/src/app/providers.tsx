import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

export function createQueryClient() {
  return new QueryClient({ defaultOptions: {
    queries: { staleTime: 30000, gcTime: 300000, retry: false, refetchOnWindowFocus: false },
    mutations: { retry: false },
  } });
}
export function AppProviders({ children, client: provided }: { children: ReactNode; client?: QueryClient }) {
  const [client] = useState(() => provided || createQueryClient());
  useEffect(() => () => { void client.cancelQueries(); client.clear(); }, [client]);
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

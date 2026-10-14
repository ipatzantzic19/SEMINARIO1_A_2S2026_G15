// Datos de demostración estructurados según los esquemas de OpenAPI 1.0.0.
export const mockProfile = { userId: '596bdc55-48ac-47b9-a93d-fd15b7646db5', fullName: 'Ana López', email: 'ana@example.com', dpi: '0000000000000', profileImageUrl: null, profileComplete: true };
export const mockUserPage = { items: [{ userId: '116c8be3-6868-408b-b202-3336afeb6517', fullName: 'María Pérez', profileImageUrl: 'https://example.test/foto.jpg' }], nextCursor: null };
export const mockPostPage = { items: [], nextCursor: null };
export const mockMessages: unknown[] = [];

export type PreviewState = 'loading' | 'ready' | 'empty' | 'error';

export async function loadPreview(page: string): Promise<{ state: PreviewState; label?: string }> {
  await new Promise(resolve => setTimeout(resolve, 120));
  if (page === 'usuarios') return { state: 'ready', label: `${mockUserPage.items.length} persona de ejemplo` };
  if (page === 'perfil') return { state: 'ready', label: `Perfil de ejemplo: ${mockProfile.fullName}` };
  if (page === 'feed' && mockPostPage.items.length === 0) return { state: 'empty' };
  if (page === 'chat' && mockMessages.length === 0) return { state: 'empty' };
  return { state: 'error' };
}

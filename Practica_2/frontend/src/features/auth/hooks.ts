import { useMutation } from '@tanstack/react-query';
import type { Api } from '../../lib/api/index.ts';
import type { UploadInput, UploadRoute } from '../files/types.ts';

export function useAuthMutations(api: Api) {
  const signIn = useMutation({ mutationFn: api.login });
  const signUp = useMutation({ mutationFn: api.register });
  const uploadPhoto = useMutation({ mutationFn: (input: { route: UploadRoute; body: UploadInput }) => api.upload(input.route, input.body) });
  return { signIn, signUp, uploadPhoto, busy: signIn.isPending || signUp.isPending || uploadPhoto.isPending };
}

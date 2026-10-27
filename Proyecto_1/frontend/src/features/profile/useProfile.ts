import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { endpoints } from "../../lib/api/endpoints";

export type ProfileUpdate = {
  fullName: string;
  dpi: string;
  currentPassword: string;
  photo: File | null;
};

export function useProfile() {
  return useQuery({ queryKey: ["me"], queryFn: endpoints.me });
}

export function useUpdateProfile() {
  const query = useQueryClient();
  return useMutation({
    mutationFn: async ({ photo, ...values }: ProfileUpdate) => {
      const profileImageKey = photo
        ? (await endpoints.upload("profile", photo)).imageKey
        : undefined;
      return endpoints.updateMe({ ...values, profileImageKey });
    },
    onSuccess: async () => {
      await query.invalidateQueries({ queryKey: ["me"] });
    },
  });
}

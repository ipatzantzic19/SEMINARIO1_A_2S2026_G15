import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { endpoints } from "../../lib/api/endpoints";

export function useFeed(label: string) {
  return useInfiniteQuery({
    queryKey: ["posts", label],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => endpoints.posts(label || undefined, pageParam),
    getNextPageParam: (page) => page.nextCursor || undefined,
  });
}

export function useLabels(search: string) {
  return useQuery({
    queryKey: ["labels", search],
    queryFn: () => endpoints.labels(search || undefined),
  });
}

export function useCreatePost() {
  const query = useQueryClient();
  return useMutation({
    mutationFn: async ({
      file,
      description,
    }: {
      file: File;
      description: string;
    }) => {
      const { imageKey } = await endpoints.upload("post", file);
      return endpoints.createPost(imageKey, description.trim() || undefined);
    },
    onSuccess: async () => {
      await query.invalidateQueries({ queryKey: ["posts"] });
    },
  });
}

export function useComments(postId: string) {
  return useQuery({
    queryKey: ["comments", postId],
    queryFn: () => endpoints.comments(postId),
  });
}

export function useCreateComment(postId: string) {
  const query = useQueryClient();
  return useMutation({
    mutationFn: (body: string) => endpoints.addComment(postId, body.trim()),
    onSuccess: async () => {
      await Promise.all([
        query.invalidateQueries({ queryKey: ["comments", postId] }),
        query.invalidateQueries({ queryKey: ["posts"] }),
      ]);
    },
  });
}

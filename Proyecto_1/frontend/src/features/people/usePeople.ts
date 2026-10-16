import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { endpoints } from "../../lib/api/endpoints";

export function usePeople() {
  return useInfiniteQuery({
    queryKey: ["users"],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => endpoints.users(pageParam),
    getNextPageParam: (page) => page.nextCursor || undefined,
  });
}

export function useFriendRequests() {
  return useQuery({ queryKey: ["requests"], queryFn: endpoints.requests });
}

export function useFriends() {
  return useQuery({ queryKey: ["friends"], queryFn: endpoints.friends });
}

export function useSendRequest() {
  const query = useQueryClient();
  return useMutation({
    mutationFn: endpoints.requestFriend,
    onSuccess: async () => {
      await Promise.all([
        query.invalidateQueries({ queryKey: ["requests"] }),
        query.invalidateQueries({ queryKey: ["users"] }),
      ]);
    },
  });
}

export function useAnswerRequest() {
  const query = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      decision,
    }: {
      id: string;
      decision: "accepted" | "rejected";
    }) => endpoints.answerRequest(id, decision),
    onSuccess: async () => {
      await Promise.all([
        query.invalidateQueries({ queryKey: ["requests"] }),
        query.invalidateQueries({ queryKey: ["users"] }),
        query.invalidateQueries({ queryKey: ["friends"] }),
      ]);
    },
  });
}

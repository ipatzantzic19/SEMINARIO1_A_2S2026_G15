import { useEffect, useMemo, useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { endpoints } from "../../lib/api/endpoints";
import type { Message } from "../../lib/api/types";
import { useSession } from "../auth/session";
import type { ChatConnectionState, ChatTransport } from "./chatTransport";

export type VisibleMessage = Message & {
  clientMessageId?: string;
  delivery?: "sending" | "failed";
};

function orderedUnique(messages: VisibleMessage[]) {
  const unique = new Map<string, VisibleMessage>();
  for (const message of messages) {
    unique.set(message.messageId, message);
  }
  return [...unique.values()].sort(
    (left, right) =>
      new Date(left.createdAt).getTime() - new Date(right.createdAt).getTime(),
  );
}

export function useChatConversation({
  friendId,
  currentUserId,
  transport,
}: {
  friendId: string;
  currentUserId?: string;
  transport?: ChatTransport;
}) {
  const accessToken = useSession((state) => state.tokens?.accessToken);
  const [liveMessages, setLiveMessages] = useState<VisibleMessage[]>([]);
  const [connection, setConnection] = useState<
    ChatConnectionState | "unavailable"
  >(transport ? "connecting" : "unavailable");

  const history = useInfiniteQuery({
    queryKey: ["messages", friendId],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => endpoints.messages(friendId, pageParam),
    getNextPageParam: (page) => page.nextCursor || undefined,
  });

  useEffect(() => {
    setLiveMessages([]);
    if (!transport || !accessToken) {
      setConnection("unavailable");
      return;
    }

    setConnection("connecting");
    return transport.connect(accessToken, friendId, {
      onMessage: (message) => {
        if (
          message.senderId !== friendId &&
          message.recipientId !== friendId
        )
          return;
        setLiveMessages((current) => orderedUnique([...current, message]));
      },
      onStateChange: setConnection,
      onReconnected: () => void history.refetch(),
    });
  }, [accessToken, friendId, history.refetch, transport]);

  const messages = useMemo(
    () =>
      orderedUnique([
        ...(history.data?.pages.flatMap((page) => page.items) || []),
        ...liveMessages,
      ]),
    [history.data, liveMessages],
  );

  async function send(body: string, retryId?: string) {
    if (!transport || !currentUserId || connection !== "connected") return;
    const clientMessageId = retryId || crypto.randomUUID();
    const optimistic: VisibleMessage = {
      messageId: clientMessageId,
      clientMessageId,
      senderId: currentUserId,
      recipientId: friendId,
      body,
      createdAt: new Date().toISOString(),
      delivery: "sending",
    };
    setLiveMessages((current) =>
      orderedUnique([
        ...current.filter((message) => message.messageId !== clientMessageId),
        optimistic,
      ]),
    );

    try {
      const persisted = await transport.send({
        clientMessageId,
        recipientId: friendId,
        body,
      });
      setLiveMessages((current) =>
        orderedUnique([
          ...current.filter(
            (message) => message.messageId !== clientMessageId,
          ),
          persisted,
        ]),
      );
    } catch {
      setLiveMessages((current) =>
        current.map((message) =>
          message.messageId === clientMessageId
            ? { ...message, delivery: "failed" }
            : message,
        ),
      );
    }
  }

  return {
    connection,
    history,
    messages,
    send,
  };
}


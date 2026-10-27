import { api, uploads } from "./client";
import type {
  AuthChallenge,
  Comment,
  FriendRequest,
  Label,
  Message,
  Page,
  Post,
  Profile,
  PublicUser,
  TokenSet,
  UploadResult,
} from "./types";

export const endpoints = {
  register: async (body: {
    fullName: string;
    email: string;
    dpi: string;
    password: string;
  }) =>
    (await api.post("/auth/register", body)).data as {
      userId: string;
      email: string;
      confirmationRequired: boolean;
      profileComplete: boolean;
    },
  confirm: async (body: { email: string; code: string }) => {
    await api.post("/auth/confirm", body);
  },
  resendConfirmation: async (email: string) => {
    await api.post("/auth/confirm/resend", { email });
  },
  login: async (body: { email: string; password: string }) =>
    api.post<TokenSet | AuthChallenge>("/auth/login", body),
  createFaceChallenge: async (email: string) =>
    (await api.post("/auth/face/challenges", { email })).data as {
      challengeId: string;
      uploadToken: string;
      expiresAt: string;
    },
  verifyFaceChallenge: async (challengeId: string, captureKey: string) =>
    (
      await api.post<TokenSet>(
        `/auth/face/challenges/${encodeURIComponent(challengeId)}/verify`,
        { captureKey },
      )
    ).data,
  me: async () => (await api.get<Profile>("/me")).data,
  updateMe: async (body: {
    fullName?: string;
    dpi?: string;
    profileImageKey?: string;
    currentPassword: string;
  }) => (await api.patch<Profile>("/me", body)).data,
  completeProfile: async (profileImageKey: string) =>
    (await api.post<Profile>("/me/complete-profile", { profileImageKey })).data,
  users: async (cursor?: string) =>
    (
      await api.get<Page<PublicUser>>("/users", {
        params: { cursor, limit: 20 },
      })
    ).data,
  requests: async () =>
    (await api.get<FriendRequest[]>("/friend-requests")).data,
  requestFriend: async (addresseeId: string) =>
    (await api.post<FriendRequest>("/friend-requests", { addresseeId })).data,
  answerRequest: async (requestId: string, decision: "accepted" | "rejected") =>
    (
      await api.patch<FriendRequest>(
        `/friend-requests/${encodeURIComponent(requestId)}`,
        { decision },
      )
    ).data,
  friends: async () => (await api.get<PublicUser[]>("/friends")).data,
  posts: async (label?: string, cursor?: string) =>
    (
      await api.get<Page<Post>>("/posts", {
        params: { label, cursor, limit: 20 },
      })
    ).data,
  createPost: async (imageKey: string, description?: string) =>
    (
      await api.post<Post>("/posts", {
        imageKey,
        description: description || null,
      })
    ).data,
  comments: async (postId: string) =>
    (await api.get<Comment[]>(`/posts/${encodeURIComponent(postId)}/comments`))
      .data,
  addComment: async (postId: string, body: string) =>
    (
      await api.post<Comment>(`/posts/${encodeURIComponent(postId)}/comments`, {
        body,
      })
    ).data,
  labels: async (q?: string) =>
    (await api.get<Label[]>("/labels", { params: { q } })).data,
  translate: async (text: string, targetLanguage: "es" | "en" | "fr" | "de") =>
    (
      await api.post<{
        translatedText: string;
        sourceLanguage: string;
        targetLanguage: string;
      }>("/translations", { text, targetLanguage })
    ).data,
  bot: async (text: string, sessionId: string) =>
    (
      await api.post<{ messages: string[]; sessionId: string }>(
        "/bot/messages",
        { text, sessionId },
      )
    ).data,
  messages: async (friendId: string, cursor?: string) =>
    (
      await api.get<Page<Message>>(
        `/conversations/${encodeURIComponent(friendId)}/messages`,
        { params: { cursor, limit: 50 } },
      )
    ).data,
  upload: async (
    purpose: "profile" | "post" | "faceCapture",
    file: File,
    face?: { challengeId: string; uploadToken: string },
  ) => {
    const form = new FormData();
    form.append("purpose", purpose);
    form.append("file", file);
    if (face) form.append("challengeId", face.challengeId);
    const result = await uploads.post<UploadResult>("/uploads/images", form, {
      headers: face ? { "X-Face-Upload-Token": face.uploadToken } : undefined,
    });
    return result.data;
  },
};

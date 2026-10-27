export type PublicUser = {
  userId: string;
  fullName: string;
  profileImageUrl: string;
};
export type Profile = Omit<PublicUser, "profileImageUrl"> & {
  email: string;
  dpi: string;
  profileImageUrl: string | null;
  profileComplete: boolean;
};
export type TokenSet = {
  accessToken: string;
  idToken: string;
  refreshToken: string;
  expiresIn: number;
  tokenType: "Bearer";
  profileComplete: boolean;
};
export type AuthChallenge = {
  challenge: string;
  session: string;
  parameters?: Record<string, string>;
};
export type ApiError = {
  code: string;
  message: string;
  requestId: string;
  details?: unknown;
};
export type UploadResult = { imageKey: string; imageUrl: string | null };
export type Post = {
  postId: string;
  author: PublicUser;
  imageUrl: string;
  description?: string | null;
  labels: string[];
  commentsCount: number;
  createdAt: string;
};
export type Comment = {
  commentId: string;
  author: PublicUser;
  body: string;
  createdAt: string;
};
export type FriendRequest = {
  requestId: string;
  requester: PublicUser;
  addressee: PublicUser;
  status: "pending" | "accepted" | "rejected";
  createdAt: string;
};
export type Message = {
  messageId: string;
  senderId: string;
  recipientId: string;
  body: string;
  createdAt: string;
  readAt?: string | null;
};
export type Page<T> = { items: T[]; nextCursor?: string | null };
export type Label = { name: string; postCount: number };

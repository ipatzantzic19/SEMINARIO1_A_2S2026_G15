import { Injectable } from '@nestjs/common';
import {
  DatabaseService,
  FriendRequestDtoResponse,
  PublicUserInfo,
} from '../../database/database.service';

@Injectable()
export class FriendsService {
  constructor(private readonly databaseService: DatabaseService) {}

  async getFriends(userId: string): Promise<PublicUserInfo[]> {
    return this.databaseService.listFriends(userId);
  }

  async getFriendRequests(userId: string): Promise<FriendRequestDtoResponse[]> {
    return this.databaseService.listFriendRequests(userId);
  }

  async sendFriendRequest(
    requesterId: string,
    addresseeId: string,
  ): Promise<FriendRequestDtoResponse> {
    return this.databaseService.createFriendRequest(requesterId, addresseeId);
  }

  async decideFriendRequest(
    requestId: string,
    userId: string,
    decision: 'accepted' | 'rejected',
  ): Promise<FriendRequestDtoResponse> {
    return this.databaseService.answerFriendRequest(requestId, userId, decision);
  }
}

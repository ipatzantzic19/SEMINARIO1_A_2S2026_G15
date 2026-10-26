import { HttpException, HttpStatus, Injectable } from '@nestjs/common';

export interface FaceChallenge {
  challengeId: string;
  username: string;
  session: string | null;
  uploadToken: string;
  expiresAt: number;
}

const DEFAULT_MAX_ENTRIES = 1000;

@Injectable()
export class FaceChallengeStore {
  private readonly maxEntries: number = DEFAULT_MAX_ENTRIES;
  private readonly items = new Map<string, FaceChallenge>();

  constructor() {}


  public add(challenge: FaceChallenge): void {
    this.purgeExpired();
    if (!this.items.has(challenge.challengeId) && this.items.size >= this.maxEntries) {
      throw new HttpException(
        {
          code: 'RATE_LIMITED',
          message: 'Se excedió el límite de desafíos en memoria. Intente más tarde.',
        },
        HttpStatus.TOO_MANY_REQUESTS,
      );
    }
    this.items.set(challenge.challengeId, challenge);
  }

  public take(challengeId: string): FaceChallenge | null {
    const challenge = this.items.get(challengeId);
    if (!challenge) {
      return null;
    }
    this.items.delete(challengeId);
    if (challenge.expiresAt <= Date.now()) {
      return null;
    }
    return challenge;
  }

  public putBack(challenge: FaceChallenge): void {
    if (challenge.expiresAt > Date.now()) {
      this.items.set(challenge.challengeId, challenge);
    }
  }

  public get size(): number {
    this.purgeExpired();
    return this.items.size;
  }

  private purgeExpired(): void {
    const now = Date.now();
    for (const [key, item] of this.items.entries()) {
      if (item.expiresAt <= now) {
        this.items.delete(key);
      }
    }
  }
}

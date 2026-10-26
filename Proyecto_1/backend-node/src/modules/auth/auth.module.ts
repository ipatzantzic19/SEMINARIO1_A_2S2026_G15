import { Module } from '@nestjs/common';
import { AuthController } from './auth.controller';
import { AuthService } from './auth.service';
import { FaceChallengeStore } from './face-challenge.store';

@Module({
  controllers: [AuthController],
  providers: [AuthService, FaceChallengeStore],
  exports: [AuthService, FaceChallengeStore],
})
export class AuthModule {}

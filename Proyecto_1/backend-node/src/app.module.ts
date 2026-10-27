import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { APP_GUARD, APP_INTERCEPTOR, APP_FILTER } from '@nestjs/core';

import configuration from './config/configuration';
import { DatabaseModule } from './database/database.module';
import { CognitoAuthGuard } from './common/guards/cognito-auth.guard';
import { RequestIdInterceptor } from './common/interceptors/request-id.interceptor';
import { LoggingInterceptor } from './common/interceptors/logging.interceptor';
import { AllExceptionsFilter } from './common/filters/all-exceptions.filter';

import { HealthModule } from './modules/health/health.module';
import { AuthModule } from './modules/auth/auth.module';
import { UsersModule } from './modules/users/users.module';
import { PostsModule } from './modules/posts/posts.module';
import { CommentsModule } from './modules/comments/comments.module';
import { FriendsModule } from './modules/friends/friends.module';
import { ChatModule } from './modules/chat/chat.module';
import { TranslateModule } from './modules/translate/translate.module';
import { BotModule } from './modules/bot/bot.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      load: [configuration],
    }),
    DatabaseModule,
    HealthModule,
    AuthModule,
    UsersModule,
    PostsModule,
    CommentsModule,
    FriendsModule,
    ChatModule,
    TranslateModule,
    BotModule,
  ],
  providers: [
    {
      provide: APP_GUARD,
      useClass: CognitoAuthGuard,
    },
    {
      provide: APP_INTERCEPTOR,
      useClass: RequestIdInterceptor,
    },
    {
      provide: APP_INTERCEPTOR,
      useClass: LoggingInterceptor,
    },
    {
      provide: APP_FILTER,
      useClass: AllExceptionsFilter,
    },
  ],
})
export class AppModule {}

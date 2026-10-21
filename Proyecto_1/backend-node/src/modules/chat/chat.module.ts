import { Module } from '@nestjs/common';
import { ChatController } from './chat.controller';
import { ChatGateway } from './chat.gateway';
import { ChatSubscriberService } from './chat-subscriber.service';

@Module({
  controllers: [ChatController],
  providers: [ChatGateway, ChatSubscriberService],
  exports: [ChatGateway, ChatSubscriberService],
})
export class ChatModule {}

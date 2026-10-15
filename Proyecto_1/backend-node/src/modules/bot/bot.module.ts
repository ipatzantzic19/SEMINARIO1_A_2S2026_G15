import { Module } from '@nestjs/common';
import { BotController } from './bot.controller';

@Module({
  controllers: [BotController],
})
export class BotModule {}

import { Module } from '@nestjs/common';
import { TranslateController } from './translate.controller';

@Module({
  controllers: [TranslateController],
})
export class TranslateModule {}

import { Module } from '@nestjs/common';
import { PostsController } from './posts.controller';
import { RekognitionService } from './rekognition.service';

@Module({
  controllers: [PostsController],
  providers: [RekognitionService],
  exports: [RekognitionService],
})
export class PostsModule {}

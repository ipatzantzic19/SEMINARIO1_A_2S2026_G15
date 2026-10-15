import { Controller, Get, Post, Param, Body } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import { CurrentUser, AuthUser } from '../../common/decorators/current-user.decorator';
import { v4 as uuidv4 } from 'uuid';

@ApiTags('Comentarios')
@ApiBearerAuth()
@Controller('posts/:postId/comments')
export class CommentsController {
  @Get()
  @ApiOperation({ summary: 'Listar comentarios de una publicación' })
  async getComments(@Param('postId') postId: string) {
    return {
      postId,
      comments: [
        {
          id: uuidv4(),
          author: {
            userId: 'user-javier-uuid-222',
            fullName: 'Javier Velasquez',
            profileImageUrl: 'https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Perfil/public/javier.jpg',
          },
          content: '¡Excelente iniciativa para el proyecto 1!',
          createdAt: new Date().toISOString(),
        },
      ],
    };
  }

  @Post()
  @ApiOperation({ summary: 'Agregar un comentario a una publicación (solo amigos)' })
  async addComment(
    @CurrentUser() user: AuthUser,
    @Param('postId') postId: string,
    @Body() body: { content: string },
  ) {
    return {
      id: uuidv4(),
      postId,
      author: {
        userId: user.userId,
        fullName: 'Daniel Abraham Ortiz',
        profileImageUrl: 'https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Perfil/public/daniel.jpg',
      },
      content: body.content,
      createdAt: new Date().toISOString(),
    };
  }
}

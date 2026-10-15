import { Controller, Get, Post, Body, Query } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth, ApiQuery } from '@nestjs/swagger';
import { CurrentUser, AuthUser } from '../../common/decorators/current-user.decorator';
import { v4 as uuidv4 } from 'uuid';

@ApiTags('Publicaciones')
@ApiBearerAuth()
@Controller()
export class PostsController {
  @Get('posts')
  @ApiOperation({ summary: 'Obtener feed de publicaciones (propias y de amigos) ordenadas por fecha descendente' })
  @ApiQuery({ name: 'label', required: false, description: 'Filtrar por etiqueta de Rekognition' })
  @ApiQuery({ name: 'cursor', required: false })
  @ApiQuery({ name: 'limit', required: false })
  async getFeed(
    @CurrentUser() user: AuthUser,
    @Query('label') label?: string,
    @Query('cursor') cursor?: string,
    @Query('limit') limit = 10,
  ) {
    const postItems = [
      {
        id: uuidv4(),
        author: {
          userId: user.userId,
          fullName: 'Daniel Abraham Ortiz',
          profileImageUrl: 'https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Perfil/public/daniel.jpg',
        },
        description: '¡Bienvenidos al proyecto Semi-Social desplegado en AWS!',
        imageKey: 'Fotos_Publicadas/mock-post.jpg',
        imageUrl: 'https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Publicadas/mock-post.jpg',
        labels: ['Technology', 'Cloud', 'Engineering'],
        commentsCount: 2,
        createdAt: new Date().toISOString(),
      },
    ];

    return {
      items: postItems,
      posts: postItems, // Compatibilidad dual
      nextCursor: null,
    };
  }

  @Post('posts')
  @ApiOperation({ summary: 'Crear una nueva publicación (imagen obligatoria, descripción opcional)' })
  async createPost(
    @CurrentUser() user: AuthUser,
    @Body() body: { imageKey: string; description?: string },
  ) {
    return {
      id: uuidv4(),
      authorId: user.userId,
      imageKey: body.imageKey,
      imageUrl: `https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/${body.imageKey}`,
      description: body.description || null,
      labels: ['General', 'Cloud'],
      createdAt: new Date().toISOString(),
    };
  }

  @Get('labels')
  @ApiOperation({ summary: 'Listar etiquetas detectadas por Rekognition para filtros y buscador' })
  async getLabels() {
    const labelsList = [
      { name: 'Todos', postCount: 15, count: 15 },
      { name: 'Technology', postCount: 8, count: 8 },
      { name: 'Engineering', postCount: 5, count: 5 },
      { name: 'Cloud', postCount: 4, count: 4 },
      { name: 'Campus', postCount: 3, count: 3 },
    ];

    return {
      labels: labelsList,
      items: labelsList,
    };
  }
}

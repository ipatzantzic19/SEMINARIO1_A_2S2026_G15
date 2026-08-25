import { Module } from '@nestjs/common';
import { JwtModule } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';
import { AutenticacionController } from './autenticacion.controller';
import { AutenticacionService } from './autenticacion.service';

@Module({
  imports: [
    JwtModule.registerAsync({
      inject: [ConfigService],
      useFactory: (configService: ConfigService) => ({
        secret: configService.get<string>('jwtSecret'),
        signOptions: { 
          expiresIn: '1h', 
          algorithm: 'HS256' 
        },
      }),
    }),
  ],
  controllers: [AutenticacionController],
  providers: [AutenticacionService],
  exports: [AutenticacionService, JwtModule],
})
export class AutenticacionModule {}

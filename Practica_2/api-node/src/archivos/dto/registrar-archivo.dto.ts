import { IsString, IsNotEmpty, MaxLength, IsInt, Min, IsIn, Matches } from 'class-validator';

export class RegistrarArchivoDto {
  @IsString({ message: 'El nombre original debe ser una cadena de texto.' })
  @IsNotEmpty({ message: 'El nombre original no puede estar vacío.' })
  @MaxLength(255, { message: 'El nombre original no puede exceder 255 caracteres.' })
  nombreOriginal: string;

  @IsString({ message: 'El tipo MIME debe ser una cadena de texto.' })
  @IsNotEmpty({ message: 'El tipo MIME no puede estar vacío.' })
  @MaxLength(255, { message: 'El tipo MIME no puede exceder 255 caracteres.' })
  tipoMime: string;

  @IsInt({ message: 'El tamaño en bytes debe ser un número entero.' })
  @Min(0, { message: 'El tamaño en bytes debe ser mayor o igual a 0.' })
  tamanoBytes: number;

  @IsString({ message: 'El proveedor de almacenamiento debe ser una cadena de texto.' })
  @IsIn(['S3', 'BLOB'], { message: 'El proveedor de almacenamiento debe ser S3 o BLOB.' })
  proveedorAlmacenamiento: 'S3' | 'BLOB';

  @IsString({ message: 'La clave de objeto debe ser una cadena de texto.' })
  @IsNotEmpty({ message: 'La clave de objeto no puede estar vacía.' })
  claveObjeto: string;

  @IsString({ message: 'La URL de objeto debe ser una cadena de texto.' })
  @Matches(/^https:\/\/\S+$/, { message: 'La URL de objeto debe ser una URL HTTPS válida.' })
  urlObjeto: string;
}

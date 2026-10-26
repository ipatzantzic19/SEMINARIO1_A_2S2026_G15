import { BadRequestException, NotFoundException } from '@nestjs/common';
import { RekognitionService } from './rekognition.service';

function createService(mockMode = false): RekognitionService {
  const values: Record<string, unknown> = {
    awsRegion: 'us-east-1',
    's3.imagesBucket': 'semisocial-g15-images-581117996165',
    mockMode,
  };
  const config = { get: jest.fn((key: string) => values[key]) } as any;
  const service = new RekognitionService(config);
  (service as any).s3Client = {
    send: jest.fn().mockResolvedValue({ ContentType: 'image/jpeg', ContentLength: 1024 }),
  };
  return service;
}

describe('RekognitionService shared labels contract', () => {
  it('normalizes names with NFC, lowercase Spanish mapping and two decimals', () => {
    const service = createService();

    expect(service.normalizeLabel('  DOG  ', 98.126)).toEqual({
      name: 'perro',
      confidence: 98.13,
      sourceName: 'DOG',
    });
    expect(service.normalizeLabel(' Outdoors ', 91.444)).toEqual({
      name: 'exterior',
      confidence: 91.44,
      sourceName: 'Outdoors',
    });
  });

  it('rejects private profile and facial-capture prefixes', async () => {
    const service = createService();

    await expect(service.detectLabels('Fotos_Perfil/public/user/photo.jpg')).rejects.toBeInstanceOf(
      BadRequestException,
    );
    await expect(service.detectLabels('Fotos_Perfil/captures/challenge/photo.jpg')).rejects.toBeInstanceOf(
      BadRequestException,
    );
  });

  it('filters low-confidence labels and returns an empty list when none qualify', async () => {
    const service = createService();
    (service as any).rekognitionClient = {
      send: jest.fn().mockResolvedValue({
        Labels: [
          { Name: 'Dog', Confidence: 98.126 },
          { Name: 'Low', Confidence: 79.99 },
          { Name: '', Confidence: 99 },
        ],
      }),
    };

    await expect(service.detectLabels('Fotos_Publicadas/user/post.jpg')).resolves.toEqual([
      { name: 'perro', confidence: 98.13, sourceName: 'Dog' },
    ]);

    (service as any).rekognitionClient.send = jest.fn().mockResolvedValue({ Labels: [] });
    await expect(service.detectLabels('Fotos_Publicadas/user/empty.jpg')).resolves.toEqual([]);
  });

  it('maps a missing S3 object to IMAGE_NOT_FOUND without invoking Rekognition', async () => {
    const service = createService();
    const s3Send = jest.fn().mockRejectedValue({ name: 'NoSuchKey', message: 'missing' });
    const rekognitionSend = jest.fn();
    (service as any).s3Client = { send: s3Send };
    (service as any).rekognitionClient = { send: rekognitionSend };

    await expect(service.detectLabels('Fotos_Publicadas/user/missing.jpg')).rejects.toBeInstanceOf(
      NotFoundException,
    );
    expect(s3Send).toHaveBeenCalledTimes(1);
    expect(rekognitionSend).not.toHaveBeenCalled();
  });

  it('rejects unsupported MIME types before invoking Rekognition', async () => {
    const service = createService();
    (service as any).s3Client = {
      send: jest.fn().mockResolvedValue({ ContentType: 'image/webp', ContentLength: 1024 }),
    };
    const rekognitionSend = jest.fn();
    (service as any).rekognitionClient = { send: rekognitionSend };

    await expect(service.detectLabels('Fotos_Publicadas/user/photo.webp')).rejects.toBeInstanceOf(
      BadRequestException,
    );
    expect(rekognitionSend).not.toHaveBeenCalled();
  });
});

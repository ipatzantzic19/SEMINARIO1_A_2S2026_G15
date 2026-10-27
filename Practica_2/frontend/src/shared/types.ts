export type Cloud = 'aws' | 'azure';
export type Mode = 'mock' | 'real';
export type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;
export type Transport = (input: string, init?: RequestInit) => Promise<Response>;

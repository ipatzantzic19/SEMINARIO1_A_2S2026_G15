import type { CSSProperties } from 'react';

const paths = {
  check: 'm5 12 4 4L19 6',
  tasks: 'M9 5h11M9 12h11M9 19h11M3 5h1M3 12h1M3 19h1',
  cloud: 'M7 18a5 5 0 0 1-1-9 6 6 0 0 1 11-2 5 5 0 0 1 1 11H7Z',
  plus: 'M12 5v14M5 12h14',
  search: 'm16 16 4 4M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z',
  arrow: 'M5 12h14m-6-6 6 6-6 6',
  upload: 'M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5',
  file: 'M14 2H5v20h14V7l-5-5Zm0 0v6h6M8 13h8M8 17h5',
  image: 'M3 3h18v18H3V3Zm0 14 6-6 5 5 3-3 4 4M16 7h.01',
  edit: 'm14 4 6 6M3 21l5-1L21 7l-5-5L3 15v6Z',
  trash: 'M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7',
  close: 'm6 6 12 12M6 18 18 6',
  logout: 'M9 4H4v16h5M9 12h12m-5-5 5 5-5 5',
  clock: 'M12 8v5l3 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z',
  external: 'M14 3h7v7m0-7L10 14M10 3H3v18h18v-7',
  grid: 'M3 3h7v7H3V3Zm11 0h7v7h-7V3ZM3 14h7v7H3v-7Zm11 0h7v7h-7v-7Z',
  lock: 'M5 10h14v11H5V10Zm3 0V6a4 4 0 0 1 8 0v4M12 14v3',
};
export type IconName = keyof typeof paths;
export default function Icon({ name, size = 20, style }: { name: IconName; size?: number; style?: CSSProperties }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={style}><path d={paths[name]} /></svg>;
}

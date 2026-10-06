import type { z } from 'zod';

export function validateForm<T>(schema: z.ZodType<T>, value: unknown): T {
  const result = schema.safeParse(value);
  if (!result.success) throw new Error(result.error.issues.map(issue => issue.message).join(' · '));
  return result.data;
}

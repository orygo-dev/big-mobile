import { describe, expect, it, vi } from 'vitest';
import { mergeMessages, messageId } from './AssignmentChat';

describe('chat delivery reconciliation', () => {
  it('creates retry IDs when randomUUID is unavailable', () => {
    const getRandomValues = vi.fn(array => { array.fill(7); return array; });
    vi.stubGlobal('crypto', {getRandomValues});
    try {
      expect(messageId()).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
      expect(getRandomValues).toHaveBeenCalledOnce();
    } finally { vi.unstubAllGlobals(); }
  });
  it('keeps messages arriving between send and poll and removes retry duplicates', () => {
    const own = { id: 'own', sequence: 3, text: 'hello' };
    const result = mergeMessages([{ id: 'first', sequence: 1 }, own], [{ id: 'incoming', sequence: 2 }, own]);
    expect(result.map(item => item.id)).toEqual(['first', 'incoming', 'own']);
  });
});

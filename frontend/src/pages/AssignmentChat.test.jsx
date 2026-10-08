import { describe, expect, it } from 'vitest';
import { mergeMessages } from './AssignmentChat';

describe('chat delivery reconciliation', () => {
  it('keeps messages arriving between send and poll and removes retry duplicates', () => {
    const own = { id: 'own', sequence: 3, text: 'hello' };
    const result = mergeMessages([{ id: 'first', sequence: 1 }, own], [{ id: 'incoming', sequence: 2 }, own]);
    expect(result.map(item => item.id)).toEqual(['first', 'incoming', 'own']);
  });
});

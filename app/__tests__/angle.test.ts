import { expect, it } from '@jest/globals';
import { angleHintHe, needsAnotherAngle } from '../src/model/advice';

const head = (c: number) => ({ label: 'fresh', available: true, confidence: c });

it('asks for another angle only when the fruit is known but its condition is uncertain', () => {
  expect(needsAnotherAngle({ status: 'ok', freshness: head(0.6) }, 1)).toBe(true);
  expect(needsAnotherAngle({ status: 'ok', freshness: head(0.95), visual_spoilage: head(0.9) }, 1)).toBe(false);
  expect(needsAnotherAngle({ status: 'ok', freshness: head(0.6) }, 2)).toBe(false); // already combined two photos
  expect(needsAnotherAngle({ status: 'unsure', freshness: head(0.6) }, 1)).toBe(false); // identification flow handles it
  expect(needsAnotherAngle({ status: 'ok', freshness: { label: null, available: false, confidence: null } }, 1)).toBe(false);
});

it('gives berries a specific hint', () => {
  expect(angleHintHe('strawberry')).toContain('מלמטה');
  expect(angleHintHe('apple')).toContain('הצד השני');
});

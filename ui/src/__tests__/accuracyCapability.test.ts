import { afterEach, describe, expect, it, vi } from 'vitest';
import { SidecarClient } from '../api/sidecarClient';

afterEach(() => { delete (window as any).__TAURI__; });

function health(value: unknown) {
  const invoke = vi.fn().mockResolvedValue(value);
  (window as any).__TAURI__ = { core: { invoke } };
  return invoke;
}

describe('optional pack health gate', () => {
  it('uses the existing narrow health command', async () => {
    const invoke = health({ status: 'ready', ocr_available: true, accuracy_languages: ['en'] });
    expect(await new SidecarClient().hasEnglishAccuracyPack()).toBe(true);
    expect(invoke).toHaveBeenCalledWith('health_check');
  });

  it.each([
    { status: 'unavailable', ocr_available: true, accuracy_languages: ['en'] },
    { status: 'ready', ocr_available: false, accuracy_languages: ['en'] },
    { status: 'ready', ocr_available: true, accuracy_languages: 'en' },
    { status: 'ready', ocr_available: true, accuracy_languages: ['ar'] },
    null,
  ])('rejects missing, malformed, or unsupported capabilities', async value => {
    health(value);
    expect(await new SidecarClient().hasEnglishAccuracyPack()).toBe(false);
  });
});

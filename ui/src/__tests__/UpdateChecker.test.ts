import { describe, expect, it } from 'vitest';
import {
  isNewerVersion,
  isAutoUpdateEnabled,
  setAutoUpdateEnabled,
  CURRENT_VERSION,
} from '../api/update-checker';

describe('In-App Update Checker', () => {
  it('correctly compares semantic versions', () => {
    expect(isNewerVersion('0.1.0', '0.2.0')).toBe(true);
    expect(isNewerVersion('0.1.0', 'v0.2.0')).toBe(true);
    expect(isNewerVersion('0.1.0', '1.0.0')).toBe(true);
    expect(isNewerVersion('0.1.0', '0.1.1')).toBe(true);

    expect(isNewerVersion('0.1.0', '0.1.0')).toBe(false);
    expect(isNewerVersion('0.1.0', 'v0.1.0')).toBe(false);
    expect(isNewerVersion('0.2.0', '0.1.0')).toBe(false);
    expect(isNewerVersion('1.0.0', '0.9.9')).toBe(false);
  });

  it('persists and retrieves auto-update settings', () => {
    setAutoUpdateEnabled(true);
    expect(isAutoUpdateEnabled()).toBe(true);

    setAutoUpdateEnabled(false);
    expect(isAutoUpdateEnabled()).toBe(false);

    // Reset back to true for default behavior
    setAutoUpdateEnabled(true);
    expect(isAutoUpdateEnabled()).toBe(true);
  });

  it('has a valid current version format', () => {
    expect(CURRENT_VERSION).toMatch(/^\d+\.\d+\.\d+/);
  });
});

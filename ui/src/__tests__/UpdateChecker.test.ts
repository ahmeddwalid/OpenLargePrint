import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  CURRENT_VERSION,
  checkForUpdates,
  dismissUpdate,
  isAutoUpdateEnabled,
  isNewerVersion,
  isUpdateDismissed,
  setAutoUpdateEnabled,
} from '../api/update-checker';

function fakeDesktop(answer: unknown) {
  const invoke = vi.fn(async (cmd: string) => {
    if (cmd !== 'check_for_update') throw new Error(`unexpected ${cmd}`);
    if (answer instanceof Error) throw answer;
    return answer;
  });
  (window as any).__TAURI__ = { core: { invoke } };
  return invoke;
}

afterEach(() => {
  delete (window as any).__TAURI__;
  localStorage.clear();
});

describe('version comparison', () => {
  it('compares release numbers', () => {
    expect(isNewerVersion('0.6.0', 'v0.7.0')).toBe(true);
    expect(isNewerVersion('0.6.0', '0.6.1')).toBe(true);
    expect(isNewerVersion('0.9.9', '1.0')).toBe(true);
    expect(isNewerVersion('1.0.0-rc.1', '1.0.0')).toBe(true);
    expect(isNewerVersion('0.7.0', 'v0.7.0')).toBe(false);
    expect(isNewerVersion('1.0.0', '0.9.9')).toBe(false);
    expect(isNewerVersion('1.0.0', '1.0.0-rc.1')).toBe(false);
    expect(isNewerVersion('1.0.0', 'latest')).toBe(false);
  });

  it('has a valid current version', () => {
    expect(CURRENT_VERSION).toMatch(/^\d+\.\d+\.\d+/);
  });
});

describe('looking for a new version', () => {
  it('is on by default and can be turned off', () => {
    expect(isAutoUpdateEnabled()).toBe(true);
    setAutoUpdateEnabled(false);
    expect(isAutoUpdateEnabled()).toBe(false);
  });

  it('asks the desktop app, never the network from the page', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    const invoke = fakeDesktop({
      available: true, current_version: '0.6.0', latest_version: '0.7.0', release_notes: 'Notes',
      install_kind: 'installer', can_install: true, download_size: 300 * 1048576,
    });
    const info = await checkForUpdates(true);
    expect(invoke).toHaveBeenCalledWith('check_for_update');
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(info).toMatchObject({ available: true, latestVersion: '0.7.0', canInstall: true, installKind: 'installer' });
    fetchSpy.mockRestore();
  });

  it('checks automatically at most once a day, and not when turned off', async () => {
    const invoke = fakeDesktop({ available: false, current_version: '0.7.0', latest_version: '0.7.0' });
    expect(await checkForUpdates(false)).not.toBeNull();
    expect(await checkForUpdates(false)).toBeNull();
    expect(invoke).toHaveBeenCalledTimes(1);
    localStorage.clear();
    setAutoUpdateEnabled(false);
    expect(await checkForUpdates(false)).toBeNull();
    expect(await checkForUpdates(true)).not.toBeNull();  // "Look now" always asks
    expect(invoke).toHaveBeenCalledTimes(2);
  });

  it('reports a failed check instead of claiming to be up to date', async () => {
    fakeDesktop(new Error('Could not reach GitHub.'));
    await expect(checkForUpdates(true)).rejects.toThrow('Could not reach GitHub.');
  });

  it('does nothing outside the desktop app', async () => {
    expect(await checkForUpdates(true)).toBeNull();
  });

  it('remembers a dismissed version', () => {
    dismissUpdate('0.7.0');
    expect(isUpdateDismissed('0.7.0')).toBe(true);
    expect(isUpdateDismissed('0.7.1')).toBe(false);
  });
});

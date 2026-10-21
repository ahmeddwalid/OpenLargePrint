import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { UpdateNotification } from '../components/UpdateNotification';
import { UpdateInfo } from '../api/update-checker';

const base: UpdateInfo = {
  available: true, currentVersion: '0.6.0', latestVersion: '0.7.0',
  installKind: 'installer', canInstall: true, downloadSize: 300 * 1048576,
};

afterEach(() => {
  delete (window as any).__TAURI__;
  localStorage.clear();
});

describe('new version banner', () => {
  it('offers to install when the app can verify and install the update', () => {
    render(<UpdateNotification updateInfo={base} />);
    expect(screen.getByRole('heading', { name: 'OpenLargePrint 0.7.0 is available' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Download and install' })).toBeEnabled();
    expect(screen.getByText(/300 MB download/)).toBeInTheDocument();
  });

  it('sends portable and package installs to the release page', async () => {
    const invoke = vi.fn(async () => undefined);
    (window as any).__TAURI__ = { core: { invoke } };
    render(<UpdateNotification updateInfo={{ ...base, installKind: 'manual', canInstall: false }} />);
    fireEvent.click(screen.getByRole('button', { name: 'Open the download page' }));
    await waitFor(() => expect(invoke).toHaveBeenCalledWith('open_release_page'));
  });

  it('explains a failed install and offers to try again', async () => {
    (window as any).__TAURI__ = {
      core: { invoke: vi.fn(async () => { throw new Error('The downloaded file does not match the release checksum.'); }) },
    };
    render(<UpdateNotification updateInfo={base} />);
    fireEvent.click(screen.getByRole('button', { name: 'Download and install' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('does not match the release checksum');
    expect(screen.getByRole('button', { name: 'Try again' })).toBeEnabled();
  });

  it('remembers "Not now" for that version', () => {
    const onDismiss = vi.fn();
    render(<UpdateNotification updateInfo={base} onDismiss={onDismiss} />);
    fireEvent.click(screen.getByRole('button', { name: 'Not now' }));
    expect(onDismiss).toHaveBeenCalled();
    expect(localStorage.getItem('openlargeprint_dismissed_update_version')).toBe('0.7.0');
  });
});

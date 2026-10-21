/**
 * Looking for and installing new versions (SEC-009).
 *
 * The desktop app does the network work itself (src-tauri/src/updater.rs): it
 * asks GitHub for the latest release, picks the file for this computer and
 * checks its SHA-256 before installing. The web view only asks and shows the
 * answer, so it never needs network access of its own. Converting documents
 * never touches the network.
 */

export type InstallKind = 'installer' | 'app_image' | 'manual';

export interface UpdateInfo {
  available: boolean;
  currentVersion: string;
  latestVersion?: string;
  releaseNotes?: string;
  publishedAt?: string;
  installKind: InstallKind;
  /** True when the app can download, verify and install the update itself. */
  canInstall: boolean;
  downloadSize?: number;
}

export const CURRENT_VERSION = '0.6.0';

const AUTO_UPDATE_KEY = 'openlargeprint_auto_update';
const LAST_CHECK_KEY = 'openlargeprint_last_update_check';
const DISMISSED_VERSION_KEY = 'openlargeprint_dismissed_update_version';
const DAY_MS = 24 * 60 * 60 * 1000;

type Invoke = (cmd: string, args?: Record<string, unknown>) => Promise<any>;
type Listen = (event: string, handler: (event: { payload: any }) => void) => Promise<() => void>;

function desktop(): { invoke: Invoke; listen?: Listen } | null {
  const tauri = (window as any)?.__TAURI__;
  const invoke: Invoke | undefined = tauri?.core?.invoke || tauri?.invoke;
  return invoke ? { invoke, listen: tauri?.event?.listen } : null;
}

/** Automatic checks are on unless the reader turned them off. */
export function isAutoUpdateEnabled(): boolean {
  try {
    return localStorage.getItem(AUTO_UPDATE_KEY) !== 'false';
  } catch {
    return true;
  }
}

export function setAutoUpdateEnabled(enabled: boolean): void {
  try {
    localStorage.setItem(AUTO_UPDATE_KEY, enabled ? 'true' : 'false');
  } catch {
    // Storage can be disabled; the choice then lasts for this session only.
  }
}

/** An update the reader dismissed is not offered again until a newer one appears. */
export function isUpdateDismissed(version: string): boolean {
  try {
    return localStorage.getItem(DISMISSED_VERSION_KEY) === version;
  } catch {
    return false;
  }
}

export function dismissUpdate(version: string): void {
  try {
    localStorage.setItem(DISMISSED_VERSION_KEY, version);
  } catch {
    // ignore storage errors
  }
}

/** True when `remote` ("v0.7.0") is a later version than `current`. */
export function isNewerVersion(current: string, remote: string): boolean {
  const parse = (v: string) => {
    const [core, pre] = v.replace(/^v/i, '').trim().split('-', 2);
    const parts = core.split('.').map((p) => parseInt(p, 10));
    if (!core || parts.some((n) => Number.isNaN(n))) return null;
    while (parts.length < 3) parts.push(0);
    return { parts, pre: pre ?? null };
  };
  const a = parse(current);
  const b = parse(remote);
  if (!a || !b) return false;
  for (let i = 0; i < Math.max(a.parts.length, b.parts.length); i++) {
    const x = a.parts[i] ?? 0;
    const y = b.parts[i] ?? 0;
    if (y !== x) return y > x;
  }
  if (a.pre && !b.pre) return true;
  if (a.pre && b.pre) return b.pre > a.pre;
  return false;
}

function fromDesktop(raw: any): UpdateInfo {
  return {
    available: Boolean(raw?.available),
    currentVersion: String(raw?.current_version || CURRENT_VERSION),
    latestVersion: raw?.latest_version || undefined,
    releaseNotes: raw?.release_notes || undefined,
    publishedAt: raw?.published_at || undefined,
    installKind: raw?.install_kind === 'installer' || raw?.install_kind === 'app_image' ? raw.install_kind : 'manual',
    canInstall: Boolean(raw?.can_install),
    downloadSize: typeof raw?.download_size === 'number' ? raw.download_size : undefined,
  };
}

/**
 * Ask whether a newer version exists. The automatic check at start-up runs at
 * most once a day and not at all when turned off; `force` is the "Look now"
 * button. Returns null when no check was made. Throws with a readable message
 * when the check fails, so the reader is never told "up to date" by mistake.
 */
export async function checkForUpdates(force = false): Promise<UpdateInfo | null> {
  const app = desktop();
  if (!app) return null;
  if (!force) {
    if (!isAutoUpdateEnabled()) return null;
    try {
      const last = Number(localStorage.getItem(LAST_CHECK_KEY));
      if (Number.isFinite(last) && Date.now() - last < DAY_MS) return null;
    } catch {
      // no memory of the last check: check now
    }
  }
  const info = fromDesktop(await app.invoke('check_for_update'));
  try {
    localStorage.setItem(LAST_CHECK_KEY, String(Date.now()));
  } catch {
    // ignore storage errors
  }
  return info;
}

/**
 * Download, verify and start the update found by the last check; for a portable
 * copy or a Linux package this opens the release page instead. Progress arrives
 * as (downloaded, total) bytes.
 */
export async function installUpdate(onProgress?: (downloaded: number, total: number) => void): Promise<void> {
  const app = desktop();
  if (!app) throw new Error('Updates are installed from the desktop app.');
  let stop: (() => void) | undefined;
  if (onProgress && app.listen) {
    stop = await app.listen('update-progress', (event) => {
      onProgress(Number(event.payload?.downloaded) || 0, Number(event.payload?.total) || 0);
    });
  }
  try {
    await app.invoke('install_update');
  } finally {
    stop?.();
  }
}

export async function openReleasePage(): Promise<void> {
  const app = desktop();
  if (app) await app.invoke('open_release_page');
}

/**
 * OpenLargePrint In-App Update Checker
 *
 * SEC-009 compliant: This checker operates completely independently of the
 * document conversion pipeline. Zero network traffic is emitted during document
 * processing or conversion runs.
 */

export interface UpdateInfo {
  available: boolean;
  currentVersion: string;
  latestVersion?: string;
  releaseUrl?: string;
  downloadUrl?: string;
  releaseNotes?: string;
  publishedAt?: string;
  assetName?: string;
  expectedSha256?: string;
}

export const CURRENT_VERSION = '0.3.0';
const REPO_OWNER = 'ahmeddwalid';
const REPO_NAME = 'OpenLargePrint';
const RELEASES_API = `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest`;

const AUTO_UPDATE_KEY = 'openlargeprint_auto_update';
const DISMISSED_VERSION_KEY = 'openlargeprint_dismissed_update_version';

export function isAutoUpdateEnabled(): boolean {
  try {
    const val = localStorage.getItem(AUTO_UPDATE_KEY);
    return val === 'true';
  } catch {
    return false;
  }
}

export function setAutoUpdateEnabled(enabled: boolean): void {
  try {
    localStorage.setItem(AUTO_UPDATE_KEY, enabled ? 'true' : 'false');
  } catch {
    // ignore storage errors
  }
}

export function isUpdateDismissed(version: string): boolean {
  try {
    return sessionStorage.getItem(DISMISSED_VERSION_KEY) === version;
  } catch {
    return false;
  }
}

export function dismissUpdate(version: string): void {
  try {
    sessionStorage.setItem(DISMISSED_VERSION_KEY, version);
  } catch {
    // ignore storage errors
  }
}

/**
 * Compares two semantic version strings (e.g. "0.1.0" and "v0.2.0").
 * Returns true if remote is strictly newer than current.
 */
export function isNewerVersion(current: string, remote: string): boolean {
  const cleanCurrent = current.replace(/^v/i, '').trim();
  const cleanRemote = remote.replace(/^v/i, '').trim();

  const parseParts = (v: string) =>
    v.split('.').map((p) => {
      const num = parseInt(p, 10);
      return isNaN(num) ? 0 : num;
    });

  const curParts = parseParts(cleanCurrent);
  const remParts = parseParts(cleanRemote);

  const maxLen = Math.max(curParts.length, remParts.length, 3);
  while (curParts.length < maxLen) curParts.push(0);
  while (remParts.length < maxLen) remParts.push(0);

  for (let i = 0; i < maxLen; i++) {
    if (remParts[i] > curParts[i]) return true;
    if (remParts[i] < curParts[i]) return false;
  }

  return false;
}

/**
 * Checks GitHub Releases API for a newer version of OpenLargePrint.
 */
export async function checkForUpdates(forceCheck: boolean = false): Promise<UpdateInfo> {
  if (!forceCheck && !isAutoUpdateEnabled()) {
    return { available: false, currentVersion: CURRENT_VERSION };
  }

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 6000);

    const res = await fetch(RELEASES_API, {
      method: 'GET',
      headers: {
        Accept: 'application/vnd.github.v3+json',
      },
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!res.ok) {
      return { available: false, currentVersion: CURRENT_VERSION };
    }

    const data = await res.json();
    const tagName = typeof data?.tag_name === 'string' ? data.tag_name : '';
    const releaseUrl = typeof data?.html_url === 'string' ? data.html_url : '';
    const releaseNotes = typeof data?.body === 'string' ? data.body : '';
    const publishedAt = typeof data?.published_at === 'string' ? data.published_at : '';

    if (!tagName) {
      return { available: false, currentVersion: CURRENT_VERSION };
    }

    const hasNewer = isNewerVersion(CURRENT_VERSION, tagName);
    if (!hasNewer) {
      return {
        available: false,
        currentVersion: CURRENT_VERSION,
        latestVersion: tagName,
      };
    }

    // Locate the Windows installer asset (.exe)
    let downloadUrl: string | undefined;
    let assetName: string | undefined;
    let expectedSha256: string | undefined;

    if (/Win/i.test(navigator.platform) && Array.isArray(data.assets)) {
      const exeAsset = data.assets.find(
        (a: { name?: string; browser_download_url?: string }) =>
          typeof a.name === 'string' && a.name.toLowerCase().endsWith('.exe')
      );
      if (exeAsset) {
        downloadUrl = exeAsset.browser_download_url;
        assetName = exeAsset.name;
        if (typeof exeAsset.digest === 'string' && /^sha256:[a-f0-9]{64}$/i.test(exeAsset.digest)) {
          expectedSha256 = exeAsset.digest.slice(7);
        }
      }
    }

    return {
      available: true,
      currentVersion: CURRENT_VERSION,
      latestVersion: tagName,
      releaseUrl: releaseUrl || undefined,
      downloadUrl: downloadUrl || releaseUrl || undefined,
      releaseNotes: releaseNotes || undefined,
      publishedAt: publishedAt || undefined,
      assetName: assetName || undefined,
      expectedSha256,
    };
  } catch {
    return { available: false, currentVersion: CURRENT_VERSION };
  }
}

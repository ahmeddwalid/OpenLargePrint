//! Checking for, downloading and installing new releases.
//!
//! Everything that touches the network lives here, apart from document
//! conversion (which never does). The interface only asks "is there an
//! update?" and "install it": the release, the file to download and its
//! checksum are chosen here from GitHub's answer, so nothing the web view sends
//! can point the download somewhere else.
//!
//! * Windows (installed): the NSIS installer is downloaded, verified and run.
//! * Linux AppImage: the new AppImage is downloaded next to the running one,
//!   verified, swapped in and started.
//! * Portable zip, .deb and .rpm: the release page is opened, because those are
//!   updated by unpacking or by the system package manager.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::Duration;
use tauri::{AppHandle, Emitter, State};

const REPO: &str = "ahmeddwalid/OpenLargePrint";
const WINDOWS_INSTALLER: &str = "OpenLargePrint-Setup-x64.exe";
const MAX_DOWNLOAD: u64 = 2 * 1024 * 1024 * 1024;

pub fn current_version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

fn releases_page() -> String {
    format!("https://github.com/{REPO}/releases")
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum InstallKind {
    /// Windows, installed with the setup program.
    Installer,
    /// Linux, running from an AppImage.
    AppImage,
    /// Portable zip, .deb or .rpm: the reader downloads the new version.
    Manual,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Asset {
    pub name: String,
    pub browser_download_url: String,
    #[serde(default)]
    pub size: u64,
    #[serde(default)]
    pub digest: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Release {
    pub tag_name: String,
    #[serde(default)]
    pub html_url: String,
    #[serde(default)]
    pub body: Option<String>,
    #[serde(default)]
    pub published_at: Option<String>,
    #[serde(default)]
    pub draft: bool,
    #[serde(default)]
    pub prerelease: bool,
    #[serde(default)]
    pub assets: Vec<Asset>,
}

/// What the interface is told about an update.
#[derive(Debug, Clone, Serialize)]
pub struct UpdateInfo {
    pub available: bool,
    pub current_version: String,
    pub latest_version: Option<String>,
    pub release_notes: Option<String>,
    pub published_at: Option<String>,
    pub install_kind: InstallKind,
    /// True when the update can be installed from inside the app.
    pub can_install: bool,
    pub download_size: Option<u64>,
}

#[derive(Debug, Clone)]
struct PendingUpdate {
    version: String,
    release_url: String,
    asset: Option<(Asset, String)>, // the file and its SHA-256
}

#[derive(Default)]
pub struct UpdateState {
    pending: Mutex<Option<PendingUpdate>>,
}

// -- versions -------------------------------------------------------------------

/// "v1.2.3" or "1.2.3-rc.1" as numbers plus an optional pre-release tag.
pub fn parse_version(text: &str) -> Option<(Vec<u64>, Option<String>)> {
    let text = text.trim().trim_start_matches(['v', 'V']);
    let (core, pre) = match text.split_once('-') {
        Some((core, pre)) => (core, Some(pre.to_string())),
        None => (text, None),
    };
    let core = core.split('+').next()?;
    let numbers: Option<Vec<u64>> = core.split('.').map(|part| part.parse().ok()).collect();
    let mut numbers = numbers.filter(|n| !n.is_empty() && n.len() <= 4)?;
    numbers.resize(3.max(numbers.len()), 0);
    Some((numbers, pre))
}

/// True when `remote` is a later release than `current`.
pub fn is_newer(current: &str, remote: &str) -> bool {
    let (Some((cur, cur_pre)), Some((rem, rem_pre))) =
        (parse_version(current), parse_version(remote))
    else {
        return false;
    };
    match rem.cmp(&cur) {
        std::cmp::Ordering::Greater => true,
        std::cmp::Ordering::Less => false,
        // 1.0.0 is newer than 1.0.0-rc.1; two pre-releases compare as text.
        std::cmp::Ordering::Equal => match (cur_pre, rem_pre) {
            (Some(_), None) => true,
            (Some(a), Some(b)) => b > a,
            _ => false,
        },
    }
}

// -- which file -------------------------------------------------------------------

pub fn install_kind() -> InstallKind {
    let exe = std::env::current_exe().ok();
    install_kind_for(
        exe.as_deref(),
        std::env::var_os("APPIMAGE").map(PathBuf::from).as_deref(),
    )
}

fn install_kind_for(exe: Option<&Path>, appimage: Option<&Path>) -> InstallKind {
    if cfg!(target_os = "windows") {
        // The setup program leaves its uninstaller next to the app; the zip does not.
        let installed = exe
            .and_then(|e| e.parent())
            .map(|dir| dir.join("uninstall.exe").is_file())
            .unwrap_or(false);
        return if installed {
            InstallKind::Installer
        } else {
            InstallKind::Manual
        };
    }
    if cfg!(target_os = "linux") {
        if let Some(path) = appimage {
            if path.is_file() {
                return InstallKind::AppImage;
            }
        }
    }
    InstallKind::Manual
}

pub fn choose_asset(kind: InstallKind, assets: &[Asset]) -> Option<&Asset> {
    match kind {
        InstallKind::Installer => assets.iter().find(|a| a.name == WINDOWS_INSTALLER),
        InstallKind::AppImage => assets.iter().find(|a| {
            a.name.starts_with("OpenLargePrint_") && a.name.ends_with("_linux_x86_64.AppImage")
        }),
        InstallKind::Manual => None,
    }
}

fn is_sha256(value: &str) -> bool {
    value.len() == 64 && value.bytes().all(|b| b.is_ascii_hexdigit())
}

/// The asset's checksum from GitHub's digest, else from the release's SHA256SUMS.txt.
pub fn expected_sha256(asset: &Asset, sums: Option<&str>) -> Option<String> {
    if let Some(digest) = asset
        .digest
        .as_deref()
        .and_then(|d| d.strip_prefix("sha256:"))
    {
        if is_sha256(digest) {
            return Some(digest.to_ascii_lowercase());
        }
    }
    sums?.lines().find_map(|line| {
        let mut parts = line.split_whitespace();
        let (hash, name) = (parts.next()?, parts.next()?);
        (name.trim_start_matches('*') == asset.name && is_sha256(hash))
            .then(|| hash.to_ascii_lowercase())
    })
}

/// Downloads may only come from this project's own release files on GitHub.
pub fn is_release_download(url: &str, asset_name: &str) -> bool {
    let Ok(url) = tauri::Url::parse(url) else {
        return false;
    };
    url.scheme() == "https"
        && url.host_str() == Some("github.com")
        && url.port().is_none()
        && url.username().is_empty()
        && url.password().is_none()
        && url.query().is_none()
        && url.fragment().is_none()
        && url
            .path()
            .starts_with(&format!("/{REPO}/releases/download/"))
        && url.path().ends_with(&format!("/{asset_name}"))
}

// -- network --------------------------------------------------------------------

fn agent() -> ureq::Agent {
    ureq::AgentBuilder::new()
        .timeout_connect(Duration::from_secs(15))
        .timeout_read(Duration::from_secs(60))
        .user_agent(&format!("OpenLargePrint/{}", current_version()))
        .try_proxy_from_env(true)
        .build()
}

fn describe(error: ureq::Error) -> String {
    match error {
        ureq::Error::Status(403, _) | ureq::Error::Status(429, _) => {
            "GitHub is limiting requests right now. Please try again in an hour.".into()
        }
        ureq::Error::Status(404, _) => "No published release was found.".into(),
        ureq::Error::Status(code, _) => format!("GitHub answered with an error ({code})."),
        ureq::Error::Transport(_) => {
            "Could not reach GitHub. Check the internet connection and try again.".into()
        }
    }
}

fn fetch_latest() -> Result<(Release, Option<String>), String> {
    let agent = agent();
    let url = format!("https://api.github.com/repos/{REPO}/releases/latest");
    let body = agent
        .get(&url)
        .set("Accept", "application/vnd.github+json")
        .set("X-GitHub-Api-Version", "2022-11-28")
        .call()
        .map_err(describe)?
        .into_string()
        .map_err(|_| "The release information could not be read.".to_string())?;
    let release: Release = serde_json::from_str(&body)
        .map_err(|_| "The release information could not be read.".to_string())?;
    // Only needed when an asset carries no digest.
    let sums = release
        .assets
        .iter()
        .find(|a| a.name == "SHA256SUMS.txt" && a.digest.is_none())
        .and_then(|a| agent.get(&a.browser_download_url).call().ok())
        .and_then(|r| r.into_string().ok());
    Ok((release, sums))
}

fn evaluate(
    release: &Release,
    sums: Option<&str>,
    kind: InstallKind,
) -> (UpdateInfo, Option<PendingUpdate>) {
    let current = current_version();
    let newer = !release.draft && !release.prerelease && is_newer(current, &release.tag_name);
    let latest = release.tag_name.trim_start_matches(['v', 'V']).to_string();
    let asset = if newer {
        choose_asset(kind, &release.assets)
            .filter(|a| {
                is_release_download(&a.browser_download_url, &a.name) && a.size <= MAX_DOWNLOAD
            })
            .and_then(|a| expected_sha256(a, sums).map(|hash| (a.clone(), hash)))
    } else {
        None
    };
    let info = UpdateInfo {
        available: newer,
        current_version: current.to_string(),
        latest_version: Some(latest.clone()),
        release_notes: release.body.clone().filter(|b| !b.trim().is_empty()),
        published_at: release.published_at.clone(),
        install_kind: kind,
        can_install: asset.is_some(),
        download_size: asset.as_ref().map(|(a, _)| a.size),
    };
    let release_url = if release
        .html_url
        .starts_with(&format!("https://github.com/{REPO}/releases/"))
    {
        release.html_url.clone()
    } else {
        releases_page()
    };
    let pending = newer.then_some(PendingUpdate {
        version: latest,
        release_url,
        asset,
    });
    (info, pending)
}

// -- commands ---------------------------------------------------------------------

#[tauri::command]
pub async fn check_for_update(state: State<'_, UpdateState>) -> Result<UpdateInfo, String> {
    let kind = install_kind();
    let (release, sums) = tokio::task::spawn_blocking(fetch_latest)
        .await
        .map_err(|_| "The update check stopped unexpectedly.".to_string())??;
    let (info, pending) = evaluate(&release, sums.as_deref(), kind);
    *state.pending.lock().unwrap() = pending;
    Ok(info)
}

/// Open the release page of the update that was found (or the releases list).
#[tauri::command]
pub async fn open_release_page(state: State<'_, UpdateState>) -> Result<(), String> {
    let url = state
        .pending
        .lock()
        .unwrap()
        .as_ref()
        .map(|p| p.release_url.clone())
        .unwrap_or_else(releases_page);
    open_url(&url)
}

fn open_url(url: &str) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    let result = {
        use std::os::windows::process::CommandExt;
        std::process::Command::new("rundll32")
            .args(["url.dll,FileProtocolHandler", url])
            .creation_flags(0x08000000)
            .spawn()
    };
    #[cfg(not(target_os = "windows"))]
    let result = std::process::Command::new("xdg-open").arg(url).spawn();
    result
        .map(|_| ())
        .map_err(|_| "Could not open the web browser.".to_string())
}

#[derive(Clone, Serialize)]
struct Progress {
    downloaded: u64,
    total: u64,
}

/// Download `url` to `target` while hashing it; the file is removed if anything fails.
fn download(
    url: &str,
    expected: &str,
    size: u64,
    target: &Path,
    progress: impl Fn(u64, u64),
) -> Result<(), String> {
    let result = (|| {
        let response = agent().get(url).call().map_err(describe)?;
        let total = response
            .header("Content-Length")
            .and_then(|v| v.parse().ok())
            .unwrap_or(size);
        if total > MAX_DOWNLOAD {
            return Err("The update file is unexpectedly large.".to_string());
        }
        let mut reader = response.into_reader().take(MAX_DOWNLOAD + 1);
        let mut file = std::fs::File::create(target)
            .map_err(|_| "Could not save the update. Is there enough free space?".to_string())?;
        let mut hash = Sha256::new();
        let mut buffer = vec![0_u8; 256 * 1024];
        let (mut downloaded, mut reported) = (0_u64, 0_u64);
        loop {
            let count = reader
                .read(&mut buffer)
                .map_err(|_| "The download was interrupted. Please try again.".to_string())?;
            if count == 0 {
                break;
            }
            hash.update(&buffer[..count]);
            file.write_all(&buffer[..count]).map_err(|_| {
                "Could not save the update. Is there enough free space?".to_string()
            })?;
            downloaded += count as u64;
            if downloaded - reported >= 1024 * 1024 || downloaded == total {
                reported = downloaded;
                progress(downloaded, total);
            }
        }
        file.sync_all().ok();
        if format!("{:x}", hash.finalize()) != expected {
            return Err(
                "The downloaded file does not match the release checksum, so it was not installed."
                    .into(),
            );
        }
        Ok(())
    })();
    if result.is_err() {
        let _ = std::fs::remove_file(target);
    }
    result
}

#[tauri::command]
pub async fn install_update(app: AppHandle, state: State<'_, UpdateState>) -> Result<(), String> {
    let pending = state
        .pending
        .lock()
        .unwrap()
        .clone()
        .ok_or_else(|| "Check for updates first.".to_string())?;
    let Some((asset, sha)) = pending.asset.clone() else {
        return open_url(&pending.release_url);
    };
    match install_kind() {
        InstallKind::Installer => {
            let dir =
                std::env::temp_dir().join(format!("OpenLargePrint-update-{}", pending.version));
            std::fs::create_dir_all(&dir)
                .map_err(|_| "Could not prepare the update.".to_string())?;
            let installer = dir.join(WINDOWS_INSTALLER);
            let handle = app.clone();
            let target = installer.clone();
            tokio::task::spawn_blocking(move || {
                download(
                    &asset.browser_download_url,
                    &sha,
                    asset.size,
                    &target,
                    |downloaded, total| {
                        let _ = handle.emit("update-progress", Progress { downloaded, total });
                    },
                )
            })
            .await
            .map_err(|_| "The download stopped unexpectedly.".to_string())??;
            std::process::Command::new(&installer)
                .spawn()
                .map_err(|_| "The installer could not be started.".to_string())?;
            // The installer replaces files in use, so the app makes way for it.
            tokio::time::sleep(Duration::from_millis(800)).await;
            app.exit(0);
            Ok(())
        }
        InstallKind::AppImage => {
            let current = std::env::var_os("APPIMAGE")
                .map(PathBuf::from)
                .filter(|p| p.is_file())
                .ok_or_else(|| "The running AppImage could not be found.".to_string())?;
            let dir = current
                .parent()
                .ok_or_else(|| "The running AppImage could not be found.".to_string())?
                .to_path_buf();
            let partial = dir.join(format!(".{}.download", asset.name));
            let handle = app.clone();
            let target = partial.clone();
            tokio::task::spawn_blocking(move || {
                download(
                    &asset.browser_download_url,
                    &sha,
                    asset.size,
                    &target,
                    |downloaded, total| {
                        let _ = handle.emit("update-progress", Progress { downloaded, total });
                    },
                )
            })
            .await
            .map_err(|_| "The download stopped unexpectedly.".to_string())?
            .map_err(|e| {
                if e.starts_with("Could not save") {
                    format!(
                        "{e} The folder {} must be writable to update in place.",
                        dir.display()
                    )
                } else {
                    e
                }
            })?;
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                std::fs::set_permissions(&partial, std::fs::Permissions::from_mode(0o755))
                    .map_err(|_| "Could not make the new version runnable.".to_string())?;
            }
            // Same folder, so the swap is a single rename; the old version keeps
            // running from its open file until it exits.
            std::fs::rename(&partial, &current).map_err(|_| {
                let _ = std::fs::remove_file(&partial);
                "Could not replace the AppImage. Is its folder writable?".to_string()
            })?;
            std::process::Command::new(&current).spawn().map_err(|_| {
                "The new version is installed. Please start OpenLargePrint again.".to_string()
            })?;
            app.exit(0);
            Ok(())
        }
        InstallKind::Manual => open_url(&pending.release_url),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn asset(name: &str, digest: Option<&str>) -> Asset {
        Asset {
            name: name.into(),
            browser_download_url: format!(
                "https://github.com/{REPO}/releases/download/v9.0.0/{name}"
            ),
            size: 1000,
            digest: digest.map(String::from),
        }
    }

    fn release(tag: &str, assets: Vec<Asset>) -> Release {
        Release {
            tag_name: tag.into(),
            html_url: format!("https://github.com/{REPO}/releases/tag/{tag}"),
            body: Some("Notes".into()),
            published_at: None,
            draft: false,
            prerelease: false,
            assets,
        }
    }

    #[test]
    fn compares_versions() {
        assert!(is_newer("0.6.0", "v0.7.0"));
        assert!(is_newer("0.6.0", "0.6.1"));
        assert!(is_newer("0.9.9", "1.0"));
        assert!(is_newer("1.0.0-rc.1", "1.0.0"));
        assert!(!is_newer("0.7.0", "v0.7.0"));
        assert!(!is_newer("0.7.0", "0.6.9"));
        assert!(!is_newer("1.0.0", "1.0.0-rc.2"));
        assert!(!is_newer("0.7.0", "latest"));
        assert!(!is_newer("0.7.0", ""));
    }

    #[test]
    fn picks_the_file_for_this_kind_of_install() {
        let assets = vec![
            asset("OpenLargePrint_9.0.0_windows_x64_portable.zip", None),
            asset(WINDOWS_INSTALLER, None),
            asset("OpenLargePrint_9.0.0_linux_x86_64.AppImage", None),
            asset("OpenLargePrint_9.0.0_linux_amd64.deb", None),
        ];
        assert_eq!(
            choose_asset(InstallKind::Installer, &assets).unwrap().name,
            WINDOWS_INSTALLER
        );
        assert_eq!(
            choose_asset(InstallKind::AppImage, &assets).unwrap().name,
            "OpenLargePrint_9.0.0_linux_x86_64.AppImage"
        );
        assert!(choose_asset(InstallKind::Manual, &assets).is_none());
    }

    #[test]
    fn checksum_comes_from_the_digest_or_the_sums_file() {
        let hash = "ab".repeat(32);
        let with_digest = asset(
            WINDOWS_INSTALLER,
            Some(&format!("sha256:{}", hash.to_uppercase())),
        );
        assert_eq!(expected_sha256(&with_digest, None), Some(hash.clone()));
        let without = asset(WINDOWS_INSTALLER, None);
        let sums = format!(
            "{}  other.zip\n{}  {}\n",
            "cd".repeat(32),
            hash,
            WINDOWS_INSTALLER
        );
        assert_eq!(expected_sha256(&without, Some(&sums)), Some(hash));
        assert_eq!(expected_sha256(&without, None), None);
        assert_eq!(
            expected_sha256(&asset(WINDOWS_INSTALLER, Some("sha256:xyz")), None),
            None
        );
    }

    #[test]
    fn downloads_only_from_this_projects_releases() {
        let ok = format!("https://github.com/{REPO}/releases/download/v1/{WINDOWS_INSTALLER}");
        assert!(is_release_download(&ok, WINDOWS_INSTALLER));
        for bad in [
            format!("http://github.com/{REPO}/releases/download/v1/{WINDOWS_INSTALLER}"),
            format!("https://example.com/{REPO}/releases/download/v1/{WINDOWS_INSTALLER}"),
            format!("https://github.com/other/project/releases/download/v1/{WINDOWS_INSTALLER}"),
            format!("https://github.com/{REPO}/releases/download/v1/evil.exe"),
            format!("https://github.com:444/{REPO}/releases/download/v1/{WINDOWS_INSTALLER}"),
            format!("{ok}?x=1"),
        ] {
            assert!(!is_release_download(&bad, WINDOWS_INSTALLER), "{bad}");
        }
    }

    #[test]
    fn an_update_without_a_checksum_is_offered_as_a_download_page_only() {
        let rel = release("v99.0.0", vec![asset(WINDOWS_INSTALLER, None)]);
        let (info, pending) = evaluate(&rel, None, InstallKind::Installer);
        assert!(info.available);
        assert!(!info.can_install);
        assert!(pending.unwrap().asset.is_none());

        let digest = format!("sha256:{}", "ef".repeat(32));
        let rel = release("v99.0.0", vec![asset(WINDOWS_INSTALLER, Some(&digest))]);
        let (info, pending) = evaluate(&rel, None, InstallKind::Installer);
        assert!(info.can_install);
        assert_eq!(info.latest_version.as_deref(), Some("99.0.0"));
        assert_eq!(pending.unwrap().asset.unwrap().1, "ef".repeat(32));
    }

    #[test]
    fn same_older_draft_and_prerelease_versions_are_not_offered() {
        let digest = format!("sha256:{}", "ef".repeat(32));
        for (tag, draft, pre) in [
            (current_version(), false, false),
            ("v0.0.1", false, false),
            ("v99.0.0", true, false),
            ("v99.0.0", false, true),
        ] {
            let mut rel = release(tag, vec![asset(WINDOWS_INSTALLER, Some(&digest))]);
            rel.draft = draft;
            rel.prerelease = pre;
            let (info, pending) = evaluate(&rel, None, InstallKind::Installer);
            assert!(!info.available && pending.is_none(), "{tag}");
        }
    }

    #[test]
    fn portable_and_package_installs_go_to_the_release_page() {
        let digest = format!("sha256:{}", "ef".repeat(32));
        let rel = release("v99.0.0", vec![asset(WINDOWS_INSTALLER, Some(&digest))]);
        let (info, pending) = evaluate(&rel, None, InstallKind::Manual);
        assert!(info.available && !info.can_install);
        assert!(pending
            .unwrap()
            .release_url
            .ends_with("/releases/tag/v99.0.0"));
    }

    #[test]
    fn a_missing_appimage_is_not_treated_as_one() {
        let kind = install_kind_for(
            None,
            Some(Path::new("/nonexistent/OpenLargePrint.AppImage")),
        );
        assert_eq!(kind, InstallKind::Manual);
    }
}

#[cfg(test)]
mod live {
    /// Asks GitHub for the real latest release: `cargo test -- --ignored live`.
    #[test]
    #[ignore]
    fn live_release_lookup() {
        let (release, _) = super::fetch_latest().expect("release lookup");
        let (info, _) = super::evaluate(&release, None, super::InstallKind::Installer);
        println!("{info:?}");
        assert!(info.latest_version.is_some());
    }

    /// Downloads the release's small SHA256SUMS.txt through the update path.
    #[test]
    #[ignore]
    fn live_download_is_verified() {
        let (release, _) = super::fetch_latest().expect("release lookup");
        let sums = release
            .assets
            .iter()
            .find(|a| a.name == "SHA256SUMS.txt")
            .expect("sums asset");
        let good = super::expected_sha256(sums, None).expect("digest");
        let dir = std::env::temp_dir().join("olp-update-test");
        std::fs::create_dir_all(&dir).unwrap();
        let target = dir.join("sums.txt");
        super::download(
            &sums.browser_download_url,
            &good,
            sums.size,
            &target,
            |_, _| {},
        )
        .expect("download");
        assert!(target.is_file());
        let bad = "0".repeat(64);
        let err = super::download(
            &sums.browser_download_url,
            &bad,
            sums.size,
            &target,
            |_, _| {},
        )
        .unwrap_err();
        assert!(err.contains("checksum"), "{err}");
        assert!(!target.exists(), "a file that fails the check is removed");
    }
}

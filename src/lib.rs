use sha2::{Digest, Sha256};
use std::{fs, path::Path};
use zed_extension_api::{self as zed, settings::LspSettings, LanguageServerId, Result};

const REPOSITORY: &str = "MattiaPersico/zed-eel2";
const VERSION: &str = env!("CARGO_PKG_VERSION");
const SERVER_SHA256: &str = include_str!("../server.sha256");
const PYTHON_HELP: &str =
    "EEL2 requires Python 3.9+. Install Python or set lsp.eel2-lsp.binary.path in Zed.";

fn supported_python(version: &str) -> bool {
    let mut parts = version.trim().split('.');
    match (
        parts.next().and_then(|v| v.parse::<u32>().ok()),
        parts.next().and_then(|v| v.parse::<u32>().ok()),
    ) {
        (Some(major), Some(minor)) => (major, minor) >= (3, 9),
        _ => false,
    }
}

fn matches_checksum(bytes: &[u8], expected: &str) -> bool {
    format!("{:x}", Sha256::digest(bytes)) == expected.trim()
}

fn valid_server(path: &Path) -> bool {
    // The archive is small; bound reads even when a cache file is damaged.
    fs::metadata(path).is_ok_and(|m| m.is_file() && m.len() <= 4 * 1024 * 1024)
        && fs::read(path).is_ok_and(|bytes| matches_checksum(&bytes, SERVER_SHA256))
}

fn check_python(command: &str, env: &[(String, String)]) -> Result<()> {
    let output = zed::process::Command::new(command)
        .args(["-c", "import sys; print('%s.%s' % sys.version_info[:2])"])
        .envs(env.iter().cloned())
        .output()
        .map_err(|error| format!("Cannot start {command}: {error}. {PYTHON_HELP}"))?;
    let version = String::from_utf8_lossy(&output.stdout);
    if output.status != Some(0) || !supported_python(&version) {
        return Err(format!(
            "{command} is not a working Python 3.9+ interpreter. {PYTHON_HELP}"
        ));
    }
    Ok(())
}

struct Eel2Extension;

impl Eel2Extension {
    fn download_server(&self, server_id: &LanguageServerId) -> Result<String> {
        let filename = format!("eel2-lsp-v{VERSION}.pyz");
        let path = std::env::current_dir()
            .map_err(|error| error.to_string())?
            .join(&filename);
        if !valid_server(&path) {
            zed::set_language_server_installation_status(
                server_id,
                &zed::LanguageServerInstallationStatus::Downloading,
            );
            if let Err(error) = self.fetch_server(&filename, &path) {
                zed::set_language_server_installation_status(
                    server_id,
                    &zed::LanguageServerInstallationStatus::Failed(error.clone()),
                );
                return Err(error);
            }
        }
        zed::set_language_server_installation_status(
            server_id,
            &zed::LanguageServerInstallationStatus::None,
        );
        Ok(path.to_string_lossy().into_owned())
    }

    fn fetch_server(&self, filename: &str, destination: &Path) -> Result<()> {
        let release = zed::github_release_by_tag_name(REPOSITORY, &format!("v{VERSION}"))
            .map_err(|error| format!("Cannot find EEL2 v{VERSION} on GitHub: {error}. Check your connection and restart the language server."))?;
        let asset = release
            .assets
            .iter()
            .find(|asset| asset.name == filename)
            .ok_or_else(|| format!("Release v{VERSION} does not contain {filename}."))?;
        let temporary = format!("{filename}.download");
        let _ = fs::remove_file(&temporary);
        zed::download_file(&asset.download_url, &temporary, zed::DownloadedFileType::Uncompressed)
            .map_err(|error| format!("EEL2 server download failed: {error}. Check your connection and restart the language server."))?;
        if !valid_server(Path::new(&temporary)) {
            let _ = fs::remove_file(&temporary);
            return Err(
                "EEL2 server checksum mismatch. Restart the language server to retry the download."
                    .into(),
            );
        }
        // Windows cannot rename onto an existing file. Only replace a bad cache
        // after its replacement has been completely downloaded and verified.
        if destination.exists() {
            fs::remove_file(destination)
                .map_err(|error| format!("Cannot replace damaged EEL2 cache: {error}"))?;
        }
        fs::rename(&temporary, destination)
            .map_err(|error| format!("Cannot save EEL2 server: {error}"))
    }
}

impl zed::Extension for Eel2Extension {
    fn new() -> Self {
        Self
    }

    fn language_server_command(
        &mut self,
        server_id: &LanguageServerId,
        worktree: &zed::Worktree,
    ) -> Result<zed::Command> {
        let binary = LspSettings::for_worktree(server_id.as_ref(), worktree)?.binary;
        let mut env = vec![("PYTHONDONTWRITEBYTECODE".into(), "1".into())];
        if let Some(extra) = binary.as_ref().and_then(|b| b.env.clone()) {
            env.extend(extra);
        }
        let command = if let Some(path) = binary.as_ref().and_then(|b| b.path.clone()) {
            check_python(&path, &env)?;
            path
        } else {
            let mut selected = None;
            let mut errors = Vec::new();
            for name in ["python3", "python"] {
                if let Some(path) = worktree.which(name) {
                    match check_python(&path, &env) {
                        Ok(()) => {
                            selected = Some(path);
                            break;
                        }
                        Err(error) => errors.push(error),
                    }
                }
            }
            selected.ok_or_else(|| {
                if errors.is_empty() {
                    PYTHON_HELP.into()
                } else {
                    errors.join("\n")
                }
            })?
        };
        let args = match binary.and_then(|b| b.arguments) {
            Some(args) => args,
            None => vec![self.download_server(server_id)?, "--stdio".into()],
        };
        Ok(zed::Command { command, args, env })
    }
}

zed::register_extension!(Eel2Extension);

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn python_requirement() {
        for version in ["2.7", "3.8", "", "not python"] {
            assert!(!supported_python(version));
        }
        for version in ["3.9\n", "3.14", "3.10\r\n"] {
            assert!(supported_python(version));
        }
    }
    #[test]
    fn damaged_download_is_rejected() {
        let expected = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad\n";
        assert!(matches_checksum(b"abc", expected));
        assert!(!matches_checksum(b"abd", expected));
        assert!(!matches_checksum(b"", expected));
    }
}

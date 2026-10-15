use std::{fs, path::Path};
use zed_extension_api::{self as zed, settings::LspSettings, LanguageServerId, Result};

const REPOSITORY: &str = "MattiaPersico/zed-eel2";
const VERSION: &str = env!("CARGO_PKG_VERSION");

struct Eel2Extension;

impl Eel2Extension {
    fn download_server(&self, server_id: &LanguageServerId) -> Result<String> {
        let filename = format!("eel2-lsp-v{VERSION}.pyz");
        let path = std::env::current_dir()
            .map_err(|error| error.to_string())?
            .join(&filename);
        if !path.is_file() {
            zed::set_language_server_installation_status(
                server_id,
                &zed::LanguageServerInstallationStatus::Downloading,
            );
            let result = self.fetch_server(&filename, &path);
            if let Err(error) = result {
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
        let release = zed::github_release_by_tag_name(REPOSITORY, &format!("v{VERSION}"))?;
        let asset = release
            .assets
            .iter()
            .find(|asset| asset.name == filename)
            .ok_or_else(|| format!("Release v{VERSION} does not contain {filename}."))?;
        // A failed/interrupted download must not become a cached server.
        let temporary = format!("{filename}.download");
        let _ = fs::remove_file(&temporary);
        zed::download_file(
            &asset.download_url,
            &temporary,
            zed::DownloadedFileType::Uncompressed,
        )?;
        fs::rename(&temporary, destination).map_err(|error| error.to_string())
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
        let command = binary
            .as_ref()
            .and_then(|binary| binary.path.clone())
            .or_else(|| worktree.which("python3"))
            .or_else(|| worktree.which("python"))
            .ok_or(
                "EEL2 requires Python 3.9+. Install Python or set lsp.eel2-lsp.binary.path in Zed.",
            )?;
        let args = match binary.as_ref().and_then(|binary| binary.arguments.clone()) {
            Some(args) => args,
            None => vec![self.download_server(server_id)?, "--stdio".into()],
        };
        let mut env = vec![("PYTHONDONTWRITEBYTECODE".into(), "1".into())];
        if let Some(extra) = binary.and_then(|binary| binary.env) {
            env.extend(extra);
        }
        Ok(zed::Command { command, args, env })
    }
}

zed::register_extension!(Eel2Extension);

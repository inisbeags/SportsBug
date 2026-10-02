# One-time GitHub setup

1. Use https://github.com/inisbeags/SportsBug. This package is configured to check releases from inisbeags/SportsBug.
2. Upload all extracted project files, including `.github/workflows/windows-release.yml`. The workflow must be at the repository root, not inside an extra folder. The Windows installer will bundle Python and PySide6.
3. Open Actions → Build Windows installer → Run workflow. After it finishes, download SportsBug-Windows-installer from the run's Artifacts, extract it, and run SportsBug-Setup.exe. Quit your old Python widget before the first install. Your existing settings in your home SportsBug folder are retained.
4. Test the installed app: taskbar, settings, refresh, and update checks. Enter your repository as owner/SportsBug in Settings if using the older Python copy; builds automatically include their repository address.
5. To publish this first version, create and push tag v0.2.0 (matching VERSION in sportsbug.py). Alternatively open Releases → Draft a new release, create tag v0.2.0, and save a draft; then run the workflow for that tag and attach the tested installer yourself. The tag-triggered workflow creates a draft release automatically when no draft already exists. Publish the draft after checking the installer.
6. For future releases, update VERSION in sportsbug.py (for example 0.2.1), upload the changed files, and create the matching tag. The workflow builds a new installer. Publish its draft once tested.

Settings → Check for updates checks the latest published stable release. Launch checking can be switched off. Checks never install software silently: an available update offers a download, then you run the installer. The installer reuses the installed location and shortcuts while retaining your separate settings file. The first installed upgrade and automatic closing of the widget still need Windows testing.

This package contains build instructions, not a compiled Windows installer. GitHub Actions performs the Windows build. Public release downloads work without a GitHub sign-in; private repositories would require an authenticated updater, which this prototype does not implement.

Before publishing each draft release, complete FEED-REVIEW.md and include the findings in its release notes.

# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0-beta.3] - 2026-02-27

### Added
- **Design System:** Complete professional design system with 42+ CSS variables, system font stack, and 8pt grid.
- **Enterprise UI:** Rebuilt Sidebar, Dashboard, and Review pages with high-end aesthetic (Glassmorphism, Haptics).
- **Multi-Upload:** Support for multiple file uploads simultaneously with real-time progress monitoring.
- **Security Hardening:** Integrated ClamAV stream-scanning for all uploads and added strict Content-Security-Policy headers.
- **Performance:** Parallelized test execution using `pytest-xdist`, reducing CI time by 60%.
- **Architecture:** Transitioned to a clean Blueprint-based HMVC architecture with a single entry point CLI.

### Fixed
- **E2E Stability:** Resolved Playwright test failures by fixing pathing issues and updating element locators.
- **Data Isolation:** Enforced usage of `KUKANILEA_USER_DATA_ROOT` across all core modules.
- **Legacy Cleanup:** Removed all files with version suffixes (`_v3`, `_fixed`) and cleaned up the root directory.

### Changed
- **Branding:** Fully migrated from "Tophandwerk" naming to "KUKANILEA" Enterprise branding.
- **Navigation:** New sidebar with SVG icons and functional routes for all core modules.

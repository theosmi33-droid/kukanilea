# Packaging Plan (macOS DMG)

The canonical packaging documentation moved to:

- `docs/packaging/BUILD.md`
- `docs/packaging/SIGNING.md`

Quick path:

```bash
scripts/build/obfuscate.sh
scripts/build/bundle_macos.sh
scripts/build/dmg_macos.sh
```

Compatibility wrappers remain available:

- `scripts/build_mac.sh`
- `scripts/make_dmg.sh`

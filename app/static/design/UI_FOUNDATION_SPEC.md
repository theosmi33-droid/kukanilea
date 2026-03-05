# KUKANILEA Enterprise UI Foundation (v2.0)

## Mission
Provide an industrial-grade, local-first office operating system for craft businesses.

## Design Principles
1. **High Density Data**: Information is condensed but clear. Zero fluff.
2. **Deterministic Layout**: 8pt grid with 4pt precision adjustments.
3. **Local Sovereignty**: Zero CDN, zero tracking, maximum speed.
4. **Accessible Authority**: AA-contrast standards with high authority primary colors.

## Enterprise Tokens
### Shell Anchors
- Sidebar Width: `17rem` (Large) / `5rem` (Collapsed)
- Header Height: `4rem`
- Interaction: 100ms (Fast) / 200ms (Base)

### Functional Semantic Layers
| Layer | Background | Text | Border | Use Case |
| :--- | :--- | :--- | :--- | :--- |
| Success | Green 50 | Green 800 | Green 500 | Positive actions, Done states |
| Warning | Yellow 50 | Yellow 800 | Yellow 500 | Pending, Syncing, Memory high |
| Error | Red 50 | Red 800 | Red 500 | Failures, Blockers, Deletion |
| Info | Blue 50 | Blue 800 | Blue 500 | System status, help text |

## Component Standards
### Tables (Industrial)
- Header: Sticky support, Uppercase bold, 10px font.
- Rows: Hover highlight, 8px vertical padding.
- Selection: Primary 50 background on active rows.

### App Shell
- **Sidebar**: Nested navigation support, system health integration.
- **Top Bar**: Minimalist breadcrumbs + global context switchers.
- **Modals**: Centered, blurred backdrop, max-width responsive.

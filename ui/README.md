# UI Refactor Blueprint (White Mode)

## 1) Current UI Audit Summary

### Repository UI layer map
- **Templates/UI views:** `app/templates/` (47 files, including module pages, shared components, and skeletons).
- **Primary style sources:** `app/static/css/` + duplicated mirror in `static/css/`.
- **Primary interaction scripts:** `app/static/js/` + duplicated mirror in `static/js/`.

### Issues found
1. **Heavy inline styling debt**
   - 393 inline `style="..."` usages across templates.
   - Highest concentration: `settings.html`, `forensic_dashboard.html`, `review.html`, `audit_trail.html`.
2. **Duplicated static assets**
   - Same CSS files duplicated in both `app/static/css` and `static/css` (e.g., `components.css`, `landing.css`, `system.css`, `voice_control.css`).
3. **Token drift and semantic overlap**
   - Existing token systems mix legacy aliases and page-specific design assumptions.
   - Spacing and component dimensions vary by template.
4. **Interaction patterns are spread and inconsistent**
   - Behavior split across shell/navigation scripts, command palette, toast feedback, and module-specific scripts.

## 2) New Target Architecture

```txt
/ui
  /design-system
    tokens.css
    foundations.css
  /components
    buttons.css
    cards.css
    forms.css
    feedback.css
  /layouts
    app-shell.css
    page.css
```

### Design system decisions
- **Single white mode token source** in `ui/design-system/tokens.css`.
- **Global primitives/reset** in `ui/design-system/foundations.css`.
- **Composable component styles** isolated by concern under `ui/components`.
- **Layout scaffolding** under `ui/layouts` to enforce shell/page consistency.

## 3) White Mode Design Tokens

Token set implemented exactly as requested:
- `background.primary = #FFFFFF`
- `background.secondary = #F7F7F8`
- `background.tertiary = #F1F2F4`
- `text.primary = #111111`
- `text.secondary = #555555`
- `text.muted = #888888`
- `accent.primary = #2563EB`
- `accent.hover = #1D4ED8`
- `border.default = #E5E7EB`
- `border.soft = #F0F0F0`

Also standardized:
- spacing scale (4px base)
- typography scale
- border radius scale
- elevation scale
- interaction transitions + focus ring

## 4) Interaction Model Standardization

- **Buttons:** explicit hover/active/disabled behavior.
- **Inputs:** unified hover/focus/error-ready shell.
- **Cards:** neutral and interactive variants.
- **Feedback:** badge/alert/skeleton patterns for fast system comprehension.
- **Focus treatment:** consistent `:focus-visible` ring for keyboard accessibility.

## 5) Migration Steps (Incremental, Low-Risk)

1. **Adopt foundations first**
   - Import `ui/design-system/foundations.css` after current base styles in `app/templates/layout.html`.
2. **Replace inline styles by priority**
   - Wave 1: `settings.html`, `forensic_dashboard.html`, `review.html`, `audit_trail.html`.
   - Convert inline declarations into semantic utility/component classes.
3. **Migrate shared partials**
   - Refactor `partials/topbar.html`, `partials/sidebar.html`, and `components/*.html` to new layout/component classes.
4. **Unify static source of truth**
   - Keep only one CSS/JS serving path (prefer `app/static/*`), remove mirrored duplicates in `static/*`.
5. **Introduce UI quality gates**
   - Lint rule: block new inline styles.
   - Visual regression snapshots for key pages (dashboard, settings, messenger, automation).
6. **Decompose legacy files**
   - Gradually split broad files (`system.css`, `components.css`) into design-system/component/layout buckets.

## 6) UX Outcomes Expected

- Faster scanning through cleaner visual hierarchy and predictable spacing.
- Lower cognitive load by reducing one-off styling and interaction inconsistencies.
- Better maintainability via tokenized, modular styling architecture.
- Improved delivery speed: new screens compose from existing layout + component contracts.

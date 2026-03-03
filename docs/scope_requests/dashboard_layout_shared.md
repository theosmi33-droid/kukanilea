# Scope Request: Dashboard layout.html changes

The `dashboard` domain needs to add `htmx.min.js` to the shared `layout.html`.

## Proposed changes

```patch
<<<<
   <script src="/static/js/state.js"></script>
+  <script src="/static/js/htmx.min.js"></script>
   <script src="/static/js/command_palette.js"></script>
>>>>
```

## Rationale

The dashboard components rely on HTMX for dynamic updates.

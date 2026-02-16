# Git Worktrees — Branch Cleanup

## Typischer Fehler

`cannot delete branch ... checked out at ...`

Ursache: Der Branch ist in einem Worktree aktiv.

## Diagnose

```bash
git worktree list
```

## Aufraeumen

1. Betroffenen Worktree entfernen:
```bash
git worktree remove <path-to-worktree>
```

2. Verwaiste Referenzen bereinigen:
```bash
git worktree prune
```

3. Branch danach loeschen:
```bash
git branch -d <branch>
# oder erzwungen:
git branch -D <branch>
```

## Hinweis

- `-d` loescht nur gemergte Branches.
- `-D` erzwingt Loeschung (nur bewusst einsetzen).

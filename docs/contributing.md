# Mitarbeit & Git-Workflow

## Branches

- **`main`** ist der Hauptbranch und immer lauffähig. Auf `main` wird nicht direkt entwickelt.
- Jedes Feature bekommt einen eigenen Branch von `main`, z. B.:
  - `feature/host-assistent`
  - `fix/caddy-reload`
  - `docs/roadmap-phase-2`
- Ist das Feature fertig, wird ein **Pull Request** gegen `main` erstellt und danach gemergt.

```bash
git switch main && git pull
git switch -c feature/<name>
# … entwickeln, committen …
git push -u origin feature/<name>
gh pr create --base main --fill
gh pr merge --squash --delete-branch
```

## Commits

- Commit-E-Mail für dieses Projekt: **`git@criehe.de`** (ist lokal im Repo gesetzt,
  `git config user.email`).
- Vor einem PR müssen laufen:
  - `cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .`
  - `cd frontend && npm run check && npm run build`

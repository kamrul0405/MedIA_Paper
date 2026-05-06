# How to push this repo to GitHub

The local repo is fully initialized and committed (branch `main`; remote `origin` set to `https://github.com/kamrul0405/Nature_MI_paper.git`). To make it visible on GitHub you need to create the empty remote repository first, then push.

## Option A — GitHub Desktop (installed at `C:\Users\kamru\AppData\Local\GitHubDesktop\`)

1. Open GitHub Desktop.
2. **File → Add Local Repository** → choose `C:\Users\kamru\Downloads\Nature_MI_paper`.
3. **Repository → Push** (or click the *"Publish repository"* button at the top). Choose `kamrul0405` as the account.
4. Uncheck *"Keep this code private"* if you want it public, leave checked for private.
5. Click **Publish repository**.

GitHub Desktop will create the remote repository under `kamrul0405/Nature_MI_paper` and push the initial commit automatically.

## Option B — gh CLI (if you install it)

```powershell
winget install --id GitHub.cli       # or: choco install gh
gh auth login                         # one-time login with GitHub credentials
cd C:\Users\kamru\Downloads\Nature_MI_paper
gh repo create kamrul0405/Nature_MI_paper --source . --public --push
```

## Option C — manual (web + git)

1. Open https://github.com/new in a browser.
2. Owner: `kamrul0405`. Repository name: `Nature_MI_paper`. Public or private as you prefer. Do NOT initialize with README, .gitignore or LICENSE (we already have those locally).
3. Click **Create repository**.
4. In a terminal:
   ```bash
   cd C:\Users\kamru\Downloads\Nature_MI_paper
   git push -u origin main
   ```
   You may be prompted for a GitHub username and a Personal Access Token (not a password). Generate one at https://github.com/settings/tokens (scope: `repo`).

## Verifying the push

After pushing, the README on https://github.com/kamrul0405/Nature_MI_paper should render and the repository should contain 36 files across `manuscript/`, `figures/`, `source_data/` and `scripts/`.

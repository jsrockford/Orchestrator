# Git Instructions: Merging Development to Master

## Overview

This guide explains how to merge your `development` branch into `master` when you reach a milestone, then continue working in `development`.

**Our Workflow:**
- `master` branch: Contains stable, milestone releases
- `development` branch: Where active development happens
- When you reach a milestone: Merge `development` → `master`, then keep working in `development`

---

## Step-by-Step: Merging Development to Master

### Step 1: Make Sure Everything is Committed

Before starting, ensure all your work in `development` is saved:

```bash
git status
```

**What this does:** Shows you if you have any unsaved changes

**What to look for:**
- If you see "nothing to commit, working tree clean" → You're good to go!
- If you see modified files → You need to commit them first:

```bash
git add .
git commit -m "Your commit message describing the changes"
```

---

### Step 2: Switch to the Master Branch

```bash
git checkout master
```

**What this does:** Switches from `development` to `master` branch

**What you'll see:** A message like "Switched to branch 'master'"

---

### Step 3: Make Sure Master is Up-to-Date

```bash
git pull origin master
```

**What this does:** Downloads any changes from the remote `master` branch

**Why this matters:** Ensures you're merging into the latest version of master

---

### Step 4: Merge Development into Master

```bash
git merge development
```

**What this does:** Combines all the changes from `development` into `master`

**What might happen:**
- ✅ **"Fast-forward"** or **"Merge made..."** → Success! The merge worked
- ⚠️ **"CONFLICT"** → Git found conflicting changes (see Troubleshooting section below)

---

### Step 5: Push Master to Remote

```bash
git push origin master
```

**What this does:** Uploads your updated `master` branch to the remote repository (GitHub, GitLab, etc.)

**What you'll see:** Progress messages showing the upload

---

### Step 6: Switch Back to Development

```bash
git checkout development
```

**What this does:** Switches you back to the `development` branch so you can continue working

**You're done!** Your milestone is now in `master`, and you're back in `development` ready to work.

---

## Quick Reference: Complete Command Sequence

For when you've done this a few times and just need a reminder:

```bash
# 1. Make sure development is clean
git status

# 2. Switch to master
git checkout master

# 3. Update master
git pull origin master

# 4. Merge development into master
git merge development

# 5. Push master to remote
git push origin master

# 6. Switch back to development
git checkout development
```

---

## Troubleshooting

### Problem: Merge Conflicts

**What happened:** Git found changes in both branches that conflict and needs your help to resolve them.

**What you'll see:**
```
Auto-merging somefile.py
CONFLICT (content): Merge conflict in somefile.py
Automatic merge failed; fix conflicts and then commit the result.
```

**How to fix:**

1. **See which files have conflicts:**
   ```bash
   git status
   ```
   Look for files marked "both modified"

2. **Open the conflicting files** in your editor. You'll see sections like:
   ```
   <<<<<<< HEAD
   code from master
   =======
   code from development
   >>>>>>> development
   ```

3. **Edit the file** to keep what you want, removing the `<<<<<<<`, `=======`, and `>>>>>>>` markers

4. **Mark the conflict as resolved:**
   ```bash
   git add filename
   ```

5. **Complete the merge:**
   ```bash
   git commit -m "Merge development into master - resolved conflicts"
   ```

6. **Continue with Step 5** (push to remote)

### Problem: "You Have Uncommitted Changes"

**What happened:** You tried to switch branches but have unsaved work.

**How to fix:**

**Option A - Commit your changes:**
```bash
git add .
git commit -m "Description of your changes"
```

**Option B - Temporarily save your changes (stash):**
```bash
git stash
# ... do your merge ...
git checkout development
git stash pop  # Brings your changes back
```

### Problem: "I'm on the Wrong Branch!"

**How to check which branch you're on:**
```bash
git branch
```
The branch with a `*` is your current branch.

**How to switch:**
```bash
git checkout development  # or master
```

---

## Best Practices

1. **Always commit before switching branches** - Saves headaches!

2. **Test before merging** - Make sure your code works in `development` before merging to `master`

3. **Use descriptive commit messages** - Future you will be grateful

4. **Create a tag for milestones** (optional but helpful):
   ```bash
   git checkout master
   git tag -a v1.0 -m "Milestone 1 - Description"
   git push origin v1.0
   ```

5. **Keep development up-to-date with master** (optional, after merging):
   If you want to ensure `development` has all of `master`'s changes:
   ```bash
   git checkout development
   git merge master
   ```
   This is usually automatic since development is ahead, but good to do occasionally.

---

## What's Happening Behind the Scenes?

Think of it like this:
- **Branches** are like parallel timelines of your project
- **master** is your "official release" timeline
- **development** is your "experimental work" timeline
- **Merging** takes everything from development and adds it to master
- After merging, both branches have the same content, but you keep working in development for the next milestone

---

## Need Help?

- **See what changed:** `git log --oneline`
- **See branch differences:** `git diff master development`
- **Undo last commit (careful!):** `git reset --soft HEAD~1`
- **Abandon merge (if stuck):** `git merge --abort`

If you get stuck, don't panic! Git rarely destroys data. Most mistakes can be undone.

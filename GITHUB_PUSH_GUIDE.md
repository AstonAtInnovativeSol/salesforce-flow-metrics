# GitHub Push Guide - Complete Instructions

## 🚀 Quick Push Commands

### Step 1: Navigate to your repository
```bash
cd "/Users/afleming/Desktop/Final Python Scripts"
```

### Step 2: Check status
```bash
git status
```

### Step 3: Add all changes (from Live folder)
```bash
# Add all files in Live and migrated to GitHub folder
git add "Live and migrated to GitHub/"

# Add root-level files (organize script, migration scripts, etc.)
git add index.html  # If it's in root
git add organize_files.py
git add run_full_migration.py
git add backup_all_scripts.py
git add run_executive_dashboard.py
git add run_velocity_migration.py
git add backfill_json_history.py
git add .gitignore
git add requirements.txt
git add sf_config.py.example
git add sf_config_helper.py

# Add documentation
git add *.md

# Or add everything at once (be careful!)
git add .
```

### Step 4: Commit changes
```bash
git commit -m "Add Sales Ops Analytics landing page and organize files

- Rebrand landing page to 'Sales Ops Analytics'
- Add index.html with all dashboard links
- Organize files into Live and Historical folders
- Keep Ghost Pipeline and Past Due links unchanged
- Add velocity and executive dashboards"
```

### Step 5: Push to GitHub
```bash
git push origin main
```

**OR if your branch is called `master`:**
```bash
git push origin master
```

---

## 📋 Detailed Step-by-Step

### 1. Verify Git Setup

Check if git is initialized:
```bash
cd "/Users/afleming/Desktop/Final Python Scripts"
git status
```

If you see "not a git repository", initialize it:
```bash
git init
```

### 2. Check Remote Repository

Verify your remote is set up:
```bash
git remote -v
```

If no remote exists, add it:
```bash
git remote add origin https://github.com/AstonAtInnovativeSol/salesforce-flow-metrics.git
```

**OR if using SSH:**
```bash
git remote add origin git@github.com:AstonAtInnovativeSol/salesforce-flow-metrics.git
```

### 3. Check What Will Be Committed

**IMPORTANT:** Review what files will be committed:
```bash
git status
git diff --cached  # See what's staged
```

**Make sure sensitive files are NOT included:**
- `sf_config.py` (should be in .gitignore)
- `*.key` files
- `*.pem` files
- Any files with credentials

### 4. Add Files

**Recommended: Add specific folders/files:**
```bash
# Add the Live folder (all your active scripts and dashboards)
git add "Live and migrated to GitHub/"

# Add root-level organization files
git add index.html
git add organize_files.py
git add run_full_migration.py
git add backup_all_scripts.py
git add run_executive_dashboard.py
git add run_velocity_migration.py
git add backfill_json_history.py
git add html_template_base.py

# Add configuration files
git add .gitignore
git add requirements.txt
git add sf_config.py.example
git add sf_config_helper.py

# Add documentation
git add MIGRATION_PLAN.md
git add QUICK_START.md
git add VELOCITY_MIGRATION_GUIDE.md
git add GITHUB_*.md
git add JWT_*.md
```

**OR add everything (be careful!):**
```bash
git add .
```

### 5. Commit Changes

Create a descriptive commit message:
```bash
git commit -m "Add Sales Ops Analytics landing page and organize files

- Rebrand landing page to 'Sales Ops Analytics'
- Add index.html with all dashboard links
- Keep Ghost Pipeline and Past Due links unchanged for backward compatibility
- Organize files into 'Live and migrated to GitHub' folder
- Add velocity dashboards (Boca and Pipeline)
- Add executive dashboard
- Include all documentation and migration scripts"
```

### 6. Push to GitHub

**First time pushing?**
```bash
# Set upstream branch
git push -u origin main
```

**OR if your branch is `master`:**
```bash
git push -u origin master
```

**Subsequent pushes:**
```bash
git push origin main
# OR
git push origin master
```

---

## 🔐 GitHub Pages Setup

### Enable GitHub Pages

1. Go to your GitHub repository: `https://github.com/AstonAtInnovativeSol/salesforce-flow-metrics`
2. Click **Settings** → **Pages**
3. Under **Source**, select:
   - **Branch:** `main` (or `master`)
   - **Folder:** `/ (root)`
4. Click **Save**

### Your GitHub Pages URL

After pushing, your dashboards will be available at:

- **Landing Page:** `https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/`
- **Ghost Pipeline:** `https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/flow_slack_metrics_ghost_pipeline_latest.html`
- **Past Due Closed Date:** `https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/flow_slack_metrics_past_due_closed_date_latest.html`
- **Boca Velocity:** `https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/boca_velocity_latest.html`
- **Pipeline Velocity:** `https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/pipeline_velocity_latest.html`
- **Executive Dashboard:** `https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/exec_pipeline_dashboard - PoC.html`

---

## ⚠️ Important Notes

### Before Pushing

1. **Verify .gitignore is working:**
   ```bash
   git check-ignore sf_config.py
   # Should return: sf_config.py
   ```

2. **Check for sensitive files:**
   ```bash
   git status
   # Make sure NO sensitive files appear!
   ```

3. **Test locally first:**
   - Open `index.html` in your browser
   - Click all links to verify they work
   - Make sure all paths are correct

### After Pushing

1. **Wait 1-2 minutes** for GitHub Pages to build
2. **Visit your GitHub Pages URL** to verify
3. **Check GitHub Actions** (if enabled) for any errors

---

## 🆘 Troubleshooting

### "Permission denied" error
```bash
# Set up SSH keys or use HTTPS with personal access token
# Or use GitHub CLI:
gh auth login
```

### "Branch not found" error
```bash
# Check your branch name
git branch

# If it's 'master', use:
git push origin master
```

### "Nothing to commit" error
```bash
# Check if files are already committed
git log --oneline -5

# Or check if files are ignored
git check-ignore "Live and migrated to GitHub/"
```

### GitHub Pages not updating
1. Check GitHub Actions tab for errors
2. Verify branch is set correctly in Settings → Pages
3. Wait 2-3 minutes and refresh
4. Clear browser cache

---

## ✅ Quick Checklist

Before pushing:
- [ ] All sensitive files in .gitignore
- [ ] All files organized in "Live and migrated to GitHub"
- [ ] index.html created and tested
- [ ] All links work locally
- [ ] Git remote configured
- [ ] Branch name confirmed (main or master)

After pushing:
- [ ] GitHub Pages enabled in Settings
- [ ] Landing page loads correctly
- [ ] All dashboard links work
- [ ] Ghost Pipeline link works (your boss's bookmark)
- [ ] Past Due link works (your boss's bookmark)

---

## 📞 Need Help?

If you encounter issues:
1. Check `git status` to see what's happening
2. Review `.gitignore` to ensure sensitive files are excluded
3. Verify your GitHub repository exists and you have access
4. Check GitHub Actions logs if builds are failing


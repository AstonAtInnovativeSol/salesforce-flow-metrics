# 🚀 Quick Push Instructions

## One Command to Push Everything

```bash
cd "/Users/afleming/Desktop/Final Python Scripts"
./push_to_github.sh
```

That's it! The script will:
1. ✅ Add all files from "Live and migrated to GitHub" folder
2. ✅ Copy HTML files to root (so old links still work)
3. ✅ Add organization scripts
4. ✅ Add documentation
5. ✅ Commit with descriptive message
6. ✅ Push to GitHub

---

## Manual Push (Step-by-Step)

If you prefer to do it manually:

### 1. Navigate to repository
```bash
cd "/Users/afleming/Desktop/Final Python Scripts"
```

### 2. Copy HTML files to root (for backward compatibility)
```bash
# Copy index.html and all HTML files to root
cp "Live and migrated to GitHub/index.html" index.html
cp "Live and migrated to GitHub"/*.html .
```

### 3. Add all files
```bash
# Add Live folder
git add "Live and migrated to GitHub/"

# Add root-level HTML files
git add *.html

# Add organization scripts
git add organize_files.py
git add run_full_migration.py
git add backup_all_scripts.py
git add run_executive_dashboard.py
git add run_velocity_migration.py
git add backfill_json_history.py

# Add documentation
git add *.md

# Add .github folder
git add .github/
```

### 4. Commit
```bash
git commit -m "Add Sales Ops Analytics landing page and organize files

- Rebrand landing page to 'Sales Ops Analytics'
- Add index.html with all dashboard links
- Organize files into 'Live and migrated to GitHub' folder
- Keep Ghost Pipeline and Past Due links unchanged
- Add velocity dashboards (Boca and Pipeline)
- Add executive dashboard"
```

### 5. Push
```bash
git push origin main
```

---

## 📱 After Pushing

### Enable GitHub Pages (if not already enabled)

1. Go to: https://github.com/AstonAtInnovativeSol/salesforce-flow-metrics
2. Click **Settings** → **Pages**
3. Under **Source**, select:
   - **Branch:** `main`
   - **Folder:** `/ (root)`
4. Click **Save**

### Your URLs

After pushing (wait 1-2 minutes for GitHub Pages to build):

- **Landing Page:** `https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/`
- **Ghost Pipeline:** `https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/flow_slack_metrics_ghost_pipeline_latest.html`
- **Past Due Closed Date:** `https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/flow_slack_metrics_past_due_closed_date_latest.html`
- **Boca Velocity:** `https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/boca_velocity_latest.html`
- **Pipeline Velocity:** `https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/pipeline_velocity_latest.html`
- **Executive Dashboard:** `https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/exec_pipeline_dashboard - PoC.html`

---

## ✅ Verification

After pushing, verify:

1. **Landing page loads:** Visit `https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/`
2. **All links work:** Click each dashboard card
3. **Boss's bookmarks work:**
   - Ghost Pipeline link still works
   - Past Due link still works

---

## 🆘 Troubleshooting

### Permission denied
```bash
# Use HTTPS with personal access token, or set up SSH keys
```

### Branch not found
```bash
# Check your branch name
git branch
# If it's 'master', use: git push origin master
```

### GitHub Pages not updating
- Wait 2-3 minutes
- Check GitHub Actions tab for errors
- Clear browser cache

---

**That's it! Your Sales Ops Analytics dashboard is now live on GitHub Pages! 🎉**


# Quick Start Guide - Complete Migration

## 🚀 One Command to Rule Them All

```bash
cd "/Users/afleming/Desktop/Final Python Scripts"
python run_full_migration.py
```

This single command will:
1. ✅ Backup all scripts (timestamped)
2. ✅ Run velocity migration (Boca + Pipeline) with SOQL backfill
3. ✅ Run executive dashboard workflow (all 3 scripts)
4. ✅ Generate migration report

---

## 📋 Individual Commands

### 1. Create Backups Only
```bash
python backup_all_scripts.py
```
Creates timestamped backups in `backups_YYYYMMDD_HHMMSS/` directory

### 2. Run Velocity Migration (with backfill)
```bash
python run_velocity_migration.py --backfill --start-date 2025-11-03 --weeks 12
```

### 3. Run Executive Dashboard Workflow
```bash
python run_executive_dashboard.py
```
Runs all 3 executive scripts and combines outputs

### 4. Full Migration (with options)
```bash
# Skip backup (if already done)
python run_full_migration.py --skip-backup

# Skip velocity migration
python run_full_migration.py --skip-velocity

# Skip executive dashboard
python run_full_migration.py --skip-executive

# No backfill (faster, but no initial JSON history)
python run_full_migration.py --no-backfill
```

---

## 📁 Files Created

### Backup Scripts
- `backup_all_scripts.py` - Creates timestamped backups

### Migration Scripts
- `run_full_migration.py` - Master migration script
- `run_velocity_migration.py` - Velocity reports migration
- `run_executive_dashboard.py` - Executive dashboard workflow
- `backfill_json_history.py` - SOQL backfill for JSON history

### Documentation
- `MIGRATION_PLAN.md` - Complete migration plan
- `VELOCITY_MIGRATION_GUIDE.md` - Velocity migration guide
- `QUICK_START.md` - This file

---

## 📊 Output Files

After running migration, you'll have:

### HTML Dashboards
- `boca_velocity_latest.html` - Boca Velocity Report
- `pipeline_velocity_latest.html` - Pipeline Velocity Report
- `exec_pipeline_dashboard - PoC.html` - Executive Dashboard

### JSON History (Week-Specific)
- `boca_velocity_history.json` - 12 weeks of Boca data
- `pipeline_velocity_history.json` - 12 weeks of Pipeline data

### Backups
- `backups_YYYYMMDD_HHMMSS/` - Timestamped backup directory
- `backup_manifest.json` - Backup manifest with file locations

### Reports
- `migration_report_YYYYMMDD_HHMMSS.json` - Migration execution report

---

## 🌐 GitHub Pages URLs

After pushing to GitHub:

- **Boca Velocity:** `https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/boca_velocity_latest.html`
- **Pipeline Velocity:** `https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/pipeline_velocity_latest.html`
- **Executive Dashboard:** `https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/exec_pipeline_dashboard - PoC.html`

---

## ⚠️ Important Notes

1. **Backups First:** Always run backups before migration
2. **Week-Specific Tracking:** JSON history stores one entry per week (latest wins)
3. **JWT Authentication:** All scripts use secure JWT authentication
4. **Original Files Preserved:** All originals saved as `*_original.py`

---

## 🆘 Troubleshooting

### "Module not found" errors
```bash
cd "/Users/afleming/Desktop/Final Python Scripts"
# Make sure you're in the right directory
```

### Script fails
- Check backup directory for original files
- Review error messages in output
- Check `migration_report_*.json` for details

### Backfill fails for specific weeks
- Backfill continues even if one week fails
- Check output for specific error messages
- Can re-run backfill with `--weeks` adjusted

---

## 📖 Full Documentation

See `MIGRATION_PLAN.md` for complete migration plan and file organization structure.


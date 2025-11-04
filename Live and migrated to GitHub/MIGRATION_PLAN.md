# Complete Migration Plan - Full Suite

## Overview

This document outlines the complete backup and migration plan for all scripts in the suite.

---

## Suite Components

### [FOLDER] Touchpoint_Intel
- **Touchpoint Intelligence Report** (HTML dashboard)

### Scripts (Final Python Scripts)
1. **SnapshotSummary.py** - Pipeline snapshot sync
2. **TrailingProfServ.py** - 6-week trailing average for professional services
3. **pipev3.py** - ✅ Already converted to HTML + JSON history
4. **BocaSalesMotion2.py** - ✅ Already converted to HTML + JSON history
5. **Salesforce_flow_slack_metrics.py** - Flow execution metrics for Slack alerts
6. **dealSizeWinRate.py** - Deal size distribution and win rate analysis

### Executive Dashboard (To Run in Sequence)
1. **highlevel_upgraded.py** - Production-ready executive dashboard
2. **elite_pipeline_analysis.py** - Comprehensive pipeline analysis
3. **highlevel_clean.py** - Clean version executive dashboard
4. **Output**: `exec_pipeline_dashboard - PoC.html`

---

## Migration Phases

### Phase 1: Backup (✅ Complete)
- [x] Create timestamped backups of all scripts
- [x] Create backup manifest with file locations
- [x] Verify all files are backed up

### Phase 2: Organization (📋 Pending)
- [ ] Create folder structure:
  - `Live and migrated to GitHub/`
    - `Scripts/` - All active scripts
    - `HTML Dashboards/` - Generated HTML files
    - `JSON History/` - Week-specific JSON history files
  - `Historical Artifact/`
    - `Backups/` - All backup directories
    - `Original Scripts/` - Original versions before conversion

### Phase 3: Script Updates (🔄 In Progress)
- [x] `pipev3.py` - Converted to HTML + JSON history
- [x] `BocaSalesMotion2.py` - Converted to HTML + JSON history
- [ ] `SnapshotSummary.py` - Add HTML output option
- [ ] `TrailingProfServ.py` - Add HTML output option
- [ ] `Salesforce_flow_slack_metrics.py` - Already has HTML output
- [ ] `dealSizeWinRate.py` - Already has HTML output

### Phase 4: Executive Dashboard Workflow (📋 Pending)
- [ ] Create workflow script that runs all 3 executive scripts in sequence
- [ ] Combine outputs into single `exec_pipeline_dashboard - PoC.html`
- [ ] Add error handling and logging
- [ ] Add JSON history tracking

### Phase 5: GitHub Migration (📋 Pending)
- [ ] Initialize git repository (if not already)
- [ ] Create `.gitignore` (already exists)
- [ ] Add all scripts to repository
- [ ] Set up GitHub Actions for automated runs
- [ ] Configure GitHub Secrets for JWT authentication
- [ ] Enable GitHub Pages for HTML dashboards

### Phase 6: Cleanup (📋 Pending)
- [ ] Move all files to organized folder structure
- [ ] Archive historical artifacts
- [ ] Update documentation
- [ ] Create README.md with setup instructions

---

## File Organization Structure

```
Final Python Scripts/
├── Live and migrated to GitHub/
│   ├── Scripts/
│   │   ├── velocity/
│   │   │   ├── pipev3.py
│   │   │   ├── BocaSalesMotion2.py
│   │   │   └── run_velocity_migration.py
│   │   ├── pipeline/
│   │   │   ├── SnapshotSummary.py
│   │   │   └── TrailingProfServ.py
│   │   ├── analysis/
│   │   │   ├── dealSizeWinRate.py
│   │   │   └── Salesforce_flow_slack_metrics.py
│   │   ├── executive/
│   │   │   ├── highlevel_upgraded.py
│   │   │   ├── elite_pipeline_analysis.py
│   │   │   ├── highlevel_clean.py
│   │   │   └── run_executive_dashboard.py
│   │   └── shared/
│   │       └── html_template_base.py
│   ├── HTML Dashboards/
│   │   ├── boca_velocity_latest.html
│   │   ├── pipeline_velocity_latest.html
│   │   ├── exec_pipeline_dashboard - PoC.html
│   │   └── ...
│   └── JSON History/
│       ├── boca_velocity_history.json
│       ├── pipeline_velocity_history.json
│       └── ...
├── Historical Artifact/
│   ├── Backups/
│   │   └── backups_YYYYMMDD_HHMMSS/
│   └── Original Scripts/
│       ├── pipev3_original.py
│       ├── BocaSalesMotion2_original.py
│       └── ...
└── Touchpoint_Intel/
    └── (existing files)
```

---

## Execution Commands

### 1. Create Backups
```bash
cd "/Users/afleming/Desktop/Final Python Scripts"
python backup_all_scripts.py
```

### 2. Run Full Migration
```bash
python run_full_migration.py
```

### 3. Run Executive Dashboard
```bash
python run_executive_dashboard.py
```

### 4. Run Velocity Reports
```bash
python run_velocity_migration.py --backfill --start-date 2025-11-03 --weeks 12
```

---

## GitHub Setup

### GitHub Secrets Required
- `SF_USERNAME` - Salesforce username
- `SF_CONSUMER_KEY` - Connected App Consumer Key
- `SF_DOMAIN` - 'login' or 'test'
- `SF_PRIVATE_KEY` - Private key content (entire .pem file)

### GitHub Pages URLs
- Base: `https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/`
- Boca Velocity: `.../boca_velocity_latest.html`
- Pipeline Velocity: `.../pipeline_velocity_latest.html`
- Executive Dashboard: `.../exec_pipeline_dashboard - PoC.html`

---

## Testing Checklist

### Pre-Migration
- [ ] All scripts run successfully locally
- [ ] All backups created successfully
- [ ] Backup manifest verified

### Post-Migration
- [ ] All scripts run successfully on GitHub Actions
- [ ] HTML dashboards render correctly
- [ ] JSON history tracking works correctly
- [ ] GitHub Pages URLs accessible
- [ ] All sensitive files excluded from git

---

## Rollback Plan

If migration fails:
1. Restore from backup directory
2. Verify original scripts still work
3. Fix issues and retry migration
4. Update migration plan with lessons learned

---

## Next Steps

1. ✅ Run `backup_all_scripts.py` to create backups
2. 📋 Run `organize_files.py` to organize file structure
3. 📋 Run `run_full_migration.py` to execute full migration
4. 📋 Test all scripts and workflows
5. 📋 Push to GitHub and verify

---

## Notes

- All original scripts are preserved as `*_original.py` files
- Week-specific JSON history ensures one entry per week
- HTML dashboards use `touchpoint7.html` styling
- All scripts use JWT authentication (secure, no passwords)
- GitHub Secrets are encrypted and secure


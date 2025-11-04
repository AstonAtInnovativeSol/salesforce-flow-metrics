# Velocity Migration Guide

## Week-Specific JSON History Tracking

Both **Boca Velocity** and **Pipeline Velocity** now use **week-specific tracking**:
- **One entry per week** - If you run a script 9 times in a week, only the **latest** entry for that week is kept
- **12-week lookback** - Maintains history for the last 12 weeks
- **Week key based on data period** - Uses the week of the data period (e.g., Nov 3, 2025 week), not the generation date

### Example
- Today: Nov 4, 2025
- Data period: Nov 3, 2025 week (Sunday Nov 3 - Saturday Nov 9)
- Week key: `2025-44` (week 44 of 2025)
- If you run it 9 times this week, only the latest update is stored

---

## Quick Start: Single Command Migration

### Run Both Scripts with Initial JSON Backfill

```bash
cd "/Users/afleming/Desktop/Final Python Scripts"
python run_velocity_migration.py --backfill --start-date 2025-11-03 --weeks 12
```

This command will:
1. ✅ Run SOQL backfill to populate initial JSON history (12 weeks from Nov 3, 2025)
2. ✅ Run `BocaSalesMotion2.py` (generates HTML + JSON)
3. ✅ Run `pipev3.py` (generates HTML + JSON)

### Run Both Scripts Only (Skip Backfill)

```bash
python run_velocity_migration.py
```

### Run with Custom Options

```bash
# Backfill only 6 weeks
python run_velocity_migration.py --backfill --start-date 2025-11-03 --weeks 6

# Skip Boca, only run Pipeline
python run_velocity_migration.py --skip-boca

# Skip Pipeline, only run Boca
python run_velocity_migration.py --skip-pipeline
```

---

## Individual Scripts

### Boca Velocity
```bash
python BocaSalesMotion2.py
```

**Outputs:**
- `boca_velocity_latest.html` - HTML dashboard
- `boca_velocity_history.json` - Week-specific JSON history (12 weeks)

### Pipeline Velocity
```bash
python pipev3.py
```

**Outputs:**
- `pipeline_velocity_latest.html` - HTML dashboard
- `pipeline_velocity_history.json` - Week-specific JSON history (12 weeks)

---

## SOQL Backfill (Optional)

If you need to populate initial JSON history from Salesforce data:

```bash
# Backfill both
python backfill_json_history.py --start-date 2025-11-03 --weeks 12

# Backfill Boca only
python backfill_json_history.py --start-date 2025-11-03 --weeks 12 --boca-only

# Backfill Pipeline only
python backfill_json_history.py --start-date 2025-11-03 --weeks 12 --pipeline-only
```

**Note:** The backfill uses SOQL queries to fetch historical data from Salesforce. It processes each week sequentially, going backwards from the start date.

---

## JSON History Structure

Each entry in the JSON history file contains:

```json
{
  "week_key": "2025-44",
  "period_start": "2025-11-03",
  "generated_at": "2025-11-04T15:30:00",
  "data": {
    "period": {
      "last_week": {"start": "2025-10-27", "end": "2025-11-02"},
      "prior_week": {"start": "2025-10-20", "end": "2025-10-26"}
    },
    "data": {
      "Rep Name": {
        "meetings": {"last": 10, "prior": 8, "6w_avg": 9.5, "wow_pct": 25.0},
        "opp_dollars": {"last": 50000, "prior": 40000, "6w_avg": 45000, "wow_pct": 25.0},
        "closed_won": {"last": 30000, "prior": 25000, "wow_pct": 20.0}
      }
    }
  }
}
```

**Key Features:**
- `week_key`: Unique identifier for the week (YYYY-WW format)
- `period_start`: Start date of the data period
- `generated_at`: Timestamp when the entry was created
- Multiple runs in the same week **overwrite** the previous entry for that week

---

## GitHub Pages URLs

After pushing to GitHub:

- **Boca Velocity:** `https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/boca_velocity_latest.html`
- **Pipeline Velocity:** `https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/pipeline_velocity_latest.html`

---

## Troubleshooting

### "Module not found" errors
Make sure you're running from the script directory:
```bash
cd "/Users/afleming/Desktop/Final Python Scripts"
```

### Backfill fails for specific weeks
The backfill script will continue processing even if one week fails. Check the output for specific error messages.

### JSON history not updating
Check that the script is using the correct week key. The week key is based on the **data period start date**, not today's date.

---

## Files Created

- `html_template_base.py` - Reusable HTML template functions
- `backfill_json_history.py` - SOQL backfill script
- `run_velocity_migration.py` - Migration script (runs both scripts)
- `BocaSalesMotion2_original.py` - Backup of original Boca script
- `pipev3_original.py` - Backup of original Pipeline script


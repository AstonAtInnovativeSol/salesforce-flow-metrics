#!/usr/bin/env python3
"""
Full Suite Migration Script - Handles complete backup and migration
Executes all phases of the migration plan

Phases:
1. Backup all scripts
2. Organize file structure (optional)
3. Run velocity migration (with backfill)
4. Run executive dashboard workflow
5. Generate migration report
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime
import json
from backup_all_scripts import backup_all_scripts


def run_backup():
    """Phase 1: Create backups"""
    print("\n" + "=" * 60)
    print("PHASE 1: BACKUP ALL SCRIPTS")
    print("=" * 60)
    
    try:
        backup_dir, manifest = backup_all_scripts()
        print(f"\n✅ Backup complete: {backup_dir}")
        return True, backup_dir, manifest
    except Exception as e:
        print(f"\n❌ Backup failed: {e}")
        return False, None, None


def run_velocity_migration(backfill=True, start_date="2025-11-03", weeks=12):
    """Phase 2: Run velocity migration"""
    print("\n" + "=" * 60)
    print("PHASE 2: VELOCITY MIGRATION")
    print("=" * 60)
    
    script_dir = Path(__file__).parent
    migration_script = script_dir / "run_velocity_migration.py"
    
    if not migration_script.exists():
        print(f"⚠️  Warning: {migration_script} not found, skipping velocity migration")
        return False
    
    try:
        cmd = [sys.executable, str(migration_script)]
        if backfill:
            cmd.extend(["--backfill", "--start-date", start_date, "--weeks", str(weeks)])
        
        result = subprocess.run(
            cmd,
            cwd=str(script_dir),
            check=True,
            capture_output=False
        )
        print("\n✅ Velocity migration completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Velocity migration failed: exit code {e.returncode}")
        return False
    except Exception as e:
        print(f"\n❌ Error running velocity migration: {e}")
        return False


def run_executive_dashboard():
    """Phase 3: Run executive dashboard workflow"""
    print("\n" + "=" * 60)
    print("PHASE 3: EXECUTIVE DASHBOARD WORKFLOW")
    print("=" * 60)
    
    script_dir = Path(__file__).parent
    exec_script = script_dir / "run_executive_dashboard.py"
    
    if not exec_script.exists():
        print(f"⚠️  Warning: {exec_script} not found, skipping executive dashboard")
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, str(exec_script)],
            cwd=str(script_dir),
            check=True,
            capture_output=False
        )
        print("\n✅ Executive dashboard workflow completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Executive dashboard failed: exit code {e.returncode}")
        return False
    except Exception as e:
        print(f"\n❌ Error running executive dashboard: {e}")
        return False


def generate_migration_report(backup_dir, results):
    """Generate migration report"""
    print("\n" + "=" * 60)
    print("GENERATING MIGRATION REPORT")
    print("=" * 60)
    
    script_dir = Path(__file__).parent
    report = {
        "migration_date": datetime.now().isoformat(),
        "backup_directory": str(backup_dir) if backup_dir else None,
        "results": results,
        "output_files": {
            "velocity": {
                "boca": "boca_velocity_latest.html",
                "pipeline": "pipeline_velocity_latest.html"
            },
            "executive": "exec_pipeline_dashboard - PoC.html"
        },
        "github_pages_urls": {
            "base": "https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/",
            "boca_velocity": "https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/boca_velocity_latest.html",
            "pipeline_velocity": "https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/pipeline_velocity_latest.html",
            "executive_dashboard": "https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/exec_pipeline_dashboard - PoC.html"
        }
    }
    
    report_file = script_dir / f"migration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"✅ Migration report saved: {report_file}")
    return report_file


def main():
    """Run complete migration"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Full suite migration - backup and migrate all scripts"
    )
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Skip backup phase (use with caution)"
    )
    parser.add_argument(
        "--skip-velocity",
        action="store_true",
        help="Skip velocity migration"
    )
    parser.add_argument(
        "--skip-executive",
        action="store_true",
        help="Skip executive dashboard"
    )
    parser.add_argument(
        "--no-backfill",
        action="store_true",
        help="Skip SOQL backfill for velocity migration"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="2025-11-03",
        help="Start date for backfill (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--weeks",
        type=int,
        default=12,
        help="Number of weeks for backfill"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("FULL SUITE MIGRATION")
    print("=" * 60)
    print("\nThis migration will:")
    if not args.skip_backup:
        print("  ✅ Phase 1: Backup all scripts")
    if not args.skip_velocity:
        print("  ✅ Phase 2: Run velocity migration" + (" (with backfill)" if not args.no_backfill else ""))
    if not args.skip_executive:
        print("  ✅ Phase 3: Run executive dashboard workflow")
    print("  ✅ Phase 4: Generate migration report")
    print("\nStarting...")
    
    results = {}
    backup_dir = None
    manifest = None
    
    # Phase 1: Backup
    if not args.skip_backup:
        success, backup_dir, manifest = run_backup()
        results["backup"] = {
            "success": success,
            "directory": str(backup_dir) if backup_dir else None,
            "files_backed_up": len(manifest.get("backed_up_files", {})) if manifest else 0
        }
    else:
        print("\n⏭️  Skipping backup phase")
        results["backup"] = {"success": True, "skipped": True}
    
    # Phase 2: Velocity Migration
    if not args.skip_velocity:
        success = run_velocity_migration(
            backfill=not args.no_backfill,
            start_date=args.start_date,
            weeks=args.weeks
        )
        results["velocity_migration"] = {"success": success}
    else:
        print("\n⏭️  Skipping velocity migration")
        results["velocity_migration"] = {"success": True, "skipped": True}
    
    # Phase 3: Executive Dashboard
    if not args.skip_executive:
        success = run_executive_dashboard()
        results["executive_dashboard"] = {"success": success}
    else:
        print("\n⏭️  Skipping executive dashboard")
        results["executive_dashboard"] = {"success": True, "skipped": True}
    
    # Phase 4: Generate Report
    report_file = generate_migration_report(backup_dir, results)
    
    # Final Summary
    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    
    total_phases = sum(1 for v in results.values() if not v.get("skipped", False))
    successful_phases = sum(1 for v in results.values() if v.get("success", False))
    
    print(f"\n✅ Successful: {successful_phases}/{total_phases} phases")
    print(f"📄 Migration report: {report_file}")
    
    if successful_phases == total_phases:
        print("\n🎉 All phases completed successfully!")
        print("\n📊 Next Steps:")
        print("  1. Review migration report")
        print("  2. Test all generated HTML dashboards")
        print("  3. Verify GitHub Pages URLs")
        print("  4. Push to GitHub repository")
    else:
        print(f"\n⚠️  {total_phases - successful_phases} phase(s) failed. Review report for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()


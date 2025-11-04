#!/usr/bin/env python3
"""
Velocity Migration Script - Runs both Boca and Pipeline Velocity scripts
Includes optional SOQL backfill for initial JSON history creation

Usage:
    python run_velocity_migration.py
    python run_velocity_migration.py --backfill --start-date 2025-11-03 --weeks 12
"""

import argparse
import subprocess
import sys
from pathlib import Path
from datetime import date


def run_script(script_name, description):
    """Run a Python script and return success status"""
    print("\n" + "=" * 60)
    print(f"RUNNING: {description}")
    print("=" * 60)
    
    script_path = Path(__file__).parent / script_name
    if not script_path.exists():
        print(f"❌ Error: {script_name} not found at {script_path}")
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(script_path.parent),
            check=True,
            capture_output=False  # Show output in real-time
        )
        print(f"\n✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {description} failed with exit code {e.returncode}")
        return False
    except Exception as e:
        print(f"\n❌ Error running {description}: {e}")
        return False


def run_backfill(start_date, weeks):
    """Run the SOQL backfill script"""
    print("\n" + "=" * 60)
    print("RUNNING SOQL BACKFILL")
    print("=" * 60)
    
    backfill_script = Path(__file__).parent / "backfill_json_history.py"
    if not backfill_script.exists():
        print(f"❌ Error: backfill_json_history.py not found")
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, str(backfill_script),
             "--start-date", start_date,
             "--weeks", str(weeks)],
            cwd=str(backfill_script.parent),
            check=True,
            capture_output=False
        )
        print("\n✅ SOQL backfill completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ SOQL backfill failed with exit code {e.returncode}")
        return False
    except Exception as e:
        print(f"\n❌ Error running SOQL backfill: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Run Boca and Pipeline Velocity scripts with optional SOQL backfill"
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Run SOQL backfill before executing scripts (populates initial JSON history)"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="2025-11-03",
        help="Start date for backfill (YYYY-MM-DD). Default: 2025-11-03"
    )
    parser.add_argument(
        "--weeks",
        type=int,
        default=12,
        help="Number of weeks to backfill. Default: 12"
    )
    parser.add_argument(
        "--skip-boca",
        action="store_true",
        help="Skip Boca Velocity script"
    )
    parser.add_argument(
        "--skip-pipeline",
        action="store_true",
        help="Skip Pipeline Velocity script"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("VELOCITY MIGRATION SCRIPT")
    print("=" * 60)
    print("\nThis script will:")
    print("  1. Optionally run SOQL backfill for JSON history")
    print("  2. Run BocaSalesMotion2.py")
    print("  3. Run pipev3.py")
    print("\nStarting...")
    
    success_count = 0
    total_steps = 0
    
    # Step 1: Optional backfill
    if args.backfill:
        total_steps += 1
        if run_backfill(args.start_date, args.weeks):
            success_count += 1
        else:
            print("\n⚠️  Warning: Backfill failed, but continuing with scripts...")
    
    # Step 2: Boca Velocity
    if not args.skip_boca:
        total_steps += 1
        if run_script("BocaSalesMotion2.py", "Boca Velocity Report"):
            success_count += 1
    
    # Step 3: Pipeline Velocity
    if not args.skip_pipeline:
        total_steps += 1
        if run_script("pipev3.py", "Pipeline Velocity Report"):
            success_count += 1
    
    # Summary
    print("\n" + "=" * 60)
    print("MIGRATION SUMMARY")
    print("=" * 60)
    print(f"✅ Successful: {success_count}/{total_steps}")
    
    if success_count == total_steps:
        print("\n🎉 All steps completed successfully!")
        print("\n📊 Output Files:")
        script_dir = Path(__file__).parent
        print(f"   - boca_velocity_latest.html")
        print(f"   - boca_velocity_history.json")
        print(f"   - pipeline_velocity_latest.html")
        print(f"   - pipeline_velocity_history.json")
        print("\n🌐 GitHub Pages URLs:")
        print(f"   - https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/boca_velocity_latest.html")
        print(f"   - https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/pipeline_velocity_latest.html")
    else:
        print(f"\n⚠️  {total_steps - success_count} step(s) failed. Check output above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()


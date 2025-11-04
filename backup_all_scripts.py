#!/usr/bin/env python3
"""
Backup All Scripts - Creates timestamped backups before migration
Backs up all scripts from Final Python Scripts and Touchpoint_Intel folders
"""

import shutil
from pathlib import Path
from datetime import datetime
import json


def backup_all_scripts():
    """Create timestamped backups of all scripts"""
    
    # Define source directories
    base_dir = Path.home() / "Desktop"
    scripts_dir = base_dir / "Final Python Scripts"
    touchpoint_dir = base_dir / "Touchpoint_Intel"
    
    # Create backup directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = scripts_dir / f"backups_{timestamp}"
    backup_dir.mkdir(exist_ok=True)
    
    # Scripts to backup from Final Python Scripts
    scripts_to_backup = {
        "Final Python Scripts": [
            "SnapshotSummary.py",
            "TrailingProfServ.py",
            "pipev3.py",
            "BocaSalesMotion2.py",
            "Salesforce_flow_slack_metrics.py",
            "dealSizeWinRate.py",
            "highlevel_upgraded.py",
            "elite_pipeline_analysis.py",
            "highlevel_clean.py",
            "html_template_base.py",
            "backfill_json_history.py",
            "run_velocity_migration.py"
        ]
    }
    
    # Touchpoint_Intel scripts
    touchpoint_scripts = []
    if touchpoint_dir.exists():
        for file in touchpoint_dir.glob("*.py"):
            touchpoint_scripts.append(file.name)
        if touchpoint_scripts:
            scripts_to_backup["Touchpoint_Intel"] = touchpoint_scripts
    
    # Create backup manifest
    manifest = {
        "timestamp": timestamp,
        "backup_date": datetime.now().isoformat(),
        "backed_up_files": {},
        "errors": []
    }
    
    print("=" * 60)
    print("BACKING UP ALL SCRIPTS")
    print("=" * 60)
    print(f"Backup directory: {backup_dir}")
    print()
    
    # Backup files
    for folder_name, files in scripts_to_backup.items():
        source_dir = scripts_dir if folder_name == "Final Python Scripts" else touchpoint_dir
        
        if not source_dir.exists():
            print(f"⚠️  Warning: {source_dir} does not exist")
            manifest["errors"].append(f"Source directory not found: {source_dir}")
            continue
        
        print(f"\n📁 Backing up {folder_name}:")
        
        # Create subdirectory in backup
        backup_subdir = backup_dir / folder_name
        backup_subdir.mkdir(exist_ok=True)
        
        for filename in files:
            source_file = source_dir / filename
            if source_file.exists():
                try:
                    dest_file = backup_subdir / filename
                    shutil.copy2(source_file, dest_file)
                    manifest["backed_up_files"][str(source_file)] = str(dest_file)
                    print(f"  ✅ {filename}")
                except Exception as e:
                    error_msg = f"Failed to backup {filename}: {e}"
                    print(f"  ❌ {error_msg}")
                    manifest["errors"].append(error_msg)
            else:
                warning_msg = f"File not found: {filename}"
                print(f"  ⚠️  {warning_msg}")
                manifest["errors"].append(warning_msg)
    
    # Save manifest
    manifest_file = backup_dir / "backup_manifest.json"
    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print("\n" + "=" * 60)
    print("BACKUP COMPLETE")
    print("=" * 60)
    print(f"✅ Backup directory: {backup_dir}")
    print(f"✅ Manifest: {manifest_file}")
    print(f"✅ Files backed up: {len(manifest['backed_up_files'])}")
    if manifest["errors"]:
        print(f"⚠️  Errors: {len(manifest['errors'])}")
        for error in manifest["errors"]:
            print(f"   - {error}")
    
    return backup_dir, manifest


if __name__ == "__main__":
    backup_dir, manifest = backup_all_scripts()
    print(f"\n📦 Backup ready for migration")
    print(f"   Location: {backup_dir}")


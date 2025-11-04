#!/usr/bin/env python3
"""
Organize Files - Moves files into "Live and migrated to GitHub" and "Historical Artifact" folders
Organizes all files in Final Python Scripts directory based on live vs historical status
"""

import shutil
from pathlib import Path
from datetime import datetime
import json


# Live files - scripts and related files that are actively used
LIVE_SCRIPTS = [
    # Main scripts
    "SnapshotSummary.py",
    "TrailingProfServ.py",
    "pipev3.py",
    "BocaSalesMotion2.py",
    "Salesforce_flow_slack_metrics.py",
    "dealSizeWinRate.py",
    "highlevel_upgraded.py",
    "elite_pipeline_analysis.py",
    "highlevel_clean.py",
    
    # Helper/utility scripts
    "html_template_base.py",
    "run_velocity_migration.py",
    "run_executive_dashboard.py",
    "backfill_json_history.py",
]

# Live configuration and documentation files
LIVE_CONFIG_FILES = [
    ".gitignore",
    "requirements.txt",
    "sf_config.py.example",
    "sf_config_helper.py",
]

# Live documentation files
LIVE_DOCS = [
    "MIGRATION_PLAN.md",
    "VELOCITY_MIGRATION_GUIDE.md",
    "QUICK_START.md",
    "GITHUB_ACTIONS_AUTH_SETUP.md",
    "GITHUB_ACTIONS_SETUP.md",
    "GITHUB_SECRETS_EXACT_FIELDS.md",
    "GITHUB_SECRETS_SECURITY.md",
    "GITHUB_SECRETS_ENTRY_GUIDE.md",
    "GITHUB_SECRETS_FINAL_CHECK.md",
    "GITHUB_PAGES_URLS.md",
    "JWT_SETUP_GUIDE.md",
    "JWT_SECURITY_SUMMARY.md",
    "PROJECT_SUMMARY.md",
]

# Live output files (HTML dashboards and JSON history)
LIVE_OUTPUT_PATTERNS = [
    "*_latest.html",
    "*_history.json",
    "exec_pipeline_dashboard*.html",
    "flow_slack_metrics*.html",  # Flow metrics HTML files
]

# GitHub Actions workflow files
LIVE_WORKFLOWS = [
    ".github/workflows/run_scripts.yml",
]

# Files/folders to keep in root (not move)
KEEP_IN_ROOT = [
    ".git",
    ".github",
    "Live and migrated to GitHub",
    "Historical Artifact",
    "organize_files.py",  # Keep this script in root so it can be run
    "run_full_migration.py",  # Keep migration scripts in root
    "backup_all_scripts.py",
]

# Additional files that should go to Historical (old/deprecated)
HISTORICAL_PATTERNS = [
    "BocaLive.py",
    "BocaSalesMotion.py",  # Old version before BocaSalesMotion2
    "CriticalMetrics*.py",  # All CriticalMetrics variants
    "TheDaily*.py",
    "complete_pipeline_analysis.py",
    "critical3.py",
    "detailed_discrepancy_analysis.py",
    "diagnose_pipeline_discrepancy.py",
    "highlevel.py",  # Old version before highlevel_upgraded
    "investigate_remaining_discrepancy.py",
    "merge*.py",
    "pipeline_analysis_viewer.py",
    "report_based_analysis.py",
    "stagefixavg.py",
    "test_*.py",
    "trailingProfServ.py",  # Old version (TrailingProfServ.py is live)
    "ultimate2.py",
    "upload_to_github.py",
    "organize_for_github.py",
    "config.py",  # Old config
    "config_utils.py",
    "logging_config.py",
    "security.py",
    "sf_utils.py",
    "date_utils.py",
    "correct_query_match_sfdc.py",
]


def should_be_live(file_path):
    """Determine if a file should be in Live folder"""
    file_name = file_path.name
    
    # Check if it's a live script
    if file_name in LIVE_SCRIPTS:
        return True
    
    # Check if it's a live config file
    if file_name in LIVE_CONFIG_FILES:
        return True
    
    # Check if it's a live documentation file
    if file_name in LIVE_DOCS:
        return True
    
    # Check if it matches output patterns
    for pattern in LIVE_OUTPUT_PATTERNS:
        if file_path.match(pattern):
            return True
    
    # Check if it's a workflow file
    if ".github" in str(file_path.parts):
        return True
    
    return False


def should_be_historical(file_path):
    """Determine if a file should be in Historical Artifact folder"""
    file_name = file_path.name
    
    # Original/backup files
    if "_original.py" in file_name:
        return True
    
    # Backup directories
    if file_name.startswith("backups_"):
        return True
    
    # Migration reports
    if file_name.startswith("migration_report_") or file_name.startswith("organization_manifest_"):
        return True
    
    # Old/deprecated folders
    if file_name in ["Not Main Verson", "Not Main Version", "I"]:
        return True
    
    # Check against historical patterns
    for pattern in HISTORICAL_PATTERNS:
        if pattern.endswith(".py"):
            if file_name == pattern or file_name.startswith(pattern.replace("*.py", "")):
                return True
        elif "*" in pattern:
            import fnmatch
            if fnmatch.fnmatch(file_name, pattern):
                return True
        elif file_name == pattern:
            return True
    
    # Old HTML files (timestamped versions, not _latest)
    if file_name.endswith(".html") and "_latest.html" not in file_name:
        # Check if it's a timestamped version
        if any(char.isdigit() for char in file_name) and "(" in file_name:
            return True
    
    # Old markdown documentation not in LIVE_DOCS
    if file_name.endswith(".md") and file_name not in LIVE_DOCS:
        return True
    
    # Any other Python files not in LIVE_SCRIPTS
    if file_path.suffix == ".py" and file_name not in LIVE_SCRIPTS and file_name not in KEEP_IN_ROOT:
        return True
    
    # Any other files not in live lists and not in keep list
    if not should_be_live(file_path) and file_name not in KEEP_IN_ROOT:
        return True
    
    return False


def organize_files():
    """Organize all files into Live and Historical folders"""
    script_dir = Path(__file__).parent
    
    # Create target folders
    live_dir = script_dir / "Live and migrated to GitHub"
    historical_dir = script_dir / "Historical Artifact"
    
    live_dir.mkdir(exist_ok=True)
    historical_dir.mkdir(exist_ok=True)
    
    print("=" * 60)
    print("ORGANIZING FILES")
    print("=" * 60)
    print(f"\nSource: {script_dir}")
    print(f"Live folder: {live_dir}")
    print(f"Historical folder: {historical_dir}")
    print("\nStarting organization...\n")
    
    manifest = {
        "timestamp": datetime.now().isoformat(),
        "moved_to_live": [],
        "moved_to_historical": [],
        "kept_in_root": [],
        "errors": []
    }
    
    # Process all files and directories in root
    items = list(script_dir.iterdir())
    
    for item in items:
        # Skip if it's a target folder or should stay in root
        if item.name in KEEP_IN_ROOT:
            manifest["kept_in_root"].append(str(item))
            continue
        
        # Skip if it's a hidden file/directory (except .gitignore, .github)
        if item.name.startswith(".") and item.name not in [".gitignore", ".github"]:
            continue
        
        try:
            if item.is_file():
                if should_be_live(item):
                    # Move to Live folder
                    dest = live_dir / item.name
                    if dest.exists():
                        # Add timestamp to avoid conflicts
                        stem = item.stem
                        suffix = item.suffix
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        dest = live_dir / f"{stem}_{timestamp}{suffix}"
                    
                    # Move to Live folder
                    shutil.move(str(item), str(dest))
                    print(f"✅ {item.name} → Live")
                    manifest["moved_to_live"].append({
                        "source": str(item),
                        "destination": str(dest)
                    })
                    
                elif should_be_historical(item):
                    # Move to Historical folder
                    dest = historical_dir / item.name
                    if dest.exists():
                        # Add timestamp to avoid conflicts
                        stem = item.stem
                        suffix = item.suffix
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        dest = historical_dir / f"{stem}_{timestamp}{suffix}"
                    
                    shutil.move(str(item), str(dest))
                    print(f"📦 {item.name} → Historical")
                    manifest["moved_to_historical"].append({
                        "source": str(item),
                        "destination": str(dest)
                    })
                else:
                    # Keep in root (not sure where it belongs)
                    manifest["kept_in_root"].append(str(item))
                    print(f"⚠️  {item.name} → Kept in root (not categorized)")
            
            elif item.is_dir():
                # Handle directories
                if should_be_historical(item):
                    dest = historical_dir / item.name
                    if dest.exists():
                        dest = historical_dir / f"{item.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    
                    shutil.move(str(item), str(dest))
                    print(f"📦 {item.name}/ → Historical")
                    manifest["moved_to_historical"].append({
                        "source": str(item),
                        "destination": str(dest)
                    })
                else:
                    manifest["kept_in_root"].append(str(item))
                    print(f"⚠️  {item.name}/ → Kept in root (not categorized)")
        
        except Exception as e:
            error_msg = f"Error processing {item.name}: {e}"
            print(f"❌ {error_msg}")
            manifest["errors"].append(error_msg)
    
    # Save manifest
    manifest_file = script_dir / f"organization_manifest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    # Summary
    print("\n" + "=" * 60)
    print("ORGANIZATION COMPLETE")
    print("=" * 60)
    print(f"\n✅ Moved to Live: {len(manifest['moved_to_live'])} files")
    print(f"📦 Moved to Historical: {len(manifest['moved_to_historical'])} items")
    print(f"⚠️  Kept in root: {len(manifest['kept_in_root'])} items")
    if manifest["errors"]:
        print(f"❌ Errors: {len(manifest['errors'])}")
        for error in manifest["errors"]:
            print(f"   - {error}")
    print(f"\n📄 Manifest: {manifest_file}")
    
    return manifest


if __name__ == "__main__":
    import sys
    
    print("\n⚠️  WARNING: This will organize files into Live and Historical folders")
    print("   Original files will be moved (backup recommended first)")
    print("\n   Press Ctrl+C to cancel, or Enter to continue...")
    
    try:
        input()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
        sys.exit(0)
    
    manifest = organize_files()
    print("\n✅ Organization complete!")


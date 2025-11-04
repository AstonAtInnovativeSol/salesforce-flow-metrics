#!/usr/bin/env python3
"""
Executive Dashboard Workflow - Runs all 3 executive scripts in sequence
Combines outputs into single exec_pipeline_dashboard - PoC.html

Workflow:
1. highlevel_upgraded.py
2. elite_pipeline_analysis.py
3. highlevel_clean.py
4. Combine outputs → exec_pipeline_dashboard - PoC.html
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime
import json


def run_script(script_name, description):
    """Run a Python script and return success status"""
    print("\n" + "=" * 60)
    print(f"STEP: {description}")
    print("=" * 60)
    
    script_dir = Path(__file__).parent
    script_path = script_dir / script_name
    
    if not script_path.exists():
        print(f"❌ Error: {script_name} not found at {script_path}")
        return False
    
    try:
        print(f"Running: {script_name}")
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(script_dir),
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


def combine_dashboards():
    """Combine outputs from all 3 executive scripts into single dashboard"""
    print("\n" + "=" * 60)
    print("COMBINING DASHBOARDS")
    print("=" * 60)
    
    script_dir = Path(__file__).parent
    
    # Look for output files from each script
    # Note: These filenames may need to be adjusted based on actual output
    output_files = {
        "highlevel_upgraded": script_dir.glob("**/highlevel_upgraded*.html"),
        "elite_pipeline": script_dir.glob("**/elite_pipeline*.html"),
        "highlevel_clean": script_dir.glob("**/highlevel_clean*.html")
    }
    
    # Find the most recent output from each script
    found_files = {}
    for script_name, pattern in output_files.items():
        files = list(pattern)
        if files:
            # Get most recent file
            most_recent = max(files, key=lambda p: p.stat().st_mtime)
            found_files[script_name] = most_recent
            print(f"  ✅ Found {script_name}: {most_recent.name}")
        else:
            print(f"  ⚠️  No output found for {script_name}")
    
    # For now, if highlevel_clean.py outputs the final dashboard, use that
    # Otherwise, we'll need to implement a proper merge function
    if "highlevel_clean" in found_files:
        source_file = found_files["highlevel_clean"]
        output_file = script_dir / "exec_pipeline_dashboard - PoC.html"
        
        try:
            # Copy or rename the file
            import shutil
            shutil.copy2(source_file, output_file)
            print(f"\n✅ Combined dashboard saved: {output_file}")
            return True
        except Exception as e:
            print(f"\n❌ Error combining dashboards: {e}")
            return False
    else:
        print("\n⚠️  Warning: Could not find output from highlevel_clean.py")
        print("   You may need to manually combine the outputs")
        return False


def main():
    """Run the complete executive dashboard workflow"""
    print("=" * 60)
    print("EXECUTIVE DASHBOARD WORKFLOW")
    print("=" * 60)
    print("\nThis workflow will:")
    print("  1. Run highlevel_upgraded.py")
    print("  2. Run elite_pipeline_analysis.py")
    print("  3. Run highlevel_clean.py")
    print("  4. Combine outputs → exec_pipeline_dashboard - PoC.html")
    print("\nStarting...")
    
    success_count = 0
    total_steps = 3
    
    # Step 1: highlevel_upgraded.py
    if run_script("highlevel_upgraded.py", "High-Level Upgraded Dashboard"):
        success_count += 1
    
    # Step 2: elite_pipeline_analysis.py
    if run_script("elite_pipeline_analysis.py", "Elite Pipeline Analysis"):
        success_count += 1
    
    # Step 3: highlevel_clean.py
    if run_script("highlevel_clean.py", "High-Level Clean Dashboard"):
        success_count += 1
    
    # Step 4: Combine outputs
    if success_count == total_steps:
        combine_dashboards()
    
    # Summary
    print("\n" + "=" * 60)
    print("WORKFLOW SUMMARY")
    print("=" * 60)
    print(f"✅ Successful: {success_count}/{total_steps}")
    
    if success_count == total_steps:
        print("\n🎉 Executive dashboard workflow completed successfully!")
        print("\n📊 Output File:")
        script_dir = Path(__file__).parent
        output_file = script_dir / "exec_pipeline_dashboard - PoC.html"
        if output_file.exists():
            print(f"   ✅ {output_file}")
            print(f"\n🌐 GitHub Pages URL:")
            print(f"   https://AstonAtInnovativeSol.github.io/salesforce-flow-metrics/exec_pipeline_dashboard - PoC.html")
        else:
            print(f"   ⚠️  Output file not found at expected location")
            print(f"   Check individual script outputs for generated files")
    else:
        print(f"\n⚠️  {total_steps - success_count} step(s) failed. Check output above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()


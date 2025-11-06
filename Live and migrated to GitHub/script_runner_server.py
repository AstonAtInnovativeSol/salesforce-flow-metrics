#!/usr/bin/env python3
"""
Flask Server for Running Python Scripts from Web Interface
This server executes Python scripts when called from the HTML dashboard.

Usage:
    python3 script_runner_server.py

The server will run on http://localhost:5000
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import os
import sys
from pathlib import Path

app = Flask(__name__)
CORS(app)  # Enable CORS for local development

# Script paths
SCRIPT_DIR = Path(__file__).parent
SNAPSHOT_SCRIPT = SCRIPT_DIR / "SnapshotSummary.py"
TRAILING_SCRIPT = SCRIPT_DIR / "trailingProfServ.py"

@app.route('/run-script', methods=['POST'])
def run_script():
    """Execute a Python script based on the request"""
    try:
        data = request.get_json()
        script_name = data.get('script')
        
        if not script_name:
            return jsonify({'success': False, 'error': 'No script name provided'}), 400
        
        # Map script names to actual file paths
        script_map = {
            'snapshot-summary': SNAPSHOT_SCRIPT,
            'trailing-6': TRAILING_SCRIPT,
        }
        
        if script_name not in script_map:
            return jsonify({'success': False, 'error': f'Unknown script: {script_name}'}), 400
        
        script_path = script_map[script_name]
        
        if not script_path.exists():
            return jsonify({
                'success': False, 
                'error': f'Script not found: {script_path}'
            }), 404
        
        # Execute the script
        print(f"\n{'='*60}")
        print(f"Executing: {script_path.name}")
        print(f"{'='*60}\n")
        
        # Change to script directory to ensure relative imports work
        original_cwd = os.getcwd()
        os.chdir(SCRIPT_DIR)
        
        try:
            # Run the script and capture output
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            # Restore original working directory
            os.chdir(original_cwd)
            
            if result.returncode == 0:
                output = result.stdout
                print(output)
                return jsonify({
                    'success': True,
                    'message': f'{script_path.name} completed successfully',
                    'output': output
                })
            else:
                error_output = result.stderr or result.stdout
                print(f"Error output:\n{error_output}")
                return jsonify({
                    'success': False,
                    'error': f'Script execution failed with return code {result.returncode}',
                    'output': error_output
                }), 500
                
        except subprocess.TimeoutExpired:
            os.chdir(original_cwd)
            return jsonify({
                'success': False,
                'error': 'Script execution timed out (5 minutes)'
            }), 500
            
        except Exception as e:
            os.chdir(original_cwd)
            return jsonify({
                'success': False,
                'error': f'Error executing script: {str(e)}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'scripts': {
            'snapshot-summary': SNAPSHOT_SCRIPT.exists(),
            'trailing-6': TRAILING_SCRIPT.exists(),
        }
    })

@app.route('/', methods=['GET'])
def index():
    """Root endpoint with instructions"""
    return jsonify({
        'message': 'Script Runner Server',
        'endpoints': {
            'POST /run-script': 'Execute a Python script',
            'GET /health': 'Check server and script status',
        },
        'available_scripts': {
            'snapshot-summary': str(SNAPSHOT_SCRIPT),
            'trailing-6': str(TRAILING_SCRIPT),
        }
    })

if __name__ == '__main__':
    import sys
    
    # Check if running in background (no TTY)
    is_background = not sys.stdout.isatty()
    
    if not is_background:
        print("\n" + "="*60)
        print("Script Runner Server")
        print("="*60)
        print(f"\nServer starting on http://localhost:5000")
        print(f"Script directory: {SCRIPT_DIR}")
        print(f"\nAvailable scripts:")
        print(f"  - Snapshot Summary: {SNAPSHOT_SCRIPT.exists() and '✓' or '✗'} {SNAPSHOT_SCRIPT}")
        print(f"  - Trailing 6 Week: {TRAILING_SCRIPT.exists() and '✓' or '✗'} {TRAILING_SCRIPT}")
        print("\nPress Ctrl+C to stop the server\n")
    
    # Disable debug mode when running in background (no auto-reload)
    app.run(host='localhost', port=5000, debug=not is_background, use_reloader=False)


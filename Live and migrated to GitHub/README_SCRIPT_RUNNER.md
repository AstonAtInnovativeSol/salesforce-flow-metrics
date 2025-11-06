# Script Runner Server

This Flask server allows you to execute Python scripts directly from the Sales Ops Analytics dashboard.

## Quick Start

### Option 1: Run in Background (Recommended)

**Start the server:**
```bash
cd "/Users/afleming/Desktop/Final Python Scripts/Live and migrated to GitHub"
./start_script_server.sh
```

**Stop the server:**
```bash
./stop_script_server.sh
```

**Check if server is running:**
```bash
./check_script_server.sh
```

**View server logs:**
```bash
tail -f script_server.log
```

### Option 2: Run in Foreground (for debugging)

```bash
cd "/Users/afleming/Desktop/Final Python Scripts/Live and migrated to GitHub"
python3 script_runner_server.py
```

Press `Ctrl+C` to stop.

## Setup

1. **Install Flask and Flask-CORS** (if not already installed):
   ```bash
   pip3 install flask flask-cors
   ```

2. **Make scripts executable** (first time only):
   ```bash
   chmod +x start_script_server.sh stop_script_server.sh check_script_server.sh
   ```

## Available Scripts

- **Snapshot Summary**: Runs `SnapshotSummary.py` - Syncs data from `Daily_Total_Pipeline__c` to `Pipeline_Snapshot_Summary__c`
- **Trailing 6 Week**: Runs `trailingProfServ.py` - Syncs opportunities to `Weekly_Pipeline_Summary__c`

## How It Works

1. Start the server using `./start_script_server.sh` (runs in background)
2. Open the dashboard (`index.html`) in your browser
3. Click a script button in the dashboard
4. The browser sends a POST request to `http://localhost:5000/run-script`
5. The Flask server executes the Python script
6. Results are returned to the browser and displayed

## Benefits of Background Mode

- ✅ **Use your terminal freely** - Server runs in background, you can run other commands
- ✅ **Persistent** - Server stays running until you explicitly stop it
- ✅ **Easy management** - Simple start/stop/check commands
- ✅ **Logs** - All output saved to `script_server.log`

## Troubleshooting

- **Connection Error**: Make sure the Flask server is running (`./check_script_server.sh`)
- **Script Not Found**: Verify the script files are in the same directory
- **Import Errors**: Ensure all required Python packages are installed (pandas, simple-salesforce, etc.)
- **Authentication Errors**: Make sure `sf_config.py` is properly configured with your Salesforce credentials
- **Port Already in Use**: Another process may be using port 5000. Stop it or change the port in `script_runner_server.py`

## Security Note

This server is designed for **local use only**. Do not expose it to the internet without proper security measures.

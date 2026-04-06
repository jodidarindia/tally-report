# Tally Desktop Sync Agent

A lightweight Windows desktop agent that syncs your local TallyPrime data to the cloud, enabling remote access from anywhere.

## Architecture

```
TallyPrime (Local)  →  Desktop Sync Agent  →  Cloud Backend  →  Web App (Remote Access)
   Port 9000            Windows Service         API Endpoints      Accessible Anywhere
```

## Features

✅ **Automatic Sync**: Syncs data every 10 minutes (configurable)
✅ **Real-time Updates**: Dashboard auto-refreshes with latest data
✅ **Secure Connection**: Uses API key authentication
✅ **Lightweight**: Minimal CPU and memory usage
✅ **Error Handling**: Automatic retry on connection failures
✅ **Logging**: Complete audit trail in log files

## Prerequisites

1. **TallyPrime** installed and running on Windows
2. **Python 3.11+** installed ([Download](https://www.python.org/downloads/))
3. TallyPrime configured to allow API access (port 9000)

## Installation

### Step 1: Configure TallyPrime

1. Open TallyPrime
2. Go to: `Gateway of Tally → F12: Configure → Connectivity`
3. Enable: `Use Tally as Server`
4. Set Port: `9000` (default)
5. Save configuration

### Step 2: Install Desktop Agent

1. **Download** the `desktop-agent` folder to your Windows machine

2. **Install Python dependencies:**
   ```bash
   cd desktop-agent
   pip install -r requirements.txt
   ```

3. **Configure the agent:**
   ```bash
   # Copy example config
   copy .env.example .env
   
   # Edit .env file with your settings
   notepad .env
   ```

4. **Update `.env` file:**
   ```ini
   TALLY_HOST=localhost
   TALLY_PORT=9000
   BACKEND_URL=https://your-app-url.com
   AGENT_API_KEY=generate-secure-key-here
   SYNC_INTERVAL_MINUTES=10
   ```

### Step 3: Run the Agent

**Option A: Run Manually (for testing)**
```bash
python tally_sync_agent.py
```

**Option B: Install as Windows Service (recommended)**
```bash
# Install NSSM (Non-Sucking Service Manager)
# Download from: https://nssm.cc/download

# Install service
nssm install TallySyncAgent "C:\Python311\python.exe" "C:\path\to\tally_sync_agent.py"
nssm set TallySyncAgent AppDirectory "C:\path\to\desktop-agent"
nssm set TallySyncAgent DisplayName "Tally Sync Agent"
nssm set TallySyncAgent Description "Syncs TallyPrime data to cloud backend"
nssm set TallySyncAgent Start SERVICE_AUTO_START

# Start service
nssm start TallySyncAgent
```

**Option C: Run on Windows Startup**
```bash
# Create a shortcut to run_agent.bat
# Place it in: C:\Users\YourName\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup
```

## Usage

### Monitor Sync Status

1. Check the log file: `tally_sync_agent.log`
2. Or monitor real-time:
   ```bash
   tail -f tally_sync_agent.log
   ```

### Web Dashboard

1. Open your web app: `https://your-app-url.com`
2. Check connection status (green badge = connected)
3. View last sync time on dashboard
4. Data auto-refreshes every sync cycle

### Troubleshooting

**Agent can't connect to Tally:**
- Ensure TallyPrime is running
- Verify port 9000 is not blocked by firewall
- Check TallyPrime connectivity settings

**Agent can't connect to backend:**
- Verify BACKEND_URL in .env file
- Check internet connection
- Ensure AGENT_API_KEY matches backend configuration

**No data appearing in web app:**
- Check sync logs for errors
- Verify company is loaded in Tally
- Ensure Tally has actual data (inventory/sales)

## Configuration

### Change Sync Interval

Edit `.env` file:
```ini
SYNC_INTERVAL_MINUTES=5  # Sync every 5 minutes
```

### Change Tally Port

If Tally uses a different port:
```ini
TALLY_PORT=9001
```

### Enable Debug Logging

Edit `tally_sync_agent.py`:
```python
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO to DEBUG
    ...
)
```

## Security Best Practices

1. **Generate Strong Agent Key:**
   ```python
   import secrets
   print(secrets.token_urlsafe(32))
   ```

2. **Firewall Rules:**
   - Allow outbound HTTPS (443) for backend communication
   - Allow local port 9000 for Tally connection

3. **Keep Agent Updated:**
   - Regularly update Python and dependencies
   - Monitor security advisories

## Building Standalone Executable

To create a standalone .exe file:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed tally_sync_agent.py
```

The executable will be in `dist/tally_sync_agent.exe`

## Support

For issues or questions:
- Check logs: `tally_sync_agent.log`
- View backend logs in web app
- Contact support with log files

## License

MIT License - Free to use and modify

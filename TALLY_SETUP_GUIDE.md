# Complete Tally Integration Setup Guide

This guide explains how to connect your local TallyPrime installation to the cloud-based Tally SaaS Report Builder for remote access.

## Overview

**Problem**: TallyPrime runs locally on your Windows machine, but you need to access reports from anywhere.

**Solution**: Desktop Sync Agent bridges local Tally with cloud app.

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────┐     ┌──────────────┐
│  TallyPrime  │────▶│ Desktop Agent   │────▶│ Cloud Backend│────▶│   Web App    │
│   (Local)    │     │ (Your Windows)  │     │    (API)     │     │ (Anywhere)   │
│  Port 9000   │     │  Auto-sync 10m  │     │   MongoDB    │     │  Dashboard   │
└──────────────┘     └─────────────────┘     └──────────────┘     └──────────────┘
```

## Prerequisites

✅ **Windows Machine** with TallyPrime installed  
✅ **TallyPrime License** (Standard or higher)  
✅ **Python 3.11+** ([Download here](https://www.python.org/downloads/))  
✅ **Internet Connection** for syncing to cloud  
✅ **Administrator Access** (for service installation)  

---

## Part 1: Configure TallyPrime

### Step 1: Enable API Access

1. Open **TallyPrime**
2. Navigate to: `Gateway of Tally → F12 (Configure)`
3. Go to: `Advanced Configuration → Connectivity`
4. Enable these settings:
   ```
   ☑ Use Tally as Server
   Port: 9000 (default)
   ☑ Enable XML/HTTP API
   ```
5. Save and restart TallyPrime

### Step 2: Load Your Company

- Ensure your company is loaded in Tally
- The agent will sync data from the currently loaded company
- Multi-company support: Load different companies as needed

### Step 3: Verify API is Working

Open Command Prompt and test:
```cmd
curl http://localhost:9000
```

If you get a response, API is working! ✓

---

## Part 2: Install Desktop Sync Agent

### Step 1: Download Agent

Download the `desktop-agent` folder from your project to:
```
C:\TallySync\
```

### Step 2: Install Python Dependencies

Open Command Prompt in the agent folder:
```cmd
cd C:\TallySync\desktop-agent
pip install -r requirements.txt
```

You should see:
```
Successfully installed requests-2.31.0 xmltodict-1.0.4 python-dotenv-1.0.1 schedule-1.2.0
```

### Step 3: Configure Agent

1. Copy the example config:
   ```cmd
   copy .env.example .env
   ```

2. Edit `.env` file (use Notepad):
   ```cmd
   notepad .env
   ```

3. Update with your settings:
   ```ini
   # Tally Connection
   TALLY_HOST=localhost
   TALLY_PORT=9000
   
   # Your Cloud App URL (IMPORTANT!)
   BACKEND_URL=https://tally-report-ai.preview.emergentagent.com
   
   # Generate a secure key (instructions below)
   AGENT_API_KEY=your-secure-key-here
   
   # Sync every 10 minutes
   SYNC_INTERVAL_MINUTES=10
   ```

### Step 4: Generate Secure Agent Key

Run this in Python:
```python
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the output and paste it as `AGENT_API_KEY` in `.env`

Example output: `xK3mP9QzL7nR2wYvF5jH8cT4bN6sA1dE0gU7xZ9mW`

---

## Part 3: Run the Agent

### Option A: Manual Run (For Testing)

```cmd
cd C:\TallySync\desktop-agent
python tally_sync_agent.py
```

You should see:
```
╔════════════════════════════════════════════════╗
║     TALLY DESKTOP SYNC AGENT STARTED          ║
╚════════════════════════════════════════════════╝

✓ Connected to TallyPrime successfully
Fetching inventory data...
Fetched 25 inventory items from Tally
✓ Synced 25 inventory items to backend
Fetching sales data...
Fetched 150 sales vouchers from Tally
✓ Synced 150 sales vouchers to backend
✓ Sync cycle completed at 2026-06-04 10:30:00

Agent running. Syncing every 10 minutes...
Press Ctrl+C to stop.
```

### Option B: Run on Startup (Recommended)

Create a shortcut to `run_agent.bat` and place it in:
```
C:\Users\YourName\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup
```

Now the agent will start automatically when Windows boots!

### Option C: Install as Windows Service (Advanced)

For production use, install as a background service:

1. Download NSSM (Non-Sucking Service Manager):
   - Visit: https://nssm.cc/download
   - Download and extract to `C:\NSSM`

2. Open Command Prompt as Administrator:
   ```cmd
   cd C:\NSSM\win64
   
   nssm install TallySyncAgent "C:\Python311\python.exe" "C:\TallySync\desktop-agent\tally_sync_agent.py"
   
   nssm set TallySyncAgent AppDirectory "C:\TallySync\desktop-agent"
   nssm set TallySyncAgent DisplayName "Tally Desktop Sync Agent"
   nssm set TallySyncAgent Description "Syncs TallyPrime data to cloud backend every 10 minutes"
   nssm set TallySyncAgent Start SERVICE_AUTO_START
   
   nssm start TallySyncAgent
   ```

3. Verify service is running:
   ```cmd
   nssm status TallySyncAgent
   ```

---

## Part 4: Verify Integration

### Check Desktop Agent

1. Open the log file:
   ```
   C:\TallySync\desktop-agent\tally_sync_agent.log
   ```

2. Look for successful sync messages:
   ```
   ✓ Connected to TallyPrime successfully
   ✓ Synced 25 inventory items to backend
   ✓ Synced 150 sales vouchers to backend
   ```

### Check Web Dashboard

1. Open your web app: https://tally-report-ai.preview.emergentagent.com

2. Verify:
   - Connection status shows **"Connected"** (green badge)
   - Dashboard displays your actual Tally data
   - Last sync time is visible
   - Auto-refresh is enabled

3. Test features:
   - View inventory items
   - Check sales reports
   - Generate AI reports
   - Export to PDF/Excel/CSV

---

## Part 5: Troubleshooting

### Agent Can't Connect to Tally

**Error**: `Cannot connect to TallyPrime`

**Solutions**:
1. Ensure TallyPrime is running
2. Check port 9000 is accessible:
   ```cmd
   netstat -an | find "9000"
   ```
3. Verify Tally connectivity settings
4. Disable Windows Firewall temporarily to test
5. If using antivirus, whitelist port 9000

### Agent Can't Connect to Backend

**Error**: `Failed to sync inventory: HTTP 404/500`

**Solutions**:
1. Verify `BACKEND_URL` in `.env` is correct
2. Check internet connection
3. Test backend URL in browser:
   ```
   https://tally-report-ai.preview.emergentagent.com/api/tally/status
   ```
4. Ensure backend is running (check supervisor status)

### No Data in Web App

**Error**: Dashboard shows zero items

**Solutions**:
1. Check agent logs for sync errors
2. Verify company is loaded in Tally
3. Ensure Tally has actual data (not empty company)
4. Check MongoDB connection in backend logs
5. Manually trigger sync from dashboard

### Sync is Slow

**Issue**: Takes too long to sync

**Solutions**:
1. Reduce data volume: sync only recent sales (last 3 months)
2. Increase sync interval to 15-30 minutes
3. Check network bandwidth
4. Optimize Tally database (run Tally's Rewrite function)

---

## Part 6: Maintenance

### Update Sync Interval

Edit `.env`:
```ini
SYNC_INTERVAL_MINUTES=15  # Change from 10 to 15 minutes
```

Restart agent.

### View Logs

Real-time monitoring:
```cmd
tail -f C:\TallySync\desktop-agent\tally_sync_agent.log
```

Or open in Notepad for easier reading.

### Backup Configuration

Backup these files:
- `.env` (your configuration)
- `tally_sync_agent.log` (troubleshooting)

### Update Agent

When new version is released:
```cmd
cd C:\TallySync\desktop-agent
git pull  # If using git
# Or download new files and replace
```

---

## Part 7: Security Best Practices

### 1. Secure Agent Key

- Use minimum 32-character random key
- Never share or commit to version control
- Rotate key every 90 days

### 2. Firewall Configuration

Windows Firewall rules:
```cmd
# Allow outbound HTTPS to backend
netsh advfirewall firewall add rule name="Tally Agent HTTPS" dir=out action=allow protocol=TCP remoteport=443

# Allow local Tally API
netsh advfirewall firewall add rule name="Tally API" dir=in action=allow protocol=TCP localport=9000
```

### 3. Network Security

- Use VPN if syncing over public WiFi
- Enable HTTPS only (disable HTTP)
- Monitor sync logs for suspicious activity

### 4. Access Control

- Limit who can access the Windows machine
- Use Windows password protection
- Lock screen when away

---

## Part 8: Advanced Configuration

### Multi-Company Support

To sync multiple Tally companies:

1. Run separate agent instances:
   ```
   C:\TallySync\Company1\
   C:\TallySync\Company2\
   ```

2. Configure each with different `AGENT_API_KEY`

3. Load respective company in Tally before syncing

### Custom Data Filtering

Edit `tally_sync_agent.py` to filter data:

```python
# Only sync sales from last 90 days
from datetime import datetime, timedelta

def fetch_sales_from_tally(self):
    # Add date filter in XML request
    cutoff_date = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')
    # Update XML to include date filter
```

### Performance Optimization

For large datasets (>10,000 records):

1. **Incremental Sync**: Only sync changed records
2. **Batch Processing**: Split data into smaller chunks
3. **Compression**: Enable gzip compression for API calls
4. **Database Indexing**: Add indexes on frequently queried fields

---

## Part 9: Monitoring & Alerts

### Email Notifications

Add email alerts for sync failures:

```python
import smtplib
from email.mime.text import MIMEText

def send_alert(subject, message):
    msg = MIMEText(message)
    msg['Subject'] = subject
    msg['From'] = 'agent@yourdomain.com'
    msg['To'] = 'admin@yourdomain.com'
    
    s = smtplib.SMTP('smtp.gmail.com', 587)
    s.starttls()
    s.login('your-email', 'your-password')
    s.send_message(msg)
    s.quit()
```

### Dashboard Monitoring

Check web dashboard for:
- Last sync timestamp
- Sync success rate
- Data freshness indicator
- Connection status

---

## FAQ

**Q: Can I run agent on a different machine than Tally?**  
A: Yes, if TallyPrime is on a network server. Update `TALLY_HOST` to server IP.

**Q: Does agent work with Tally ERP 9?**  
A: Yes! Same XML API is supported.

**Q: What happens if internet goes down?**  
A: Agent will retry syncing when connection is restored. Data is queued locally.

**Q: Can I sync to multiple cloud backends?**  
A: Yes, run multiple agent instances with different `BACKEND_URL` values.

**Q: How much bandwidth does syncing use?**  
A: Approximately 1-5 MB per sync cycle (depends on data size).

**Q: Is my Tally data secure during sync?**  
A: Yes, all communication is over HTTPS (encrypted). Data is never stored locally by agent.

---

## Support

For help:
1. Check logs: `tally_sync_agent.log`
2. Test Tally connection: `curl http://localhost:9000`
3. Test backend: Visit backend URL in browser
4. Review this guide's troubleshooting section
5. Contact support with log files attached

---

## Next Steps

Once sync is working:

✅ Explore AI Report Builder  
✅ Set up scheduled exports  
✅ Configure user access controls  
✅ Customize dashboard widgets  
✅ Enable mobile app access  

---

**Congratulations!** Your TallyPrime is now accessible from anywhere with real-time sync! 🎉

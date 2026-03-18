# Azure Deployment Guide for GST HSN Resolver

## Prerequisites

- Azure VM with Ubuntu 20.04 LTS or similar
- Public IP address assigned
- SSH access enabled
- Python 3.8+ installed (`python3 --version`)

## Step 1: SSH into Azure VM

```bash
# From your local machine
ssh azureuser@<PUBLIC_IP>
# Enter password or use SSH key

# Verify Python is installed
python3 --version
# Should output: Python 3.x.x
```

## Step 2: Clone Repository & Setup

```bash
# Navigate to home directory
cd ~

# Clone the repository
git clone https://github.com/ekthar/gst.git
cd gst

# (IMPORTANT) Verify you're in the repo root
pwd
# Should output: /home/azureuser/gst (or similar)

# Run the setup script
chmod +x setup_azure.sh
./setup_azure.sh

# Or manually:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Step 3: Fix Python Path (If Getting ModuleNotFoundError)

If you get `ModuleNotFoundError: No module named 'gst_hsn_tool'`, add src to Python path:

```bash
cd ~/gst
export PYTHONPATH="${PWD}/src:${PYTHONPATH}"
```

To make this permanent, add to `~/.bashrc`:

```bash
echo 'export PYTHONPATH="~/gst/src:${PYTHONPATH}"' >> ~/.bashrc
source ~/.bashrc
```

## Step 4: Start Web UI

### Option A: Interactive Mode (for testing)

```bash
cd ~/gst
source .venv/bin/activate
export PYTHONPATH="${PWD}/src:${PYTHONPATH}"

# Using the new launcher script (recommended)
python run_web_app.py --server.address 0.0.0.0 --server.port 8501

# Or using streamlit directly
python -m streamlit run src/gst_hsn_tool/web_app.py \
  --server.address 0.0.0.0 \
  --server.port 8501
```

You should see:
```
  You can now view your Streamlit app in your browser.

  URL: http://<PUBLIC_IP>:8501
```

### Option B: Background Mode (daemon)

```bash
cd ~/gst
source .venv/bin/activate
export PYTHONPATH="${PWD}/src:${PYTHONPATH}"

# Start in background
nohup python run_web_app.py --server.address 0.0.0.0 --server.port 8501 > web.log 2>&1 &

# Check status
ps aux | grep streamlit
# or
lsof -i :8501

# View logs
tail -f web.log

# Stop the process
kill $(lsof -t -i:8501)
```

## Step 5: Expose Port in Azure NSG

1. **Open Azure Portal** (https://portal.azure.com)

2. **Find your VM:**
   - Search for "Virtual machines"
   - Click on your VM name

3. **Open Networking:**
   - Left sidebar → "Networking"
   - Click tab "Inbound port rules"

4. **Add Inbound Rule:**
   - Click **"+ Add inbound port rule"** button
   
5. **Configure the rule:**
   ```
   Source:              IP Addresses
   Source IP/CIDR:      <YOUR_PUBLIC_IP>/32  (e.g., 1.2.3.4/32)
   Source port ranges:  *
   Destination:         Any  
   Destination port ranges: 8501
   Protocol:            TCP
   Action:              Allow
   Priority:            100
   Name:                Allow-Streamlit-8501
   ```

6. **Click "Add"**

## Step 6: Test Access

```bash
# On Azure VM
curl -I http://127.0.0.1:8501
# Should return: HTTP/1.1 200 OK

# On your local machine
curl -I http://<PUBLIC_IP>:8501
# Should return: HTTP/1.1 200 OK
```

## Step 7: Open in Browser

Open your browser and go to:
```
http://<PUBLIC_IP>:8501
```

You should see the GST HSN Resolver web UI with 6 tabs.

## Using the Web App

### Lookup Tab
1. Enter product name (e.g., "Cadbury Silk")
2. Click "Search"
3. View results (Category, HSN codes, match confidence)

### Bulk Upload Tab
1. Prepare Excel file with product names in Column A
2. Upload the file
3. Click "Run Lookup"
4. Wait for results
5. Download as CSV or Excel

### Database Tab
1. View all products in database
2. Search by product name
3. Delete products
4. Export as CSV

## Troubleshooting

### Port 8501 Connection Refused

```bash
# Check if port is listening
ss -ltnp | grep 8501
# or
lsof -i :8501

# If not listening, check logs
tail -20 web.log

# Restart the app
kill $(lsof -t -i:8501)
sleep 2
nohup python run_web_app.py --server.address 0.0.0.0 --server.port 8501 > web.log 2>&1 &
```

### ModuleNotFoundError: No module named 'gst_hsn_tool'

```bash
# Make sure you're in repo root
cd ~/gst
pwd  # Should end with /gst

# Set PYTHONPATH
export PYTHONPATH="${PWD}/src:${PYTHONPATH}"

# Try again
python -c "from gst_hsn_tool import db; print('OK')"
```

### Database is Locked

```bash
# Stop all instances
kill $(lsof -t -i:8501)

# Delete database (will be recreated)
rm -f data/db/gst_hsn.db

# Restart
nohup python run_web_app.py --server.address 0.0.0.0 --server.port 8501 > web.log 2>&1 &
```

### Google Search Returns 0 Results

```bash
# Check working directory and paths
python -c "from gst_hsn_tool import lookup; print(lookup._search_google_for_hsn('test product'))"

# If network issue, add delay in config
# Edit src/gst_hsn_tool/config.py and increase GOOGLE_LOOKUP_DELAY
```

### Out of Memory

If running on small VM:
```bash
# Monitor memory
free -h

# Reduce Streamlit cache and workers in config.py
# Or use smaller database queries (limit=100 instead of 1000)
```

## Managing the Service

### Check if Running
```bash
ps aux | grep streamlit
lsof -i :8501
```

### View Recent Logs
```bash
tail -50 web.log
tail -f web.log  # Follow in real-time
```

### Restart Service
```bash
# Kill
kill $(lsof -t -i:8501)

# Wait
sleep 2

# Start
cd ~/gst
source .venv/bin/activate
nohup python run_web_app.py --server.address 0.0.0.0 --server.port 8501 > web.log 2>&1 &
echo "✅ Started on http://<PUBLIC_IP>:8501"
```

### Auto-Start on Boot (Optional)

Create `/home/azureuser/start_gst.sh`:
```bash
#!/bin/bash
cd ~/gst
source .venv/bin/activate
export PYTHONPATH="${PWD}/src:${PYTHONPATH}"
nohup python run_web_app.py --server.address 0.0.0.0 --server.port 8501 > web.log 2>&1 &
```

Add to crontab:
```bash
crontab -e
# Add line:
# @reboot /home/azureuser/start_gst.sh
```

## Performance Tips

1. **Improve lookup speed:**
   - Pre-populate database with common products
   - Reduce `GOOGLE_SEARCH_TIMEOUT` in config

2. **Reduce memory usage:**
   - Limit database queries to 100-500 products
   - Disable unused tabs if not needed

3. **Improve Google search reliability:**
   - Increase `GOOGLE_LOOKUP_DELAY` (0.5-1.0 seconds)
   - Use VPN if Google is blocking requests

## Security

⚠️ **Important:** Port 8501 is exposed to the internet!

For production use:
1. **Restrict port to your IP only** (already done in NSG rule)
2. **Use Streamlit authentication** (requires paid Streamlit Cloud)
3. **Run behind Nginx reverse proxy** with authentication
4. **Use HTTPS** (requires SSL certificate)

Example Nginx config (advanced):
```nginx
upstream streamlit {
    server 127.0.0.1:8501;
}

server {
    listen 443 ssl;
    server_name yourdomain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        auth_basic "Restricted";
        auth_basic_user_file /etc/nginx/.htpasswd;
        
        proxy_pass http://streamlit;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Support

For issues:
1. Check logs: `tail -50 web.log`
2. Check GitHub issues: https://github.com/ekthar/gst/issues
3. Verify Python version: `python3 --version` (should be 3.8+)
4. Verify dependencies: `pip list | grep streamlit`

---

**Last Updated:** March 18, 2026
**For Issues:** https://github.com/ekthar/gst/issues

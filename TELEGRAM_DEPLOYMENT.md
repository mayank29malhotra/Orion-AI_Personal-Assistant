# Orion Telegram Bot - Free VM Deployment Guide

This guide helps you deploy Orion AI Assistant on a **FREE FOREVER VM** and access it via Telegram.

## 📋 Prerequisites

- Oracle Cloud account (Always Free tier - NO credit card charges!)
- Telegram account

---

## 🆓 Free Hosting Options Comparison

| Provider | Free Tier | Specs | Best For |
|----------|-----------|-------|----------|
| **Oracle Cloud** ✅ | **Forever Free** | 4 ARM cores, 24GB RAM | Best overall! |
| **Fly.io** | Forever Free | 3 shared VMs, 256MB each | Simple bots |
| **Render** | Forever Free | 750 hrs/month | Web services |
| **PythonAnywhere** | Forever Free | 1 web app, limited CPU | Basic bots |
| **Hugging Face Spaces** | Forever Free | 2 vCPU, 16GB RAM | Gradio apps! |
| **Home Raspberry Pi** | One-time ~$35 | Your own hardware | Full control |
| **Old Android Phone** | Free (Termux) | Reuse old phone! | Creative hack |
| Google Cloud | 90-day trial | ❌ Charges after | NOT free |
| AWS | 12-month trial | ❌ Charges after | NOT free |

---

## 🏆 Recommended Options (Ranked)

### 1️⃣ Oracle Cloud (BEST - Full VM)
- ✅ 4 ARM cores + 24GB RAM FREE
- ✅ Truly forever free
- ✅ Full Linux VM with root access
- ⚠️ Requires credit card for verification (never charged)

### 2️⃣ Fly.io (Easy Setup)
- ✅ 3 free VMs (shared CPU, 256MB RAM)
- ✅ Easy deployment with CLI
- ✅ Auto-scaling, global regions
- ⚠️ May need to add card for verification

### 3️⃣ Hugging Face Spaces (Best for Gradio)
- ✅ 2 vCPU + 16GB RAM FREE
- ✅ Perfect for Gradio web UI
- ✅ No credit card needed
- ⚠️ Sleeps after 48hrs inactivity (wakes on request)

### 4️⃣ Render (Simple Web Apps)  
- ✅ 750 free hours/month
- ✅ Auto-deploy from GitHub
- ⚠️ Sleeps after 15 min inactivity

### 5️⃣ Raspberry Pi / Old Phone (Self-Hosted)
- ✅ No monthly costs
- ✅ Full control, no limits
- ⚠️ Needs internet/power at home

---

## 🤖 Step 1: Create Your Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/start`
3. Send `/newbot`
4. Set a name (e.g., "My Orion Assistant")
5. Set a username (e.g., "my_orion_bot")
6. **Copy the BOT_TOKEN** - you'll need this!

### Get Your Telegram User ID

1. Search for **@userinfobot** on Telegram
2. Send `/start`
3. **Copy your User ID** (a number like `123456789`)

---

## ☁️ Step 2: Create Oracle Cloud VM (Always Free)

### 2.1 Create Oracle Cloud Account

1. Go to [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/)
2. Click **Start for Free**
3. Create account (credit card required for verification but **NEVER charged** for Always Free resources)
4. Select your home region (choose one close to you)

### 2.2 Create VM Instance

1. Go to **Compute** > **Instances** > **Create Instance**

**Settings for Always Free (ARM - Recommended):**
- **Name:** `orion-bot`
- **Image:** Ubuntu 22.04 (or Oracle Linux)
- **Shape:** Click **Change Shape** → **Ampere** → **VM.Standard.A1.Flex**
  - **OCPUs:** 2 (can use up to 4 free)
  - **Memory:** 12 GB (can use up to 24 GB free)
- **Boot volume:** 50 GB (up to 200 GB free)
- **Add SSH keys:** Generate or upload your SSH key

**Alternative - AMD Shape (if ARM unavailable):**
- **Shape:** VM.Standard.E2.1.Micro (1 OCPU, 1 GB RAM)

### 2.3 Download SSH Key & Note Public IP

1. Download the private key (`.key` file)
2. Note the **Public IP Address** from instance details

### 2.4 Connect to VM

```bash
# Linux/Mac
chmod 400 ~/Downloads/ssh-key.key
ssh -i ~/Downloads/ssh-key.key ubuntu@YOUR_PUBLIC_IP

# Windows (PowerShell)
ssh -i C:\Users\YOU\Downloads\ssh-key.key ubuntu@YOUR_PUBLIC_IP
```

---

## 🔧 Step 3: Setup VM Environment

### 3.1 Update System & Install Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11+
sudo apt install -y python3.11 python3.11-venv python3-pip git

# Install system dependencies for Playwright
sudo apt install -y libnss3 libxss1 libasound2 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2

# Install Tesseract OCR
sudo apt install -y tesseract-ocr
```

### 3.2 Clone Your Project

```bash
cd ~
git clone YOUR_REPO_URL orion
cd orion
```

Or upload files via SCP:
```bash
# From your local machine
scp -i ~/Downloads/ssh-key.key -r ./Orion ubuntu@YOUR_PUBLIC_IP:~/orion
```

### 3.3 Create Virtual Environment

```bash
cd ~/orion
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 3.4 Configure Environment Variables

Create `.env` file:
```bash
nano .env
```

Add your configuration:
```env
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_ALLOWED_USER_ID=your_telegram_user_id

# AI APIs
GROQ_API_KEY=your_groq_key
GEMINI_API_KEY=your_gemini_key
SERPER_API_KEY=your_serper_key

# Email (optional)
EMAIL_ADDRESS=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
```

---

## 🌐 Step 4: Expose Your Bot (Choose One Method)

### Option A: Cloudflare Tunnel (Recommended - Free)

No need to open ports or manage SSL certificates!

```bash
# Install cloudflared
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb

# Login to Cloudflare
cloudflared tunnel login

# Create tunnel
cloudflared tunnel create orion

# Configure tunnel (creates ~/.cloudflared/config.yml)
cat > ~/.cloudflared/config.yml << EOF
tunnel: orion
credentials-file: /home/$USER/.cloudflared/YOUR_TUNNEL_ID.json

ingress:
  - hostname: orion.yourdomain.com
    service: http://localhost:8000
  - service: http_status:404
EOF

# Route DNS
cloudflared tunnel route dns orion orion.yourdomain.com

# Run tunnel
cloudflared tunnel run orion
```

Your webhook URL will be: `https://orion.yourdomain.com/telegram/webhook`

### Option B: Direct Port with Nginx + Let's Encrypt

```bash
# Install Nginx and Certbot
sudo apt install -y nginx certbot python3-certbot-nginx

# Configure Nginx
sudo nano /etc/nginx/sites-available/orion

# Add:
server {
    server_name orion.yourdomain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Enable site
sudo ln -s /etc/nginx/sites-available/orion /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Get SSL certificate
sudo certbot --nginx -d orion.yourdomain.com
```

---

## 🚀 Step 5: Run the Bot

### Test Run

```bash
cd ~/orion
source .venv/bin/activate
python telegram_integration.py --port 8000
```

### Set Telegram Webhook

```bash
# Using the bot itself
python telegram_integration.py --set-webhook https://orion.yourdomain.com/telegram/webhook

# Or via curl
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
    -d "url=https://orion.yourdomain.com/telegram/webhook"
```

### Run as Systemd Service (Production)

Create service file:
```bash
sudo nano /etc/systemd/system/orion-telegram.service
```

Add:
```ini
[Unit]
Description=Orion Telegram Bot
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/orion
Environment=PATH=/home/YOUR_USERNAME/orion/.venv/bin
ExecStart=/home/YOUR_USERNAME/orion/.venv/bin/python telegram_integration.py --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable orion-telegram
sudo systemctl start orion-telegram

# Check status
sudo systemctl status orion-telegram

# View logs
sudo journalctl -u orion-telegram -f
```

---

## 💰 Cost Breakdown

| Item | Monthly Cost |
|------|-------------|
| Oracle Cloud VM (Always Free) | **$0** (forever!) |
| Telegram Bot API | **$0** (free forever) |
| Cloudflare Tunnel | **$0** (free tier) |
| SSL Certificate | **$0** (Let's Encrypt / Cloudflare) |
| **Total** | **$0 FOREVER** |

**Oracle Cloud Always Free includes:**
- Up to 4 ARM Ampere A1 cores + 24 GB RAM
- 2 AMD VMs (1 GB RAM each)  
- 200 GB total boot volume storage
- 10 TB/month outbound data transfer
- **No expiration - truly free forever!**

---

## 🔐 Security Best Practices

1. **Restrict bot access** - Set `TELEGRAM_ALLOWED_USER_ID` to only your user ID
2. **Use environment variables** - Never commit API keys
3. **Enable firewall** - Only allow ports 80, 443 (and 22 for SSH)
4. **Keep updated** - Regularly update system packages
5. **Monitor logs** - Check for unauthorized access attempts

```bash
# Setup firewall
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw enable
```

---

## 🧪 Testing

1. Open Telegram
2. Find your bot by username
3. Send `/start`
4. Send a test message like "What time is it?"
5. Wait for Orion's response!

---

## 🔧 Troubleshooting

### Bot not responding?

```bash
# Check if service is running
sudo systemctl status orion-telegram

# Check logs
sudo journalctl -u orion-telegram -n 100

# Verify webhook
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

### Memory issues on e2-micro?

```bash
# Create swap file (2GB)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## 📱 Telegram Commands

Your bot supports these commands:

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/status` | Check bot status |
| `/help` | Show help |

Any other message will be processed by Orion AI!

---

## 🎉 You're Done!

Your Orion AI assistant is now accessible 24/7 via Telegram, running on a free Oracle Cloud VM!

---

## 🔄 Alternative Deployment Options

### Option A: Fly.io (Easiest)

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login (creates free account)
flyctl auth signup

# Create fly.toml in your project
cat > fly.toml << EOF
app = "orion-bot"
primary_region = "sjc"

[build]
  builder = "paketobuildpacks/builder:base"

[env]
  PORT = "8000"

[http_service]
  internal_port = 8000
  force_https = true
EOF

# Deploy
flyctl launch
flyctl secrets set TELEGRAM_BOT_TOKEN=xxx TELEGRAM_ALLOWED_USER_ID=xxx

# Set webhook
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://orion-bot.fly.dev/telegram/webhook"
```

---

### Option B: Hugging Face Spaces (Best for Gradio UI - PRIVATE)

Perfect if you want the **web UI accessible from anywhere** - completely **private**!

#### Step 1: Create Private Space

1. Go to [huggingface.co/spaces](https://huggingface.co/spaces)
2. Click **Create new Space**
3. **IMPORTANT:** Set visibility to **🔒 Private**
4. Select **Gradio** as SDK
5. Choose **CPU basic (free)** - 2 vCPU, 16GB RAM

#### Step 2: Required Files

Create these files in your Space:

**`app.py`** (main entry point for HF Spaces):
```python
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from integrations.gradio_ui import create_gradio_interface

# Password protection (set HF_PASSWORD in secrets)
auth = None
password = os.getenv("HF_PASSWORD")
if password:
    auth = ("admin", password)

interface = create_gradio_interface()
interface.launch(auth=auth)
```

**`requirements.txt`** - copy from your project

#### Step 3: Upload Your Project Files

Upload these files/folders:
- `orion.py`
- `config.py`
- `utils.py`
- `memory.py` *(NEW - persistent memory)*
- `tools_enhanced.py`
- `integrations/` folder
- `google_cred/` folder (for Gmail access)

#### Step 4: Configure Secrets (Environment Variables)

Go to **Settings** → **Repository secrets** → Add:

| Secret Name | Value |
|-------------|-------|
| `GROQ_API_KEY` | your_groq_key |
| `GEMINI_API_KEY` | your_gemini_key |
| `SERPER_API_KEY` | your_serper_key |
| `HF_PASSWORD` | your_secret_password |

#### Step 5: Enable Persistent Storage (Memory!)

1. Go to **Settings** → **Persistent storage**
2. Enable **Persistent storage** (free tier available)
3. This maps to `/data` directory - memory.py automatically uses this!

Your conversations will be **remembered** even after restarts!

#### Privacy Layers

| Layer | Protection |
|-------|------------|
| **🔒 Private Space** | Only you (logged in) can see it |
| **🔑 Gradio Auth** | Password required to use |
| **🔐 API Keys as Secrets** | Never exposed in code |
| **💾 Persistent Memory** | Your conversations stay private |

Your app will be at: `https://huggingface.co/spaces/YOUR_USERNAME/orion`

---

### Option C: Render (Auto-deploy from GitHub)

1. Go to [render.com](https://render.com)
2. Connect GitHub repo
3. Create **Web Service**
4. Set:
   - Build: `pip install -r requirements.txt`
   - Start: `python telegram_integration.py`
5. Add environment variables in dashboard

⚠️ Free tier sleeps after 15 min - use with Telegram webhook (wakes on message)

---

### Option D: PythonAnywhere (Simple)

1. Go to [pythonanywhere.com](https://www.pythonanywhere.com)
2. Create free account
3. Upload files via Files tab
4. Create web app → Flask
5. Set up scheduled task to keep alive

⚠️ Limited CPU, but works for light usage

---

### Option E: Old Android Phone (Termux) 🤯

Turn an old phone into a 24/7 server!

```bash
# Install Termux from F-Droid (NOT Play Store)
# In Termux:
pkg update && pkg upgrade
pkg install python git

# Clone and setup
git clone YOUR_REPO orion
cd orion
pip install -r requirements.txt

# Run (use tmux to keep running)
pkg install tmux
tmux new -s orion
python telegram_integration.py

# Detach: Ctrl+B, D
# Reattach: tmux attach -t orion
```

Keep phone plugged in, on WiFi, with screen off!

---

### Option F: Raspberry Pi (One-time $35)

Buy once, run forever with no monthly costs!

```bash
# On Raspberry Pi (Raspberry Pi OS)
sudo apt update
sudo apt install python3-pip python3-venv git

# Setup same as Ubuntu VM
git clone YOUR_REPO orion
cd orion
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run as service (same systemd setup)
```

**Recommended:** Raspberry Pi 4 (4GB) or Pi 5

---

## 📊 Quick Decision Guide

| Your Situation | Best Option |
|---------------|-------------|
| Want full VM, no limits | **Oracle Cloud** |
| Quick setup, don't want VM | **Fly.io** |
| Want web UI accessible | **Hugging Face Spaces** |
| Have old Android phone | **Termux** |
| Want full control at home | **Raspberry Pi** |
| Just testing | **Render / PythonAnywhere** |

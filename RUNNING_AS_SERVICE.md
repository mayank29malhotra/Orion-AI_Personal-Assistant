# 🚀 Running Orion as a Service & WhatsApp Integration

## Quick Start Options

### Option 1: Double-Click to Start (Easiest) ⚡
Just double-click **`start_orion.bat`** - that's it! Orion will start in a new window.

### Option 2: Background Mode (Hidden)
Double-click **`start_orion_background.bat`** to run Orion in the background without showing a window.

### Option 3: Windows Service (Auto-start with PC) 🔄

#### Install as Windows Service:
1. Open PowerShell/CMD **as Administrator**
2. Navigate to the Orion folder:
   ```powershell
   cd "c:\Users\Mayank.Malhotra\OneDrive - Shell\Desktop\orion\Orion-AI_Personal-Assistant"
   ```

3. Install dependencies:
   ```powershell
   pip install pywin32
   ```

4. Install the service:
   ```powershell
   python install_service.py install
   ```

5. Start the service:
   ```powershell
   python install_service.py start
   ```

#### Service Management Commands:
```powershell
# Check service status
sc query OrionAI

# Start service
python install_service.py start
# OR
net start OrionAI

# Stop service
python install_service.py stop
# OR
net stop OrionAI

# Remove service
python install_service.py remove
```

#### Make it Start Automatically:
```powershell
# Set to auto-start with Windows
sc config OrionAI start=auto
```

---

## 📱 WhatsApp Integration Setup

### Prerequisites
1. **Twilio Account** (Free tier available)
2. **Public IP or ngrok** (for webhook)
3. **WhatsApp Sandbox Access**

### Step 1: Get Twilio Credentials

1. Sign up at [https://www.twilio.com/](https://www.twilio.com/)
2. Go to Console Dashboard
3. Copy your **Account SID** and **Auth Token**
4. Go to **Messaging → Try it out → Send a WhatsApp message**
5. Join the WhatsApp Sandbox by sending the code to their number
6. Copy your **Twilio WhatsApp Number** (format: `whatsapp:+14155238886`)

### Step 2: Configure Environment Variables

Add to your `.env` file:
```env
# WhatsApp Integration
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
WHATSAPP_WEBHOOK_PORT=5000
```

### Step 3: Install Dependencies
```powershell
pip install -r requirements.txt
```

### Step 4: Expose Your Server

#### Option A: Using ngrok (Easiest for testing)
```powershell
# Install ngrok from https://ngrok.com/
ngrok http 5000
```
Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)

#### Option B: Using Your Public IP
If your PC has a public IP, configure your router to forward port 5000 to your PC.

### Step 5: Start WhatsApp Server
```powershell
python whatsapp_integration.py
```

The server will start on port 5000 (or your configured port).

### Step 6: Configure Twilio Webhook

1. Go to Twilio Console → **Messaging → Settings → WhatsApp Sandbox Settings**
2. Under **"When a message comes in"**, paste your webhook URL:
   ```
   https://your-ngrok-url.ngrok.io/webhook
   ```
   OR
   ```
   http://your-public-ip:5000/webhook
   ```
3. Set method to **POST**
4. Click **Save**

### Step 7: Test It! 🎉

Send a WhatsApp message to your Twilio WhatsApp number:
```
Hello Orion, what's the weather today?
```

Orion will:
1. ✅ Acknowledge your message
2. 🔄 Process the task
3. 📤 Send you the result

---

## 🎯 How It Works

### When Orion is Running:
- Messages are processed immediately
- You get instant responses via WhatsApp

### When Orion is Offline:
- Messages are stored in a local SQLite database
- When Orion starts, it automatically processes all pending tasks
- You'll receive all responses when it comes back online

### Task Database Location:
`whatsapp_tasks.db` (created automatically in the project folder)

---

## 🔧 Advanced Configuration

### Run WhatsApp Server as a Service

Create `start_whatsapp.bat`:
```batch
@echo off
cd /d "%~dp0"
python whatsapp_integration.py
```

Then install it as a service following the same steps as the main Orion service.

### Custom Port
Change the port in `.env`:
```env
WHATSAPP_WEBHOOK_PORT=8080
```

Don't forget to update:
- ngrok: `ngrok http 8080`
- Twilio webhook URL

### Security Considerations
- **Never expose your Auth Token**
- Use HTTPS for webhooks (ngrok provides this automatically)
- Consider using Twilio's request validation in production
- Add authentication to your webhook in production environments

---

## 📝 Usage Examples

### Via WhatsApp:
```
Send email to john@example.com saying "Meeting at 3pm"
```

```
Search for latest AI news
```

```
Create a reminder for tomorrow at 9am to call mom
```

```
Take a screenshot
```

```
Generate a QR code for https://example.com
```

---

## 🐛 Troubleshooting

### Service won't start:
```powershell
# Check logs
type orion.log
```

### WhatsApp not responding:
1. Check if the server is running: `http://localhost:5000/health`
2. Verify Twilio credentials in `.env`
3. Check ngrok is running: `http://127.0.0.1:4040`
4. Verify webhook URL in Twilio console

### Messages not processing when offline:
- Check `whatsapp_tasks.db` exists
- Verify database permissions
- Check logs: `type orion.log`

### Port already in use:
```powershell
# Find process using port 5000
netstat -ano | findstr :5000

# Kill the process (replace PID)
taskkill /PID <process_id> /F
```

---

## 💡 Tips

1. **Keep ngrok running** if you're using it for the webhook
2. **Use background mode** (`start_orion_background.bat`) if you don't want to see the window
3. **Install as service** for true "set and forget" operation
4. **Monitor logs** regularly: `type orion.log`
5. **Test webhook** with a simple message before complex tasks

---

## 📊 Monitoring

### Check if Orion is running:
```powershell
# If running as service
sc query OrionAI

# If running normally
tasklist | findstr python
```

### View pending tasks:
```powershell
# Open SQLite database
sqlite3 whatsapp_tasks.db
SELECT * FROM pending_tasks WHERE status='pending';
.quit
```

### Health check:
Open in browser: `http://localhost:5000/health`

---

## 🔄 Updating Orion

If you update Orion code:

1. **If running as service:**
   ```powershell
   python install_service.py stop
   # Make your changes
   python install_service.py start
   ```

2. **If running normally:**
   - Just close and restart using the `.bat` file

---

Enjoy your automated AI assistant! 🎉

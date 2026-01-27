---
title: Orion AI Assistant
emoji: 🌟
colorFrom: purple
colorTo: indigo
sdk: gradio
sdk_version: 4.44.0
app_file: app_both.py
pinned: false
license: mit
---

# 🌟 Orion AI Personal Assistant

An advanced AI-powered personal assistant with **35+ tools** across multiple categories!

## ✨ Features
- 📧 Email Management (SMTP)
- 📅 Google Calendar Integration
- ✅ Task & Note Management
- 📄 PDF Processing & OCR
- 📊 Data Analysis (CSV, Excel, JSON)
- 🌐 Web Search & Automation
- 🐍 Python Code Execution
- 💬 **Telegram Bot** (runs alongside Gradio!)

## 🚀 Access Methods
- **Web UI**: Use this Gradio interface
- **Telegram**: Message your bot directly!

## ⚙️ Required Secrets
Set these in Space Settings → Variables and secrets:

**Required:**
- `GROQ_API_KEY` - Main LLM (Groq)
- `GEMINI_API_KEY` - Evaluator LLM
- `SERPER_API_KEY` - Web search

**Optional:**
- `EMAIL_ADDRESS` & `EMAIL_PASSWORD` - Email (SMTP)
- `GOOGLE_CALENDAR_TOKEN_JSON` - Calendar (paste full JSON)
- `NTFY_TOPIC` - Push notifications
- `TELEGRAM_BOT_TOKEN` - Telegram bot token
- `TELEGRAM_ALLOWED_USER_ID` - Your Telegram user ID

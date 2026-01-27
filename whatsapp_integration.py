"""
WhatsApp Integration for Orion AI Assistant
Uses Flask webhook to receive WhatsApp messages and Twilio API to send responses
"""
import os
import json
import sqlite3
from datetime import datetime
from flask import Flask, request
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from threading import Thread
from queue import Queue
import asyncio
from config import Config
from orion import Orion
from utils import Logger

logger = Logger().logger

# Initialize Flask app
app = Flask(__name__)

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")  # Format: whatsapp:+14155238886

# Initialize Twilio client
twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Task queue for offline messages
task_queue = Queue()

# Database for storing pending tasks
DB_PATH = "whatsapp_tasks.db"


def init_database():
    """Initialize SQLite database for task storage"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            result TEXT
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("WhatsApp task database initialized")


def save_task(phone_number: str, message: str):
    """Save a task to the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO pending_tasks (phone_number, message, timestamp)
        VALUES (?, ?, ?)
    ''', (phone_number, message, datetime.now().isoformat()))
    conn.commit()
    task_id = cursor.lastrowid
    conn.close()
    logger.info(f"Task saved to database: ID={task_id}, From={phone_number}")
    return task_id


def get_pending_tasks():
    """Get all pending tasks from the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, phone_number, message, timestamp 
        FROM pending_tasks 
        WHERE status = 'pending'
        ORDER BY timestamp ASC
    ''')
    tasks = cursor.fetchall()
    conn.close()
    return tasks


def update_task_status(task_id: int, status: str, result: str = None):
    """Update task status in the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE pending_tasks 
        SET status = ?, result = ?
        WHERE id = ?
    ''', (status, result, task_id))
    conn.commit()
    conn.close()
    logger.info(f"Task {task_id} updated: {status}")


def send_whatsapp_message(to_number: str, message: str):
    """Send a WhatsApp message via Twilio"""
    if not twilio_client:
        logger.error("Twilio client not configured")
        return False
    
    try:
        # Ensure phone number has whatsapp: prefix
        if not to_number.startswith("whatsapp:"):
            to_number = f"whatsapp:{to_number}"
        
        message = twilio_client.messages.create(
            body=message,
            from_=TWILIO_WHATSAPP_NUMBER,
            to=to_number
        )
        logger.info(f"WhatsApp message sent to {to_number}: {message.sid}")
        return True
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {str(e)}")
        return False


async def process_whatsapp_task(phone_number: str, message: str, task_id: int = None):
    """Process a WhatsApp task using Orion"""
    try:
        logger.info(f"Processing WhatsApp task from {phone_number}: {message[:50]}...")
        
        # Initialize Orion
        orion = Orion()
        await orion.setup()
        
        # Process the message
        results = await orion.run_superstep(message, success_criteria="", history=[])
        
        # Extract the final response
        if results and len(results) > 0:
            final_response = results[-1][1] if len(results[-1]) > 1 else "Task completed"
        else:
            final_response = "Task completed successfully"
        
        # Send response back via WhatsApp
        response_msg = f"✅ Task completed!\n\n{final_response[:1000]}"  # Limit to 1000 chars
        send_whatsapp_message(phone_number, response_msg)
        
        # Update task status if it was from database
        if task_id:
            update_task_status(task_id, "completed", final_response)
        
        logger.info(f"Task completed for {phone_number}")
        
    except Exception as e:
        error_msg = f"❌ Error processing task: {str(e)}"
        logger.error(f"WhatsApp task failed: {str(e)}")
        send_whatsapp_message(phone_number, error_msg)
        
        if task_id:
            update_task_status(task_id, "failed", str(e))


def process_pending_tasks():
    """Process all pending tasks from the database"""
    logger.info("Processing pending WhatsApp tasks...")
    tasks = get_pending_tasks()
    
    if not tasks:
        logger.info("No pending tasks found")
        return
    
    logger.info(f"Found {len(tasks)} pending tasks")
    
    for task in tasks:
        task_id, phone_number, message, timestamp = task
        logger.info(f"Processing pending task {task_id} from {timestamp}")
        
        # Update status to processing
        update_task_status(task_id, "processing")
        
        # Process the task
        asyncio.run(process_whatsapp_task(phone_number, message, task_id))


@app.route("/webhook", methods=["POST"])
def whatsapp_webhook():
    """Webhook endpoint for receiving WhatsApp messages"""
    try:
        # Get message details
        incoming_msg = request.values.get('Body', '').strip()
        from_number = request.values.get('From', '')
        
        logger.info(f"Received WhatsApp message from {from_number}: {incoming_msg[:50]}...")
        
        # Save task to database
        task_id = save_task(from_number, incoming_msg)
        
        # Send acknowledgment
        resp = MessagingResponse()
        resp.message("📝 Task received! Orion is processing your request...")
        
        # Process task in background
        def process_in_background():
            asyncio.run(process_whatsapp_task(from_number, incoming_msg, task_id))
        
        thread = Thread(target=process_in_background)
        thread.daemon = True
        thread.start()
        
        return str(resp)
        
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        resp = MessagingResponse()
        resp.message("❌ Error processing your request. Please try again.")
        return str(resp)


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return {"status": "online", "service": "Orion WhatsApp Integration"}, 200


def start_whatsapp_server(host="0.0.0.0", port=5000):
    """Start the WhatsApp webhook server"""
    init_database()
    
    # Process any pending tasks on startup
    logger.info("Starting WhatsApp integration server...")
    process_pending_tasks()
    
    logger.info(f"WhatsApp webhook server starting on {host}:{port}")
    logger.info(f"Webhook URL: http://your-server-ip:{port}/webhook")
    
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    start_whatsapp_server()

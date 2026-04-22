import os
import sys
import time
import csv
import json
import urllib.request
from datetime import datetime
from dotenv import load_dotenv
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

# Load environment variables
load_dotenv()

# Configuration
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
BOT_TWILIO_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
MY_MOBILE_NUMBER = os.getenv('MY_MOBILE_NUMBER')

# Log file
LOG_FILE = 'call_logs.csv'

# ANSI Colors for Terminal
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
RESET = '\033[0m'

def initialize_csv():
    """Create CSV with headers if it doesn't exist."""
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Timestamp', 'Call SID', 'From', 'To', 'Duration (sec)', 'Status', 'Cost', 'Notes'])

def log_call(call_sid, from_num, to_num, duration, status, price, notes):
    """Log the call details to CSV."""
    with open(LOG_FILE, mode='a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            call_sid, from_num, to_num, duration, status, price, notes
        ])

# def get_ngrok_url():
#     """Fetch the current public URL from the local Ngrok instance."""
#     print(f"{CYAN}Checking Ngrok status...{RESET}")
#     try:
#         req = urllib.request.Request("http://127.0.0.1:4040/api/tunnels")
#         with urllib.request.urlopen(req) as response:
#             data = json.loads(response.read().decode())
#             tunnels = data.get("tunnels", [])
#             if not tunnels:
#                 print(f"{YELLOW}Warning: Ngrok API reachable, but no active tunnels found!{RESET}")
#                 return None
#             else:
#                 public_url = tunnels[0].get('public_url')
#                 # ensure it's https
#                 if public_url.startswith("http://"):
#                     public_url = public_url.replace("http://", "https://")
#                 print(f"{GREEN}Ngrok is active: {public_url}{RESET}")
#                 return public_url
#     except Exception as e:
#         print(f"{RED}Error: Ngrok is NOT reachable at localhost:4040. Ensure it is running! ({e}){RESET}")
#         return None

def trigger_call_to_me():
    """Trigger an outbound call from the chatbot Twilio number to your mobile number."""
    # Ensure environment variables exist
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        print(f"{RED}Error: TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN is missing in .env!{RESET}")
        return
    if not BOT_TWILIO_NUMBER or not MY_MOBILE_NUMBER or MY_MOBILE_NUMBER == "+8801XXXXXXXXX":
        print(f"{RED}Error: Please add your actual mobile number to MY_MOBILE_NUMBER in .env!{RESET}")
        print(f"{YELLOW}Current MY_MOBILE_NUMBER is set to: {MY_MOBILE_NUMBER}{RESET}")
        print(f"{YELLOW}Current TWILIO_PHONE_NUMBER is set to: {BOT_TWILIO_NUMBER}{RESET}")
        return

    # Check for Ngrok URL
    # ngrok_url = get_ngrok_url()
    # if not ngrok_url:
    #     print(f"{RED}Aborting call because Ngrok could not be found. Start Ngrok first!{RESET}")
    #     return
        
    # # Standard endpoint for the FastAPI Twilio webhook
    # webhook_url = f"{ngrok_url}/voice"
    # Use production domain instead of ngrok
    webhook_url = "https://test3.fireai.agency/voice"
    print(f"{CYAN}Webhook URL configured to: {webhook_url}{RESET}")
    
    #print(f"{CYAN}Webhook URL configured to: {webhook_url}{RESET}")

    # Initialize Twilio Client
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    
    print(f"{CYAN}Initiating call from Bot '{BOT_TWILIO_NUMBER}' to your phone '{MY_MOBILE_NUMBER}'...{RESET}")
    
    call_sid = "N/A"
    try:
        # Create the outbound call. URL points Twilio to the chatbot logic once answered.
        call = client.calls.create(
            to=MY_MOBILE_NUMBER,
            from_=BOT_TWILIO_NUMBER,
            url=webhook_url 
        )
        call_sid = call.sid
        print(f"{GREEN}Call initiated successfully! Call SID: {call_sid}{RESET}")
        print(f"{YELLOW}Status: ringing... Please answer your phone ({MY_MOBILE_NUMBER})!{RESET}")
        
        # Track the status periodically until the call is finished
        while True:
            time.sleep(3) # Wait 3 seconds
            current_call = client.calls(call_sid).fetch()
            status = current_call.status
            print(f"... Current status: {status}")
            
            if status in ['completed', 'busy', 'failed', 'no-answer', 'canceled']:
                print(f"{GREEN}Call finished. Final Status: {status}{RESET}")
                
                duration = current_call.duration or "0"
                price = current_call.price or "Unknown"
                
                log_call(call_sid, BOT_TWILIO_NUMBER, MY_MOBILE_NUMBER, duration, status, price, "Call Me Now Live Tester")
                break
                
    except TwilioRestException as e:
        print(f"{RED}Twilio API Error: {e}{RESET}")
        log_call(call_sid, BOT_TWILIO_NUMBER, MY_MOBILE_NUMBER, 0, 'failed', 'N/A', f"Error: {e}")
    except Exception as e:
        print(f"{RED}Unexpected Error: {e}{RESET}")
        log_call(call_sid, BOT_TWILIO_NUMBER, MY_MOBILE_NUMBER, 0, 'failed', 'N/A', f"Unexpected error: {e}")

if __name__ == '__main__':
    initialize_csv()
    print("\n" + "="*40)
    print(f"{CYAN}'CALL ME NOW' Twilio AI Chatbot Tester{RESET}")
    print("="*40)
    print("This script will call your personal mobile number.")
    #print("When you answer, it instructs Twilio to connect the call to your local Ngrok /voice webhook.")
    #print("Make sure FastAPI and Ngrok are running before continuing.")
    print("When you answer, Twilio connects the call to your live AI webhook.")
    print("Make sure your FastAPI server is running on AWS.")
    print("="*40)
    
    # Prompt before calling
    user_num = os.getenv('MY_MOBILE_NUMBER', 'your phone')
    input(f"\nPress ENTER to trigger the call to {user_num}...")
    
    trigger_call_to_me()

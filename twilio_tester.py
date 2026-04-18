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
FROM_NUMBER = os.getenv('FROM_NUMBER')
TO_NUMBER = os.getenv('TO_NUMBER')
AUTO_HANGUP_SECONDS = int(os.getenv('AUTO_HANGUP_SECONDS', 45))

# Log file
LOG_FILE = 'call_logs.csv'

# ANSI Colors for Terminal
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
RESET = '\033[0m'

# Simulated conversational TwiML for Number A
# It waits 4 seconds for AI to greet, says it wants pizza, waits 7 secs for AI, orders specific pizza, waits 7 secs, confirms.
CONVERSATION_TWIML = """<Response>
    <Pause length="4"/>
    <Say voice="Polly.Matthew-Neural">Hello, I'd like to place a pizza order.</Say>
    <Pause length="7"/>
    <Say voice="Polly.Matthew-Neural">I would like a large pepperoni pizza with extra cheese.</Say>
    <Pause length="7"/>
    <Say voice="Polly.Matthew-Neural">That is all, please finalize the order.</Say>
    <Pause length="10"/>
</Response>"""

def initialize_csv():
    # Create CSV with headers if it doesn't exist
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Timestamp', 'Call SID', 'From', 'To', 'Duration (sec)', 'Status', 'Cost', 'Notes'])

def log_call(call_sid, from_num, to_num, duration, status, price, notes):
    with open(LOG_FILE, mode='a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            call_sid, from_num, to_num, duration, status, price, notes
        ])

def check_ngrok():
    print(f"{CYAN}Checking Ngrok status...{RESET}")
    try:
        req = urllib.request.Request("http://127.0.0.1:4040/api/tunnels")
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            tunnels = data.get("tunnels", [])
            if not tunnels:
                print(f"{YELLOW}Warning: Ngrok API reachable, but no active tunnels found!{RESET}")
                return False
            else:
                public_url = tunnels[0].get('public_url')
                print(f"{GREEN}Ngrok is active: {public_url}{RESET}")
                return True
    except Exception as e:
        print(f"{RED}Error: Ngrok is NOT reachable at localhost:4040. Ensure it is running! ({e}){RESET}")
        return False

def make_test_call():
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        print(f"{RED}Error: TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN is missing in .env!{RESET}")
        return
    if not FROM_NUMBER or not TO_NUMBER:
        print(f"{RED}Error: FROM_NUMBER or TO_NUMBER is missing in .env!{RESET}")
        return

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    
    # Check ngrok first
    check_ngrok()
    
    print(f"{CYAN}Initiating call from {FROM_NUMBER} to {TO_NUMBER}...{RESET}")
    print(f"Using test timeout: {AUTO_HANGUP_SECONDS} seconds.")
    
    client_called = False
    call_sid = "N/A"
    try:
        call = client.calls.create(
            to=TO_NUMBER,
            from_=FROM_NUMBER,
            twiml=CONVERSATION_TWIML
        )
        call_sid = call.sid
        client_called = True
        print(f"{GREEN}Call initiated successfully! Call SID: {call_sid}{RESET}")
        
        # Wait for the AI to answer and for the conversation to play out
        print(f"Waiting for {AUTO_HANGUP_SECONDS} seconds before auto-hangup...")
        for i in range(AUTO_HANGUP_SECONDS):
            time.sleep(1)
            if i > 0 and i % 5 == 0:
                print(f"... {i} seconds elapsed ...")

        # Auto Hangup
        print(f"{YELLOW}Time's up! Hanging up the call...{RESET}")
        client.calls(call_sid).update(status='completed')
        
        # Wait a moment to fetch final call details
        time.sleep(2)
        final_call = client.calls(call_sid).fetch()
        
        duration = final_call.duration or AUTO_HANGUP_SECONDS
        price = final_call.price or "Unknown"
        status = final_call.status
        
        print(f"{GREEN}Call finished. Status: {status}, Duration: {duration}s, Cost: {price}{RESET}")
        log_call(call_sid, FROM_NUMBER, TO_NUMBER, duration, status, price, "Success")
        
    except TwilioRestException as e:
        print(f"{RED}Twilio API Error: {e}{RESET}")
        log_call(call_sid, FROM_NUMBER, TO_NUMBER, 0, 'failed', 'N/A', f"Error: {e}")
        
        # One-time retry logic
        if not client_called:
            print(f"{YELLOW}Retrying call once...{RESET}")
            time.sleep(2)
            try:
                call = client.calls.create(
                    to=TO_NUMBER,
                    from_=FROM_NUMBER,
                    twiml=CONVERSATION_TWIML
                )
                print(f"{GREEN}Retry successful! Call SID: {call.sid}{RESET}")
                time.sleep(AUTO_HANGUP_SECONDS)
                client.calls(call.sid).update(status='completed')
                log_call(call.sid, FROM_NUMBER, TO_NUMBER, AUTO_HANGUP_SECONDS, 'completed (retry)', 'N/A', "Success on retry")
            except Exception as retry_e:
                print(f"{RED}Retry failed: {retry_e}{RESET}")
                log_call('N/A', FROM_NUMBER, TO_NUMBER, 0, 'failed', 'N/A', f"Retry failed: {retry_e}")

    except Exception as e:
        print(f"{RED}Unexpected Error: {e}{RESET}")
        log_call(call_sid, FROM_NUMBER, TO_NUMBER, 0, 'failed', 'N/A', f"Error: {e}")

def run_menu():
    initialize_csv()
    while True:
        print("\n" + "="*40)
        print(f"{CYAN}Twilio Automated Test Caller Menu{RESET}")
        print("="*40)
        print("1. Run a single test call (Simulator)")
        print("2. Run 3 quick test calls (Stress test)")
        print("3. Show recent logs")
        print("4. Exit")
        choice = input("Enter your choice (1-4): ")

        if choice == '1':
            make_test_call()
        elif choice == '2':
            for i in range(3):
                print(f"\n{CYAN}--- Test Call {i+1} of 3 ---{RESET}")
                make_test_call()
                if i < 2:
                    time.sleep(5) # Brief pause between rapid calls
        elif choice == '3':
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, mode='r') as f:
                    print(f"\n{CYAN}--- Recent Logs ---{RESET}")
                    print(f.read())
            else:
                print(f"{YELLOW}No logs found.{RESET}")
        elif choice == '4':
            print(f"{GREEN}Exiting...{RESET}")
            sys.exit(0)
        else:
            print(f"{RED}Invalid choice. Please select 1-4.{RESET}")

if __name__ == '__main__':
    run_menu()

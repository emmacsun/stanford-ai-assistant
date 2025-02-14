import streamlit as st
import time
from openai import OpenAI
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime
import pytz

# Google Sheets setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

@st.cache_resource
def get_google_sheets_service():
    """Initialize Google Sheets service"""
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    service = build('sheets', 'v4', credentials=credentials)
    return service

def log_interaction(service, spreadsheet_id, user_message, assistant_response, sunet_id):
    """Log interaction to Google Sheets"""
    # Get PST timezone
    pst = pytz.timezone('America/Los_Angeles')
    current_time = datetime.now(pst).strftime('%Y-%m-%d %H:%M:%S %Z')
    
    # Prepare the row data
    row_data = [
        [
            current_time,
            sunet_id,
            user_message,
            assistant_response,
            len(user_message),  # Message length
            len(assistant_response),  # Response length
        ]
    ]
    
    # Append the row to the sheet
    body = {
        'values': row_data
    }
    
    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range='Logs!A:F',  # Assumes sheet named 'Logs'
        valueInputOption='RAW',
        insertDataOption='INSERT_ROWS',
        body=body
    ).execute()

def initialize_sheet_if_needed(service, spreadsheet_id):
    """Initialize the sheet with headers if it's new"""
    headers = [
        ['Timestamp', 'SUNet ID', 'User Message', 'Assistant Response', 
         'Message Length', 'Response Length']
    ]
    
    try:
        # Check if headers exist
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range='Logs!A1:F1'
        ).execute()
        
        if 'values' not in result:
            # Sheet is empty, add headers
            body = {
                'values': headers
            }
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range='Logs!A1:F1',
                valueInputOption='RAW',
                body=body
            ).execute()
    except Exception as e:
        print(f"Error checking/initializing sheet: {e}")

# Modified main_app function
def main_app():
    client, assistant, thread = initialize_assistant()
    sheets_service = get_google_sheets_service()
    spreadsheet_id = st.secrets["SPREADSHEET_ID"]
    
    # Initialize sheet if needed
    initialize_sheet_if_needed(sheets_service, spreadsheet_id)
    
    st.title("🎓 Stanford Course Helper")
    # Rest of your existing welcome message code...
    
    if prompt := st.chat_input("Ask about courses..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Create assistant response
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            
            # Create and run the assistant response
            message = client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=prompt
            )
            run = client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=assistant.id,
                instructions="Be concise and focused on course-related information."
            )

            # Wait for completion and stream response
            while run.status in ["queued", "in_progress"]:
                run = client.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id
                )
                time.sleep(0.5)

            # Get the response
            messages = client.beta.threads.messages.list(
                thread_id=thread.id,
                order="asc",
                after=message.id
            )
            if messages.data:
                response = messages.data[0].content[0].text.value
                message_placeholder.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
                
                # Log the interaction to Google Sheets
                try:
                    log_interaction(
                        sheets_service,
                        spreadsheet_id,
                        prompt,
                        response,
                        st.session_state.sunet_id
                    )
                except Exception as e:
                    st.error(f"Failed to log interaction: {e}")

    # Your existing sidebar code...
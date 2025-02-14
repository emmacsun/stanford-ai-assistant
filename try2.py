import streamlit as st
import time
from openai import OpenAI
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime
import pytz
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Google Sheets setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Initialize session state for login
if "authenticated" not in st.session_state:
   st.session_state.authenticated = False

@st.cache_resource
def get_google_sheets_service():
    """Initialize Google Sheets service"""
    try:
        #st.write("🔄 Attempting to connect to Google Sheets...")
        logger.info("Attempting to connect to Google Sheets...")
        
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=SCOPES
        )
        #st.write("✅ Credentials created successfully")
        
        service = build('sheets', 'v4', credentials=credentials)
        #st.write("✅ Service built successfully")
        
        # Test the connection by trying to access the spreadsheet
        spreadsheet_id = st.secrets["SPREADSHEET_ID"]
        result = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        #st.write(f"✅ Successfully accessed spreadsheet: {result.get('properties', {}).get('title')}")
        logger.info(f"Successfully accessed spreadsheet: {spreadsheet_id}")
        
        return service
    except Exception as e:
        error_msg = f"Failed to connect to Google Sheets: {str(e)}"
        st.error(error_msg)
        logger.error(error_msg)
        return None

def log_interaction(service, spreadsheet_id, user_message, assistant_response, sunet_id):
    """Log interaction to Google Sheets"""
    if not service:
        error_msg = "Google Sheets service not initialized"
        st.error(error_msg)
        logger.error(error_msg)
        return False
        
    try:
        #st.write("🔄 Attempting to log interaction...")
        logger.info("Attempting to log interaction...")
        
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
                len(user_message),
                len(assistant_response),
            ]
        ]
        
        # Show the data being logged
        #st.write("📝 Logging data:")
        #st.write({"time": current_time, "user": sunet_id, "msg_length": len(user_message)})
        
        # Append the row to the sheet
        body = {
            'values': row_data
        }
        
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range='Logs!A:F',
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        
        #st.write("✅ Successfully logged interaction to Google Sheets")
        logger.info("Successfully logged interaction to Google Sheets")
        return True
    except Exception as e:
        error_msg = f"Failed to log interaction: {str(e)}"
        st.error(error_msg)
        logger.error(error_msg)
        return False

def initialize_sheet_if_needed(service, spreadsheet_id):
    """Initialize the sheet with headers if it's new"""
    if not service:
        st.error("Google Sheets service not initialized")
        return
        
    try:
        headers = [
            ['Timestamp', 'SUNet ID', 'User Message', 'Assistant Response', 
             'Message Length', 'Response Length']
        ]
        
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
            #st.write("✅ Initialized sheet with headers!")
    except Exception as e:
        st.error(f"❌ Error checking/initializing sheet: {str(e)}")

def validate_sunet(sunet_id):
    """
    Validate SUNet ID format (you may want to add more validation rules)
    """
    # Basic validation: non-empty and follows general SUNet format
    if not sunet_id:
        return False
    # Add more validation rules as needed
    return True

def login_page():
    st.title("🎓 Stanford Course Helper Login")
    st.markdown("Please enter your SUNet ID to access the course helper.")
    
    # Create login form
    with st.form("login_form"):
        sunet_id = st.text_input("SUNet ID").strip()
        submitted = st.form_submit_button("Login")
        
        if submitted:
            if validate_sunet(sunet_id):
                st.session_state.authenticated = True
                st.session_state.sunet_id = sunet_id
                st.rerun()
            else:
                st.error("Invalid SUNet ID. Please try again.")

@st.cache_resource
def initialize_assistant():
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    assistant = client.beta.assistants.retrieve(st.secrets["ASSISTANT_KEY"])
    thread = client.beta.threads.create()
    return client, assistant, thread

def main_app():
    st.title("🎓 Stanford Course Helper")
    
    # Initialize services
    client, assistant, thread = initialize_assistant()
    sheets_service = get_google_sheets_service()
    
    if not sheets_service:
        st.error("Failed to initialize Google Sheets service. Check your credentials.")
        return
        
    spreadsheet_id = st.secrets["SPREADSHEET_ID"]
    
    # Initialize sheet if needed
    initialize_sheet_if_needed(sheets_service, spreadsheet_id)
    
    # Display welcome message with SUNet ID
    st.markdown(f"""
        Welcome to the Stanford Course Helper, {st.session_state.sunet_id}! I can help you:
        - Check course prerequisites
        - Recommend courses based on your interests
        - Validate your course schedule
        - Provide information about specific courses
    """)
    
    # Create a chat interface
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Ask about courses..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Create assistant response
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            
            try:
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
                    success = log_interaction(
                        sheets_service,
                        spreadsheet_id,
                        prompt,
                        response,
                        st.session_state.sunet_id
                    )
                    
                    if not success:
                        st.sidebar.warning("Failed to log this interaction. Please check the errors above.")
                        
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")

    # Add sidebar with helpful information
    with st.sidebar:
        st.header("Tips for using the Course Helper")
        st.markdown("""
        - Ask about specific courses by their course codes (e.g., CS106B)
        - Check if your schedule is feasible
        - Ask for course recommendations in specific areas
        - Inquire about prerequisites and requirements
        """)
        
        # Add logout button
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.messages = []
            st.rerun()
            
        # Add clear chat button
        if st.button("Clear Chat History"):
            st.session_state.messages = []
            thread = client.beta.threads.create()  # Create new thread when clearing history
            st.rerun()

# Main flow control
if not st.session_state.authenticated:
    login_page()
else:
    main_app()
    # Temporary test code
    sheets_service = get_google_sheets_service()
    if sheets_service:
        try:
            spreadsheet_id = st.secrets["SPREADSHEET_ID"]
            result = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            print("✅ Successfully connected to sheet:", result['properties']['title'])
            
            # Try to read the Logs sheet
            result = sheets_service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range='Logs!A1:A1'
            ).execute()
            #st.write("✅ Successfully accessed 'Logs' sheet")
        except Exception as e:
            st.error(f"❌ Error accessing sheet: {str(e)}")
    else:
        st.error("❌ Failed to initialize Google Sheets service")
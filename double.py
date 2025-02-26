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
        logger.info("Attempting to connect to Google Sheets...")
        
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=SCOPES
        )
        
        service = build('sheets', 'v4', credentials=credentials)
        
        # Test the connection
        spreadsheet_id = st.secrets["SPREADSHEET_ID"]
        result = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        logger.info(f"Successfully accessed spreadsheet: {spreadsheet_id}")
        
        return service
    except Exception as e:
        error_msg = f"Failed to connect to Google Sheets: {str(e)}"
        st.error(error_msg)
        logger.error(error_msg)
        return None

def log_interaction(service, spreadsheet_id, user_message, assistant_response, sunet_id, assistant_type):
    """Log interaction to Google Sheets with assistant type"""
    if not service:
        error_msg = "Google Sheets service not initialized"
        st.error(error_msg)
        logger.error(error_msg)
        return False
        
    try:
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
                assistant_type  # Add assistant type to logging
            ]
        ]
        
        # Append the row to the sheet
        body = {
            'values': row_data
        }
        
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range='Logs!A:G',  # Extended range to include assistant type
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        
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
             'Message Length', 'Response Length', 'Assistant Type']
        ]
        
        # Check if headers exist
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range='Logs!A1:G1'
        ).execute()
        
        if 'values' not in result:
            # Sheet is empty, add headers
            body = {
                'values': headers
            }
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range='Logs!A1:G1',
                valueInputOption='RAW',
                body=body
            ).execute()
    except Exception as e:
        st.error(f"❌ Error checking/initializing sheet: {str(e)}")

def validate_sunet(sunet_id):
    """Validate SUNet ID format"""
    return True;

def login_page():
    st.title("🎓 Stanford AI Academic Advisor")
    st.markdown("Please enter your SUNet ID to access Athena. (Ex. jsmith).")
    
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
def initialize_assistants():
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    
    # Initialize all assistants
    labeler = client.beta.assistants.retrieve(st.secrets["LABELER_ID"])
    course_scheduler = client.beta.assistants.retrieve(st.secrets["COURSE_SCHEDULER_ID"])
    admin_info = client.beta.assistants.retrieve(st.secrets["ADMIN_INFO_ID"])
    
    # Create initial thread
    thread = client.beta.threads.create()
    
    return client, labeler, course_scheduler, admin_info, thread

def run_assistant(client, thread_id, assistant_id):
    """Run an assistant and get its response"""
    try:
        # Start the run
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
        )
        
        # Wait for completion
        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )
            if run_status.status == 'completed':
                break
            elif run_status.status == 'failed':
                raise Exception("Assistant run failed")
            time.sleep(0.5)
        
        # Get latest message
        messages = client.beta.threads.messages.list(
            thread_id=thread_id,
            order="desc",
            limit=1
        )
        return messages.data[0].content[0].text.value
        
    except Exception as e:
        logger.error(f"Error running assistant: {str(e)}")
        raise

def process_user_query(client, thread, labeler, course_scheduler, admin_info, user_question):
    """Process user query through dual assistant system"""
    try:
        # Create new thread for this interaction
        thread = client.beta.threads.create()
        
        # Send user's question to labeler
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_question
        )
        
        # Get labeler's decision
        label = int(run_assistant(client, thread.id, labeler.id))
        
        # Choose next assistant based on label
        next_assistant = course_scheduler if label == 1 else admin_info
        assistant_type = "Course Scheduler" if label == 1 else "Admin Info"
        
        # Get final response from chosen assistant
        final_response = run_assistant(client, thread.id, next_assistant.id)
        
        return final_response, assistant_type
        
    except Exception as e:
        error_msg = f"Error processing query: {str(e)}"
        logger.error(error_msg)
        return error_msg, "Error"

# Function to handle prompt button clicks
def set_prompt(prompt_text):
    st.session_state.prompt = prompt_text

def main_app():
    st.title("🧝🏼‍♀️ Ask Athena")
    
    # Initialize services
    client, labeler, course_scheduler, admin_info, thread = initialize_assistants()
    sheets_service = get_google_sheets_service()
    
    if not sheets_service:
        st.error("Failed to initialize Google Sheets service. Check your credentials.")
        return
        
    spreadsheet_id = st.secrets["SPREADSHEET_ID"]
    
    # Initialize sheet if needed
    initialize_sheet_if_needed(sheets_service, spreadsheet_id)
    
    # Display welcome message
    st.markdown(f"""
        Hello from your AI academic advisor, {st.session_state.sunet_id}! 
    """)
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Initialize prompt state if not exists
    if "prompt" not in st.session_state:
        st.session_state.prompt = ""
    
    # Add the three autofill prompt buttons
    st.markdown("### Quick Questions:")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.button("What classes should I take as a History major?", 
                  on_click=set_prompt, 
                  args=["What classes should I take as a History major?"])
    with col2:
        st.button("What classes fulfill WAYS A-II?", 
                  on_click=set_prompt, 
                  args=["What classes fulfill WAYS A-II?"])
    with col3:
        st.button("What are some afternoon classes I can take?", 
                  on_click=set_prompt, 
                  args=["What are some afternoon classes I can take?"])

    # Chat input with pre-filled text from buttons if available
    prompt = st.chat_input("Ask about courses...", value=st.session_state.prompt)
    
    # Clear the prompt state after it's been used
    if prompt:
        # If prompt came from button, clear it for next use
        if prompt == st.session_state.prompt:
            st.session_state.prompt = ""
            
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Create assistant response
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            
            try:
                # Process through dual assistant system
                response, assistant_type = process_user_query(
                    client, thread, labeler, course_scheduler, admin_info, prompt
                )
                
                # Display response
                message_placeholder.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
                
                # Log the interaction
                success = log_interaction(
                    sheets_service,
                    spreadsheet_id,
                    prompt,
                    response,
                    st.session_state.sunet_id,
                    assistant_type
                )
                
                if not success:
                    st.sidebar.warning("Failed to log this interaction. Please check the errors above.")
                    
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")

    # Sidebar
    with st.sidebar:
        st.header("Tips for using the Course Helper")
        st.markdown("""
        - Ask about specific courses by their course codes (e.g., CS106B)
        - Check if your schedule is feasible
        - Ask for course recommendations in specific areas
        - Inquire about prerequisites and requirements
        """)
        
        # Logout button
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.messages = []
            st.rerun()
            
        # Clear chat button
        if st.button("Clear Chat History"):
            st.session_state.messages = []
            thread = client.beta.threads.create()
            st.rerun()

# Main flow control
if not st.session_state.authenticated:
    login_page()
else:
    main_app()

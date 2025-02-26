import streamlit as st
import time
from openai import OpenAI
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime
import pytz
import logging
import re
import base64

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Google Sheets setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Initialize session state for login
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# App styling and configuration
st.set_page_config(
    page_title="Stanford Course Helper",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
def local_css():
    st.markdown("""
    <style>
        /* Main app styling */
        .stApp {
            background-color: #f5f5f5;
        }
        
        /* Header styling */
        h1, h2, h3 {
            color: #8C1515 !important; /* Stanford cardinal color */
            font-family: 'Source Sans Pro', sans-serif;
        }
        
        /* Card styling for containers */
        .css-1r6slb0, .css-1pe84o1, .css-12oz5g7 {
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            padding: 1rem;
            background-color: white;
        }
        
        /* Login container */
        .login-container {
            max-width: 500px;
            margin: 0 auto;
            padding: 2rem;
            border-radius: 10px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            background-color: white;
            text-align: center;
        }
        
        /* Button styling */
        .stButton>button {
            background-color: #8C1515;
            color: white;
            border-radius: 5px;
            border: none;
            padding: 0.5rem 1rem;
            font-weight: bold;
            transition: all 0.3s;
        }
        
        .stButton>button:hover {
            background-color: #600E0E;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
        }
        
        /* Custom SUNet ID Input field */
        .sunet-input {
            position: relative;
            margin-bottom: 1rem;
        }
        
        .sunet-input input {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
        
        .stanford-domain {
            position: absolute;
            right: 10px;
            top: 50%;
            transform: translateY(-50%);
            color: #888;
            opacity: 0.6;
            font-size: 0.9rem;
            pointer-events: none;
        }
        
        /* Chat message styling */
        .user-message {
            background-color: #F0F2F6;
            border-radius: 10px;
            padding: 10px;
            margin: 5px 0;
        }
        
        .assistant-message {
            background-color: #E6F3E6;
            border-radius: 10px;
            padding: 10px;
            margin: 5px 0;
        }
        
        /* Loading animation */
        @keyframes pulse {
            0% { opacity: 0.5; }
            50% { opacity: 1; }
            100% { opacity: 0.5; }
        }
        
        .loading-dots {
            display: flex;
            justify-content: center;
            margin: 10px 0;
        }
        
        .dot {
            height: 12px;
            width: 12px;
            margin: 0 5px;
            background-color: #8C1515;
            border-radius: 50%;
            display: inline-block;
            animation: pulse 1.5s infinite ease-in-out;
        }
        
        .dot:nth-child(2) {
            animation-delay: 0.3s;
        }
        
        .dot:nth-child(3) {
            animation-delay: 0.6s;
        }
        
        /* Sidebar styling */
        .css-1aumxhk {
            background-color: #f9f9f9;
        }
        
        /* Footer */
        .footer {
            text-align: center;
            padding: 10px;
            color: #666;
            font-size: 0.8rem;
            margin-top: 2rem;
        }
    </style>
    """, unsafe_allow_html=True)

# Function to encode image to base64 for embedding
def get_image_base64(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

# Function to display the Stanford logo (replace with your actual logo path)
def display_logo():
    st.markdown("""
    <div style="text-align: center; margin-bottom: 2rem;">
        <img src="https://identity.stanford.edu/wp-content/uploads/sites/3/2020/07/stanforduniversity-stacked.png" 
             width="250px" alt="Stanford Logo">
    </div>
    """, unsafe_allow_html=True)
    
    # If you want to use a local logo, use this instead:
    # logo_base64 = get_image_base64("path/to/your/logo.png")
    # st.markdown(f"""
    # <div style="text-align: center; margin-bottom: 2rem;">
    #     <img src="data:image/png;base64,{logo_base64}" width="250px" alt="Course Helper Logo">
    # </div>
    # """, unsafe_allow_html=True)

# Loading animation component
def loading_animation():
    return st.markdown("""
    <div class="loading-dots">
        <div class="dot"></div>
        <div class="dot"></div>
        <div class="dot"></div>
    </div>
    """, unsafe_allow_html=True)

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
    # Apply custom CSS
    local_css()
    
    # Display logo
    display_logo()
    
    st.markdown("""
    <div class="login-container">
        <h1>Stanford Course Helper</h1>
        <p style="color: #666; margin-bottom: 2rem;">
            Your AI assistant for course planning and academic guidance
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Create a centered container for the login form
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        
        with st.form("login_form"):
            # Custom SUNet ID input with Stanford domain
            st.markdown("""
            <div class="sunet-input">
                <label for="sunet">SUNet ID</label>
                <input type="text" id="sunet" name="sunet" placeholder="Enter your SUNet ID">
                <span class="stanford-domain">@stanford.edu</span>
            </div>
            """, unsafe_allow_html=True)
            
            # Hidden text input that actually captures the value
            sunet_id = st.text_input("", label_visibility="collapsed").strip()
            
            # Submit button with custom styling
            submitted = st.form_submit_button("Login")
            
            if submitted:
                with st.spinner("Authenticating..."):
                    # Add a small delay to simulate authentication process
                    time.sleep(1)
                    
                    if validate_sunet(sunet_id):
                        st.session_state.authenticated = True
                        st.session_state.sunet_id = sunet_id
                        st.success("Login successful!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Invalid SUNet ID. Please try again.")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
    # Footer
    st.markdown("""
    <div class="footer">
        © 2023 Stanford University. All rights reserved.
    </div>
    """, unsafe_allow_html=True)

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

def main_app():
    # Apply custom CSS
    local_css()
    
    # Page layout
    st.markdown("""
    <h1 style="text-align: center; margin-bottom: 1rem;">
        <span style="color: #8C1515;">🎓 Stanford Course Helper</span>
    </h1>
    """, unsafe_allow_html=True)
    
    # Initialize services
    client, labeler, course_scheduler, admin_info, thread = initialize_assistants()
    sheets_service = get_google_sheets_service()
    
    if not sheets_service:
        st.error("Failed to initialize Google Sheets service. Check your credentials.")
        return
        
    spreadsheet_id = st.secrets["SPREADSHEET_ID"]
    
    # Initialize sheet if needed
    initialize_sheet_if_needed(sheets_service, spreadsheet_id)
    
    # Create a container for chat content
    chat_container = st.container()
    
    # Sidebar with user info and options
    with st.sidebar:
        st.markdown(f"""
        <div style="text-align: center; margin-bottom: 1rem;">
            <img src="https://identity.stanford.edu/wp-content/uploads/sites/3/2020/07/stanforduniversity-stacked.png" 
                 width="150px" alt="Stanford Logo">
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="background-color: white; padding: 1rem; border-radius: 10px; margin-bottom: 1.5rem;">
            <h3 style="margin-top: 0;">👋 Welcome, {st.session_state.sunet_id}!</h3>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div style="background-color: white; padding: 1rem; border-radius: 10px; margin-bottom: 1.5rem;">
            <h3 style="margin-top: 0;">💡 How I Can Help</h3>
            <ul style="padding-left: 1.5rem;">
                <li>Check course prerequisites</li>
                <li>Recommend courses for your interests</li>
                <li>Validate your course schedule</li>
                <li>Provide information about specific courses</li>
                <li>Answer questions about academic policies</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div style="background-color: white; padding: 1rem; border-radius: 10px; margin-bottom: 1.5rem;">
            <h3 style="margin-top: 0;">💬 Tips for Best Results</h3>
            <ul style="padding-left: 1.5rem;">
                <li>Use course codes (e.g., CS106B)</li>
                <li>Be specific about your requirements</li>
                <li>Mention your major/interests for recommendations</li>
                <li>Ask about specific policies by name</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        # Action buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Clear Chat", use_container_width=True):
                st.session_state.messages = []
                thread = client.beta.threads.create()
                st.rerun()
        
        with col2:
            if st.button("Logout", use_container_width=True):
                st.session_state.authenticated = False
                st.session_state.messages = []
                st.rerun()

    # Initialize chat history if not exists
    if "messages" not in st.session_state:
        st.session_state.messages = []
        # Add a welcome message
        welcome_msg = {
            "role": "assistant", 
            "content": f"Hi {st.session_state.sunet_id}! I'm your Stanford Course Helper. How can I assist you with your academic planning today?"
        }
        st.session_state.messages.append(welcome_msg)

    # Chat interface
    with chat_container:
        # Chat messages area
        chat_area = st.container()
        
        # Display chat history
        with chat_area:
            for message in st.session_state.messages:
                if message["role"] == "user":
                    st.markdown(f"""
                    <div class="user-message">
                        <strong>You:</strong><br>{message["content"]}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="assistant-message">
                        <strong>Course Helper:</strong><br>{message["content"]}
                    </div>
                    """, unsafe_allow_html=True)
        
        # Chat input
        user_input = st.chat_input("Ask about courses or academic policies...")
        
        if user_input:
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": user_input})
            
            # Rerun to display user message
            st.rerun()

    # Process the user input after rerun to show the loading animation
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user" and "processing" not in st.session_state:
        st.session_state.processing = True
        
        # Get the last user message
        prompt = st.session_state.messages[-1]["content"]
        
        # Display loading animation
        with chat_container:
            loading_placeholder = st.empty()
            with loading_placeholder:
                loading_animation()
            
            try:
                # Process through dual assistant system
                response, assistant_type = process_user_query(
                    client, thread, labeler, course_scheduler, admin_info, prompt
                )

                # Clean up the response
                cleaned_response = re.sub(r'【\d+:\d+†source】', '', response)  # Remove all source markers
                cleaned_response = cleaned_response.replace("<userStyle>Normal</userStyle>", "")  # Remove style tags
                cleaned_response = cleaned_response.strip()  # Remove any extra whitespace
                
                # Add to chat history
                st.session_state.messages.append({"role": "assistant", "content": cleaned_response})
                
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
                    st.warning("Failed to log this interaction. Please contact support if issues persist.")
                    
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": "I'm sorry, I encountered an error processing your request. Please try again later."
                })
            
            # Clear the loading animation and rerun to display the response
            loading_placeholder.empty()
            del st.session_state.processing
            st.rerun()

# Main flow control
if not st.session_state.authenticated:
    login_page()
else:
    main_app()

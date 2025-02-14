import streamlit as st
import time
from openai import OpenAI

# Initialize session state for login
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

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
    client, assistant, thread = initialize_assistant()
    
    st.title("🎓 Stanford Course Helper")
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
            thread = client.beta.threads.create()
            st.rerun()

# Main flow control
if not st.session_state.authenticated:
    login_page()
else:
    main_app()
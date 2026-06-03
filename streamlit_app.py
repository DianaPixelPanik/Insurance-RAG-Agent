import streamlit as st
import requests
import json
import time
import os
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


def query_agent(user_input: str, user_id: str = "default_user") -> str:
    """Send user input to the backend agent API."""
    try:
        response = requests.post(
            f"{BACKEND_URL}/query",
            json={"user_input": user_input, "user_id": user_id},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["response"]
    except requests.exceptions.HTTPError as e:
        st.error(f"HTTP error: {e}")
        return f"Error: {e}"
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to backend. Make sure backend_app.py is running on port 8000.")
        return "Error: Backend unavailable."
    except requests.exceptions.Timeout:
        st.error("Request timed out.")
        return "Error: Timeout."
    except (json.JSONDecodeError, KeyError) as e:
        st.error(f"Invalid response from backend: {e}")
        return "Error: Invalid response."
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        return f"Error: {e}"


def set_custom_css():
    st.markdown(
        """
        <style>
            .main { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
            .stTextInput input { border-radius: 20px; padding: 10px 15px; }
            .chat-message { padding: 1.5rem; border-radius: 15px; margin-bottom: 1rem;
                            box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
            .user-message { background: #ffffff; border: 1px solid #e0e0e0; }
            .bot-message { background: #007bff; color: white; }
            .stMarkdown table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
            .stMarkdown th { background-color: #007bff; color: white; padding: 12px;
                             border: 1px solid #ddd; text-align: left; }
            .stMarkdown td { padding: 12px; border: 1px solid #ddd; text-align: left; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main():
    st.set_page_config(page_title="Insurance AI Assistant", page_icon="🛡️", layout="wide")
    set_custom_css()

    st.title("🛡️ Insurance AI — Knowledge Retrieval System")
    st.markdown("Ask your insurance-related questions.")

    # Sidebar
    with st.sidebar:
        st.header("Options")

        user_id = st.text_input("User ID (for session memory)", value="user_1")

        if st.button("ℹ️ About"):
            st.info(
                "This AI Assistant answers insurance-related questions "
                "using your customer data and general insurance knowledge."
            )

        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.rerun()

        st.markdown("---")
        st.caption("Powered by Claude (Anthropic) via Agno")

    # Chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"], unsafe_allow_html=True)

    # Input
    if prompt := st.chat_input("Ask a question about insurance..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            response_container = st.empty()
            agent_response = query_agent(prompt, user_id=user_id)

            # Typing animation
            for i in range(0, len(agent_response), 5):
                response_container.markdown(agent_response[: i + 5] + "▌", unsafe_allow_html=True)
                time.sleep(0.01)
            response_container.markdown(agent_response, unsafe_allow_html=True)

        st.session_state.messages.append({"role": "assistant", "content": agent_response})


if __name__ == "__main__":
    main()

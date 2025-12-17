"""
Streamlit UI for BrowserFreak - AI-powered browser automation
"""

import asyncio
import base64
import concurrent.futures
import json
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, cast

import streamlit as st

try:
    # Try relative imports first (for development)
    from .browser_agent import run_agent_workflow
    from .browser_manager import health_check
    from .config import settings
    from .exceptions import BrowserFreakError
    from .logging_config import log
except ImportError:
    # Fall back to absolute imports (for installed package)
    from browserfreak.browser_agent import run_agent_workflow
    from browserfreak.browser_manager import health_check
    from browserfreak.config import settings
    from browserfreak.exceptions import BrowserFreakError
    from browserfreak.logging_config import log

# Set page configuration
st.set_page_config(
    page_title=settings.ui.page_title,
    page_icon=settings.ui.page_icon,
    layout=cast(
        Literal["centered", "wide"],
        settings.ui.layout if settings.ui.layout in ["centered", "wide"] else "wide",
    ),
    initial_sidebar_state=cast(
        Literal["auto", "expanded", "collapsed"],
        (
            settings.ui.sidebar_state
            if settings.ui.sidebar_state in ["auto", "expanded", "collapsed"]
            else "auto"
        ),
    ),
)


# Initialize session state
def initialize_session_state():
    """Initialize all necessary session state variables"""
    # Core chat state
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "log_entries" not in st.session_state:
        st.session_state.log_entries = []

    # Approval system state
    if "pending_approval" not in st.session_state:
        st.session_state.pending_approval = False

    if "pending_action" not in st.session_state:
        st.session_state.pending_action = ""

    # Execution state
    if "execution_in_progress" not in st.session_state:
        st.session_state.execution_in_progress = False

    if "agent_state" not in st.session_state:
        st.session_state.agent_state = None

    if "task_complete" not in st.session_state:
        st.session_state.task_complete = False

    # Session management
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    if "last_activity" not in st.session_state:
        st.session_state.last_activity = datetime.now()

    # UI state
    if "input_placeholder" not in st.session_state:
        st.session_state.input_placeholder = ""

    # Error tracking
    if "error_count" not in st.session_state:
        st.session_state.error_count = 0

    if "last_error" not in st.session_state:
        st.session_state.last_error = None


# Display log entries with proper formatting
def display_log(log_entries: List[Dict[str, Any]]):
    """Display the agent's execution log with appropriate formatting"""
    if not log_entries:
        st.info("No log entries yet. Launch the agent to see execution details.")
        return

    for entry in log_entries:
        entry_type = entry.get("type", "unknown")
        content = entry.get("content", "")

        if entry_type == "thought":
            st.markdown(f"💡 **Agent Thought:** {content}")
        elif entry_type == "action":
            st.markdown(f"🛠️ **Tool Call:** `{content}`")
        elif entry_type == "observation":
            st.markdown(f"✅ **Observation:** {content}")
        elif entry_type == "error":
            st.error(f"⚠️ **Error:** {content}")
        else:
            st.text(f"📝 {content}")

        st.divider()


# Task templates for quick selection
TASK_TEMPLATES = {
    "Basic Navigation": "Navigate to example.com and describe what you see",
    "Form Filling": "Go to a contact form and fill it out with sample data",
    "E-commerce": "Find the highest rated chair on Amazon",
    "Search Task": "Search for 'Python programming' on Google and click the first result",
    "Content Interaction": "Scroll through a news article and summarize the main points",
    "Custom": "",
}


async def execute_agent_task(
    task: str, use_real_browser: Optional[bool] = None, max_iterations: Optional[int] = None
) -> tuple[List[Dict[str, Any]], bool, str]:
    """
    Execute agent task with proper configuration and error handling.

    Args:
        task: The task description
        use_real_browser: Override browser setting (optional)
        max_iterations: Override max iterations (optional)

    Returns:
        Tuple of (log_entries, requires_approval, action_details)
    """
    log_entries = []
    start_time = datetime.now()

    # Use configuration defaults if not specified
    use_real_browser = (
        use_real_browser if use_real_browser is not None else settings.agent.use_real_browser
    )
    max_iterations = max_iterations if max_iterations is not None else settings.agent.max_iterations

    try:
        log.info(
            f"Starting agent execution for task: '{task}' (real_browser={use_real_browser}, max_iterations={max_iterations})"
        )

        # Add initial log entry
        log_entries.append(
            {
                "type": "thought",
                "timestamp": start_time.isoformat(),
                "content": f"🚀 Starting execution for task: '{task}'",
            }
        )

        # Execute the agent workflow
        result = await run_agent_workflow(
            task, max_iterations=max_iterations, use_real_browser=use_real_browser
        )

        # Process messages and create log entries
        for message in result.get("messages", []):
            entry = {
                "timestamp": datetime.now().isoformat(),
                "role": message.get("role", "unknown"),
            }

            if message.get("role") == "user":
                entry.update(
                    {"type": "thought", "content": f"🧠 User request: {message['content']}"}
                )
            elif message.get("role") == "assistant":
                if "tool_calls" in message:
                    for tool_call in message["tool_calls"]:
                        log_entries.append(
                            {
                                "type": "action",
                                "timestamp": datetime.now().isoformat(),
                                "content": f"{tool_call['name']} with args: {tool_call['args']}",
                                "tool_call": tool_call,
                            }
                        )
                else:
                    entry.update(
                        {"type": "thought", "content": f"💡 Agent response: {message['content']}"}
                    )
            elif message.get("role") == "tool":
                entry.update(
                    {"type": "observation", "content": f"✅ Tool result: {message['content']}"}
                )
            else:
                continue

            log_entries.append(entry)

        # Check if human approval is needed
        browser_action = result.get("browser_action")
        if browser_action and settings.agent.enable_security_checks:
            log_entries.append(
                {
                    "type": "thought",
                    "timestamp": datetime.now().isoformat(),
                    "content": f"⚠️ Human approval required for: {browser_action}",
                }
            )
            log.warning(f"Security approval required for action: {browser_action}")
            return log_entries, True, browser_action

        # Task completion
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        log_entries.append(
            {
                "type": "thought",
                "timestamp": end_time.isoformat(),
                "content": f"🎉 Task completed successfully in {duration:.1f}s!",
            }
        )

        log.info(f"Agent task completed successfully in {duration:.1f}s")
        return log_entries, False, ""

    except BrowserFreakError as e:
        error_msg = f"BrowserFreak error: {str(e)}"
        log.error(error_msg)
        log_entries.append(
            {"type": "error", "timestamp": datetime.now().isoformat(), "content": f"❌ {error_msg}"}
        )
        return log_entries, False, ""

    except Exception as e:
        error_msg = f"Unexpected error during execution: {str(e)}"
        log.error(error_msg, exc_info=True)
        log_entries.append(
            {"type": "error", "timestamp": datetime.now().isoformat(), "content": f"❌ {error_msg}"}
        )
        return log_entries, False, ""


# Main execution handler
async def handle_agent_execution(
    task: str, use_real_browser: Optional[bool] = None, max_iterations: Optional[int] = None
):
    """Handle the complete agent execution workflow"""
    st.session_state.execution_in_progress = True
    st.session_state.log_entries = []
    st.session_state.task_complete = False

    try:
        # Execute the agent task with custom settings
        new_logs, requires_approval, action_details = await execute_agent_task(
            task, use_real_browser=use_real_browser, max_iterations=max_iterations
        )

        # Update log entries
        st.session_state.log_entries.extend(new_logs)

        if requires_approval:
            st.session_state.pending_approval = True
            st.session_state.pending_action = action_details
            st.session_state.execution_in_progress = False
            return

        # If no approval needed, continue to completion
        st.session_state.task_complete = True
        st.session_state.execution_in_progress = False

    except Exception as e:
        log.error(f"Agent execution failed: {e}")
        st.session_state.log_entries.append(
            {
                "type": "error",
                "timestamp": datetime.now().isoformat(),
                "content": f"❌ Execution failed: {str(e)}",
            }
        )
        st.session_state.execution_in_progress = False


def create_download_link(data: str, filename: str, link_text: str) -> str:
    """Create a download link for data export"""
    b64 = base64.b64encode(data.encode()).decode()
    href = f'<a href="data:file/txt;base64,{b64}" download="{filename}">{link_text}</a>'
    return href


def display_health_status():
    """Display system health information"""
    try:
        # Use asyncio in a separate thread to avoid Streamlit event loop conflicts
        def run_health_check():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(health_check())
            finally:
                loop.close()

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_health_check)
            health_status = future.result(timeout=10)  # 10 second timeout

        if health_status["status"] == "healthy":
            st.success("✅ System Health: Good")
            st.info("🎯 Browser automation is fully functional")
        elif health_status["status"] == "degraded":
            st.warning("⚠️ System Health: Degraded")
            st.info("🔧 Some features may be limited. Try using mock mode for testing.")
        else:
            st.error("❌ System Health: Unhealthy")
            st.warning(
                "🚫 Browser automation is not available. The app will work in mock mode only."
            )

        with st.expander("Health Details"):
            st.write(f"**Service:** {health_status['service']}")
            st.write(f"**Status:** {health_status['status']}")
            if "response_time" in health_status:
                st.write(f"**Response Time:** {health_status['response_time']}s")

            if health_status.get("checks"):
                st.write("**Checks:**")
                for check, status in health_status["checks"].items():
                    if status == "pass":
                        st.write(f"  ✅ {check}")
                    else:
                        st.write(f"  ❌ {check}: {status}")

    except concurrent.futures.TimeoutError:
        st.error("❌ Health check timed out")
        st.info("💡 The system may be busy. Try refreshing the page.")
    except Exception as e:
        st.error(f"❌ Health check failed: {e}")
        st.warning(
            "🚫 Browser system is not available. You can still use the chat interface in mock mode."
        )


def display_message(message: Dict[str, Any]):
    """Display a single chat message with proper styling"""
    role = message.get("role", "unknown")
    content = message.get("content", "")
    timestamp = message.get("timestamp", datetime.now())

    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp)

    # Format timestamp
    time_str = timestamp.strftime("%H:%M")

    if role == "user":
        # User message (right-aligned)
        col1, col2 = st.columns([1, 3])
        with col2:
            st.markdown(
                f"""
            <div style="background-color: #007bff; color: white; padding: 10px; border-radius: 10px; margin: 5px 0; text-align: right;">
                <div style="font-size: 0.8em; opacity: 0.8; margin-bottom: 5px;">{time_str}</div>
                {content}
            </div>
            """,
                unsafe_allow_html=True,
            )
    elif role == "assistant":
        # Assistant message (left-aligned)
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(
                f"""
            <div style="background-color: #f1f1f1; color: black; padding: 10px; border-radius: 10px; margin: 5px 0;">
                <div style="font-size: 0.8em; opacity: 0.8; margin-bottom: 5px;">🤖 BrowserFreak • {time_str}</div>
                {content}
            </div>
            """,
                unsafe_allow_html=True,
            )
    elif role == "tool":
        # Tool execution message
        st.markdown(
            f"""
        <div style="background-color: #e9ecef; color: #495057; padding: 8px; border-radius: 8px; margin: 3px 0; border-left: 3px solid #28a745;">
            <div style="font-size: 0.8em; opacity: 0.7;">🔧 Tool Result • {time_str}</div>
            <div style="font-family: monospace; font-size: 0.9em; margin-top: 5px;">{content}</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    elif role == "error":
        # Error message
        st.markdown(
            f"""
        <div style="background-color: #f8d7da; color: #721c24; padding: 8px; border-radius: 8px; margin: 3px 0; border-left: 3px solid #dc3545;">
            <div style="font-size: 0.8em; opacity: 0.7;">❌ Error • {time_str}</div>
            <div style="margin-top: 5px;">{content}</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    elif role == "system":
        # System message
        st.markdown(
            f"""
        <div style="background-color: #fff3cd; color: #856404; padding: 6px; border-radius: 6px; margin: 2px 0; border-left: 3px solid #ffc107;">
            <div style="font-size: 0.8em;">ℹ️ System • {time_str}</div>
            <div style="margin-top: 3px;">{content}</div>
        </div>
        """,
            unsafe_allow_html=True,
        )


def display_chat_messages():
    """Display all chat messages in the conversation"""
    if not st.session_state.messages:
        # Welcome message
        st.markdown(
            """
        <div style="text-align: center; padding: 40px; color: #666;">
            <div style="font-size: 3em; margin-bottom: 20px;">🤖</div>
            <h3>Welcome to BrowserFreak!</h3>
            <p>I'm your AI-powered browser automation assistant. Describe what you'd like me to do in the browser, and I'll handle it for you.</p>
            <p style="font-size: 0.9em; margin-top: 20px;">Try asking me to navigate to a website, fill out a form, or search for information.</p>
        </div>
        """,
            unsafe_allow_html=True,
        )
        return

    for message in st.session_state.messages:
        display_message(message)


def process_user_message_sync(
    user_input: str, use_real_browser: bool = False, max_iterations: int = 5
):
    """Process a user message and generate agent response (synchronous wrapper)"""
    # Add user message to chat
    user_message = {"role": "user", "content": user_input, "timestamp": datetime.now().isoformat()}
    st.session_state.messages.append(user_message)

    # Add typing indicator
    typing_message = {
        "role": "system",
        "content": "🤖 BrowserFreak is thinking...",
        "timestamp": datetime.now().isoformat(),
    }
    st.session_state.messages.append(typing_message)

    try:
        # Use asyncio.run() in a separate thread to avoid Streamlit event loop conflicts
        def run_async_task():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    execute_agent_task(
                        user_input, use_real_browser=use_real_browser, max_iterations=max_iterations
                    )
                )
            finally:
                loop.close()

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_async_task)
            log_entries, requires_approval, action_details = future.result(
                timeout=30
            )  # 30 second timeout

        # Remove typing indicator
        if st.session_state.messages and st.session_state.messages[-1]["role"] == "system":
            st.session_state.messages.pop()

        # Process the results and create chat messages
        agent_response = ""
        tool_results = []

        for log_entry in log_entries:
            entry_type = log_entry.get("type", "")
            content = log_entry.get("content", "")

            if entry_type == "thought" and "Agent response:" in content:
                # Extract agent response
                agent_response = content.replace("💡 Agent response: ", "")
            elif entry_type == "action":
                # Tool call
                tool_msg = {
                    "role": "assistant",
                    "content": f"🔧 Executing: {content}",
                    "timestamp": datetime.now().isoformat(),
                }
                st.session_state.messages.append(tool_msg)
            elif entry_type == "observation":
                # Tool result
                if "Tool result:" in content:
                    tool_result = content.replace("✅ Tool result: ", "")
                    tool_results.append(tool_result)
                elif "Human approved action:" in content:
                    approval_msg = {
                        "role": "system",
                        "content": f"✅ {content.replace('Human approved action: ', '')}",
                        "timestamp": datetime.now().isoformat(),
                    }
                    st.session_state.messages.append(approval_msg)
            elif entry_type == "error":
                error_msg = {
                    "role": "error",
                    "content": content.replace("❌ ", ""),
                    "timestamp": datetime.now().isoformat(),
                }
                st.session_state.messages.append(error_msg)

        # Add agent response if any
        if agent_response:
            response_msg = {
                "role": "assistant",
                "content": agent_response,
                "timestamp": datetime.now().isoformat(),
            }
            st.session_state.messages.append(response_msg)

        # Add tool results
        for tool_result in tool_results:
            tool_msg = {
                "role": "tool",
                "content": tool_result,
                "timestamp": datetime.now().isoformat(),
            }
            st.session_state.messages.append(tool_msg)

        # Handle approval required
        if requires_approval:
            st.session_state.pending_approval = True
            st.session_state.pending_action = action_details

            approval_msg = {
                "role": "system",
                "content": f"⚠️ **Security Approval Required:** {action_details}",
                "timestamp": datetime.now().isoformat(),
            }
            st.session_state.messages.append(approval_msg)

    except concurrent.futures.TimeoutError:
        # Track error
        st.session_state.error_count += 1
        st.session_state.last_error = "Request timed out after 30 seconds"

        # Remove typing indicator
        if st.session_state.messages and st.session_state.messages[-1]["role"] == "system":
            st.session_state.messages.pop()

        # Add timeout error message
        error_msg = {
            "role": "error",
            "content": "Request timed out. The operation took too long to complete.",
            "timestamp": datetime.now().isoformat(),
        }
        st.session_state.messages.append(error_msg)

    except Exception as e:
        # Track error
        st.session_state.error_count += 1
        st.session_state.last_error = str(e)

        # Remove typing indicator
        if st.session_state.messages and st.session_state.messages[-1]["role"] == "system":
            st.session_state.messages.pop()

        # Add error message
        error_msg = {
            "role": "error",
            "content": f"Failed to process request: {str(e)}",
            "timestamp": datetime.now().isoformat(),
        }
        st.session_state.messages.append(error_msg)


def handle_approval_response(approved: bool):
    """Handle user approval/denial response"""
    if approved:
        # Add approval message
        approval_msg = {
            "role": "system",
            "content": f"✅ Approved: {st.session_state.pending_action}",
            "timestamp": datetime.now().isoformat(),
        }
        st.session_state.messages.append(approval_msg)

        # Mark task as complete
        st.session_state.task_complete = True
    else:
        # Add denial message
        denial_msg = {
            "role": "error",
            "content": f"❌ Denied: {st.session_state.pending_action}",
            "timestamp": datetime.now().isoformat(),
        }
        st.session_state.messages.append(denial_msg)

        # Reset execution state
        st.session_state.execution_in_progress = False

    # Clear approval state
    st.session_state.pending_approval = False
    st.session_state.pending_action = ""


# Main UI
def main():
    """Main Streamlit application - Chat-like interface"""
    initialize_session_state()

    # Custom CSS for better chat styling
    st.markdown(
        """
    <style>
    .chat-container {
        max-height: 600px;
        overflow-y: auto;
        padding: 10px;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        background-color: #fafafa;
        margin-bottom: 20px;
    }
    .input-container {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background-color: white;
        padding: 20px;
        border-top: 1px solid #e0e0e0;
        z-index: 1000;
    }
    .main-content {
        margin-bottom: 120px;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    # Sidebar for settings and status
    with st.sidebar:
        st.title("⚙️ Settings")

        # Agent settings
        st.subheader("🤖 Agent Configuration")
        use_real_browser = st.checkbox(
            "Use Real Browser",
            value=settings.agent.use_real_browser,
            help="Use actual browser instead of mock mode",
        )
        max_iterations = st.slider(
            "Max Iterations",
            min_value=1,
            max_value=20,
            value=settings.agent.max_iterations,
            help="Maximum steps the agent can take",
        )
        st.checkbox(
            "Security Checks",
            value=settings.agent.enable_security_checks,
            help="Enable approval for destructive actions",
        )

        st.divider()

        # Status section
        st.subheader("📊 Status")
        display_health_status()

        # Conversation info
        st.subheader("💬 Conversation")
        st.write(f"**Messages:** {len(st.session_state.messages)}")
        st.write(f"**Session ID:** {st.session_state.conversation_id}")

        # Error tracking
        if st.session_state.error_count > 0:
            st.subheader("⚠️ Recent Issues")
            st.warning(f"**Errors encountered:** {st.session_state.error_count}")
            if st.session_state.last_error:
                with st.expander("Last Error Details"):
                    st.code(str(st.session_state.last_error), language="text")
            st.info("💡 Try using mock mode or check the browser setup if issues persist.")

        # Action buttons
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Clear Chat", use_container_width=True):
                initialize_session_state()
                st.rerun()
        with col2:
            if st.button("📥 Export", use_container_width=True):
                if st.session_state.messages:
                    chat_json = json.dumps(st.session_state.messages, indent=2)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"browserfreak_chat_{timestamp}.json"
                    st.markdown(
                        create_download_link(chat_json, filename, "📥 Download Chat"),
                        unsafe_allow_html=True,
                    )

    # Main chat interface
    st.title("🤖 BrowserFreak Chat")
    st.markdown("*Your AI-powered browser automation assistant*")

    # Chat container
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    display_chat_messages()
    st.markdown("</div>", unsafe_allow_html=True)

    # Security approval section (if needed)
    if st.session_state.pending_approval:
        st.error("⚠️ **Security Approval Required**")
        st.markdown(f"**Action:** {st.session_state.pending_action}")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Approve", type="primary", use_container_width=True):
                handle_approval_response(True)
                st.rerun()
        with col2:
            if st.button("❌ Deny", type="secondary", use_container_width=True):
                handle_approval_response(False)
                st.rerun()

    # Chat input at the bottom
    st.markdown('<div class="input-container">', unsafe_allow_html=True)

    # Quick action buttons
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button(
            "🌐 Navigate", use_container_width=True, disabled=st.session_state.execution_in_progress
        ):
            st.session_state.input_placeholder = "Navigate to example.com and describe what you see"
            st.rerun()
    with col2:
        if st.button(
            "📝 Fill Form",
            use_container_width=True,
            disabled=st.session_state.execution_in_progress,
        ):
            st.session_state.input_placeholder = (
                "Go to a contact form and fill it out with sample data"
            )
            st.rerun()
    with col3:
        if st.button(
            "🛒 Shop", use_container_width=True, disabled=st.session_state.execution_in_progress
        ):
            st.session_state.input_placeholder = "Find the highest rated chair on Amazon"
            st.rerun()
    with col4:
        if st.button(
            "🔍 Search", use_container_width=True, disabled=st.session_state.execution_in_progress
        ):
            st.session_state.input_placeholder = "Search for 'Python programming' on Google"
            st.rerun()

    # Main input area
    user_input = st.text_area(
        "Type your request...",
        placeholder=getattr(
            st.session_state,
            "input_placeholder",
            "Describe what you'd like me to do in the browser...",
        ),
        height=80,
        key="user_input",
        disabled=st.session_state.execution_in_progress,
        label_visibility="collapsed",
    )

    # Send button
    if st.button(
        "🚀 Send",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.execution_in_progress or not user_input.strip(),
    ):
        # Clear placeholder
        if hasattr(st.session_state, "input_placeholder"):
            del st.session_state.input_placeholder

        # Process the message
        process_user_message_sync(
            user_input.strip(), use_real_browser=use_real_browser, max_iterations=max_iterations
        )
        st.rerun()

    # Status indicator
    if st.session_state.execution_in_progress:
        st.info("🤖 BrowserFreak is working on your request...")

    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()

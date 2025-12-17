"""
Browser automation agent for BrowserFreak
"""

import asyncio
from typing import Any, Dict, List, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from .browser_manager import close_browser_context, create_browser_context, navigate_to_url
from .decision_engine import decision_engine
from .exceptions import ValidationError
from .logging_config import log
from .security import security_manager
from .tools import BrowserContext, execute_tool


# Define the state structure for our graph
class AgentState(TypedDict):
    messages: List[Dict[str, Any]]  # Conversation history
    page_map: str  # Current DOM representation
    browser_action: str  # Pending action requiring approval
    task_complete: bool  # Flag to indicate task completion


async def security_check_node(
    state: AgentState, context: Optional[BrowserContext] = None
) -> AgentState:
    """Check the current page state and validate actions for security"""
    log.debug("Running security check...")

    # Update page state if we have a browser context
    if context:
        from .tools import get_page_state_wrapper

        state["page_map"] = await get_page_state_wrapper(context)
    else:
        # Mock page state for testing
        state["page_map"] = "<html><body><button>Submit</button></body></html>"

    # Check if there's a pending browser action that needs approval
    if state.get("browser_action"):
        log.info(f"Waiting for human approval on action: {state['browser_action']}")
        # In a real implementation, this would pause and wait for human input
        # For now, we'll simulate approval by clearing the action
        state["browser_action"] = ""

    log.debug("Security check completed")
    return state


async def agent_node(state: AgentState) -> AgentState:
    """Agent node that decides the next action"""
    log.debug("Agent node: Deciding next action...")

    # Get agent decision
    result = await decision_engine.make_decision(state["messages"], state["page_map"])

    # Check if the agent wants to use a tool
    if "tool_calls" in result:
        tool_call = result["tool_calls"][0]
        action_name = tool_call["name"]
        action_args = tool_call["args"]

        # Check for destructive actions requiring approval
        if security_manager.should_require_approval(action_name, action_args):
            approval_message = security_manager.get_approval_message(action_name, action_args)
            log.warning(f"Destructive action detected: {approval_message}")
            state["browser_action"] = approval_message
            state["messages"].append({"role": "assistant", "tool_calls": [tool_call]})
            return state

        # Add the tool call to messages
        state["messages"].append({"role": "assistant", "tool_calls": [tool_call]})
        return state

    elif "FINISH" in str(result.get("content", "")).upper():
        state["task_complete"] = True
        state["messages"].append({"role": "assistant", "content": "Task completed successfully"})
        return state
    else:
        # For content responses, add the message and mark task as complete
        # This prevents infinite loops for tasks that don't require tool use
        state["messages"].append({"role": "assistant", "content": result["content"]})
        state["task_complete"] = True
        return state


async def tool_node(state: AgentState, context: Optional[BrowserContext] = None) -> AgentState:
    """Execute the tool requested by the agent"""
    log.debug("Tool node: Executing requested action...")

    # Get the last message (should be a tool call)
    last_message = state["messages"][-1]

    if "tool_calls" in last_message:
        tool_call = last_message["tool_calls"][0]
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        log.info(f"Executing tool: {tool_name}")

        # Execute the tool
        result = await execute_tool(tool_name, tool_args, context)

        # Update page state for get_page_state tool
        if tool_name == "get_page_state" and context:
            from .tools import get_page_state_wrapper

            state["page_map"] = await get_page_state_wrapper(context)

        # Add tool result to messages
        tool_result = {
            "role": "tool",
            "tool_call_id": tool_call.get("id", "1"),
            "content": f"Tool {tool_name} executed with result: {result}",
        }
        state["messages"].append(tool_result)

        # Mark task as complete after tool execution
        state["task_complete"] = True

        if result:
            log.info(f"Tool {tool_name} executed successfully")
        else:
            log.warning(f"Tool {tool_name} failed")

    return state


def create_workflow() -> Any:
    """Create and return a LangGraph workflow"""
    log.debug("Building LangGraph workflow...")

    # Create the workflow
    workflow = StateGraph(AgentState)

    # Define node functions with context handling
    async def security_check_wrapper(state: AgentState):
        return await security_check_node(state)

    async def tool_wrapper(state: AgentState):
        return await tool_node(state)

    # Add nodes to the graph
    workflow.add_node("security_check", security_check_wrapper)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tool", tool_wrapper)

    # Define conditional edges
    def should_request_approval(state: AgentState) -> str:
        """Check if human approval is needed"""
        return "human_approval" if state.get("browser_action", "") else "agent"

    def should_continue_to_tool(state: AgentState) -> str:
        """Check if agent wants to use a tool"""
        last_message = state["messages"][-1]
        has_tool_calls = "tool_calls" in last_message
        return "tool" if has_tool_calls else END

    def should_end_workflow(state: AgentState) -> str:
        """Check if task is complete"""
        return END if state.get("task_complete", False) else "security_check"

    # Add conditional edges
    workflow.add_conditional_edges(
        "security_check",
        should_request_approval,
        {"agent": "agent", "human_approval": "human_approval"},
    )

    workflow.add_conditional_edges("agent", should_continue_to_tool, {"tool": "tool", END: END})

    workflow.add_conditional_edges(
        "tool", should_end_workflow, {END: END, "security_check": "security_check"}
    )

    # Set entry point
    workflow.set_entry_point("security_check")

    # Add human approval node
    async def human_approval_node(state: AgentState) -> AgentState:
        """Human approval node - simulates approval for now"""
        action = state.get("browser_action", "")
        log.info(f"Human approval required for: {action}")
        # Simulate approval by clearing the action
        state["browser_action"] = ""
        return state

    workflow.add_node("human_approval", human_approval_node)
    workflow.add_edge("human_approval", "agent")

    # Compile the workflow
    try:
        memory = MemorySaver()
        app = workflow.compile(checkpointer=memory, interrupt_before=["human_approval"])
    except Exception as e:
        log.warning(f"Checkpointer configuration failed: {e}, using simple compilation")
        app = workflow.compile()

    log.info("LangGraph workflow built successfully")
    return app


async def run_agent_workflow(
    initial_task: str, max_iterations: int = 5, use_real_browser: bool = False
) -> Dict[str, Any]:
    """
    Run the browser automation agent workflow with enhanced error handling

    Args:
        initial_task: The task description to execute
        max_iterations: Maximum number of iterations
        use_real_browser: Whether to use real browser or mock mode

    Returns:
        Final workflow state
    """
    log.info(f"Starting browser agent with task: {initial_task}")

    # Validate input parameters
    if not initial_task or not initial_task.strip():
        raise ValidationError("Task description cannot be empty")

    if max_iterations < 1 or max_iterations > 20:
        raise ValidationError("max_iterations must be between 1 and 20")

    # Create initial state
    state: AgentState = {
        "messages": [{"role": "user", "content": initial_task.strip()}],
        "page_map": "",
        "browser_action": "",
        "task_complete": False,
    }

    # Initialize browser context if needed
    browser_context: Optional[BrowserContext] = None
    browser_creation_attempts = 0
    max_browser_attempts = 3

    if use_real_browser:
        while browser_creation_attempts < max_browser_attempts:
            try:
                log.info(
                    f"Creating browser context (attempt {browser_creation_attempts + 1}/{max_browser_attempts})..."
                )
                browser_context = await create_browser_context()

                # Test the browser context with a simple navigation
                await navigate_to_url(browser_context, "about:blank")
                log.info("Browser context created and tested successfully")
                break

            except Exception as e:
                browser_creation_attempts += 1
                log.warning(
                    f"Browser context creation attempt {browser_creation_attempts} failed: {e}"
                )

                if browser_creation_attempts >= max_browser_attempts:
                    log.error(
                        f"Failed to create browser context after {max_browser_attempts} attempts, falling back to mock mode"
                    )
                    use_real_browser = False
                    browser_context = None
                else:
                    # Wait before retrying
                    await asyncio.sleep(1 * browser_creation_attempts)

    try:
        # Create and run workflow with error recovery
        workflow_attempts = 0
        max_workflow_attempts = 2

        while workflow_attempts < max_workflow_attempts:
            try:
                app = create_workflow()

                # Execute the workflow
                log.debug(
                    f"Executing workflow (attempt {workflow_attempts + 1}/{max_workflow_attempts})..."
                )
                config = {
                    "configurable": {"thread_id": "default"},
                    "recursion_limit": max_iterations,
                }
                final_state = await app.ainvoke(state, config=config)

                log.info("Workflow completed successfully")
                return dict(final_state)

            except Exception as workflow_error:
                workflow_attempts += 1
                log.warning(
                    f"Workflow execution attempt {workflow_attempts} failed: {workflow_error}"
                )

                if workflow_attempts >= max_workflow_attempts:
                    log.error(f"Workflow failed after {max_workflow_attempts} attempts")
                    raise workflow_error
                else:
                    # Reset state for retry
                    state["browser_action"] = ""
                    await asyncio.sleep(0.5)

        # This should not be reached, but just in case
        raise RuntimeError("Workflow execution failed unexpectedly")

    except Exception as e:
        # Enhanced error logging and handling
        error_details = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "task": initial_task[:100],
            "use_real_browser": use_real_browser,
            "max_iterations": max_iterations,
            "browser_context_created": browser_context is not None,
        }

        log.error(f"Agent workflow failed: {error_details}")

        # Return error state instead of raising
        return {
            "messages": state["messages"],
            "page_map": state["page_map"],
            "browser_action": state["browser_action"],
            "task_complete": False,
            "error": error_details,
        }

    finally:
        # Clean up browser context with enhanced error handling
        if browser_context:
            cleanup_attempts = 0
            max_cleanup_attempts = 3

            while cleanup_attempts < max_cleanup_attempts:
                try:
                    await close_browser_context(browser_context)
                    log.info("Browser context closed successfully")
                    break
                except Exception as cleanup_error:
                    cleanup_attempts += 1
                    log.warning(
                        f"Browser cleanup attempt {cleanup_attempts} failed: {cleanup_error}"
                    )

                    if cleanup_attempts >= max_cleanup_attempts:
                        log.error(
                            f"Failed to cleanup browser context after {max_cleanup_attempts} attempts"
                        )
                    else:
                        await asyncio.sleep(0.5)


# Legacy function for backward compatibility
def is_destructive_action(action: str) -> bool:
    """Check if an action is destructive (legacy function)"""
    return security_manager.is_destructive_action(action)


# Example usage
if __name__ == "__main__":
    example_task = "Click the submit button on the page"

    print("🚀 Browser Agent")
    print("=" * 50)

    # Run the agent workflow
    asyncio.run(run_agent_workflow(example_task))

    print("\n" + "=" * 50)
    print("Testing destructive action detection:")

    # Test destructive action
    destructive_task = "Click the pay now button to complete purchase"
    asyncio.run(run_agent_workflow(destructive_task))

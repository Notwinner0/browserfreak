"""
Command-line interface for BrowserFreak
"""

import asyncio
import sys
from typing import Optional

import click

from .browser_agent import run_agent_workflow
from .browser_manager import health_check
from .config import settings
from .logging_config import log


@click.group()
@click.option("--log-level", default=None, help="Set logging level (DEBUG, INFO, WARNING, ERROR)")
@click.option("--config", default=None, help="Path to config file")
def cli(log_level: Optional[str], config: Optional[str]):
    """BrowserFreak - AI-powered browser automation framework"""

    # Configure logging level if specified
    if log_level:
        settings.agent.log_level = log_level.upper()

    # Re-initialize logging with new level
    from .logging_config import setup_logging

    setup_logging()


@cli.command()
@click.argument("task")
@click.option("--real-browser", is_flag=True, help="Use real browser instead of mock mode")
@click.option(
    "--max-iterations", default=None, type=int, help="Maximum iterations for agent workflow"
)
def run(task: str, real_browser: bool, max_iterations: Optional[int]):
    """Run a browser automation task"""

    if max_iterations:
        settings.agent.max_iterations = max_iterations

    if real_browser:
        settings.agent.use_real_browser = True

    log.info(f"Starting BrowserFreak with task: {task}")
    log.info(
        f"Configuration: real_browser={settings.agent.use_real_browser}, max_iterations={settings.agent.max_iterations}"
    )

    try:
        result = asyncio.run(
            run_agent_workflow(
                task,
                max_iterations=settings.agent.max_iterations,
                use_real_browser=settings.agent.use_real_browser,
            )
        )

        if result.get("task_complete"):
            log.info("Task completed successfully!")
            sys.exit(0)
        else:
            log.warning("Task did not complete successfully")
            sys.exit(1)

    except Exception as e:
        log.error(f"Task execution failed: {e}")
        sys.exit(1)


@cli.command()
def health():
    """Check system health"""

    log.info("Running health check...")

    try:
        health_status = asyncio.run(health_check())

        click.echo(f"Service: {health_status['service']}")
        click.echo(f"Status: {health_status['status']}")
        click.echo(f"Response Time: {health_status.get('response_time', 'N/A')}s")

        if health_status["status"] == "healthy":
            click.secho("✅ All checks passed", fg="green")
            sys.exit(0)
        else:
            click.secho("❌ Health check failed", fg="red")
            if "error" in health_status:
                click.echo(f"Error: {health_status['error']}")
            sys.exit(1)

    except Exception as e:
        click.secho(f"❌ Health check error: {e}", fg="red")
        sys.exit(1)


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind the server to")
@click.option("--port", default=8000, type=int, help="Port to bind the server to")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def server(host: str, port: int, reload: bool):
    """Start the FastAPI server"""
    try:
        import uvicorn

        log.info(f"Starting BrowserFreak API server on {host}:{port}")
        click.echo(f"🚀 Starting BrowserFreak API server on http://{host}:{port}")
        click.echo(f"📚 API documentation: http://{host}:{port}/docs")
        click.echo(f"🔄 ReDoc documentation: http://{host}:{port}/redoc")

        uvicorn.run(
            "browserfreak.server:app",
            host=host,
            port=port,
            reload=reload,
            log_level=settings.agent.log_level.lower(),
        )
    except ImportError:
        click.secho(
            "❌ FastAPI or uvicorn not installed. Install with: pip install fastapi uvicorn",
            fg="red",
        )
        sys.exit(1)
    except Exception as e:
        click.secho(f"❌ Failed to start server: {e}", fg="red")
        sys.exit(1)


@cli.command()
def config():
    """Show current configuration"""

    click.echo("BrowserFreak Configuration:")
    click.echo("=" * 40)

    click.echo("Browser Settings:")
    click.echo(f"  Headless: {settings.browser.headless}")
    click.echo(f"  Channel: {settings.browser.channel}")
    click.echo(f"  Default Timeout: {settings.browser.default_timeout}ms")
    click.echo(f"  Page Load Timeout: {settings.browser.page_load_timeout}ms")

    click.echo("\nAgent Settings:")
    click.echo(f"  Max Iterations: {settings.agent.max_iterations}")
    click.echo(f"  Use Real Browser: {settings.agent.use_real_browser}")
    click.echo(f"  Log Level: {settings.agent.log_level}")

    click.echo("\nAnthropic API:")
    click.echo(f"  Available: {settings.anthropic.is_available}")
    if settings.anthropic.is_available:
        click.echo(f"  Model: {settings.anthropic.model}")
        click.echo(f"  Temperature: {settings.anthropic.temperature}")
    else:
        click.echo("  ⚠️  API not configured - using fallback mode")


def main():
    """Main CLI entry point"""
    cli()


if __name__ == "__main__":
    main()

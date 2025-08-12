import typer
from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.table import Table
from .config import Config
from .aws_adfs import execute_aws_adfs, generate_exports, check_aws_adfs_exists

app = typer.Typer(help="AWS Login Tool - ADFS authentication with YAML configuration")
console = Console()

def find_config_file(config_path: Optional[str] = None) -> Optional[str]:
    """Find configuration file"""
    if config_path:
        return config_path

    possible_paths = [
        Path('./aws-login.yaml'),
        Path('./aws-login.yml'),
        Path.home() / '.config' / 'aws-login.yaml',
        Path.home() / '.config' / 'aws-login.yml',
    ]

    for path in possible_paths:
        if path.exists():
            return str(path)

    return None

def load_config(config_path: Optional[str] = None) -> tuple[Config, str]:
    """Load configuration file"""
    config_file = find_config_file(config_path)

    if not config_file:
        console.print("❌ No config file found. Please create aws-login.yaml or specify with --config", style="red")
        raise typer.Exit(1)

    try:
        return Config.from_file(config_file), config_file
    except Exception as e:
        console.print(f"❌ Error loading config: {e}", style="red")
        raise typer.Exit(1)

@app.command()
def login(
    environment: str = typer.Option(..., "--environment", "-e", help="Environment (tf-dev, shared, prod, etc.)"),
    profile: str = typer.Option("eu", "--profile", "-p", help="Profile to use (eu, us, etc.)"),
    aws_profile: str = typer.Option("default", "--aws-profile", help="AWS CLI profile name"),
    session_duration: Optional[int] = typer.Option(None, "--session-duration", "-s", help="Session duration in seconds"),
    dry_run: bool = typer.Option(False, "--dry-run", "-d", help="Show what would be executed"),
    debug: bool = typer.Option(False, "--debug", help="Show debug information"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config file")
):
    """Execute AWS login and output environment variables for sourcing"""
    config_obj, _ = load_config(config)

    # Validate inputs
    if profile not in config_obj.profiles:
        available = ', '.join(config_obj.profiles.keys())
        console.print(f"❌ Profile '{profile}' not found. Available: {available}", style="red")
        raise typer.Exit(1)

    if environment not in config_obj.environments:
        available = ', '.join(config_obj.environments.keys())
        console.print(f"❌ Environment '{environment}' not found. Available: {available}", style="red")
        raise typer.Exit(1)

    # Execute aws-adfs
    success = execute_aws_adfs(
        config=config_obj,
        profile=profile,
        environment=environment,
        aws_profile=aws_profile,
        session_duration=session_duration,
        dry_run=dry_run
    )

    if not success and not dry_run:
        raise typer.Exit(1)

    # Generate export commands (to stdout for sourcing)
    exports = generate_exports(config_obj, profile, environment, aws_profile)
    for export in exports:
        typer.echo(export)

    if debug:
        resolved = config_obj.resolve_environment(environment, profile)
        profile_config = config_obj.profiles[profile]
        console.print("Debug: Environment variables set:", style="yellow")
        console.print(f"  AWS_PROFILE={aws_profile}")
        console.print(f"  AWS_REGION={profile_config.region}")
        console.print(f"  TF_VAR_target_account_id={resolved.target_account_id}")

@app.command("list-environments")
def list_environments(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config file")
):
    """List available environments"""
    config_obj, _ = load_config(config)

    table = Table(title="Available Environments")
    table.add_column("Name", style="cyan")
    table.add_column("Role", style="green")
    table.add_column("State Account", style="yellow")
    table.add_column("Target Account", style="blue")
    table.add_column("Session Duration", style="magenta")

    for name, env in config_obj.environments.items():
        # Show role with default indicator
        role_display = env.role
        if env.role == config_obj.defaults.role_name:
            role_display = f"{env.role} [dim](default)[/dim]"

        target = env.target_account_id or f"[dim](same as state: {env.state_account_id})[/dim]"
        duration = f"{env.session_duration}s" if env.session_duration else f"[dim](default: {config_obj.defaults.session_duration}s)[/dim]"

        state_display = env.state_account_id or "[red]REQUIRED[/red]"

        table.add_row(
            name,
            role_display,
            state_display,
            target,
            duration
        )

    console.print(table)

@app.command("list-profiles")
def list_profiles(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config file")
):
    """List available profiles"""
    config_obj, _ = load_config(config)  # Use 'config' directly

    table = Table(title="Available Profiles")
    table.add_column("Name", style="cyan")
    table.add_column("Region", style="green")
    table.add_column("Username", style="yellow")
    table.add_column("ADFS Host", style="blue")
    table.add_column("Session Duration", style="magenta")

    for name, profile in config_obj.profiles.items():
        duration = f"{profile.session_duration}s" if profile.session_duration else "default"
        table.add_row(
            name,
            profile.region,
            profile.username,
            profile.adfs_host,
            duration
        )

    console.print(table)

@app.command()
def validate(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config file")
):
    """Validate configuration and prerequisites"""
    config_obj, config_path = load_config(config)

    console.print("🔍 Validating configuration...", style="bold blue")

    # Check config file
    console.print(f"[green]PASS[/green] Config file loaded: {config_path}")

    # Check aws-adfs
    if check_aws_adfs_exists():
        console.print("[green]PASS[/green] aws-adfs tool found")
    else:
        console.print("[red]FAIL[/red] aws-adfs tool not found in PATH")
        console.print("      Install from: https://github.com/venth/aws-adfs", style="yellow")

    # Check SSL certificate
    cert_path = config_obj.expand_path(config_obj.ssl.ca_bundle_path)
    if Path(cert_path).exists():
        console.print(f"[green]PASS[/green] SSL certificate found: {cert_path}")
    else:
        console.print(f"[yellow]WARN[/yellow] SSL certificate not found: {cert_path}")

    # Validate environments
    console.print("\n🔧 Validating environments:", style="bold blue")

    table = Table()
    table.add_column("Environment", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("State → Target", style="yellow")

    for name in config_obj.environments.keys():
        try:
            resolved = config_obj.resolve_environment(name)
            table.add_row(
                name,
                "[green]VALID[/green]",
                f"{resolved.state_account_id} → {resolved.target_account_id}"
            )
        except ValueError as e:
            table.add_row(name, f"[red]ERROR[/red]", str(e))

    console.print(table)
    console.print("\n[green]PASS[/green] Validation complete!", style="bold")

@app.callback()
def main(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config file")
):
    """
    AWS Login Tool - ADFS authentication with YAML configuration

    Examples:
      aws-login login -e tf-dev -p eu
      aws-login list-profiles
      aws-login validate
    """
    pass

if __name__ == "__main__":
    app()
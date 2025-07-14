import subprocess
import os
import sys
from typing import List
from .config import Config

def check_aws_adfs_exists() -> bool:
    """Check if aws-adfs command is available"""
    try:
        subprocess.run(['aws-adfs', '--version'],
                      capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def generate_command(config: Config, profile: str, environment: str,
                    aws_profile: str, session_duration: int = None) -> List[str]:
    """Generate aws-adfs command"""
    if profile not in config.profiles:
        raise ValueError(f"Profile '{profile}' not found")

    profile_config = config.profiles[profile]
    resolved_env = config.resolve_environment(environment, profile)

    # Use command line override, or resolved session duration
    session_dur = session_duration or resolved_env.session_duration

    cmd = [
        "aws-adfs", "login",
        "--env",
        "--no-session-cache"
    ]

    # SSL verification
    if config.ssl.verify_ssl:
        cmd.append("--ssl-verification")
    else:
        cmd.append("--no-ssl-verification")

    # Add remaining arguments
    cmd.extend([
        "--adfs-host", profile_config.adfs_host,
        "--adfs-ca-bundle", config.expand_path(config.ssl.ca_bundle_path),
        "--role-arn", f"arn:aws:iam::{resolved_env.state_account_id}:role/{resolved_env.role}",
        "--region", profile_config.region,
        "--session-duration", str(session_dur),
        "--profile", aws_profile
    ])

    return cmd

def generate_exports(config: Config, profile: str, environment: str,
                    aws_profile: str) -> List[str]:
    """Generate export commands for shell sourcing"""
    if profile not in config.profiles:
        raise ValueError(f"Profile '{profile}' not found")

    profile_config = config.profiles[profile]
    resolved_env = config.resolve_environment(environment, profile)

    exports = [
        f'export username="{profile_config.username}"',
        'unset AWS_PROFILE',
        'unset AWS_REGION',
        f'export AWS_PROFILE="{aws_profile}"',
        f'export AWS_REGION="{profile_config.region}"',
        f'export TF_VAR_target_account_id="{resolved_env.target_account_id}"',
        f'# AWS environment configured for {environment}/{profile}'
    ]

    return exports

def execute_aws_adfs(config: Config, profile: str, environment: str,
                    aws_profile: str = "default", session_duration: int = None,
                    dry_run: bool = False) -> bool:
    """Execute aws-adfs command"""
    if not check_aws_adfs_exists():
        print("Error: aws-adfs tool not found in PATH. Please install it from https://github.com/venth/aws-adfs",
              file=sys.stderr)
        return False

    profile_config = config.profiles[profile]
    resolved_env = config.resolve_environment(environment, profile)

    # Use command line override, or resolved session duration
    final_session_duration = session_duration or resolved_env.session_duration

    # Print info to stderr
    print(f"AWS CLI   ({environment}={resolved_env.state_account_id}) on ({profile_config.region}) :: "
          f"profile={aws_profile} role={resolved_env.role}", file=sys.stderr)
    print(f"Terraform ({environment}={resolved_env.target_account_id}) on ({profile_config.region}) :: "
          f"TF_VAR_target_account_id={resolved_env.target_account_id}", file=sys.stderr)
    print(f"Session duration: {final_session_duration} seconds ({final_session_duration//3600}h {(final_session_duration%3600)//60}m)", file=sys.stderr)

    # Generate command
    cmd = generate_command(config, profile, environment, aws_profile, session_duration)

    if dry_run:
        print(f"Would execute: {' '.join(cmd)}", file=sys.stderr)
        return True

    print("Generating credentials...", file=sys.stderr)

    # Set username environment variable for aws-adfs
    os.environ['username'] = profile_config.username

    # Unset existing AWS environment variables
    for var in ['AWS_PROFILE', 'AWS_REGION']:
        os.environ.pop(var, None)

    try:
        # Execute aws-adfs command
        result = subprocess.run(cmd, check=True, stderr=sys.stderr, stdin=sys.stdin)
        print("aws-adfs completed successfully", file=sys.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to execute aws-adfs: {e}", file=sys.stderr)
        return False
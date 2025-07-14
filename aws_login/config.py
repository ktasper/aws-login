from dataclasses import dataclass
from typing import Dict, Optional
import yaml
import os
from pathlib import Path

@dataclass
class Profile:
    region: str
    username: str
    adfs_host: str
    session_duration: Optional[int] = None

@dataclass
class Environment:
    role: str
    state_account_id: Optional[str] = None
    target_account_id: Optional[str] = None
    session_duration: Optional[int] = None

@dataclass
class Defaults:
    role_name: str
    state_account_id: str
    session_duration: int
    target_account_id: str

@dataclass
class SSL:
    ca_bundle_path: str
    verify_ssl: bool

@dataclass
class ResolvedEnvironment:
    """Environment with all values resolved"""
    state_account_id: str
    target_account_id: str
    role: str
    session_duration: int

@dataclass
class Config:
    profiles: Dict[str, Profile]
    environments: Dict[str, Environment]
    defaults: Defaults
    ssl: SSL

    @classmethod
    def from_yaml(cls, yaml_content: str) -> 'Config':
        """Parse config from YAML string"""
        data = yaml.safe_load(yaml_content)
        return cls.from_dict(data)

    @classmethod
    def from_file(cls, file_path: str) -> 'Config':
        """Load config from YAML file"""
        with open(file_path, 'r') as f:
            return cls.from_yaml(f.read())

    @classmethod
    def from_dict(cls, data: dict) -> 'Config':
        """Parse config from dictionary"""
        # Parse profiles
        profiles = {}
        for name, profile_data in data.get('profiles', {}).items():
            profiles[name] = Profile(
                region=profile_data['region'],
                username=profile_data['username'],
                adfs_host=profile_data['adfs-host'],
                session_duration=profile_data.get('session_duration')
            )

        # Parse environments
        environments = {}
        for name, env_data in data.get('environments', {}).items():
            environments[name] = Environment(
                state_account_id=env_data.get('state_account_id'),
                target_account_id=env_data.get('target_account_id'),
                role=env_data['role'],
                session_duration=env_data.get('session_duration')
            )

        # Parse defaults (MOVED OUT of the loop)
        defaults_data = data.get('defaults', {})
        defaults = Defaults(
            role_name=defaults_data['role_name'],
            state_account_id=defaults_data['state_account_id'],
            session_duration=defaults_data['session_duration'],
            target_account_id=defaults_data['target_account_id']
        )

        # Parse SSL
        ssl_data = data.get('ssl', {})
        ssl = SSL(
            ca_bundle_path=ssl_data['ca_bundle_path'],
            verify_ssl=ssl_data['verify_ssl']
        )

        return cls(
            profiles=profiles,
            environments=environments,
            defaults=defaults,
            ssl=ssl
        )

    def resolve_environment(self, environment_name: str, profile_name: str = None) -> ResolvedEnvironment:
        """Resolve environment with defaults applied"""
        if environment_name not in self.environments:
            raise ValueError(f"Environment '{environment_name}' not found")

        env = self.environments[environment_name]

        # Resolve state_account_id FIRST
        state_account_id = env.state_account_id or self.defaults.state_account_id

        # Resolve target_account_id using the RESOLVED state_account_id
        if env.target_account_id:
            target_account_id = env.target_account_id
        elif env.state_account_id:
            # If target not specified but state is explicitly set, use state for both
            target_account_id = env.state_account_id
        else:
            # If neither target nor state are set, use the resolved state (which includes default)
            target_account_id = state_account_id

        # Resolve session_duration with priority:
        session_duration = env.session_duration

        if not session_duration and profile_name and profile_name in self.profiles:
            session_duration = self.profiles[profile_name].session_duration

        if not session_duration:
            session_duration = self.defaults.session_duration

        return ResolvedEnvironment(
            state_account_id=state_account_id,
            target_account_id=target_account_id,
            role=env.role,
            session_duration=session_duration
        )

    def expand_path(self, path: str) -> str:
        """Expand ~ in paths"""
        if path.startswith('~/'):
            return str(Path.home() / path[2:])
        return path
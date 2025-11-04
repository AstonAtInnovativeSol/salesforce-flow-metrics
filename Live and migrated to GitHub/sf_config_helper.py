#!/usr/bin/env python3
"""
Salesforce Configuration Helper
Supports both local execution (sf_config.py) and GitHub Actions (environment variables)

Usage:
    from sf_config_helper import get_sf_config
    
    config = get_sf_config()
    # Use config.SF_USERNAME, config.SF_CONSUMER_KEY, etc.
"""

import os
from pathlib import Path
from typing import Optional

class SalesforceConfig:
    """Salesforce configuration with fallback to environment variables"""
    def __init__(self, username: str, consumer_key: str, domain: str, private_key_file: Optional[str] = None, private_key_content: Optional[str] = None):
        self.SF_USERNAME = username
        self.SF_CONSUMER_KEY = consumer_key
        self.SF_DOMAIN = domain
        self.PRIVATE_KEY_FILE = private_key_file
        self._private_key_content = private_key_content
    
    def get_private_key(self) -> str:
        """Get private key content - either from file or content"""
        if self._private_key_content:
            return self._private_key_content
        elif self.PRIVATE_KEY_FILE:
            with open(self.PRIVATE_KEY_FILE, "r") as f:
                return f.read()
        else:
            raise ValueError("No private key available - neither file nor content provided")


def get_sf_config():
    """
    Get Salesforce configuration with fallback logic:
    1. Try to import sf_config.py (local execution)
    2. Fall back to environment variables (GitHub Actions)
    
    Returns:
        SalesforceConfig: Configuration object
        
    Raises:
        ValueError: If no configuration is found
    """
    # First, try to import from sf_config.py (local execution)
    try:
        import sf_config
        # Check if it has the required attributes
        if hasattr(sf_config, 'SF_USERNAME') and hasattr(sf_config, 'SF_CONSUMER_KEY'):
            # If PRIVATE_KEY_FILE exists, use it
            if hasattr(sf_config, 'PRIVATE_KEY_FILE') and sf_config.PRIVATE_KEY_FILE:
                return SalesforceConfig(
                    username=sf_config.SF_USERNAME,
                    consumer_key=sf_config.SF_CONSUMER_KEY,
                    domain=sf_config.SF_DOMAIN,
                    private_key_file=sf_config.PRIVATE_KEY_FILE
                )
    except ImportError:
        pass  # sf_config.py not found, continue to environment variables
    
    # Fall back to environment variables (GitHub Actions)
    username = os.getenv('SF_USERNAME')
    consumer_key = os.getenv('SF_CONSUMER_KEY')
    domain = os.getenv('SF_DOMAIN', 'login')
    private_key_content = os.getenv('SF_PRIVATE_KEY')  # For GitHub Actions
    private_key_file = os.getenv('SF_PRIVATE_KEY_FILE')  # Alternative: file path
    
    if username and consumer_key:
        # Check if we have private key content or file
        if private_key_content:
            return SalesforceConfig(
                username=username,
                consumer_key=consumer_key,
                domain=domain,
                private_key_content=private_key_content
            )
        elif private_key_file:
            return SalesforceConfig(
                username=username,
                consumer_key=consumer_key,
                domain=domain,
                private_key_file=private_key_file
            )
        else:
            raise ValueError(
                "Private key required but not found. Provide either:\n"
                "- SF_PRIVATE_KEY (environment variable with key content)\n"
                "- SF_PRIVATE_KEY_FILE (environment variable with file path)\n"
                "- PRIVATE_KEY_FILE in sf_config.py (local file)"
            )
    
    raise ValueError(
        "Salesforce configuration not found. Provide either:\n"
        "- sf_config.py file (for local execution)\n"
        "- Environment variables: SF_USERNAME, SF_CONSUMER_KEY, SF_DOMAIN (for GitHub Actions)"
    )


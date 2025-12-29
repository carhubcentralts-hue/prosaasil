"""
ARI Connection Validator
Validates Asterisk ARI connectivity and credentials
"""
import os
import sys
import logging
import requests
from typing import Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def validate_ari_connection(
    ari_url: str,
    username: str,
    password: str
) -> Tuple[bool, str]:
    """
    Validate ARI connection and credentials.
    
    Args:
        ari_url: ARI base URL (e.g., http://localhost:8088/ari)
        username: ARI username
        password: ARI password
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # Test 1: Check if ARI is reachable
        logger.info(f"Testing ARI connection to {ari_url}...")
        
        # Try to get API docs
        response = requests.get(
            f"{ari_url}/api-docs/resources.json",
            auth=(username, password),
            timeout=5
        )
        
        if response.status_code == 401:
            return False, "❌ Authentication failed - check username/password"
        
        response.raise_for_status()
        
        # Test 2: Check Asterisk info
        logger.info("Checking Asterisk info...")
        response = requests.get(
            f"{ari_url}/asterisk/info",
            auth=(username, password),
            timeout=5
        )
        response.raise_for_status()
        
        info = response.json()
        asterisk_version = info.get("system", {}).get("version", "unknown")
        
        logger.info(f"✅ [ARI] Connected successfully to Asterisk ARI")
        logger.info(f"   Asterisk Version: {asterisk_version}")
        logger.info(f"   ARI URL: {ari_url}")
        logger.info(f"   Username: {username}")
        
        return True, f"✅ ARI connection successful (Asterisk {asterisk_version})"
        
    except requests.exceptions.ConnectionError:
        return False, f"❌ Cannot connect to {ari_url} - is Asterisk running?"
    except requests.exceptions.Timeout:
        return False, f"❌ Connection timeout to {ari_url}"
    except requests.exceptions.HTTPError as e:
        return False, f"❌ HTTP error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        return False, f"❌ Unexpected error: {e}"


def main():
    """Main validation function."""
    # Get credentials from environment
    ari_url = os.getenv("ASTERISK_ARI_URL", "http://localhost:8088/ari")
    username = os.getenv("ASTERISK_ARI_USER", "prosaas")
    password = os.getenv("ASTERISK_ARI_PASSWORD")
    
    if not password:
        logger.error("❌ ASTERISK_ARI_PASSWORD environment variable not set")
        logger.info("   Set it with: export ASTERISK_ARI_PASSWORD=your_password")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("ARI Connection Validator")
    logger.info("=" * 60)
    logger.info(f"ARI URL: {ari_url}")
    logger.info(f"Username: {username}")
    logger.info(f"Password: {'*' * len(password)}")
    logger.info("=" * 60)
    
    # Validate connection
    success, message = validate_ari_connection(ari_url, username, password)
    
    logger.info("")
    logger.info(message)
    logger.info("=" * 60)
    
    if success:
        logger.info("✅ ARI validation passed - ready for use")
        sys.exit(0)
    else:
        logger.error("❌ ARI validation failed - fix issues and try again")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
ARI Originate Test - Test outbound call creation via ARI
Tests that backend can control calls through Asterisk ARI
"""
import os
import sys
import logging
import requests
import time
from typing import Dict, Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class ARIClient:
    """Simple ARI client for testing."""
    
    def __init__(self, ari_url: str, username: str, password: str):
        self.ari_url = ari_url.rstrip('/')
        self.auth = (username, password)
    
    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make ARI request."""
        url = f"{self.ari_url}{endpoint}"
        response = requests.request(method, url, auth=self.auth, **kwargs)
        response.raise_for_status()
        return response
    
    def get_channels(self) -> list:
        """Get all active channels."""
        response = self._request("GET", "/channels")
        return response.json()
    
    def originate_call(
        self,
        endpoint: str,
        app: str,
        caller_id: str = "Test Call",
        variables: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Originate a call through ARI.
        
        Args:
            endpoint: Destination endpoint (e.g., "PJSIP/+1234567890@didww")
            app: Stasis application name
            caller_id: Caller ID to use
            variables: Channel variables
            
        Returns:
            Channel data
        """
        data = {
            "endpoint": endpoint,
            "app": app,
            "callerId": caller_id
        }
        
        if variables:
            data["variables"] = variables
        
        logger.info(f"Originating call to {endpoint}...")
        response = self._request("POST", "/channels", json=data)
        channel = response.json()
        
        logger.info(f"✅ Channel created: {channel['id']}")
        return channel
    
    def hangup_channel(self, channel_id: str):
        """Hangup a channel."""
        logger.info(f"Hanging up channel {channel_id}...")
        self._request("DELETE", f"/channels/{channel_id}")
        logger.info(f"✅ Channel {channel_id} hung up")
    
    def get_channel(self, channel_id: str) -> Dict[str, Any]:
        """Get channel details."""
        response = self._request("GET", f"/channels/{channel_id}")
        return response.json()


def test_originate(
    ari_url: str,
    username: str,
    password: str,
    test_number: str,
    trunk: str = "didww"
):
    """
    Test outbound call origination via ARI.
    
    Args:
        ari_url: ARI URL
        username: ARI username
        password: ARI password
        test_number: Phone number to call (E.164 format)
        trunk: SIP trunk name (default: didww)
    """
    client = ARIClient(ari_url, username, password)
    
    logger.info("=" * 60)
    logger.info("ARI Originate Test")
    logger.info("=" * 60)
    
    # Check initial channels
    logger.info("Checking active channels...")
    channels = client.get_channels()
    logger.info(f"Active channels: {len(channels)}")
    
    # Originate test call
    endpoint = f"PJSIP/{test_number}@{trunk}"
    
    try:
        channel = client.originate_call(
            endpoint=endpoint,
            app="prosaas_ai",
            caller_id="ARI Test",
            variables={
                "TENANT_ID": "1",
                "DIRECTION": "outbound",
                "TEST_CALL": "yes"
            }
        )
        
        channel_id = channel['id']
        logger.info(f"Channel ID: {channel_id}")
        logger.info(f"State: {channel['state']}")
        
        # Wait a few seconds
        logger.info("Waiting 5 seconds...")
        time.sleep(5)
        
        # Check channel status
        logger.info("Checking channel status...")
        channel = client.get_channel(channel_id)
        logger.info(f"Current state: {channel['state']}")
        
        # Hangup
        client.hangup_channel(channel_id)
        
        logger.info("=" * 60)
        logger.info("✅ ARI originate test completed successfully")
        logger.info("=" * 60)
        
        return True
        
    except requests.exceptions.HTTPError as e:
        logger.error(f"❌ HTTP Error: {e.response.status_code}")
        logger.error(f"   Response: {e.response.text}")
        return False
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False


def main():
    """Main test function."""
    # Get credentials from environment
    ari_url = os.getenv("ASTERISK_ARI_URL", "http://localhost:8088/ari")
    username = os.getenv("ASTERISK_ARI_USER", "prosaas")
    password = os.getenv("ASTERISK_ARI_PASSWORD")
    
    # Test configuration
    test_number = os.getenv("TEST_PHONE_NUMBER")
    trunk = os.getenv("ASTERISK_SIP_TRUNK", "didww")
    
    if not password:
        logger.error("❌ ASTERISK_ARI_PASSWORD not set")
        sys.exit(1)
    
    if not test_number:
        logger.error("❌ TEST_PHONE_NUMBER not set")
        logger.info("   Example: export TEST_PHONE_NUMBER=+1234567890")
        sys.exit(1)
    
    logger.info(f"Testing with number: {test_number}")
    logger.info(f"Using trunk: {trunk}")
    
    # Run test
    success = test_originate(ari_url, username, password, test_number, trunk)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

"""
Asterisk Telephony Provider - ARI-based implementation
Replaces Twilio with Asterisk + DID + SIP for call management
"""
import os
import logging
import requests
from typing import Dict, Any, Optional
from server.telephony.provider_base import (
    TelephonyProvider,
    CallStatus,
    CallDirection
)

logger = logging.getLogger(__name__)


class AsteriskProvider(TelephonyProvider):
    """
    Asterisk-based telephony provider using ARI (Asterisk REST Interface).
    
    Connects to Asterisk via HTTP REST API and WebSocket events for:
    - Outbound call origination
    - Call control (hangup, status)
    - Recording management
    - Real-time media streaming via ExternalMedia
    """
    
    def __init__(
        self,
        ari_url: Optional[str] = None,
        ari_username: Optional[str] = None,
        ari_password: Optional[str] = None,
        stasis_app: str = "prosaas_ai"
    ):
        """
        Initialize Asterisk provider.
        
        Args:
            ari_url: Asterisk ARI base URL (default: http://localhost:8088/ari)
            ari_username: ARI username (default: from ASTERISK_ARI_USER env)
            ari_password: ARI password (default: from ASTERISK_ARI_PASSWORD env)
            stasis_app: Stasis application name (default: prosaas_ai)
        """
        self.ari_url = ari_url or os.getenv("ASTERISK_ARI_URL", "http://localhost:8088/ari")
        self.ari_username = ari_username or os.getenv("ASTERISK_ARI_USER", "asterisk")
        self.ari_password = ari_password or os.getenv("ASTERISK_ARI_PASSWORD", "asterisk")
        self.stasis_app = stasis_app
        
        # Validate connection on initialization
        self._validate_connection()
        
        logger.info(f"[ASTERISK] Initialized provider: ari_url={self.ari_url}, app={self.stasis_app}")
    
    def _validate_connection(self) -> None:
        """Validate ARI connection is available."""
        try:
            response = requests.get(
                f"{self.ari_url}/asterisk/info",
                auth=(self.ari_username, self.ari_password),
                timeout=5
            )
            response.raise_for_status()
            logger.info("[ASTERISK] ARI connection validated successfully")
        except Exception as e:
            logger.error(f"[ASTERISK] Failed to connect to ARI: {e}")
            raise ConnectionError(f"Cannot connect to Asterisk ARI at {self.ari_url}: {e}")
    
    def _make_ari_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> requests.Response:
        """
        Make authenticated ARI HTTP request.
        
        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: ARI endpoint path (e.g., "/channels")
            **kwargs: Additional requests parameters
            
        Returns:
            Response object
            
        Raises:
            requests.HTTPError: If request fails
        """
        url = f"{self.ari_url}{endpoint}"
        response = requests.request(
            method,
            url,
            auth=(self.ari_username, self.ari_password),
            **kwargs
        )
        response.raise_for_status()
        return response
    
    def start_outbound_call(
        self,
        tenant_id: int,
        to_number: str,
        from_number: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Initiate outbound call via ARI originate.
        
        Creates a call through Asterisk that enters the Stasis application
        and connects to the Media Gateway for AI interaction.
        
        Args:
            tenant_id: Business/tenant ID
            to_number: Destination phone (E.164)
            from_number: Caller ID phone (E.164)
            metadata: Optional metadata (lead_id, template_id, job_id, etc.)
            
        Returns:
            channel_id: Asterisk channel ID (unique call identifier)
        """
        metadata = metadata or {}
        
        # Build channel variables to pass metadata
        variables = {
            "TENANT_ID": str(tenant_id),
            "DIRECTION": "outbound",
            "LEAD_ID": str(metadata.get("lead_id", "")),
            "TEMPLATE_ID": str(metadata.get("template_id", "")),
            "JOB_ID": str(metadata.get("job_id", "")),
            "BUSINESS_NAME": metadata.get("business_name", ""),
            "LEAD_NAME": metadata.get("lead_name", "")
        }
        
        # Originate call through SIP trunk
        # Endpoint format: PJSIP/{number}@{trunk_name}
        trunk_name = os.getenv("ASTERISK_SIP_TRUNK", "provider")
        endpoint = f"PJSIP/{to_number}@{trunk_name}"
        
        logger.info(f"[ASTERISK] Originating outbound call: to={to_number}, from={from_number}, tenant={tenant_id}")
        
        try:
            response = self._make_ari_request(
                "POST",
                "/channels",
                json={
                    "endpoint": endpoint,
                    "app": self.stasis_app,
                    "appArgs": f"tenant={tenant_id},direction=outbound",
                    "callerId": from_number,
                    "variables": variables,
                    "channelId": None  # Let Asterisk generate unique ID
                }
            )
            
            channel_data = response.json()
            channel_id = channel_data["id"]
            
            logger.info(f"[ASTERISK] ✅ Outbound call created: channel_id={channel_id}, to={to_number}")
            
            return channel_id
            
        except Exception as e:
            logger.error(f"[ASTERISK] ❌ Failed to create outbound call: {e}")
            raise
    
    def hangup_call(self, call_id: str, reason: Optional[str] = None) -> None:
        """
        Hangup active call via ARI.
        
        Args:
            call_id: Asterisk channel ID
            reason: Optional hangup reason (logged but not sent to Asterisk)
        """
        logger.info(f"[ASTERISK] Hanging up call: channel_id={call_id}, reason={reason}")
        
        try:
            self._make_ari_request(
                "DELETE",
                f"/channels/{call_id}",
                json={"reason": reason or "normal"}
            )
            logger.info(f"[ASTERISK] ✅ Call hung up: {call_id}")
            
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"[ASTERISK] Call already ended: {call_id}")
            else:
                logger.error(f"[ASTERISK] ❌ Failed to hangup call: {e}")
                raise
    
    def get_call_status(self, call_id: str) -> Dict[str, Any]:
        """
        Get current call status from Asterisk.
        
        Args:
            call_id: Asterisk channel ID
            
        Returns:
            Dict with call status and metadata
        """
        try:
            response = self._make_ari_request(
                "GET",
                f"/channels/{call_id}"
            )
            
            channel = response.json()
            
            # Map Asterisk state to normalized CallStatus
            state = channel.get("state", "unknown")
            status_map = {
                "Down": CallStatus.INITIATED,
                "Rsrvd": CallStatus.INITIATED,
                "OffHook": CallStatus.INITIATED,
                "Dialing": CallStatus.RINGING,
                "Ring": CallStatus.RINGING,
                "Ringing": CallStatus.RINGING,
                "Up": CallStatus.IN_PROGRESS,
                "Busy": CallStatus.BUSY,
            }
            normalized_status = status_map.get(state, CallStatus.IN_PROGRESS)
            
            return {
                "status": normalized_status,
                "duration": channel.get("creationtime", "0"),  # Time since channel creation
                "direction": CallDirection.OUTBOUND if "outbound" in channel.get("name", "").lower() else CallDirection.INBOUND,
                "from_number": channel.get("caller", {}).get("number", ""),
                "to_number": channel.get("connected", {}).get("number", ""),
                "metadata": {
                    "channel_state": state,
                    "channel_name": channel.get("name", ""),
                    "dialplan_context": channel.get("dialplan", {}).get("context", "")
                }
            }
            
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                # Channel not found = call ended
                return {
                    "status": CallStatus.COMPLETED,
                    "duration": 0,
                    "direction": CallDirection.OUTBOUND,
                    "from_number": "",
                    "to_number": "",
                    "metadata": {"error": "channel_not_found"}
                }
            else:
                logger.error(f"[ASTERISK] Failed to get call status: {e}")
                raise
    
    def get_recording_url(self, call_id: str) -> Optional[str]:
        """
        Get recording URL for completed call.
        
        For Asterisk, recordings are stored locally and managed via
        recording service (not directly via ARI).
        
        Args:
            call_id: Asterisk channel ID
            
        Returns:
            Recording file path or URL (handled by recording service)
        """
        # Asterisk recordings are managed via MixMonitor and stored locally
        # Recording URLs are handled by recording_service.py which manages
        # local files and S3/MinIO uploads
        
        # Format: /var/spool/asterisk/recordings/{tenant_id}/{call_id}.wav
        # Actual URL is generated by recording service after upload
        
        logger.debug(f"[ASTERISK] Recording URL requested for {call_id} - managed by recording service")
        return None  # Recording service handles URL generation
    
    def supports_media_streams(self) -> bool:
        """
        Asterisk supports real-time media via ExternalMedia channels.
        
        Returns:
            True (Asterisk supports RTP streaming to Media Gateway)
        """
        return True
    
    def get_webhook_urls(self, public_host: str) -> Dict[str, str]:
        """
        Get webhook URLs for Asterisk integration.
        
        Note: Asterisk uses ARI events (WebSocket), not HTTP webhooks.
        These URLs are provided for compatibility but not actively used.
        
        Args:
            public_host: Public hostname
            
        Returns:
            Dict with placeholder webhook URLs
        """
        return {
            "incoming_call": f"https://{public_host}/api/asterisk/incoming",
            "call_status": f"https://{public_host}/api/asterisk/status",
            "recording_completed": f"https://{public_host}/api/asterisk/recording"
        }

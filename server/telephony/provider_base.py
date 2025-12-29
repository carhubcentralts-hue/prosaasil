"""
Base Telephony Provider Interface - SSOT for telephony operations
All telephony providers (Twilio, Asterisk) must implement this interface
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum


class CallStatus(Enum):
    """Normalized call statuses across all providers"""
    INITIATED = "initiated"
    RINGING = "ringing"
    ANSWERED = "answered"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    CANCELED = "canceled"


class CallDirection(Enum):
    """Call direction types"""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class TelephonyProvider(ABC):
    """
    Base interface for all telephony providers.
    
    This ensures consistent API regardless of underlying provider (Twilio, Asterisk, etc.)
    SSOT: All telephony operations must go through this interface
    """
    
    @abstractmethod
    def start_outbound_call(
        self,
        tenant_id: int,
        to_number: str,
        from_number: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Initiate an outbound call.
        
        Args:
            tenant_id: Business/tenant ID
            to_number: Destination phone number (E.164 format)
            from_number: Source phone number (E.164 format)
            metadata: Optional call metadata (lead_id, template_id, etc.)
            
        Returns:
            call_id: Unique identifier for the call (CallSid for Twilio, UniqueID for Asterisk)
            
        Raises:
            Exception: If call creation fails
        """
        pass
    
    @abstractmethod
    def hangup_call(self, call_id: str, reason: Optional[str] = None) -> None:
        """
        Terminate an active call.
        
        Args:
            call_id: Unique call identifier
            reason: Optional hangup reason (voicemail_detected, silence_timeout, etc.)
            
        Raises:
            Exception: If hangup fails
        """
        pass
    
    @abstractmethod
    def get_call_status(self, call_id: str) -> Dict[str, Any]:
        """
        Get current call status and metadata.
        
        Args:
            call_id: Unique call identifier
            
        Returns:
            Dict containing:
                - status: CallStatus enum value
                - duration: Call duration in seconds (if available)
                - direction: CallDirection enum value
                - from_number: Caller number
                - to_number: Callee number
                - metadata: Provider-specific metadata
                
        Raises:
            Exception: If call not found or status fetch fails
        """
        pass
    
    @abstractmethod
    def get_recording_url(self, call_id: str) -> Optional[str]:
        """
        Get recording URL for a completed call.
        
        Args:
            call_id: Unique call identifier
            
        Returns:
            Recording URL if available, None otherwise
        """
        pass
    
    @abstractmethod
    def supports_media_streams(self) -> bool:
        """
        Check if provider supports real-time media streaming.
        
        Returns:
            True if provider supports WebSocket-based media streams
        """
        pass
    
    @abstractmethod
    def get_webhook_urls(self, public_host: str) -> Dict[str, str]:
        """
        Get webhook URLs for this provider.
        
        Args:
            public_host: Public hostname for webhook callbacks
            
        Returns:
            Dict mapping webhook names to URLs:
                - incoming_call: URL for incoming call webhook
                - call_status: URL for call status updates
                - recording_completed: URL for recording completion
        """
        pass

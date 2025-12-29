"""
Call State Machine - Explicit state tracking for Asterisk calls
Ensures clean lifecycle management and proper cleanup
"""
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class CallState(Enum):
    """
    Explicit call states for lifecycle management.
    
    State transitions:
    - INITIATED → RINGING → ACTIVE → COMPLETED
    - Any state → FAILED
    - ACTIVE → SILENT → HUNGUP (silence timeout)
    - ACTIVE → HUNGUP (voicemail detected)
    """
    INITIATED = "initiated"      # Call created, not yet ringing
    RINGING = "ringing"          # Call ringing (outbound) or answered (inbound)
    ACTIVE = "active"            # Call connected, media streaming
    SILENT = "silent"            # No audio detected for >20s (watchdog)
    HUNGUP = "hungup"           # Call ended by any party
    FAILED = "failed"           # Call failed to connect
    COMPLETED = "completed"      # Call ended successfully


class HangupReason(Enum):
    """
    Explicit hangup reasons for tracking and analytics.
    
    Ownership:
    - AI: Normal call completion by AI logic
    - WATCHDOG: Silence timeout triggered
    - VOICEMAIL: Voicemail detected in first 15s
    - USER: User hung up
    - SYSTEM: System error or timeout
    """
    AI_COMPLETE = "ai_complete"              # AI finished conversation
    SILENCE_TIMEOUT = "silence_timeout"      # No audio for 20s
    VOICEMAIL_DETECTED = "voicemail_detected"  # AMD detected voicemail
    USER_HANGUP = "user_hangup"             # User disconnected
    SYSTEM_ERROR = "system_error"           # Technical error
    NETWORK_FAILURE = "network_failure"     # Network issue
    TIMEOUT = "timeout"                     # General timeout
    FAILED_TO_CONNECT = "failed_to_connect"  # Call never connected


class CallStateMachine:
    """
    Manages call state transitions and ensures proper cleanup.
    
    Responsibilities:
    - Track current call state
    - Validate state transitions
    - Record hangup reason and owner
    - Ensure cleanup is called exactly once
    - Provide state history for debugging
    """
    
    def __init__(self, call_id: str):
        """
        Initialize state machine for a call.
        
        Args:
            call_id: Unique call identifier
        """
        self.call_id = call_id
        self.current_state = CallState.INITIATED
        self.hangup_reason: Optional[HangupReason] = None
        self.hangup_owner: Optional[str] = None
        self.cleanup_called = False
        
        # State history for debugging
        self.state_history = [
            {
                "state": CallState.INITIATED,
                "timestamp": datetime.utcnow().isoformat(),
                "reason": "call_created"
            }
        ]
        
        logger.info(f"[STATE_MACHINE] {call_id}: Initialized in state INITIATED")
    
    def transition_to(self, new_state: CallState, reason: str = "") -> bool:
        """
        Transition to a new state with validation.
        
        Args:
            new_state: Target state
            reason: Reason for transition (for logging)
            
        Returns:
            True if transition successful, False if invalid
        """
        # Validate transition
        valid = self._is_valid_transition(self.current_state, new_state)
        
        if not valid:
            logger.warning(
                f"[STATE_MACHINE] {self.call_id}: Invalid transition "
                f"{self.current_state.value} → {new_state.value}"
            )
            return False
        
        old_state = self.current_state
        self.current_state = new_state
        
        # Record in history
        self.state_history.append({
            "state": new_state,
            "timestamp": datetime.utcnow().isoformat(),
            "reason": reason,
            "from_state": old_state.value
        })
        
        logger.info(
            f"[STATE_MACHINE] {self.call_id}: "
            f"{old_state.value} → {new_state.value} (reason: {reason})"
        )
        
        return True
    
    def _is_valid_transition(self, from_state: CallState, to_state: CallState) -> bool:
        """Validate if state transition is allowed."""
        # Can always transition to FAILED, HUNGUP, or COMPLETED from any state
        if to_state in (CallState.FAILED, CallState.HUNGUP, CallState.COMPLETED):
            return True
        
        # Valid forward transitions
        valid_transitions = {
            CallState.INITIATED: [CallState.RINGING, CallState.ACTIVE],
            CallState.RINGING: [CallState.ACTIVE],
            CallState.ACTIVE: [CallState.SILENT],
            CallState.SILENT: []  # Can only go to terminal states
        }
        
        return to_state in valid_transitions.get(from_state, [])
    
    def mark_hangup(
        self,
        reason: HangupReason,
        owner: str,
        force: bool = False
    ) -> bool:
        """
        Mark call as hung up with reason and owner.
        
        Args:
            reason: Why the call was hung up
            owner: Who initiated hangup (ai, watchdog, voicemail, user, system)
            force: Force hangup even if already hung up
            
        Returns:
            True if hangup recorded, False if already hung up
        """
        if self.hangup_reason is not None and not force:
            logger.warning(
                f"[STATE_MACHINE] {self.call_id}: Already hung up "
                f"(reason: {self.hangup_reason.value}, owner: {self.hangup_owner})"
            )
            return False
        
        self.hangup_reason = reason
        self.hangup_owner = owner
        
        # Transition to HUNGUP state
        self.transition_to(CallState.HUNGUP, f"{owner}_{reason.value}")
        
        logger.info(
            f"[STATE_MACHINE] {self.call_id}: HANGUP recorded - "
            f"reason={reason.value}, owner={owner}"
        )
        
        return True
    
    def request_cleanup(self) -> bool:
        """
        Request cleanup of call resources.
        
        Ensures cleanup is called exactly once per call.
        
        Returns:
            True if cleanup should proceed, False if already cleaned up
        """
        if self.cleanup_called:
            logger.warning(
                f"[STATE_MACHINE] {self.call_id}: Cleanup already called"
            )
            return False
        
        self.cleanup_called = True
        logger.info(f"[STATE_MACHINE] {self.call_id}: Cleanup requested")
        return True
    
    def get_state_summary(self) -> Dict[str, Any]:
        """Get summary of current state for logging/debugging."""
        return {
            "call_id": self.call_id,
            "current_state": self.current_state.value,
            "hangup_reason": self.hangup_reason.value if self.hangup_reason else None,
            "hangup_owner": self.hangup_owner,
            "cleanup_called": self.cleanup_called,
            "state_history_count": len(self.state_history)
        }
    
    def is_terminal_state(self) -> bool:
        """Check if call is in a terminal state."""
        return self.current_state in (
            CallState.HUNGUP,
            CallState.FAILED,
            CallState.COMPLETED
        )
    
    def get_duration_in_state(self, state: CallState) -> Optional[float]:
        """
        Calculate how long call has been in a specific state.
        
        Args:
            state: State to check duration for
            
        Returns:
            Duration in seconds, or None if never in that state
        """
        # Find last time we entered this state
        for entry in reversed(self.state_history):
            if entry["state"] == state:
                timestamp = datetime.fromisoformat(entry["timestamp"])
                duration = (datetime.utcnow() - timestamp).total_seconds()
                return duration
        
        return None

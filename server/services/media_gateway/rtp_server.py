"""
RTP Server - UDP server for receiving/sending RTP packets from/to Asterisk
Implements proper RTP parsing, jitter buffer, and session management
"""
import asyncio
import logging
import struct
from typing import Dict, Optional, Callable, Tuple
from collections import deque
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)


@dataclass
class RTPPacket:
    """
    Parsed RTP packet structure.
    
    RTP Header (12 bytes minimum):
    - V (2 bits): Version (always 2)
    - P (1 bit): Padding
    - X (1 bit): Extension
    - CC (4 bits): CSRC count
    - M (1 bit): Marker
    - PT (7 bits): Payload type (0 = PCMU/g711 ulaw)
    - Sequence number (16 bits)
    - Timestamp (32 bits)
    - SSRC (32 bits)
    """
    version: int
    padding: bool
    extension: bool
    marker: bool
    payload_type: int
    sequence: int
    timestamp: int
    ssrc: int
    payload: bytes
    
    @classmethod
    def parse(cls, data: bytes) -> Optional['RTPPacket']:
        """
        Parse raw RTP packet data.
        
        Args:
            data: Raw UDP packet data
            
        Returns:
            RTPPacket object or None if invalid
        """
        if len(data) < 12:
            logger.warning(f"[RTP] Packet too short: {len(data)} bytes")
            return None
        
        try:
            # Parse RTP header
            byte0, byte1 = struct.unpack('!BB', data[0:2])
            
            version = (byte0 >> 6) & 0x3
            padding = bool((byte0 >> 5) & 0x1)
            extension = bool((byte0 >> 4) & 0x1)
            cc = byte0 & 0xF
            
            marker = bool((byte1 >> 7) & 0x1)
            payload_type = byte1 & 0x7F
            
            sequence, timestamp, ssrc = struct.unpack('!HIL', data[2:12])
            
            # Skip CSRC identifiers
            header_len = 12 + (cc * 4)
            
            # Skip extension if present
            if extension:
                if len(data) < header_len + 4:
                    return None
                ext_len = struct.unpack('!H', data[header_len+2:header_len+4])[0]
                header_len += 4 + (ext_len * 4)
            
            # Extract payload
            payload = data[header_len:]
            
            # Remove padding if present
            if padding and len(payload) > 0:
                padding_len = payload[-1]
                payload = payload[:-padding_len]
            
            return cls(
                version=version,
                padding=padding,
                extension=extension,
                marker=marker,
                payload_type=payload_type,
                sequence=sequence,
                timestamp=timestamp,
                ssrc=ssrc,
                payload=payload
            )
            
        except Exception as e:
            logger.error(f"[RTP] Failed to parse packet: {e}")
            return None
    
    def to_bytes(self) -> bytes:
        """
        Serialize RTP packet to bytes for transmission.
        
        Returns:
            Raw RTP packet bytes
        """
        # Build header
        byte0 = (2 << 6) | (int(self.padding) << 5) | (int(self.extension) << 4)
        byte1 = (int(self.marker) << 7) | (self.payload_type & 0x7F)
        
        header = struct.pack(
            '!BBHIL',
            byte0,
            byte1,
            self.sequence & 0xFFFF,
            self.timestamp & 0xFFFFFFFF,
            self.ssrc & 0xFFFFFFFF
        )
        
        return header + self.payload


class JitterBuffer:
    """
    Jitter buffer for RTP packets.
    
    Compensates for network jitter by buffering packets and releasing them
    in sequence order with proper timing (20ms frames).
    """
    
    def __init__(self, buffer_size: int = 5, frame_duration_ms: int = 20):
        """
        Initialize jitter buffer.
        
        Args:
            buffer_size: Number of packets to buffer
            frame_duration_ms: Expected frame duration in milliseconds
        """
        self.buffer_size = buffer_size
        self.frame_duration_ms = frame_duration_ms
        self.frame_duration_s = frame_duration_ms / 1000.0
        
        # Buffer: {sequence: (packet, arrival_time)}
        self.buffer: Dict[int, Tuple[RTPPacket, float]] = {}
        
        # Expected next sequence number
        self.next_sequence: Optional[int] = None
        
        # Statistics
        self.packets_received = 0
        self.packets_dropped = 0
        self.packets_late = 0
        
        logger.debug(f"[JITTER_BUFFER] Initialized: size={buffer_size}, frame_ms={frame_duration_ms}")
    
    def add_packet(self, packet: RTPPacket) -> None:
        """
        Add packet to jitter buffer.
        
        Args:
            packet: RTP packet to buffer
        """
        self.packets_received += 1
        
        # Initialize sequence tracking
        if self.next_sequence is None:
            self.next_sequence = packet.sequence
        
        # Check if packet is too late (already released)
        seq_diff = (packet.sequence - self.next_sequence) & 0xFFFF
        if seq_diff > 32768:  # Wrapped around, packet is late
            self.packets_late += 1
            logger.debug(f"[JITTER_BUFFER] Late packet: seq={packet.sequence}, expected={self.next_sequence}")
            return
        
        # Add to buffer
        self.buffer[packet.sequence] = (packet, time.time())
        
        # Trim buffer if too large
        if len(self.buffer) > self.buffer_size * 2:
            self._trim_buffer()
    
    def get_next_packet(self) -> Optional[RTPPacket]:
        """
        Get next packet in sequence from buffer.
        
        Returns:
            Next RTP packet or None if not available
        """
        if self.next_sequence is None:
            return None
        
        # Check if next packet is available
        if self.next_sequence in self.buffer:
            packet, _ = self.buffer.pop(self.next_sequence)
            self.next_sequence = (self.next_sequence + 1) & 0xFFFF
            return packet
        
        # Packet not available - check if we should skip it
        if len(self.buffer) >= self.buffer_size:
            # Buffer full, skip missing packet
            self.packets_dropped += 1
            logger.debug(f"[JITTER_BUFFER] Skipping missing packet: seq={self.next_sequence}")
            self.next_sequence = (self.next_sequence + 1) & 0xFFFF
            return self.get_next_packet()  # Try next
        
        return None
    
    def _trim_buffer(self):
        """Remove old packets from buffer."""
        if self.next_sequence is None:
            return
        
        # Remove packets older than buffer window
        cutoff = (self.next_sequence - self.buffer_size) & 0xFFFF
        to_remove = []
        
        for seq in self.buffer:
            if ((seq - cutoff) & 0xFFFF) > 32768:
                to_remove.append(seq)
        
        for seq in to_remove:
            self.buffer.pop(seq, None)
            self.packets_dropped += 1
    
    def get_stats(self) -> Dict[str, int]:
        """Get jitter buffer statistics."""
        return {
            "packets_received": self.packets_received,
            "packets_dropped": self.packets_dropped,
            "packets_late": self.packets_late,
            "buffer_size": len(self.buffer)
        }


class RTPSession:
    """
    RTP session for a single call.
    
    Manages RTP packets for one call, including jitter buffer,
    sequence tracking, and SSRC identification.
    """
    
    def __init__(
        self,
        call_id: str,
        remote_addr: Tuple[str, int],
        on_audio: Callable[[bytes], None]
    ):
        """
        Initialize RTP session.
        
        Args:
            call_id: Unique call identifier
            remote_addr: Remote IP and port
            on_audio: Callback for decoded audio (PCM16)
        """
        self.call_id = call_id
        self.remote_addr = remote_addr
        self.on_audio = on_audio
        
        # Jitter buffer
        self.jitter_buffer = JitterBuffer()
        
        # SSRC tracking
        self.ssrc: Optional[int] = None
        
        # Sequence and timestamp for outbound packets
        self.out_sequence = 0
        self.out_timestamp = 0
        
        # Statistics
        self.packets_received = 0
        self.packets_sent = 0
        
        logger.info(f"[RTP_SESSION] {call_id}: Created session for {remote_addr}")
    
    def handle_incoming_packet(self, packet: RTPPacket):
        """
        Handle incoming RTP packet.
        
        Args:
            packet: Parsed RTP packet
        """
        self.packets_received += 1
        
        # Track SSRC
        if self.ssrc is None:
            self.ssrc = packet.ssrc
            logger.debug(f"[RTP_SESSION] {self.call_id}: SSRC={packet.ssrc}")
        
        # Add to jitter buffer
        self.jitter_buffer.add_packet(packet)
    
    def get_next_audio_frame(self) -> Optional[bytes]:
        """
        Get next audio frame from jitter buffer.
        
        Returns:
            Audio payload (g711 ulaw) or None if not available
        """
        packet = self.jitter_buffer.get_next_packet()
        if packet:
            return packet.payload
        return None
    
    def create_outbound_packet(self, payload: bytes, marker: bool = False) -> RTPPacket:
        """
        Create outbound RTP packet.
        
        Args:
            payload: Audio data (g711 ulaw)
            marker: Marker bit (set for first packet after silence)
            
        Returns:
            RTP packet ready to send
        """
        packet = RTPPacket(
            version=2,
            padding=False,
            extension=False,
            marker=marker,
            payload_type=0,  # PCMU/g711 ulaw
            sequence=self.out_sequence,
            timestamp=self.out_timestamp,
            ssrc=self.ssrc or 12345,  # Use remote SSRC or default
            payload=payload
        )
        
        # Increment for next packet
        self.out_sequence = (self.out_sequence + 1) & 0xFFFF
        # 160 samples per 20ms frame at 8kHz
        self.out_timestamp = (self.out_timestamp + 160) & 0xFFFFFFFF
        
        self.packets_sent += 1
        
        return packet
    
    def get_stats(self) -> Dict[str, any]:
        """Get session statistics."""
        jitter_stats = self.jitter_buffer.get_stats()
        return {
            "call_id": self.call_id,
            "packets_received": self.packets_received,
            "packets_sent": self.packets_sent,
            "jitter_buffer": jitter_stats,
            "ssrc": self.ssrc
        }


class RTPServer:
    """
    UDP server for RTP packets.
    
    Listens on a UDP port range and routes packets to appropriate sessions.
    """
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port_start: int = 10000,
        port_end: int = 20000,
        on_packet: Optional[Callable] = None
    ):
        """
        Initialize RTP server.
        
        Args:
            host: Host to bind
            port_start: Start of port range
            port_end: End of port range
            on_packet: Optional callback for raw packets
        """
        self.host = host
        self.port_start = port_start
        self.port_end = port_end
        self.on_packet = on_packet
        
        # Sessions: {(remote_ip, remote_port): RTPSession}
        self.sessions: Dict[Tuple[str, int], RTPSession] = {}
        
        # Transport
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.protocol: Optional['RTPProtocol'] = None
        
        logger.info(f"[RTP_SERVER] Initialized: {host}:{port_start}-{port_end}")
    
    async def start(self):
        """Start RTP server."""
        loop = asyncio.get_event_loop()
        
        # Try to bind to a port in range
        for port in range(self.port_start, self.port_end):
            try:
                self.transport, self.protocol = await loop.create_datagram_endpoint(
                    lambda: RTPProtocol(self),
                    local_addr=(self.host, port)
                )
                logger.info(f"[RTP_SERVER] ✅ Started on {self.host}:{port}")
                return
            except OSError:
                continue
        
        raise RuntimeError(f"Failed to bind RTP server to any port in range {self.port_start}-{self.port_end}")
    
    async def stop(self):
        """Stop RTP server."""
        if self.transport:
            self.transport.close()
            logger.info("[RTP_SERVER] ✅ Stopped")
    
    def handle_packet(self, data: bytes, addr: Tuple[str, int]):
        """
        Handle incoming UDP packet.
        
        Args:
            data: Raw packet data
            addr: Source address (IP, port)
        """
        # Parse RTP packet
        packet = RTPPacket.parse(data)
        if not packet:
            return
        
        # Route to session
        session = self.sessions.get(addr)
        if session:
            session.handle_incoming_packet(packet)
        else:
            logger.debug(f"[RTP_SERVER] Packet from unknown source: {addr}")
        
        # Call optional callback
        if self.on_packet:
            self.on_packet(data, addr)
    
    def send_packet(self, packet: RTPPacket, addr: Tuple[str, int]):
        """
        Send RTP packet to address.
        
        Args:
            packet: RTP packet to send
            addr: Destination address (IP, port)
        """
        if self.transport:
            data = packet.to_bytes()
            self.transport.sendto(data, addr)
    
    def register_session(self, session: RTPSession):
        """
        Register RTP session.
        
        Args:
            session: RTP session to register
        """
        self.sessions[session.remote_addr] = session
        logger.info(f"[RTP_SERVER] Registered session for {session.remote_addr}")
    
    def unregister_session(self, remote_addr: Tuple[str, int]):
        """
        Unregister RTP session.
        
        Args:
            remote_addr: Remote address to unregister
        """
        if remote_addr in self.sessions:
            del self.sessions[remote_addr]
            logger.info(f"[RTP_SERVER] Unregistered session for {remote_addr}")


class RTPProtocol(asyncio.DatagramProtocol):
    """Asyncio protocol for RTP server."""
    
    def __init__(self, server: RTPServer):
        self.server = server
    
    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        """Handle received UDP datagram."""
        self.server.handle_packet(data, addr)
    
    def error_received(self, exc: Exception):
        """Handle protocol error."""
        logger.error(f"[RTP_PROTOCOL] Error: {exc}")

#!/usr/bin/env python3
"""
Benchmark DSP performance to verify < 1ms processing time

Tests processing time for typical telephony frames (20ms = 160 bytes)
to ensure real-time processing is feasible.
"""
import sys
import os
import time
import audioop
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.services.audio_dsp import AudioDSPProcessor

def generate_test_audio(duration_ms=20, frequency=440):
    """Generate test audio (pure tone)"""
    sample_rate = 8000
    num_samples = int(sample_rate * duration_ms / 1000)
    
    t = np.linspace(0, duration_ms / 1000, num_samples, endpoint=False)
    signal = np.sin(2 * np.pi * frequency * t) * 16000
    
    pcm16_data = signal.astype(np.int16).tobytes()
    mulaw_data = audioop.lin2ulaw(pcm16_data, 2)
    
    return mulaw_data

def benchmark_dsp():
    """Benchmark DSP processing time"""
    print("=" * 60)
    print("DSP Performance Benchmark")
    print("=" * 60)
    
    processor = AudioDSPProcessor()
    
    # Generate test audio (20ms frame)
    test_audio = generate_test_audio(duration_ms=20, frequency=440)
    print(f"\nTest audio: {len(test_audio)} bytes (20ms frame @ 8kHz)")
    
    # Warmup (first call may be slower due to JIT compilation)
    for _ in range(10):
        processor.process(test_audio)
    
    # Benchmark
    num_iterations = 1000
    print(f"\nBenchmarking {num_iterations} iterations...")
    
    start_time = time.perf_counter()
    for _ in range(num_iterations):
        processor.process(test_audio)
    end_time = time.perf_counter()
    
    # Calculate statistics
    total_time = end_time - start_time
    avg_time_ms = (total_time / num_iterations) * 1000
    fps = 1000 / avg_time_ms  # Frames per second
    realtime_factor = 20 / avg_time_ms  # How many times faster than real-time
    
    print("\n" + "=" * 60)
    print("Results")
    print("=" * 60)
    print(f"Total time:           {total_time:.3f} seconds")
    print(f"Average per frame:    {avg_time_ms:.3f} ms")
    print(f"Throughput:           {fps:.0f} frames/second")
    print(f"Real-time factor:     {realtime_factor:.1f}x (faster than real-time)")
    print(f"CPU overhead:         {(avg_time_ms / 20) * 100:.1f}% of frame duration")
    
    # Verdict
    print("\n" + "=" * 60)
    print("Verdict")
    print("=" * 60)
    
    if avg_time_ms < 1.0:
        print(f"✅ EXCELLENT: {avg_time_ms:.3f}ms < 1ms (< 5% overhead)")
        verdict = "excellent"
    elif avg_time_ms < 5.0:
        print(f"✅ GOOD: {avg_time_ms:.3f}ms < 5ms (< 25% overhead)")
        verdict = "good"
    elif avg_time_ms < 20.0:
        print(f"⚠️  WARNING: {avg_time_ms:.3f}ms is getting close to frame duration (20ms)")
        verdict = "warning"
    else:
        print(f"❌ FAIL: {avg_time_ms:.3f}ms > 20ms (cannot keep up with real-time!)")
        verdict = "fail"
    
    print(f"\nReal-time processing: {'✅ FEASIBLE' if realtime_factor > 1.0 else '❌ NOT FEASIBLE'}")
    
    return verdict

if __name__ == "__main__":
    verdict = benchmark_dsp()
    sys.exit(0 if verdict in ["excellent", "good"] else 1)

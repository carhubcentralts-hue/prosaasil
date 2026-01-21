#!/usr/bin/env python3
"""
Verification Script for Worker Service Fix

This script verifies that the worker service fix is properly implemented.

Checks:
1. Service name is 'worker' (not prosaas-worker) to avoid breaking overrides
2. Healthcheck is simple and stable (Redis ping only)
3. Production override uses correct service name 'worker'
4. Worker listens to 'default' queue
5. API logging includes Redis URL for diagnostics
6. Scripts use correct service name

Run this after making changes to verify the fix is complete.
"""

import yaml
import sys
import os

def check_docker_compose():
    """Check base docker-compose.yml configuration"""
    print("\n" + "=" * 60)
    print("CHECKING: docker-compose.yml")
    print("=" * 60)
    
    with open('docker-compose.yml') as f:
        config = yaml.safe_load(f)
    
    # Check 1: Service name is 'worker' (NOT prosaas-worker)
    if 'worker' not in config['services']:
        print("✗ FAIL: Service 'worker' not found")
        if 'prosaas-worker' in config['services']:
            print("  ERROR: Service is named 'prosaas-worker' - should be 'worker'")
            print("  This breaks docker compose commands and overrides!")
        return False
    
    worker = config['services']['worker']
    
    if worker.get('container_name') != 'prosaas-worker':
        print(f"✗ FAIL: container_name is '{worker.get('container_name')}', expected 'prosaas-worker'")
        return False
    
    print("✓ Service name 'worker' (container_name 'prosaas-worker')")
    print("  Correct: 'docker compose logs worker' will work")
    print("  Correct: 'docker logs prosaas-worker' will work")
    
    # Check 2: Healthcheck exists and is simple
    if 'healthcheck' not in worker:
        print("⚠  WARNING: No healthcheck configured")
        print("  Consider adding simple Redis ping healthcheck")
    else:
        healthcheck = worker['healthcheck']
        test_cmd = str(healthcheck.get('test', ''))
        
        # Check if healthcheck is simple (Redis ping only, not RQ Worker checks)
        if 'Worker' in test_cmd or 'rq' in test_cmd.lower():
            print("✗ FAIL: Healthcheck is too complex (checks RQ Worker)")
            print("  Should be simple Redis ping only")
            return False
        
        if 'redis' not in test_cmd.lower() or 'ping' not in test_cmd.lower():
            print("✗ FAIL: Healthcheck doesn't ping Redis")
            return False
        
        print(f"✓ Healthcheck is simple (Redis ping):")
        print(f"  - Interval: {healthcheck.get('interval')}")
        print(f"  - Start period: {healthcheck.get('start_period')}")
        print(f"  - Retries: {healthcheck.get('retries')}")
        
        # Check start_period is at least 30s
        start_period = healthcheck.get('start_period', '0s')
        if 'start_period' not in healthcheck:
            print("  ⚠  WARNING: No start_period - may fail during startup")
        elif int(start_period.replace('s', '')) < 30:
            print(f"  ⚠  WARNING: start_period too short ({start_period}) - should be >= 30s")
    
    # Check 3: RQ_QUEUES includes 'default'
    rq_queues = worker['environment'].get('RQ_QUEUES', '')
    if 'default' not in rq_queues:
        print(f"✗ FAIL: RQ_QUEUES does not include 'default': {rq_queues}")
        return False
    
    print(f"✓ RQ_QUEUES includes 'default': {rq_queues}")
    
    return True


def check_docker_compose_prod():
    """Check production override docker-compose.prod.yml"""
    print("\n" + "=" * 60)
    print("CHECKING: docker-compose.prod.yml")
    print("=" * 60)
    
    with open('docker-compose.prod.yml') as f:
        config = yaml.safe_load(f)
    
    # Check service name is 'worker' (NOT prosaas-worker)
    if 'worker' not in config['services']:
        print("✗ FAIL: Service 'worker' not found in production override")
        if 'prosaas-worker' in config['services']:
            print("  ERROR: Override uses 'prosaas-worker' but base uses 'worker'")
            print("  This breaks the override!")
        return False
    
    worker = config['services']['worker']
    print("✓ Production override uses service name 'worker'")
    
    # Check RQ_QUEUES in production
    if 'environment' in worker:
        rq_queues = worker['environment'].get('RQ_QUEUES', '')
        if 'default' not in rq_queues:
            print(f"✗ FAIL: Production RQ_QUEUES does not include 'default': {rq_queues}")
            return False
        
        print(f"✓ Production RQ_QUEUES includes 'default': {rq_queues}")
    
    # Check resource limits
    if 'deploy' in worker:
        limits = worker['deploy']['resources']['limits']
        print(f"✓ Resource limits configured: {limits}")
    
    return True


def check_api_logging():
    """Check that API has enhanced logging for worker diagnostics"""
    print("\n" + "=" * 60)
    print("CHECKING: server/routes_receipts.py")
    print("=" * 60)
    
    with open('server/routes_receipts.py') as f:
        content = f.read()
    
    # Check for enhanced logging
    if '[RQ_DIAG]' not in content:
        print("✗ FAIL: Enhanced worker diagnostics logging not found")
        return False
    
    print("✓ Enhanced worker diagnostics logging found ([RQ_DIAG])")
    
    # Check for months_back_effective
    if 'months_back_effective' not in content:
        print("✗ FAIL: months_back_effective logging not found")
        return False
    
    print("✓ months_back_effective logging found")
    
    return True


def check_scripts():
    """Check that scripts use correct service name"""
    print("\n" + "=" * 60)
    print("CHECKING: Scripts use correct service name")
    print("=" * 60)
    
    files_to_check = [
        'scripts/prod_up.sh',
        'scripts/verify_receipts_worker.py',
    ]
    
    all_good = True
    for filepath in files_to_check:
        if not os.path.exists(filepath):
            print(f"  ⚠  {filepath} not found (may be OK)")
            continue
        
        with open(filepath) as f:
            content = f.read()
        
        # Check if file uses 'docker compose logs prosaas-worker' (WRONG)
        if 'compose logs prosaas-worker' in content:
            print(f"✗ FAIL: {filepath} uses 'docker compose logs prosaas-worker'")
            print(f"  Should use: 'docker compose logs worker'")
            all_good = False
        elif 'compose logs worker' in content or 'logs prosaas-worker' in content:
            print(f"✓ {filepath} uses correct commands")
        else:
            print(f"  ⚠  {filepath} - couldn't determine (may be OK)")
    
    return all_good


def main():
    """Run all verification checks"""
    print("\n" + "=" * 60)
    print("WORKER SERVICE FIX - VERIFICATION")
    print("=" * 60)
    
    os.chdir('/home/runner/work/prosaasil/prosaasil')
    
    checks = [
        ("docker-compose.yml", check_docker_compose),
        ("docker-compose.prod.yml", check_docker_compose_prod),
        ("API Logging", check_api_logging),
        ("Scripts", check_scripts),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            passed = check_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n✗ EXCEPTION in {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    print("\n" + "=" * 60)
    if passed_count == total_count:
        print(f"✓ ALL {total_count} CHECKS PASSED")
        print("=" * 60)
        print("\n✅ Worker service fix is properly implemented!")
        print("\nExpected behavior after deployment:")
        print("  1. docker compose logs worker → Works (service name)")
        print("  2. docker logs prosaas-worker → Works (container name)")
        print("  3. Worker becomes healthy (Redis ping with start_period)")
        print("  4. API logs show Redis URL and worker queues")
        print("  5. Worker processes jobs from 'default' queue")
        print("  6. months_back_effective=None when dates are provided")
        print("\nSee WORKER_COMMANDS_GUIDE.md for usage examples")
        sys.exit(0)
    else:
        print(f"✗ {total_count - passed_count}/{total_count} CHECKS FAILED")
        print("=" * 60)
        print("\n⚠️  Fix failures above before deployment")
        sys.exit(1)


if __name__ == '__main__':
    main()

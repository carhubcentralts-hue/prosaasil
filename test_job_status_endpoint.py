"""
Test job status endpoint for delete leads
Verifies that /api/jobs/<job_id> returns proper responses
"""
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_job_status_endpoint():
    """
    Test the /api/jobs/<job_id> endpoint
    
    This test verifies:
    1. Endpoint exists and is accessible
    2. Returns 200 OK for existing jobs
    3. Returns 200 OK with 'unknown' status for non-existent jobs (not 404)
    4. Includes all required fields in the response
    """
    from flask import Flask
    from server.routes_leads import leads_bp
    from server.models_sql import db, BackgroundJob, Business, User
    from server.auth_api import create_session_token
    
    # Create test Flask app
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///:memory:')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['TESTING'] = True
    
    db.init_app(app)
    app.register_blueprint(leads_bp)
    
    with app.app_context():
        # Create tables
        db.create_all()
        
        # Create test business
        business = Business(
            name="Test Business",
            business_type="general"
        )
        db.session.add(business)
        db.session.commit()
        
        # Create test user
        user = User(
            email="test@example.com",
            name="Test User",
            role="owner",
            business_id=business.id
        )
        db.session.add(user)
        db.session.commit()
        
        # Create test job
        job = BackgroundJob(
            business_id=business.id,
            requested_by_user_id=user.id,
            job_type='delete_leads',
            status='completed',
            total=10,
            processed=10,
            succeeded=10,
            failed_count=0
        )
        db.session.add(job)
        db.session.commit()
        
        job_id = job.id
        business_id = business.id
        
        # Create test client
        client = app.test_client()
        
        # Create session token for authentication
        token = create_session_token(user.id, user.email, user.role, business_id)
        
        print("=" * 70)
        print("🧪 Testing /api/jobs/<job_id> endpoint")
        print("=" * 70)
        
        # Test 1: Get existing job status
        print("\n✅ Test 1: Get status of existing job")
        response = client.get(
            f'/api/jobs/{job_id}',
            headers={'Authorization': f'Bearer {token}'}
        )
        
        print(f"   Status code: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.get_json()
        print(f"   Response: {data}")
        
        assert data['success'] == True, "Expected success=True"
        assert data['status'] == 'completed', "Expected status=completed"
        assert data['job_id'] == job_id, f"Expected job_id={job_id}"
        assert data['total'] == 10, "Expected total=10"
        assert data['processed'] == 10, "Expected processed=10"
        assert data['succeeded'] == 10, "Expected succeeded=10"
        
        print("   ✓ All fields correct")
        
        # Test 2: Get non-existent job (should return 200 with unknown status)
        print("\n✅ Test 2: Get status of non-existent job (should return 200 OK)")
        non_existent_job_id = 99999
        response = client.get(
            f'/api/jobs/{non_existent_job_id}',
            headers={'Authorization': f'Bearer {token}'}
        )
        
        print(f"   Status code: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.get_json()
        print(f"   Response: {data}")
        
        assert data['success'] == True, "Expected success=True"
        assert data['status'] == 'unknown', "Expected status=unknown"
        assert data['job_id'] == non_existent_job_id, f"Expected job_id={non_existent_job_id}"
        assert 'message' in data, "Expected message field"
        
        print("   ✓ Returns 200 OK with 'unknown' status (not 404)")
        
        # Test 3: Verify required fields are present
        print("\n✅ Test 3: Verify all required fields are present")
        response = client.get(
            f'/api/jobs/{job_id}',
            headers={'Authorization': f'Bearer {token}'}
        )
        data = response.get_json()
        
        required_fields = [
            'success', 'job_id', 'status', 'total', 'processed',
            'succeeded', 'failed_count', 'percent', 'is_stuck'
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
            print(f"   ✓ Field '{field}' present")
        
        print("\n" + "=" * 70)
        print("✅ All tests passed!")
        print("=" * 70)
        print("\n📌 Summary:")
        print("   - Endpoint exists and is accessible")
        print("   - Returns 200 OK for existing jobs")
        print("   - Returns 200 OK with 'unknown' status for non-existent jobs (not 404)")
        print("   - All required fields are present in the response")
        print("   - UI polling will not show error toasts anymore! 🎉")

if __name__ == '__main__':
    test_job_status_endpoint()

"""
Test for N+1 query fix in routes_intelligence.py
Verifies that the customer intelligence endpoint executes a bounded number of queries
regardless of the number of customers returned.
"""
import os
import pytest
from unittest.mock import patch, MagicMock


def test_intelligence_customers_n_plus_1_fix():
    """
    Test that /api/intelligence/customers endpoint uses aggregated queries
    instead of N+1 pattern (4 queries per customer).
    
    For 50 customers, should execute single-digit queries, not 200+.
    """
    os.environ['MIGRATION_MODE'] = '1'
    os.environ['TESTING'] = '1'
    
    from server.app_factory import create_app
    from server.models_sql import db, Business, Customer, Lead, CallLog
    from flask import Flask
    
    app = create_app()
    
    with app.app_context():
        # Create test business
        business = Business(
            name="Test Business Intelligence",
            business_type="general",
            is_active=True
        )
        db.session.add(business)
        db.session.flush()
        
        # Create test customers
        customers = []
        for i in range(10):  # Create 10 customers for testing
            customer = Customer(
                business_id=business.id,
                name=f"Customer {i}",
                phone_e164=f"+97250123456{i}"
            )
            customers.append(customer)
            db.session.add(customer)
        
        db.session.flush()
        
        # Create some test leads
        for i in range(5):
            lead = Lead(
                tenant_id=business.id,
                name=f"Lead {i}",
                phone_e164=f"+97250123456{i}",
                source="call",
                status="new"
            )
            db.session.add(lead)
        
        # Create some test calls
        for i in range(5):
            call = CallLog(
                business_id=business.id,
                from_number=f"+97250123456{i}",
                to_number="+972501111111",
                call_sid=f"CA{i}",
                status="completed"
            )
            db.session.add(call)
        
        db.session.commit()
        
        # Test the endpoint with query counting
        with app.test_client() as client:
            # Mock authentication
            with patch('server.auth_api.require_api_auth') as mock_auth:
                def auth_decorator(roles):
                    def decorator(f):
                        def wrapper(*args, **kwargs):
                            # Set business context
                            from flask import request
                            request.business_id = business.id
                            return f(*args, **kwargs)
                        wrapper.__name__ = f.__name__
                        return wrapper
                    return decorator
                
                mock_auth.side_effect = auth_decorator
                
                # Import and register blueprint after mocking auth
                from server.routes_intelligence import intelligence_bp
                app.register_blueprint(intelligence_bp)
                
                # Track query count using SQLAlchemy event
                query_count = {'count': 0}
                
                def count_queries(conn, cursor, statement, parameters, context, executemany):
                    # Count only SELECT queries (ignore SET timezone, etc.)
                    if statement.strip().upper().startswith('SELECT'):
                        query_count['count'] += 1
                
                from sqlalchemy import event
                event.listen(db.engine, "before_cursor_execute", count_queries)
                
                try:
                    # Make request
                    response = client.get(
                        '/api/intelligence/customers',
                        headers={'Authorization': 'Bearer test_token'}
                    )
                    
                    # Verify response is successful
                    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.data}"
                    
                    # Verify query count is bounded (not N+1)
                    # With the fix, we should have:
                    # 1. Query to fetch customers (1)
                    # 2. Query for leads counts (1)
                    # 3. Query for calls counts (1)
                    # 4. Query for latest leads (1)
                    # 5. Query for last calls (1)
                    # Total: ~5-7 queries regardless of customer count
                    
                    # Old N+1 pattern would be: 1 + (10 customers × 4 queries) = 41 queries
                    # New aggregated pattern should be: ~5-10 queries total
                    
                    print(f"Query count: {query_count['count']}")
                    
                    # Assert that query count is bounded (not linear with customer count)
                    # Allow some buffer for other queries (business lookup, etc.)
                    assert query_count['count'] < 20, \
                        f"Query count {query_count['count']} is too high. Expected < 20 for 10 customers. " \
                        f"N+1 pattern would be 41+ queries."
                    
                    # Verify response structure
                    data = response.get_json()
                    assert isinstance(data, list), "Response should be a list"
                    assert len(data) <= 10, "Should return at most 10 customers"
                    
                    print(f"✅ N+1 fix verified: {query_count['count']} queries for {len(data)} customers")
                    
                finally:
                    # Remove event listener
                    event.remove(db.engine, "before_cursor_execute", count_queries)
        
        # Cleanup
        db.session.rollback()


def test_intelligence_customers_response_structure():
    """
    Test that the response structure is correct after the N+1 fix.
    Ensures that proxy objects work correctly and return expected data.
    """
    os.environ['MIGRATION_MODE'] = '1'
    os.environ['TESTING'] = '1'
    
    from server.app_factory import create_app
    from server.models_sql import db, Business, Customer, Lead, CallLog
    from flask import Flask
    
    app = create_app()
    
    with app.app_context():
        # Create test business
        business = Business(
            name="Test Business Structure",
            business_type="general",
            is_active=True
        )
        db.session.add(business)
        db.session.flush()
        
        # Create a customer
        customer = Customer(
            business_id=business.id,
            name="Test Customer",
            phone_e164="+972501234567"
        )
        db.session.add(customer)
        db.session.flush()
        
        # Create a lead for the customer
        lead = Lead(
            tenant_id=business.id,
            name="Test Lead",
            phone_e164="+972501234567",
            source="call",
            status="qualified",
            notes="Test notes for the lead"
        )
        db.session.add(lead)
        db.session.flush()
        
        # Create a call for the customer
        call = CallLog(
            business_id=business.id,
            from_number="+972501234567",
            to_number="+972501111111",
            call_sid="CA123",
            status="completed",
            transcription="Test call transcription"
        )
        db.session.add(call)
        db.session.commit()
        
        # Test the endpoint
        with app.test_client() as client:
            # Mock authentication
            with patch('server.auth_api.require_api_auth') as mock_auth:
                def auth_decorator(roles):
                    def decorator(f):
                        def wrapper(*args, **kwargs):
                            from flask import request
                            request.business_id = business.id
                            return f(*args, **kwargs)
                        wrapper.__name__ = f.__name__
                        return wrapper
                    return decorator
                
                mock_auth.side_effect = auth_decorator
                
                # Import and register blueprint
                from server.routes_intelligence import intelligence_bp
                app.register_blueprint(intelligence_bp)
                
                # Make request
                response = client.get('/api/intelligence/customers')
                
                # Verify response
                assert response.status_code == 200
                data = response.get_json()
                
                assert len(data) == 1, "Should return 1 customer"
                
                customer_data = data[0]
                assert customer_data['name'] == "Test Customer"
                assert customer_data['phone_e164'] == "+972501234567"
                assert customer_data['leads_count'] == 1
                assert customer_data['calls_count'] == 1
                
                # Verify latest lead data
                assert 'latest_lead' in customer_data
                latest_lead = customer_data['latest_lead']
                assert latest_lead['status'] == 'qualified'
                assert latest_lead['notes'] == "Test notes for the lead"
                
                # Verify recent activity
                assert 'recent_activity' in customer_data
                assert len(customer_data['recent_activity']) > 0
                
                print("✅ Response structure verified after N+1 fix")
        
        # Cleanup
        db.session.rollback()


if __name__ == "__main__":
    test_intelligence_customers_n_plus_1_fix()
    test_intelligence_customers_response_structure()
    print("All tests passed!")

"""
Agent API Routes - Endpoints for AI Agent interactions
Provides REST API for agent-powered conversations and actions
"""
from flask import Blueprint, request, jsonify
from server.agent_tools.agent_factory import get_agent, AGENTS_ENABLED
from server.models_sql import db, Business
import logging

logger = logging.getLogger(__name__)

bp = Blueprint("agent_api", __name__, url_prefix="/api/agent")

@bp.post("/booking")
def agent_booking():
    """
    Process a booking request with the AI agent
    
    Request JSON:
    {
        "text": "רוצה לקבוע מסאז' מחר ב-10",
        "business_id": 1,
        "customer_name": "יוסי כהן",
        "customer_phone": "+972501234567",
        "source": "call" | "whatsapp" | "web",
        "context": {...}  # Optional conversation context
    }
    
    Response JSON:
    {
        "reply": "מעולה! קבעתי לך...",
        "tool_calls": [...],  # List of tools that were executed
        "final_data": {...},  # Structured output if any
        "agent_enabled": true
    }
    """
    if not AGENTS_ENABLED:
        return jsonify({
            "error": "Agents are disabled",
            "agent_enabled": False
        }), 503
    
    try:
        # Parse request
        data = request.get_json(force=True)
        user_text = data.get("text", "")
        business_id = data.get("business_id")
        
        if not user_text:
            return jsonify({"error": "Missing 'text' field"}), 400
        if not business_id:
            return jsonify({"error": "Missing 'business_id' field"}), 400
        
        # Get business name for agent personalization
        business = Business.query.get(business_id)
        business_name = business.name if business else "העסק שלנו"
        
        # Build context for the agent
        context = {
            "business_id": business_id,
            "business_name": business_name,
            "customer_name": data.get("customer_name", ""),
            "customer_phone": data.get("customer_phone", ""),
            "source": data.get("source", "api"),
            **data.get("context", {})
        }
        
        # Get or create booking agent
        agent = get_agent(agent_type="booking", business_name=business_name)
        
        if not agent:
            return jsonify({
                "error": "Failed to create agent",
                "agent_enabled": False
            }), 500
        
        # Run the agent
        logger.info(f"🤖 Running agent for business {business_id}: '{user_text[:50]}...'")
        
        # Note: We'll use a simplified approach here
        # The actual Agent SDK might have different API
        result = agent.run(
            input=user_text,
            context=context
        )
        
        # Extract response
        reply_text = result.output_text if hasattr(result, 'output_text') else str(result)
        tool_calls = result.tool_calls if hasattr(result, 'tool_calls') else []
        final_data = result.output_data if hasattr(result, 'output_data') else None
        
        logger.info(f"✅ Agent completed with {len(tool_calls)} tool calls")
        
        return jsonify({
            "reply": reply_text,
            "tool_calls": [call.dict() if hasattr(call, 'dict') else str(call) for call in tool_calls],
            "final_data": final_data,
            "agent_enabled": True
        })
        
    except Exception as e:
        logger.error(f"Agent error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": str(e),
            "agent_enabled": AGENTS_ENABLED
        }), 500


@bp.post("/sales")
def agent_sales():
    """
    Process a sales inquiry with the AI agent
    
    Similar to /booking but uses sales-focused agent
    """
    if not AGENTS_ENABLED:
        return jsonify({
            "error": "Agents are disabled",
            "agent_enabled": False
        }), 503
    
    try:
        data = request.get_json(force=True)
        user_text = data.get("text", "")
        business_id = data.get("business_id")
        
        if not user_text:
            return jsonify({"error": "Missing 'text' field"}), 400
        if not business_id:
            return jsonify({"error": "Missing 'business_id' field"}), 400
        
        # Get business
        business = Business.query.get(business_id)
        business_name = business.name if business else "העסק שלנו"
        
        # Context
        context = {
            "business_id": business_id,
            "business_name": business_name,
            "customer_name": data.get("customer_name", ""),
            "customer_phone": data.get("customer_phone", ""),
            "source": data.get("source", "api"),
            **data.get("context", {})
        }
        
        # Get sales agent
        agent = get_agent(agent_type="sales", business_name=business_name)
        
        if not agent:
            return jsonify({
                "error": "Failed to create agent",
                "agent_enabled": False
            }), 500
        
        # Run
        result = agent.run(input=user_text, context=context)
        
        reply_text = result.output_text if hasattr(result, 'output_text') else str(result)
        tool_calls = result.tool_calls if hasattr(result, 'tool_calls') else []
        
        return jsonify({
            "reply": reply_text,
            "tool_calls": [call.dict() if hasattr(call, 'dict') else str(call) for call in tool_calls],
            "agent_enabled": True
        })
        
    except Exception as e:
        logger.error(f"Sales agent error: {e}")
        return jsonify({
            "error": str(e),
            "agent_enabled": AGENTS_ENABLED
        }), 500


@bp.get("/status")
def agent_status():
    """Check if agents are enabled and available"""
    return jsonify({
        "agents_enabled": AGENTS_ENABLED,
        "available_types": ["booking", "sales"] if AGENTS_ENABLED else []
    })

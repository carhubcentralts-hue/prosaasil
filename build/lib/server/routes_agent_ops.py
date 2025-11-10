"""
Agent Operations API - Unified endpoint for AgentKit full operations
Handles appointments, leads, invoices, contracts, WhatsApp, and summaries
"""
from flask import Blueprint, request, jsonify, g
from server.agent_tools.agent_factory import create_ops_agent, get_agent
from server.models_sql import db, AgentTrace
from datetime import datetime
import logging
import time

logger = logging.getLogger(__name__)

# Create blueprint
ops_bp = Blueprint("agent_ops", __name__, url_prefix="/api/agent")

@ops_bp.route("/ops", methods=["POST"])
def agent_ops():
    """
    Unified AgentKit operations endpoint
    
    Request:
    {
        "text": "User message",
        "messages": [{"role": "user", "content": "..."}],  // optional conversation history
        "business_id": 1,
        "customer_phone": "+972...",  // optional
        "whatsapp_from": "+972...",   // optional
        "channel": "voice|whatsapp|web",
        "conversation_id": "...",     // optional
        "duration_min": 60            // optional, for appointments
    }
    
    Response:
    {
        "reply": "Agent's Hebrew response",
        "tool_calls": [{...}],
        "data": {...},
        "status": "success|error"
    }
    """
    start_time = time.time()
    
    try:
        # Parse request
        data = request.get_json(force=True)
        
        user_text = data.get("text", "")
        history = data.get("messages", [])
        
        # Context for tools
        business_id = data.get("business_id")
        if not business_id:
            return jsonify({
                "error": "Missing business_id",
                "status": "error"
            }), 400
        
        customer_phone = data.get("customer_phone")
        whatsapp_from = data.get("whatsapp_from")
        channel = data.get("channel", "agent")
        conversation_id = data.get("conversation_id")
        duration_min = data.get("duration_min", 60)
        
        # Build context
        ctx = {
            "business_id": business_id,
            "customer_phone": customer_phone,
            "whatsapp_from": whatsapp_from,
            "channel": channel,
            "tz": "Asia/Jerusalem",
            "locale": "he-IL",
            "conversation_id": conversation_id,
            "duration_min": duration_min,
            "user_text": user_text
        }
        
        logger.info(f"🎯 Agent ops request: business_id={business_id}, channel={channel}, text='{user_text[:50]}...'")
        
        # Get agent
        from server.models_sql import Business
        business = Business.query.get(business_id)
        business_name = business.name if business else "העסק"
        
        # Use ops agent
        agent = get_agent(
            agent_type="ops",
            business_name=business_name,
            business_id=business_id,
            channel=channel
        )
        
        if not agent:
            return jsonify({
                "error": "Agents disabled (AGENTS_ENABLED=0)",
                "status": "error"
            }), 503
        
        # Prepare messages
        messages = history + [{"role": "user", "content": user_text}]
        
        # Run agent
        result = agent.run(messages=messages, context=ctx)
        
        # Extract response
        reply = result.output_text if hasattr(result, 'output_text') else str(result)
        tool_calls = []
        output_data = {}
        
        if hasattr(result, 'tool_calls') and result.tool_calls:
            tool_calls = [
                {
                    "tool": tc.name if hasattr(tc, 'name') else str(tc),
                    "args": tc.arguments if hasattr(tc, 'arguments') else {},
                    "result": tc.result if hasattr(tc, 'result') else None
                }
                for tc in result.tool_calls
            ]
        
        if hasattr(result, 'output_data'):
            output_data = result.output_data
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Log trace
        try:
            trace = AgentTrace()
            trace.business_id = business_id
            trace.agent_type = "ops"
            trace.channel = channel
            trace.customer_phone = customer_phone
            trace.user_message = user_text
            trace.agent_response = reply
            trace.tool_calls = tool_calls
            trace.tool_count = len(tool_calls)
            trace.status = "success"
            trace.duration_ms = duration_ms
            
            db.session.add(trace)
            db.session.commit()
        except Exception as e:
            logger.error(f"Failed to log agent trace: {e}")
            # Don't fail the request if logging fails
        
        logger.info(f"✅ Agent ops completed in {duration_ms}ms, {len(tool_calls)} tools used")
        
        return jsonify({
            "reply": reply,
            "tool_calls": tool_calls,
            "data": output_data,
            "status": "success",
            "duration_ms": duration_ms
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Agent ops error: {e}", exc_info=True)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Log error trace
        try:
            trace = AgentTrace()
            trace.business_id = data.get("business_id") if data else None
            trace.agent_type = "ops"
            trace.channel = data.get("channel", "unknown") if data else "unknown"
            trace.user_message = data.get("text", "") if data else ""
            trace.status = "error"
            trace.error_message = str(e)
            trace.duration_ms = duration_ms
            
            db.session.add(trace)
            db.session.commit()
        except:
            pass
        
        return jsonify({
            "error": "Internal error processing request",
            "status": "error",
            "duration_ms": duration_ms
        }), 500

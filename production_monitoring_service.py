"""
Task 10: Production Logging and Monitoring Service
שירות מוניטורינג ולוגינג מתקדם לסביבת ייצור
"""

import logging
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from app import db
from models import CallLog, ConversationTurn, CRMCustomer, Business

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class ProductionMonitoringService:
    """Task 10: Comprehensive production monitoring and logging"""
    
    def __init__(self):
        self.metrics_cache = {}
        self.last_update = None
        
    def log_system_event(self, event_type: str, details: Dict[str, Any], 
                        level: str = 'info') -> None:
        """Task 10: Structured system event logging"""
        try:
            log_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'event_type': event_type,
                'details': details,
                'level': level,
                'service': 'hebrew_ai_call_center'
            }
            
            # Log to file and console based on level
            if level == 'error':
                logger.error(f"🚨 {event_type}: {json.dumps(details, ensure_ascii=False)}")
            elif level == 'warning':
                logger.warning(f"⚠️ {event_type}: {json.dumps(details, ensure_ascii=False)}")
            else:
                logger.info(f"ℹ️ {event_type}: {json.dumps(details, ensure_ascii=False)}")
                
        except Exception as e:
            logger.error(f"Error logging system event: {e}")
    
    def collect_performance_metrics(self) -> Dict[str, Any]:
        """Task 10: Collect comprehensive performance metrics"""
        try:
            metrics = {}
            
            # Database performance metrics
            metrics['database'] = self._collect_database_metrics()
            
            # Call processing metrics
            metrics['calls'] = self._collect_call_metrics()
            
            # Customer interaction metrics
            metrics['customers'] = self._collect_customer_metrics()
            
            # AI processing metrics
            metrics['ai_processing'] = self._collect_ai_metrics()
            
            # System resource metrics
            metrics['system'] = self._collect_system_metrics()
            
            # Cache metrics for performance
            self.metrics_cache = metrics
            self.last_update = datetime.utcnow()
            
            self.log_system_event('metrics_collected', {
                'metrics_count': len(metrics),
                'collection_time': datetime.utcnow().isoformat()
            })
            
            return metrics
            
        except Exception as e:
            self.log_system_event('metrics_collection_error', {
                'error': str(e)
            }, 'error')
            return {}
    
    def _collect_database_metrics(self) -> Dict[str, Any]:
        """Collect database performance metrics"""
        try:
            # Query execution times and counts
            total_businesses = Business.query.count()
            active_businesses = Business.query.filter_by(is_active=True).count()
            total_customers = CRMCustomer.query.count()
            active_customers = CRMCustomer.query.filter_by(status='active').count()
            total_calls = CallLog.query.count()
            total_turns = ConversationTurn.query.count()
            
            # Recent activity
            last_24h = datetime.utcnow() - timedelta(hours=24)
            recent_calls = CallLog.query.filter(CallLog.created_at >= last_24h).count()
            recent_customers = CRMCustomer.query.filter(CRMCustomer.created_at >= last_24h).count()
            
            return {
                'businesses': {'total': total_businesses, 'active': active_businesses},
                'customers': {'total': total_customers, 'active': active_customers},
                'calls': {'total': total_calls, 'recent_24h': recent_calls},
                'conversation_turns': total_turns,
                'activity': {
                    'new_customers_24h': recent_customers,
                    'calls_24h': recent_calls
                }
            }
            
        except Exception as e:
            logger.error(f"Error collecting database metrics: {e}")
            return {}
    
    def _collect_call_metrics(self) -> Dict[str, Any]:
        """Collect call processing metrics"""
        try:
            # Call duration statistics
            calls = CallLog.query.filter(CallLog.duration.isnot(None)).all()
            durations = [call.duration for call in calls if call.duration]
            
            if durations:
                avg_duration = sum(durations) / len(durations)
                max_duration = max(durations)
                min_duration = min(durations)
            else:
                avg_duration = max_duration = min_duration = 0
            
            # Call outcomes
            completed_calls = CallLog.query.filter_by(status='completed').count()
            failed_calls = CallLog.query.filter_by(status='failed').count()
            
            # Success rate
            total_calls = CallLog.query.count()
            success_rate = (completed_calls / total_calls * 100) if total_calls > 0 else 0
            
            return {
                'duration_stats': {
                    'average': avg_duration,
                    'maximum': max_duration,
                    'minimum': min_duration
                },
                'outcomes': {
                    'completed': completed_calls,
                    'failed': failed_calls,
                    'success_rate': round(success_rate, 2)
                },
                'total_processed': total_calls
            }
            
        except Exception as e:
            logger.error(f"Error collecting call metrics: {e}")
            return {}
    
    def _collect_customer_metrics(self) -> Dict[str, Any]:
        """Collect customer interaction metrics"""
        try:
            # Customer sources
            source_counts = defaultdict(int)
            customers = CRMCustomer.query.all()
            
            for customer in customers:
                source_counts[customer.source or 'unknown'] += 1
            
            # Customer lifecycle metrics
            new_customers_week = CRMCustomer.query.filter(
                CRMCustomer.created_at >= datetime.utcnow() - timedelta(days=7)
            ).count()
            
            # Interaction frequency
            active_customers = CRMCustomer.query.filter_by(status='active').count()
            
            return {
                'sources': dict(source_counts),
                'lifecycle': {
                    'new_this_week': new_customers_week,
                    'currently_active': active_customers
                },
                'total': len(customers)
            }
            
        except Exception as e:
            logger.error(f"Error collecting customer metrics: {e}")
            return {}
    
    def _collect_ai_metrics(self) -> Dict[str, Any]:
        """Collect AI processing metrics"""
        try:
            # Conversation analysis
            turns = ConversationTurn.query.all()
            total_turns = len(turns)
            
            # Response types
            ai_responses = len([turn for turn in turns if turn.speaker == 'assistant'])
            user_inputs = len([turn for turn in turns if turn.speaker == 'user'])
            
            # Average response length
            ai_turn_lengths = [len(turn.message) for turn in turns if turn.speaker == 'assistant' and turn.message]
            avg_response_length = sum(ai_turn_lengths) / len(ai_turn_lengths) if ai_turn_lengths else 0
            
            return {
                'conversation_turns': {
                    'total': total_turns,
                    'ai_responses': ai_responses,
                    'user_inputs': user_inputs
                },
                'response_quality': {
                    'average_length': round(avg_response_length, 2)
                }
            }
            
        except Exception as e:
            logger.error(f"Error collecting AI metrics: {e}")
            return {}
    
    def _collect_system_metrics(self) -> Dict[str, Any]:
        """Collect system resource metrics"""
        try:
            import psutil
            
            # Memory usage
            memory = psutil.virtual_memory()
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            
            return {
                'memory': {
                    'total_mb': round(memory.total / 1024 / 1024, 2),
                    'used_mb': round(memory.used / 1024 / 1024, 2),
                    'percent': memory.percent
                },
                'cpu': {
                    'percent': cpu_percent
                },
                'disk': {
                    'total_gb': round(disk.total / 1024 / 1024 / 1024, 2),
                    'used_gb': round(disk.used / 1024 / 1024 / 1024, 2),
                    'percent': round(disk.used / disk.total * 100, 2)
                }
            }
            
        except ImportError:
            # psutil not available, return basic metrics
            return {
                'memory': {'status': 'monitoring_unavailable'},
                'cpu': {'status': 'monitoring_unavailable'},
                'disk': {'status': 'monitoring_unavailable'}
            }
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return {}
    
    def generate_health_report(self) -> Dict[str, Any]:
        """Task 10: Generate comprehensive health report"""
        try:
            # Collect fresh metrics
            metrics = self.collect_performance_metrics()
            
            # Analyze health indicators
            health_indicators = {}
            
            # Database health
            if metrics.get('database'):
                db_metrics = metrics['database']
                health_indicators['database'] = {
                    'status': 'healthy' if db_metrics.get('businesses', {}).get('active', 0) > 0 else 'warning',
                    'active_businesses': db_metrics.get('businesses', {}).get('active', 0),
                    'recent_activity': db_metrics.get('activity', {}).get('calls_24h', 0)
                }
            
            # Call processing health
            if metrics.get('calls'):
                call_metrics = metrics['calls']
                success_rate = call_metrics.get('outcomes', {}).get('success_rate', 0)
                health_indicators['calls'] = {
                    'status': 'healthy' if success_rate >= 80 else 'warning' if success_rate >= 60 else 'critical',
                    'success_rate': success_rate,
                    'total_processed': call_metrics.get('total_processed', 0)
                }
            
            # System resource health
            if metrics.get('system'):
                sys_metrics = metrics['system']
                memory_percent = sys_metrics.get('memory', {}).get('percent', 0)
                cpu_percent = sys_metrics.get('cpu', {}).get('percent', 0)
                
                resource_status = 'healthy'
                if memory_percent > 90 or cpu_percent > 90:
                    resource_status = 'critical'
                elif memory_percent > 75 or cpu_percent > 75:
                    resource_status = 'warning'
                
                health_indicators['system'] = {
                    'status': resource_status,
                    'memory_percent': memory_percent,
                    'cpu_percent': cpu_percent
                }
            
            # Overall health assessment
            statuses = [indicator['status'] for indicator in health_indicators.values()]
            if 'critical' in statuses:
                overall_status = 'critical'
            elif 'warning' in statuses:
                overall_status = 'warning'
            else:
                overall_status = 'healthy'
            
            health_report = {
                'overall_status': overall_status,
                'indicators': health_indicators,
                'metrics': metrics,
                'generated_at': datetime.utcnow().isoformat(),
                'system_uptime': self._get_uptime()
            }
            
            # Log health report generation
            self.log_system_event('health_report_generated', {
                'overall_status': overall_status,
                'indicators_count': len(health_indicators)
            })
            
            return health_report
            
        except Exception as e:
            self.log_system_event('health_report_error', {
                'error': str(e)
            }, 'error')
            return {
                'overall_status': 'error',
                'error': str(e),
                'generated_at': datetime.utcnow().isoformat()
            }
    
    def _get_uptime(self) -> str:
        """Get system uptime information"""
        try:
            import psutil
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            return str(uptime).split('.')[0]  # Remove microseconds
        except:
            return 'unknown'
    
    def monitor_api_endpoint(self, endpoint: str, response_time: float, 
                           status_code: int, error: Optional[str] = None) -> None:
        """Task 10: Monitor API endpoint performance"""
        try:
            log_data = {
                'endpoint': endpoint,
                'response_time_ms': round(response_time * 1000, 2),
                'status_code': status_code,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            if error:
                log_data['error'] = error
                self.log_system_event('api_endpoint_error', log_data, 'error')
            elif response_time > 5.0:  # Slow response
                self.log_system_event('api_endpoint_slow', log_data, 'warning')
            else:
                self.log_system_event('api_endpoint_success', log_data)
                
        except Exception as e:
            logger.error(f"Error monitoring API endpoint: {e}")

# Global monitoring service instance
monitoring_service = ProductionMonitoringService()

# Task 10: Wrapper functions for easy integration
def log_event(event_type: str, details: Dict[str, Any], level: str = 'info') -> None:
    """Task 10: Log system event wrapper"""
    monitoring_service.log_system_event(event_type, details, level)

def get_health_report() -> Dict[str, Any]:
    """Task 10: Get system health report wrapper"""
    return monitoring_service.generate_health_report()

def collect_metrics() -> Dict[str, Any]:
    """Task 10: Collect performance metrics wrapper"""
    return monitoring_service.collect_performance_metrics()

def monitor_endpoint(endpoint: str, response_time: float, status_code: int, error: Optional[str] = None) -> None:
    """Task 10: Monitor API endpoint wrapper"""
    monitoring_service.monitor_api_endpoint(endpoint, response_time, status_code, error)
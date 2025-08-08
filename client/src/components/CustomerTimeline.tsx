/**
 * AgentLocator v39 - Customer Timeline Component
 * רכיב ציר זמן לקוח עם פילטרים ואירועים
 */

import React, { useState, useEffect } from 'react';
import { 
    Phone, 
    MessageCircle, 
    Calendar, 
    FileText, 
    Receipt, 
    Clock,
    Filter,
    ExternalLink,
    ChevronDown,
    ChevronRight
} from 'lucide-react';

interface TimelineItem {
    id: string;
    kind: 'call' | 'whatsapp' | 'task' | 'contract' | 'invoice';
    timestamp: string;
    reference: string;
    title: string;
    metadata: any;
    actions: Array<{
        type: string;
        label: string;
        url: string;
    }>;
}

interface TimelineSummary {
    total_items: number;
    calls: number;
    whatsapp: number;
    tasks: number;
    contracts: number;
    invoices: number;
    date_range: {
        earliest: string | null;
        latest: string | null;
    };
}

interface CustomerTimelineProps {
    customerId: number;
    className?: string;
}

const CustomerTimeline = ({ 
    customerId, 
    className = '' 
}: CustomerTimelineProps) => {
    const [selectedFilters, setSelectedFilters] = useState<Set<string>>(
        new Set(['call', 'whatsapp', 'task', 'contract', 'invoice'])
    );
    const [isFilterExpanded, setIsFilterExpanded] = useState(false);
    const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());

    // Mock timeline data for demonstration
    const [timeline, setTimeline] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);

    const refetch = async () => {
        try {
            setIsLoading(true);
            const response = await fetch(`/api/customers/${customerId}/timeline?limit=100`);
            if (!response.ok) {
                throw new Error('Failed to fetch timeline');
            }
            const data = await response.json();
            setTimeline(data);
            setError(null);
        } catch (err) {
            console.error('Timeline fetch error:', err);
            setError(err);
            // Use mock data for demonstration
            setTimeline({
                summary: {
                    total_items: 3,
                    calls: 2,
                    whatsapp: 1,
                    tasks: 0,
                    contracts: 0,
                    invoices: 0
                },
                items: [
                    {
                        id: 'call_1',
                        kind: 'call',
                        timestamp: new Date().toISOString(),
                        reference: '12345',
                        title: 'שיחה נכנסת',
                        metadata: {
                            duration: 120,
                            status: 'completed',
                            transcription: 'שיחת בדיקה לתצוגת ציר הזמן'
                        },
                        actions: [{ type: 'view', label: 'צפה בשיחה', url: '/calls/1' }]
                    }
                ]
            });
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        if (customerId) {
            refetch();
        }
    }, [customerId]);

    // Filter items based on selected filters
    const filteredItems = timeline?.items?.filter((item: TimelineItem) => 
        selectedFilters.has(item.kind)
    ) || [];

    // Event type configurations
    const eventConfig = {
        call: {
            icon: Phone,
            color: 'text-green-600 bg-green-50',
            label: 'שיחה'
        },
        whatsapp: {
            icon: MessageCircle,
            color: 'text-green-500 bg-green-50',
            label: 'WhatsApp'
        },
        task: {
            icon: Calendar,
            color: 'text-blue-600 bg-blue-50',
            label: 'משימה'
        },
        contract: {
            icon: FileText,
            color: 'text-purple-600 bg-purple-50',
            label: 'חוזה'
        },
        invoice: {
            icon: Receipt,
            color: 'text-orange-600 bg-orange-50',
            label: 'חשבונית'
        }
    };

    // Toggle filter
    const toggleFilter = (filter: string) => {
        const newFilters = new Set(selectedFilters);
        if (newFilters.has(filter)) {
            newFilters.delete(filter);
        } else {
            newFilters.add(filter);
        }
        setSelectedFilters(newFilters);
    };

    // Toggle item expansion
    const toggleItemExpansion = (itemId: string) => {
        const newExpanded = new Set(expandedItems);
        if (newExpanded.has(itemId)) {
            newExpanded.delete(itemId);
        } else {
            newExpanded.add(itemId);
        }
        setExpandedItems(newExpanded);
    };

    // Format timestamp
    const formatTimestamp = (timestamp: string) => {
        return new Date(timestamp).toLocaleString('he-IL', {
            year: 'numeric',
            month: '2-digit', 
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    // Render metadata based on event type
    const renderMetadata = (item: TimelineItem, expanded: boolean) => {
        if (!expanded) return null;

        const { metadata } = item;

        switch (item.kind) {
            case 'call':
                return (
                    <div className="text-sm text-gray-600 space-y-1">
                        <div className="flex justify-between">
                            <span>משך:</span>
                            <span className="ltr">{metadata.duration || 0} שניות</span>
                        </div>
                        <div className="flex justify-between">
                            <span>סטטוס:</span>
                            <span>{metadata.status}</span>
                        </div>
                        {metadata.transcription && (
                            <div className="mt-2">
                                <span className="font-medium">תמלול:</span>
                                <p className="mt-1 text-gray-800 hebrew bg-gray-50 p-2 rounded text-sm">
                                    {metadata.transcription}
                                </p>
                            </div>
                        )}
                        {metadata.summary && (
                            <div className="mt-2">
                                <span className="font-medium">סיכום:</span>
                                <p className="mt-1 text-gray-800 hebrew bg-blue-50 p-2 rounded text-sm">
                                    {metadata.summary}
                                </p>
                            </div>
                        )}
                    </div>
                );

            case 'whatsapp':
                return (
                    <div className="text-sm text-gray-600 space-y-1">
                        <div className="flex justify-between">
                            <span>כיוון:</span>
                            <span>{metadata.direction === 'inbound' ? 'נכנס' : 'יוצא'}</span>
                        </div>
                        <div className="flex justify-between">
                            <span>סטטוס:</span>
                            <span>{metadata.status}</span>
                        </div>
                        {metadata.message_body && (
                            <div className="mt-2">
                                <span className="font-medium">הודעה:</span>
                                <p className="mt-1 text-gray-800 hebrew bg-green-50 p-2 rounded text-sm">
                                    {metadata.message_body}
                                </p>
                            </div>
                        )}
                    </div>
                );

            case 'task':
                return (
                    <div className="text-sm text-gray-600 space-y-1">
                        <div className="flex justify-between">
                            <span>סטטוס:</span>
                            <span className="hebrew">{metadata.status_hebrew}</span>
                        </div>
                        <div className="flex justify-between">
                            <span>עדיפות:</span>
                            <span>{metadata.priority}</span>
                        </div>
                        {metadata.due_at && (
                            <div className="flex justify-between">
                                <span>מועד יעד:</span>
                                <span className="ltr">{formatTimestamp(metadata.due_at)}</span>
                            </div>
                        )}
                        <div className="flex justify-between">
                            <span>ערוץ:</span>
                            <span>{metadata.channel}</span>
                        </div>
                        {metadata.notes && (
                            <div className="mt-2">
                                <span className="font-medium">הערות:</span>
                                <p className="mt-1 text-gray-800 hebrew bg-yellow-50 p-2 rounded text-sm">
                                    {metadata.notes}
                                </p>
                            </div>
                        )}
                    </div>
                );

            case 'invoice':
                return (
                    <div className="text-sm text-gray-600 space-y-1">
                        <div className="flex justify-between">
                            <span>סטטוס:</span>
                            <span className="hebrew">{metadata.status_hebrew}</span>
                        </div>
                        <div className="flex justify-between">
                            <span>סכום:</span>
                            <span className="font-medium">₪{metadata.amount?.toLocaleString()}</span>
                        </div>
                        {metadata.due_date && (
                            <div className="flex justify-between">
                                <span>תאריך תשלום:</span>
                                <span className="ltr">{formatTimestamp(metadata.due_date)}</span>
                            </div>
                        )}
                    </div>
                );

            case 'contract':
                return (
                    <div className="text-sm text-gray-600 space-y-1">
                        <div className="flex justify-between">
                            <span>סטטוס:</span>
                            <span className="hebrew">{metadata.status_hebrew}</span>
                        </div>
                        {metadata.signed_at && (
                            <div className="flex justify-between">
                                <span>תאריך חתימה:</span>
                                <span className="ltr">{formatTimestamp(metadata.signed_at)}</span>
                            </div>
                        )}
                    </div>
                );

            default:
                return (
                    <pre className="text-xs text-gray-500 bg-gray-50 p-2 rounded overflow-x-auto">
                        {JSON.stringify(metadata, null, 2)}
                    </pre>
                );
        }
    };

    if (error) {
        return (
            <div className={`bg-red-50 border border-red-200 rounded-lg p-4 ${className}`}>
                <div className="flex items-center text-red-600">
                    <ExternalLink className="w-5 h-5 mr-2" />
                    <span>שגיאה בטעינת ציר הזמן</span>
                </div>
                <button 
                    onClick={() => refetch()}
                    className="mt-2 text-red-600 hover:text-red-700 underline text-sm"
                >
                    נסה שוב
                </button>
            </div>
        );
    }

    return (
        <div className={`bg-white rounded-lg shadow-sm border ${className}`}>
            {/* Header */}
            <div className="px-6 py-4 border-b border-gray-200">
                <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold text-gray-900">ציר זמן לקוח</h3>
                    <div className="flex items-center gap-4">
                        {timeline?.summary && (
                            <span className="text-sm text-gray-500">
                                {timeline.summary.total_items} אירועים
                            </span>
                        )}
                        <button
                            onClick={() => setIsFilterExpanded(!isFilterExpanded)}
                            className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-800 transition-colors"
                        >
                            <Filter className="w-4 h-4" />
                            פילטר
                            {isFilterExpanded ? 
                                <ChevronDown className="w-4 h-4" /> : 
                                <ChevronRight className="w-4 h-4" />
                            }
                        </button>
                    </div>
                </div>
            </div>

            {/* Filters */}
            {isFilterExpanded && (
                <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
                    <div className="flex flex-wrap gap-2">
                        {Object.entries(eventConfig).map(([type, config]) => (
                            <button
                                key={type}
                                onClick={() => toggleFilter(type)}
                                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                                    selectedFilters.has(type)
                                        ? config.color + ' border'
                                        : 'text-gray-500 bg-white border border-gray-200 hover:bg-gray-50'
                                }`}
                            >
                                <config.icon className="w-4 h-4" />
                                {config.label}
                                {timeline?.summary && (
                                    <span className="bg-white bg-opacity-75 px-1 rounded text-xs">
                                        {timeline.summary[type as keyof TimelineSummary] || 0}
                                    </span>
                                )}
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {/* Timeline Content */}
            <div className="px-6 py-4">
                {isLoading ? (
                    <div className="flex items-center justify-center py-8">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                        <span className="mr-3 text-gray-600">טוען ציר זמן...</span>
                    </div>
                ) : filteredItems.length === 0 ? (
                    <div className="text-center py-8 text-gray-500">
                        <Clock className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                        <p>אין אירועים להציג</p>
                        {selectedFilters.size < 5 && (
                            <p className="text-sm mt-1">נסה להרחיב את הפילטרים</p>
                        )}
                    </div>
                ) : (
                    <div className="space-y-4">
                        {filteredItems.map((item: TimelineItem) => {
                            const config = eventConfig[item.kind] || eventConfig.call;
                            const isExpanded = expandedItems.has(item.id);
                            const Icon = config.icon;

                            return (
                                <div key={item.id} className="border border-gray-200 rounded-lg">
                                    <div 
                                        className="p-4 cursor-pointer hover:bg-gray-50 transition-colors"
                                        onClick={() => toggleItemExpansion(item.id)}
                                    >
                                        <div className="flex items-start justify-between">
                                            <div className="flex items-start gap-3 flex-1">
                                                <div className={`flex items-center justify-center w-8 h-8 rounded-full ${config.color}`}>
                                                    <Icon className="w-4 h-4" />
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <h4 className="font-medium text-gray-900 hebrew">
                                                        {item.title}
                                                    </h4>
                                                    <p className="text-sm text-gray-500 ltr">
                                                        {formatTimestamp(item.timestamp)}
                                                    </p>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                {item.actions?.map((action) => (
                                                    <a
                                                        key={action.type}
                                                        href={action.url}
                                                        className="text-blue-600 hover:text-blue-700 text-sm underline"
                                                        onClick={(e) => e.stopPropagation()}
                                                    >
                                                        {action.label}
                                                    </a>
                                                ))}
                                                {isExpanded ? 
                                                    <ChevronDown className="w-5 h-5 text-gray-400" /> :
                                                    <ChevronRight className="w-5 h-5 text-gray-400" />
                                                }
                                            </div>
                                        </div>
                                    </div>
                                    {isExpanded && (
                                        <div className="px-4 pb-4 border-t border-gray-100">
                                            <div className="pt-3">
                                                {renderMetadata(item, isExpanded)}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
};

export default CustomerTimeline;
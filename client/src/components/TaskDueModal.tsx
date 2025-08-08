/**
 * AgentLocator v39 - Task Due Modal
 * מודל מסך מלא להתראות משימות במועד
 */

import React from 'react';
import { X, Phone, MessageCircle, Clock, CheckCircle2, AlertTriangle } from 'lucide-react';
import { type TaskDueEvent } from '@/lib/socket';

interface TaskDueModalProps {
    isOpen: boolean;
    task: TaskDueEvent | null;
    onClose: () => void;
    onCall: (phone: string) => void;
    onWhatsApp: (phone: string) => void;
    onSnooze: (taskId: number, minutes: number) => void;
    onComplete: (taskId: number) => void;
}

const TaskDueModal: React.FC<TaskDueModalProps> = ({
    isOpen,
    task,
    onClose,
    onCall,
    onWhatsApp,
    onSnooze,
    onComplete
}) => {
    if (!isOpen || !task) return null;

    const priorityColor = {
        low: 'text-green-600 bg-green-50',
        medium: 'text-yellow-600 bg-yellow-50', 
        high: 'text-orange-600 bg-orange-50',
        urgent: 'text-red-600 bg-red-50'
    }[task.priority] || 'text-gray-600 bg-gray-50';

    const priorityText = {
        low: 'עדיפות נמוכה',
        medium: 'עדיפות בינונית',
        high: 'עדיפות גבוהה', 
        urgent: 'דחוף'
    }[task.priority] || task.priority;

    const channelIcon = {
        call: <Phone className="w-5 h-5" />,
        whatsapp: <MessageCircle className="w-5 h-5" />,
        meeting: <Clock className="w-5 h-5" />,
        email: <Clock className="w-5 h-5" />,
        sms: <MessageCircle className="w-5 h-5" />
    }[task.channel] || <Clock className="w-5 h-5" />;

    const channelText = {
        call: 'התקשרות',
        whatsapp: 'WhatsApp',
        meeting: 'פגישה',
        email: 'אימייל',
        sms: 'SMS'
    }[task.channel] || task.channel;

    return (
        <div className="fixed inset-0 z-50 overflow-y-auto" role="dialog" aria-modal="true">
            {/* Backdrop */}
            <div 
                className="fixed inset-0 bg-black bg-opacity-75 transition-opacity"
                onClick={onClose}
            />
            
            {/* Modal */}
            <div className="flex min-h-full items-center justify-center p-4">
                <div className="relative w-full max-w-md transform overflow-hidden rounded-2xl bg-white shadow-2xl transition-all">
                    
                    {/* Header */}
                    <div className="bg-gradient-to-l from-blue-600 to-purple-600 px-6 py-8 text-white">
                        <div className="flex items-start justify-between">
                            <div className="flex-1">
                                <div className="flex items-center gap-2 mb-2">
                                    <AlertTriangle className="w-6 h-6 text-yellow-300" />
                                    <h2 className="text-xl font-bold">משימה במועד</h2>
                                </div>
                                <p className="text-blue-100 text-sm">זמן לטפל בלקוח</p>
                            </div>
                            <button
                                onClick={onClose}
                                className="rounded-lg p-2 text-white hover:bg-white hover:bg-opacity-20 transition-colors"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>
                    </div>

                    {/* Content */}
                    <div className="px-6 py-6">
                        
                        {/* Customer Info */}
                        <div className="mb-6">
                            <h3 className="text-lg font-semibold text-gray-900 mb-2 hebrew">
                                {task.customer_name}
                            </h3>
                            <div className="flex items-center gap-2 text-gray-600 ltr">
                                <Phone className="w-4 h-4" />
                                <span className="font-mono">{task.customer_phone}</span>
                            </div>
                        </div>

                        {/* Task Details */}
                        <div className="mb-6 space-y-4">
                            <div>
                                <h4 className="text-sm font-medium text-gray-500 mb-1">משימה</h4>
                                <p className="text-gray-900 hebrew">{task.task_title}</p>
                            </div>
                            
                            <div className="flex items-center justify-between">
                                <div>
                                    <h4 className="text-sm font-medium text-gray-500 mb-1">סוג משימה</h4>
                                    <div className="flex items-center gap-2">
                                        {channelIcon}
                                        <span className="text-gray-900">{channelText}</span>
                                    </div>
                                </div>
                                
                                <div className="text-left">
                                    <h4 className="text-sm font-medium text-gray-500 mb-1">עדיפות</h4>
                                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${priorityColor}`}>
                                        {priorityText}
                                    </span>
                                </div>
                            </div>
                            
                            <div>
                                <h4 className="text-sm font-medium text-gray-500 mb-1">מועד יעד</h4>
                                <p className="text-gray-900 ltr">
                                    {new Date(task.due_at).toLocaleString('he-IL')}
                                </p>
                            </div>
                        </div>

                        {/* Action Buttons */}
                        <div className="space-y-3">
                            
                            {/* Primary Actions */}
                            <div className="grid grid-cols-2 gap-3">
                                <button
                                    onClick={() => onCall(task.customer_phone)}
                                    className="flex items-center justify-center gap-2 bg-green-600 hover:bg-green-700 text-white px-4 py-3 rounded-lg font-medium transition-colors"
                                >
                                    <Phone className="w-5 h-5" />
                                    התקשר
                                </button>
                                
                                <button
                                    onClick={() => onWhatsApp(task.customer_phone)}
                                    className="flex items-center justify-center gap-2 bg-green-500 hover:bg-green-600 text-white px-4 py-3 rounded-lg font-medium transition-colors"
                                >
                                    <MessageCircle className="w-5 h-5" />
                                    WhatsApp
                                </button>
                            </div>

                            {/* Snooze Options */}
                            <div className="grid grid-cols-3 gap-2">
                                <button
                                    onClick={() => onSnooze(task.task_id, 5)}
                                    className="flex items-center justify-center gap-1 bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
                                >
                                    <Clock className="w-4 h-4" />
                                    5 דקות
                                </button>
                                
                                <button
                                    onClick={() => onSnooze(task.task_id, 15)}
                                    className="flex items-center justify-center gap-1 bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
                                >
                                    <Clock className="w-4 h-4" />
                                    15 דקות
                                </button>
                                
                                <button
                                    onClick={() => onSnooze(task.task_id, 60)}
                                    className="flex items-center justify-center gap-1 bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
                                >
                                    <Clock className="w-4 h-4" />
                                    שעה
                                </button>
                            </div>

                            {/* Complete Task */}
                            <button
                                onClick={() => onComplete(task.task_id)}
                                className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-3 rounded-lg font-medium transition-colors"
                            >
                                <CheckCircle2 className="w-5 h-5" />
                                סמן כהושלם
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default TaskDueModal;
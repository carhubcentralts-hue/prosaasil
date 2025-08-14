interface TaskDueModalProps {
  isOpen: boolean;
  onClose: () => void;
  task: {
    id: string;
    title: string;
    description?: string;
    due_date: string;
    customer_name?: string;
  } | null;
}

// Simple modal component for task notifications
function TaskDueModal({ isOpen, onClose, task }: TaskDueModalProps) {
  if (!isOpen || !task) return null;

  const handleSnooze = () => {
    // TODO: Implement snooze functionality
    onClose();
  };

  const handleMarkComplete = () => {
    // TODO: Implement mark complete functionality
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4" dir="rtl">
        <div className="text-right mb-4">
          <h2 className="text-xl font-bold">🔔 משימה דחופה</h2>
          <p className="text-gray-600">זמן המשימה הגיע!</p>
        </div>
        
        <div className="space-y-4 text-right mb-6">
          <div>
            <h3 className="font-semibold text-lg">{task.title}</h3>
            {task.description && (
              <p className="text-sm text-gray-600 mt-1">{task.description}</p>
            )}
          </div>
          
          {task.customer_name && (
            <div className="bg-blue-50 p-3 rounded-lg">
              <span className="text-sm text-blue-800">
                לקוח: {task.customer_name}
              </span>
            </div>
          )}
          
          <div className="text-sm text-gray-500">
            תאריך יעד: {new Date(task.due_date).toLocaleString('he-IL')}
          </div>
        </div>

        <div className="flex gap-2 justify-end">
          <button 
            onClick={handleSnooze}
            className="px-4 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
          >
            דחה ל-15 דקות
          </button>
          <button 
            onClick={handleMarkComplete}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            סמן כהושלם
          </button>
        </div>
      </div>
    </div>
  );
}

export { TaskDueModal };
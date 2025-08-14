import { useState, useCallback } from 'react';
import { AuthProvider, useAuth } from './hooks/useAuth';
import { Login } from './components/Login';
import { SystemSelector } from './components/SystemSelector';
import { AdminDashboard } from './components/AdminDashboard';
import { BusinessDashboard } from './components/BusinessDashboard';
import { TaskDueModal } from './components/TaskDueModal';
import { useTaskDue } from './hooks/useTaskDue';

function AppContent() {
  const { user, isLoading, logout } = useAuth();
  const [selectedSystem, setSelectedSystem] = useState<string | null>(null);
  const [dueTask, setDueTask] = useState<any>(null);
  const [isTaskModalOpen, setIsTaskModalOpen] = useState(false);

  const handleTaskDue = useCallback((task: any) => {
    setDueTask(task);
    setIsTaskModalOpen(true);
  }, []);

  useTaskDue(handleTaskDue);

  const closeTaskModal = () => {
    setIsTaskModalOpen(false);
    setDueTask(null);
  };

  const handleSelectSystem = async (system: string) => {
    if (system === 'logout') {
      await logout();
      setSelectedSystem(null);
      return;
    }

    // For now, we only implement admin and business dashboards
    if (system === 'admin-users' || system === 'admin-businesses') {
      setSelectedSystem('admin');
    } else if (system === 'calls' || system === 'whatsapp' || system === 'crm') {
      setSelectedSystem('business');
    } else {
      setSelectedSystem(system);
    }
  };

  const handleBack = () => {
    setSelectedSystem(null);
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-xl text-gray-600" dir="rtl">טוען...</div>
      </div>
    );
  }

  if (!user) {
    return <Login />;
  }

  if (selectedSystem === 'admin' && user.role === 'admin') {
    return <AdminDashboard onBack={handleBack} />;
  }

  if (selectedSystem === 'business') {
    return <BusinessDashboard onBack={handleBack} />;
  }

  return (
    <>
      <SystemSelector user={user} onSelectSystem={handleSelectSystem} />
      <TaskDueModal
        isOpen={isTaskModalOpen}
        onClose={closeTaskModal}
        task={dueTask}
      />
    </>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
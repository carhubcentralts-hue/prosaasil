import { http } from '../../services/http';
import { StatusResponse, DashboardStats, ActivityResponse } from '../../types/api';

export const statusApi = {
  // Get system status
  getStatus: () => http.get<StatusResponse>('/api/status'),
  
  // Get dashboard stats (role-aware)
  getStats: () => http.get<DashboardStats>('/api/dashboard/stats'),
  
  // Get recent activity (role-aware)
  getActivity: () => http.get<ActivityResponse>('/api/dashboard/activity'),
};
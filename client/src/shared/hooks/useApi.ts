import { useState, useEffect } from 'react';

interface UseApiState<T> {
  data: T | null;
  isLoading: boolean;
  error: string | null;
}

export function useApi<T>(
  apiCall: () => Promise<T>,
  deps: any[] = []
): UseApiState<T> & { refetch: () => Promise<void> } {
  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    isLoading: true,
    error: null,
  });

  const fetchData = async () => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));
    try {
      const data = await apiCall();
      setState({ data, isLoading: false, error: null });
    } catch (error) {
      setState({ 
        data: null, 
        isLoading: false, 
        error: error instanceof Error ? error.message : 'שגיאה לא ידועה' 
      });
    }
  };

  useEffect(() => {
    fetchData();
  }, deps);

  return { ...state, refetch: fetchData };
}
import { useState, useCallback, useEffect } from 'react';
import { http } from '../../services/http';

export interface AIPromptData {
  calls_prompt: string;
  whatsapp_prompt: string;
  version: number;
  updated_at: string | null;
  updated_by: string | null;
}

export interface PromptHistoryItem {
  version: number;
  prompt: string;
  createdAt: string;
  updatedBy: string;
}

/**
 * Hook for managing AI Prompt for current business (impersonated)
 * Uses the /api/business/current/prompt endpoints
 */
export function useAIPrompt() {
  const [isEditing, setIsEditing] = useState(false);
  const [editablePrompt, setEditablePrompt] = useState('');
  
  // Prompt data state
  const [promptData, setPromptData] = useState<AIPromptData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  
  // History data state  
  const [history, setHistory] = useState<PromptHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  
  // Saving state
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<Error | null>(null);

  // Fetch prompt data
  const fetchPrompt = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await http.get<AIPromptData>('/api/business/current/prompt');
      setPromptData(result);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch AI prompt'));
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch history
  const fetchHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const result = await http.get<PromptHistoryItem[]>('/api/business/current/prompt/history');
      setHistory(result);
    } catch (err) {
      // History error is not critical
      console.error('Failed to fetch prompt history:', err);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  // Load data on mount
  useEffect(() => {
    fetchPrompt();
    fetchHistory();
  }, [fetchPrompt, fetchHistory]);

  const startEditing = useCallback(() => {
    // Use calls_prompt as the main prompt for editing
    setEditablePrompt(promptData?.calls_prompt || '');
    setIsEditing(true);
  }, [promptData?.calls_prompt]);

  const cancelEditing = useCallback(() => {
    setIsEditing(false);
    setEditablePrompt('');
  }, []);

  const savePrompt = useCallback(async () => {
    if (!editablePrompt.trim()) return;
    
    setIsSaving(true);
    setSaveError(null);
    
    try {
      await http.put('/api/business/current/prompt', { 
        calls_prompt: editablePrompt.trim(),
        whatsapp_prompt: editablePrompt.trim()
      });
      
      // Refresh data after successful save
      await fetchPrompt();
      await fetchHistory();
      
      setIsEditing(false);
      setEditablePrompt('');
    } catch (err) {
      setSaveError(err instanceof Error ? err : new Error('Failed to save prompt'));
    } finally {
      setIsSaving(false);
    }
  }, [editablePrompt, fetchPrompt, fetchHistory]);

  const refetch = useCallback(() => {
    fetchPrompt();
    fetchHistory();
  }, [fetchPrompt, fetchHistory]);

  return {
    // Data
    promptData,
    history,
    isLoading,
    historyLoading,
    error,
    
    // Editing state
    isEditing,
    editablePrompt,
    setEditablePrompt,
    
    // Actions
    startEditing,
    cancelEditing,
    savePrompt,
    refetch,
    
    // Mutation state
    isSaving,
    saveError,
  };
}
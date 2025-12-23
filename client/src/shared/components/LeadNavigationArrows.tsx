import React, { useEffect, useState } from 'react';
import { ChevronUp, ChevronDown } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { 
  NavigationContext, 
  parseNavigationContext, 
  encodeNavigationContext,
  getPrevNextLeads,
  LeadNavigationResult 
} from '../../services/leadNavigation';
import { http } from '../../services/http';

interface LeadNavigationArrowsProps {
  currentLeadId: number;
  className?: string;
  variant?: 'desktop' | 'mobile';
}

/**
 * Lead Navigation Arrows Component
 * 
 * Displays up/down arrows to navigate between leads based on the
 * context from which the user entered the lead detail page.
 * 
 * - Desktop: Shows inline arrows next to the lead name
 * - Mobile: Shows floating arrows in the bottom-right corner
 */
export function LeadNavigationArrows({ 
  currentLeadId, 
  className = '',
  variant = 'desktop'
}: LeadNavigationArrowsProps) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [navigation, setNavigation] = useState<LeadNavigationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [context, setContext] = useState<NavigationContext | null>(null);

  // Parse navigation context from URL
  useEffect(() => {
    const parsedContext = parseNavigationContext(searchParams);
    setContext(parsedContext);
  }, [searchParams]);

  // Load prev/next lead IDs
  useEffect(() => {
    if (!context) {
      setNavigation(null);
      return;
    }

    const loadNavigation = async () => {
      setLoading(true);
      try {
        const result = await getPrevNextLeads(currentLeadId, context, http);
        setNavigation(result);
      } catch (error) {
        console.error('Error loading navigation:', error);
        setNavigation(null);
      } finally {
        setLoading(false);
      }
    };

    loadNavigation();
  }, [currentLeadId, context]);

  // Don't show arrows if no context or no navigation available
  if (!context || !navigation) {
    return null;
  }

  const handleNavigate = (leadId: number | null) => {
    if (!leadId || !context) return;
    
    // Build URL with preserved context
    const params = encodeNavigationContext(context);
    navigate(`/app/leads/${leadId}?${params.toString()}`);
  };

  if (variant === 'mobile') {
    // Mobile: Floating buttons in bottom-right
    return (
      <div className={`fixed bottom-4 left-4 z-50 flex flex-col gap-2 ${className}`}>
        <button
          onClick={() => handleNavigate(navigation.prevLeadId)}
          disabled={!navigation.hasPrev || loading}
          className={`
            p-3 rounded-full shadow-lg transition-all
            ${navigation.hasPrev && !loading
              ? 'bg-blue-600 text-white hover:bg-blue-700 active:scale-95'
              : 'bg-gray-300 text-gray-500 cursor-not-allowed'
            }
          `}
          title="ליד קודם"
          aria-label="ליד קודם"
        >
          <ChevronUp className="w-6 h-6" />
        </button>
        <button
          onClick={() => handleNavigate(navigation.nextLeadId)}
          disabled={!navigation.hasNext || loading}
          className={`
            p-3 rounded-full shadow-lg transition-all
            ${navigation.hasNext && !loading
              ? 'bg-blue-600 text-white hover:bg-blue-700 active:scale-95'
              : 'bg-gray-300 text-gray-500 cursor-not-allowed'
            }
          `}
          title="ליד הבא"
          aria-label="ליד הבא"
        >
          <ChevronDown className="w-6 h-6" />
        </button>
      </div>
    );
  }

  // Desktop: Inline arrows
  return (
    <div className={`flex items-center gap-1 ${className}`}>
      <button
        onClick={() => handleNavigate(navigation.prevLeadId)}
        disabled={!navigation.hasPrev || loading}
        className={`
          p-2 rounded-lg transition-colors
          ${navigation.hasPrev && !loading
            ? 'hover:bg-gray-100 text-gray-700'
            : 'text-gray-300 cursor-not-allowed'
          }
        `}
        title="ליד קודם"
        aria-label="ליד קודם"
      >
        <ChevronUp className="w-5 h-5" />
      </button>
      <button
        onClick={() => handleNavigate(navigation.nextLeadId)}
        disabled={!navigation.hasNext || loading}
        className={`
          p-2 rounded-lg transition-colors
          ${navigation.hasNext && !loading
            ? 'hover:bg-gray-100 text-gray-700'
            : 'text-gray-300 cursor-not-allowed'
          }
        `}
        title="ליד הבא"
        aria-label="ליד הבא"
      >
        <ChevronDown className="w-5 h-5" />
      </button>
    </div>
  );
}

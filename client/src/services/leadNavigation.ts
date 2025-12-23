/**
 * Lead Navigation Service
 * 
 * Provides navigation between leads based on context (list/filters/tab).
 * Preserves the user's navigation context when moving between leads.
 */

export interface NavigationContext {
  from: 'leads' | 'recent_calls' | 'inbound_calls' | 'outbound_calls' | 'whatsapp';
  tab?: string;
  filters?: {
    status?: string;
    source?: string;
    direction?: string;
    outbound_list_id?: string;
    search?: string;
    dateFrom?: string;
    dateTo?: string;
  };
  listId?: string; // For tracking position in paginated list
  currentIndex?: number; // Current position in list
}

export interface LeadNavigationResult {
  prevLeadId: number | null;
  nextLeadId: number | null;
  hasPrev: boolean;
  hasNext: boolean;
}

// Cache for lead IDs to improve navigation performance
interface NavigationCache {
  key: string;
  leadIds: number[];
  timestamp: number;
}

let navigationCache: NavigationCache | null = null;
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

/**
 * Generate cache key from navigation context
 */
function getCacheKey(context: NavigationContext): string {
  const parts = [
    context.from,
    context.tab || '',
    context.filters?.status || '',
    context.filters?.source || '',
    context.filters?.direction || '',
    context.filters?.outbound_list_id || '',
    context.filters?.search || '',
    context.filters?.dateFrom || '',
    context.filters?.dateTo || '',
  ];
  return parts.join('|');
}

/**
 * Clear navigation cache
 */
export function clearNavigationCache() {
  navigationCache = null;
}

/**
 * Parse navigation context from URL search params
 */
export function parseNavigationContext(searchParams: URLSearchParams): NavigationContext | null {
  const from = searchParams.get('from') as NavigationContext['from'] | null;
  const tab = searchParams.get('tab') || undefined;
  const listId = searchParams.get('listId') || undefined;
  const currentIndex = searchParams.get('index');
  
  if (!from) {
    return null;
  }

  // Parse filters from URL
  const filters: NavigationContext['filters'] = {};
  const status = searchParams.get('filterStatus');
  const source = searchParams.get('filterSource');
  const direction = searchParams.get('filterDirection');
  const outbound_list_id = searchParams.get('filterOutboundList');
  const search = searchParams.get('filterSearch');
  const dateFrom = searchParams.get('filterDateFrom');
  const dateTo = searchParams.get('filterDateTo');
  
  if (status) filters.status = status;
  if (source) filters.source = source;
  if (direction) filters.direction = direction;
  if (outbound_list_id) filters.outbound_list_id = outbound_list_id;
  if (search) filters.search = search;
  if (dateFrom) filters.dateFrom = dateFrom;
  if (dateTo) filters.dateTo = dateTo;

  return {
    from,
    tab,
    filters: Object.keys(filters).length > 0 ? filters : undefined,
    listId,
    currentIndex: currentIndex ? parseInt(currentIndex, 10) : undefined,
  };
}

/**
 * Encode navigation context into URL search params
 */
export function encodeNavigationContext(context: NavigationContext): URLSearchParams {
  const params = new URLSearchParams();
  
  params.set('from', context.from);
  
  if (context.tab) {
    params.set('tab', context.tab);
  }
  
  if (context.listId) {
    params.set('listId', context.listId);
  }
  
  if (context.currentIndex !== undefined) {
    params.set('index', context.currentIndex.toString());
  }
  
  // Encode filters
  if (context.filters) {
    if (context.filters.status) params.set('filterStatus', context.filters.status);
    if (context.filters.source) params.set('filterSource', context.filters.source);
    if (context.filters.direction) params.set('filterDirection', context.filters.direction);
    if (context.filters.outbound_list_id) params.set('filterOutboundList', context.filters.outbound_list_id);
    if (context.filters.search) params.set('filterSearch', context.filters.search);
    if (context.filters.dateFrom) params.set('filterDateFrom', context.filters.dateFrom);
    if (context.filters.dateTo) params.set('filterDateTo', context.filters.dateTo);
  }
  
  return params;
}

/**
 * Get prev/next lead IDs based on navigation context
 * 
 * This function should be called from the lead detail page to determine
 * which leads to navigate to. Uses caching to improve performance.
 */
export async function getPrevNextLeads(
  currentLeadId: number,
  context: NavigationContext,
  apiClient: any // http client
): Promise<LeadNavigationResult> {
  try {
    const cacheKey = getCacheKey(context);
    let leadIds: number[] = [];
    
    // Check cache first
    if (navigationCache && navigationCache.key === cacheKey) {
      const cacheAge = Date.now() - navigationCache.timestamp;
      if (cacheAge < CACHE_TTL) {
        // Use cached lead IDs
        leadIds = navigationCache.leadIds;
      } else {
        // Cache expired
        navigationCache = null;
      }
    }
    
    // If no valid cache, fetch from API
    if (leadIds.length === 0) {
      // Build API query based on context
      let endpoint = '/api/leads';
      const params = new URLSearchParams();
      
      // Apply filters from context
      if (context.filters) {
        if (context.filters.status) params.set('status', context.filters.status);
        if (context.filters.source) params.set('source', context.filters.source);
        if (context.filters.direction) params.set('direction', context.filters.direction);
        if (context.filters.outbound_list_id) params.set('outbound_list_id', context.filters.outbound_list_id);
        if (context.filters.search) params.set('search', context.filters.search);
        if (context.filters.dateFrom) params.set('from', context.filters.dateFrom);
        if (context.filters.dateTo) params.set('to', context.filters.dateTo);
      }
      
      // Special handling for different contexts
      switch (context.from) {
        case 'recent_calls':
          endpoint = '/api/calls';
          break;
        case 'inbound_calls':
          endpoint = '/api/calls';
          params.set('direction', 'inbound');
          break;
        case 'outbound_calls':
          endpoint = '/api/calls';
          params.set('direction', 'outbound');
          break;
        case 'whatsapp':
          // WhatsApp leads might have a different filter
          params.set('source', 'whatsapp');
          break;
      }
      
      // Fetch the list
      const queryString = params.toString();
      const url = queryString ? `${endpoint}?${queryString}` : endpoint;
      const response = await apiClient.get(url);
      
      // Extract lead IDs from response
      if (context.from === 'recent_calls' || context.from === 'inbound_calls' || context.from === 'outbound_calls') {
        // For calls, extract lead_id from call records
        const calls = response?.calls || [];
        leadIds = calls
          .filter((call: any) => call.lead_id)
          .map((call: any) => call.lead_id);
      } else {
        // For leads
        const leads = response?.leads || [];
        leadIds = leads.map((lead: any) => lead.id);
      }
      
      // Remove duplicates
      leadIds = Array.from(new Set(leadIds));
      
      // Cache the result
      navigationCache = {
        key: cacheKey,
        leadIds,
        timestamp: Date.now(),
      };
    }
    
    // Find current position
    const currentIndex = leadIds.indexOf(currentLeadId);
    
    if (currentIndex === -1) {
      // Current lead not in list - clear cache and return empty
      navigationCache = null;
      return {
        prevLeadId: null,
        nextLeadId: null,
        hasPrev: false,
        hasNext: false,
      };
    }
    
    return {
      prevLeadId: currentIndex > 0 ? leadIds[currentIndex - 1] : null,
      nextLeadId: currentIndex < leadIds.length - 1 ? leadIds[currentIndex + 1] : null,
      hasPrev: currentIndex > 0,
      hasNext: currentIndex < leadIds.length - 1,
    };
  } catch (error) {
    console.error('Error getting prev/next leads:', error);
    return {
      prevLeadId: null,
      nextLeadId: null,
      hasPrev: false,
      hasNext: false,
    };
  }
}

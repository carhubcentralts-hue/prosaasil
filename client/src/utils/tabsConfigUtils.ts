/**
 * Utility functions for managing lead tabs configuration
 * Ensures no duplicates and proper validation
 */

/**
 * Remove duplicates from tabs configuration
 * If a tab appears in both primary and secondary, it stays only in primary
 * 
 * @param primaryTabs - Array of primary tab keys
 * @param secondaryTabs - Array of secondary tab keys
 * @returns Object with unique primary and secondary arrays
 */
export function deduplicateTabsConfig(
  primaryTabs: string[],
  secondaryTabs: string[]
): { uniquePrimary: string[]; uniqueSecondary: string[] } {
  // Remove duplicates within primary (preserve order)
  const uniquePrimary = [...new Set(primaryTabs)];
  
  // Remove duplicates within secondary and filter out items that appear in primary
  // Use Set for O(1) lookup performance
  const primarySet = new Set(uniquePrimary);
  const uniqueSecondary = [...new Set(secondaryTabs.filter(tab => !primarySet.has(tab)))];
  
  return { uniquePrimary, uniqueSecondary };
}

/**
 * Validate tabs configuration
 * 
 * @param primaryTabs - Array of primary tab keys
 * @param secondaryTabs - Array of secondary tab keys
 * @param maxPrimary - Maximum number of primary tabs (default: 5)
 * @param maxSecondary - Maximum number of secondary tabs (default: unlimited)
 * @returns Error message if invalid, null if valid
 */
export function validateTabsConfig(
  primaryTabs: string[],
  secondaryTabs: string[],
  maxPrimary: number = 5,
  maxSecondary: number | null = null
): string | null {
  if (primaryTabs.length === 0) {
    return 'חובה לבחור לפחות טאב אחד ראשי';
  }
  
  if (primaryTabs.length > maxPrimary) {
    return `ניתן לבחור עד ${maxPrimary} טאבים ראשיים`;
  }
  
  // Secondary tabs now have no limit (null means unlimited)
  if (maxSecondary !== null && secondaryTabs.length > maxSecondary) {
    return `ניתן לבחור עד ${maxSecondary} טאבים משניים`;
  }
  
  return null;
}

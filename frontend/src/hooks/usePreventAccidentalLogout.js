/**
 * Hook to prevent accidental logout on page refresh (Ctrl+Shift+R)
 * Allows normal page reload but prevents logout API call
 */

import { useEffect } from "react";

export const usePreventAccidentalLogout = () => {
  useEffect(() => {
    // Flag to track if page is being unloaded
    let isUnloading = false;

    const handleBeforeUnload = (event) => {
      isUnloading = true;
      // Don't prevent the reload, just set the flag
      // This allows the page to refresh normally
    };

    const handleUnload = (event) => {
      isUnloading = true;
    };

    // Add listeners for page unload/refresh events
    window.addEventListener("beforeunload", handleBeforeUnload);
    window.addEventListener("unload", handleUnload);

    // Store the flag globally so API calls can check it
    window.__isPageUnloading = false;

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
      window.removeEventListener("unload", handleUnload);
    };
  }, []);

  return {
    isUnloading: () => window.__isPageUnloading,
  };
};

export default usePreventAccidentalLogout;

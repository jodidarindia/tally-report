import { useState, useEffect, useRef } from 'react';
import { toast } from 'sonner';

export function useIdleTimeout(isAuthenticated, onLogout) {
  const [idleWarning, setIdleWarning] = useState(false);
  const idleTimerRef = useRef(null);
  const warningTimerRef = useRef(null);
  const onLogoutRef = useRef(onLogout);
  onLogoutRef.current = onLogout;

  useEffect(() => {
    if (!isAuthenticated) {
      setIdleWarning(false);
      clearTimeout(idleTimerRef.current);
      clearTimeout(warningTimerRef.current);
      return;
    }

    const IDLE_LIMIT = 14 * 60 * 1000; // 14 min — show warning
    const LOGOUT_DELAY = 1 * 60 * 1000; // 1 min after warning — auto logout

    const resetIdle = () => {
      clearTimeout(idleTimerRef.current);
      clearTimeout(warningTimerRef.current);
      setIdleWarning(false);
      idleTimerRef.current = setTimeout(() => {
        setIdleWarning(true);
        warningTimerRef.current = setTimeout(() => {
          if (onLogoutRef.current) onLogoutRef.current();
          toast.info('You were logged out due to inactivity.');
        }, LOGOUT_DELAY);
      }, IDLE_LIMIT);
    };

    const events = ['mousedown', 'mousemove', 'keydown', 'scroll', 'touchstart', 'click'];
    events.forEach(ev => window.addEventListener(ev, resetIdle, { passive: true }));
    resetIdle();

    return () => {
      events.forEach(ev => window.removeEventListener(ev, resetIdle));
      clearTimeout(idleTimerRef.current);
      clearTimeout(warningTimerRef.current);
    };
  }, [isAuthenticated]);

  return { idleWarning, dismissWarning: () => setIdleWarning(false) };
}

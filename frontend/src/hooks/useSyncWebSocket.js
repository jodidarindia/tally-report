import { useState, useEffect, useRef, useCallback } from 'react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export function useSyncWebSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const [syncProgress, setSyncProgress] = useState(null);
  const [lastEvent, setLastEvent] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const wsUrl = BACKEND_URL
      .replace('https://', 'wss://')
      .replace('http://', 'ws://') + '/api/ws/sync-status';

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;
        // Request current status
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ action: 'get_status' }));
        }
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          setLastEvent(msg);

          const eventType = msg.event || msg.data?.type;

          if (eventType === 'status_response') {
            setSyncProgress(prev => ({ ...prev, ...msg.data }));
          } else if (eventType === 'sync_started') {
            setSyncProgress({
              isSyncing: true,
              phase: 'starting',
              message: msg.data?.is_first_sync ? 'Starting full sync...' : 'Starting incremental sync...',
              progress: 0
            });
          } else if (eventType === 'phase_start') {
            const phase = msg.data?.phase || '';
            setSyncProgress(prev => ({
              ...prev,
              isSyncing: true,
              phase,
              message: `Syncing ${phase}...`,
            }));
          } else if (eventType === 'sales_batch_start') {
            setSyncProgress(prev => ({
              ...prev,
              isSyncing: true,
              phase: 'sales',
              totalBatches: msg.data?.total_batches || 0,
              currentBatch: 0,
              message: `Preparing to fetch sales in ${msg.data?.total_batches} batches...`,
              progress: 0
            }));
          } else if (eventType === 'sales_batch_progress') {
            const batch = msg.data?.batch || 0;
            const total = msg.data?.total_batches || 1;
            const month = msg.data?.month || '';
            const pct = Math.round((batch / total) * 100);
            setSyncProgress(prev => ({
              ...prev,
              isSyncing: true,
              phase: 'sales',
              currentBatch: batch,
              totalBatches: total,
              currentMonth: month,
              vouchersSoFar: msg.data?.vouchers_so_far || 0,
              message: `Fetching ${month} (${batch}/${total})...`,
              progress: pct
            }));
          } else if (eventType === 'sales_batch_complete') {
            setSyncProgress(prev => ({
              ...prev,
              phase: 'sales',
              message: `Fetched ${msg.data?.total_vouchers || 0} vouchers`,
              progress: 100
            }));
          } else if (eventType === 'phase_complete') {
            const phase = msg.data?.phase || '';
            const count = msg.data?.count || 0;
            setSyncProgress(prev => ({
              ...prev,
              phase,
              message: `${phase}: ${count} items synced`,
            }));
          } else if (eventType === 'sync_complete') {
            setSyncProgress({
              isSyncing: false,
              phase: 'complete',
              message: 'Sync complete',
              progress: 100,
              inventoryCount: msg.data?.inventory_count,
              salesCount: msg.data?.sales_count,
              customerCount: msg.data?.customer_count,
              completedAt: msg.timestamp
            });
          } else if (eventType === 'sync_error') {
            setSyncProgress(prev => ({
              ...prev,
              isSyncing: false,
              phase: 'error',
              message: `Error: ${msg.data?.error || 'Unknown error'}`,
              progress: 0
            }));
          } else if (eventType === 'data_synced') {
            // Actual data arrived at backend
            setSyncProgress(prev => ({
              ...prev,
              [`${msg.data?.data_type}Count`]: msg.data?.count,
              lastDataSync: msg.timestamp
            }));
          }
        } catch (err) {
          console.error('WebSocket message parse error:', err);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        wsRef.current = null;
        // Reconnect with exponential backoff
        const delay = Math.min(5000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
        reconnectAttemptsRef.current += 1;
        reconnectTimeoutRef.current = setTimeout(connect, delay);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch (err) {
      console.error('WebSocket connection error:', err);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  const requestStatus = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'get_status' }));
    }
  }, []);

  return { isConnected, syncProgress, lastEvent, requestStatus };
}

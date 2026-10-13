"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { ApiError } from "./api";

interface State<T> {
  data: T | null;
  error: unknown;
  loading: boolean;
}

/**
 * Load data from the API whenever `key` changes. A lapsed session (401/403)
 * goes back to sign-in. Stale responses never overwrite newer ones.
 */
export function useApi<T>(load: () => Promise<T>, key: string) {
  const router = useRouter();
  const pathname = usePathname();
  const loadRef = useRef(load);
  const [state, setState] = useState<State<T>>({ data: null, error: null, loading: true });

  useEffect(() => {
    loadRef.current = load;
  });

  useEffect(() => {
    let cancelled = false;
    loadRef.current().then(
      (data) => {
        if (!cancelled) setState({ data, error: null, loading: false });
      },
      (error: unknown) => {
        if (cancelled) return;
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
          router.replace(`/login?next=${encodeURIComponent(pathname)}`);
          return;
        }
        setState({ data: null, error, loading: false });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [key, router, pathname]);

  const setData = (update: (current: T | null) => T | null) =>
    setState((s) => ({ ...s, data: update(s.data) }));

  return { ...state, setData };
}

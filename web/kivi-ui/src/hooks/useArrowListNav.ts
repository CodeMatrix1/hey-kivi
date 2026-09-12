import { useCallback, useEffect, useRef, useState } from "react";

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (target.isContentEditable) return true;
  return false;
}

function isExemptActionButton(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target.classList.contains("btn-new-conversation") ||
    target.classList.contains("btn-new-reminder") ||
    target.classList.contains("sidebar-panel-toggle")
  );
}

interface UseArrowListNavOptions<T> {
  items: T[];
  enabled: boolean;
  selectedId: string | null;
  getId: (item: T) => string;
  onSelect: (id: string) => void;
}

export function useArrowListNav<T>({
  items,
  enabled,
  selectedId,
  getId,
  onSelect,
}: UseArrowListNavOptions<T>) {
  const [focusIndex, setFocusIndex] = useState(-1);
  const focusIndexRef = useRef(-1);
  const itemRefs = useRef<Array<HTMLElement | null>>([]);

  useEffect(() => {
    focusIndexRef.current = focusIndex;
  }, [focusIndex]);

  useEffect(() => {
    if (!selectedId) return;
    const idx = items.findIndex((item) => getId(item) === selectedId);
    if (idx >= 0) setFocusIndex(idx);
  }, [selectedId, items, getId]);

  useEffect(() => {
    if (!enabled) setFocusIndex(-1);
  }, [enabled]);

  useEffect(() => {
    if (focusIndex < 0) return;
    itemRefs.current[focusIndex]?.scrollIntoView({ block: "nearest" });
  }, [focusIndex]);

  useEffect(() => {
    if (!enabled || items.length === 0) return;

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp" && e.key !== "Enter") return;
      if (isTypingTarget(e.target)) return;
      if (isExemptActionButton(e.target)) return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setFocusIndex((current) => {
          if (items.length === 0) return -1;
          if (current < 0) return 0;
          return Math.min(items.length - 1, current + 1);
        });
        return;
      }

      if (e.key === "ArrowUp") {
        e.preventDefault();
        setFocusIndex((current) => {
          if (items.length === 0) return -1;
          if (current < 0) return items.length - 1;
          return Math.max(0, current - 1);
        });
        return;
      }

      const current = focusIndexRef.current;
      if (current >= 0 && current < items.length) {
        e.preventDefault();
        onSelect(getId(items[current]));
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [enabled, items, getId, onSelect]);

  const setItemRef = useCallback(
    (index: number) => (el: HTMLElement | null) => {
      itemRefs.current[index] = el;
    },
    [],
  );

  return { focusIndex, setItemRef };
}

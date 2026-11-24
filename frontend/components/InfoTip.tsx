"use client";

import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export function InfoTip({ text }: { text: string }) {
  const triggerRef = useRef<HTMLSpanElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState({ left: 0, top: 0, ready: false });
  const id = useId();

  useLayoutEffect(() => {
    if (!open) return;
    const update = () => {
      const trigger = triggerRef.current;
      const tooltip = tooltipRef.current;
      if (!trigger || !tooltip) return;
      const rect = trigger.getBoundingClientRect();
      const gap = 8;
      const edge = 8;
      const width = tooltip.offsetWidth;
      const height = tooltip.offsetHeight;
      const left = Math.min(
        Math.max(rect.left + rect.width / 2 - width / 2, edge),
        window.innerWidth - width - edge,
      );
      const below = rect.top < height + gap + edge;
      setCoords({
        left,
        top: below ? rect.bottom + gap : rect.top - height - gap,
        ready: true,
      });
    };
    update();
    window.addEventListener("scroll", update, true);
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update, true);
      window.removeEventListener("resize", update);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  return (
    <span
      ref={triggerRef}
      className="info-tip"
      role="note"
      tabIndex={0}
      aria-label={text}
      aria-describedby={open ? id : undefined}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      ?
      {open &&
        typeof document !== "undefined" &&
        createPortal(
          <div
            ref={tooltipRef}
            id={id}
            role="tooltip"
            className="info-tip-tooltip"
            style={{
              left: coords.left,
              top: coords.top,
              visibility: coords.ready ? "visible" : "hidden",
            }}
          >
            {text}
          </div>,
          document.body,
        )}
    </span>
  );
}

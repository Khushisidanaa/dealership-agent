import { useState, useEffect, useCallback, useRef } from "react";
import "./VehicleImageSlideshow.css";

const DEFAULT_PLACEHOLDER =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='260' fill='%231e2a3a'%3E%3Crect width='400' height='260'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' fill='%236b7a8f' font-size='16' font-family='system-ui'%3ENo Image%3C/text%3E%3C/svg%3E";

const ROTATE_MS = 4000;

export interface VehicleImageSlideshowProps {
  imageUrls: string[];
  alt: string;
  placeholder?: string;
  className?: string;
  imgClassName?: string;
  /** When true, only the first image is shown (no rotation). Still supports multiple for detail views. */
  staticFirst?: boolean;
}

const isPlaceholderUrl = (url: string) =>
  !url || url.startsWith("data:image/svg+xml");

/**
 * Rolling slideshow for listing images. Auto-rotates every 4s when multiple URLs.
 * Shows dots only when there are 2+ real (non-placeholder) images.
 */
export function VehicleImageSlideshow({
  imageUrls,
  alt,
  placeholder = DEFAULT_PLACEHOLDER,
  className = "",
  imgClassName = "",
  staticFirst = false,
}: VehicleImageSlideshowProps) {
  const rawUrls = Array.isArray(imageUrls) ? imageUrls.filter(Boolean) : [];
  const realUrls = rawUrls.filter((u) => !isPlaceholderUrl(String(u)));
  const effective =
    realUrls.length > 0 ? realUrls : rawUrls.length > 0 ? rawUrls : [placeholder];
  const hasMultiple =
    effective.length > 1 && effective.some((u) => !isPlaceholderUrl(String(u)));

  const [index, setIndex] = useState(0);
  const [failed, setFailed] = useState<Set<number>>(new Set());

  const currentSrc = effective[index];
  const isPlaceholder =
    isPlaceholderUrl(String(currentSrc)) || failed.has(index);
  const displaySrc = isPlaceholder ? placeholder : currentSrc;

  const lastLoggedKey = useRef<string>("");
  const urlKey = Array.isArray(imageUrls)
    ? imageUrls.length + ":" + imageUrls.map(String).join("|").slice(0, 500)
    : "";
  useEffect(() => {
    if (!urlKey || typeof window === "undefined") return;
    const key = `${alt ?? ""}:${urlKey}`;
    if (lastLoggedKey.current === key) return;
    lastLoggedKey.current = key;
    const label = (alt ?? "vehicle").slice(0, 50);
    const urlsToLog = rawUrls.map((u) =>
      typeof u === "string" && u.length > 120 ? u.slice(0, 120) + "…" : u,
    );
    console.log(`[VehicleImageSlideshow] "${label}": ${rawUrls.length} URL(s)`, urlsToLog);
  }, [alt, urlKey]);

  const handleError = useCallback(() => {
    if (typeof window !== "undefined") {
      console.warn(
        `[VehicleImageSlideshow] Image failed to load (index ${index}):`,
        typeof currentSrc === "string" && currentSrc.length > 100
          ? currentSrc.slice(0, 100) + "…"
          : currentSrc,
      );
    }
    setFailed((prev) => new Set(prev).add(index));
  }, [index, currentSrc]);

  const goTo = useCallback(
    (i: number) => {
      const next = ((i % effective.length) + effective.length) % effective.length;
      setIndex(next);
    },
    [effective.length],
  );

  const goNext = useCallback(() => {
    goTo(index + 1);
  }, [goTo, index]);

  useEffect(() => {
    if (staticFirst || !hasMultiple) return;
    const t = setInterval(goNext, ROTATE_MS);
    return () => clearInterval(t);
  }, [staticFirst, hasMultiple, goNext]);

  if (effective.length === 0) {
    return (
      <div className={`vehicle-slideshow ${className}`.trim()}>
        <img
          src={placeholder}
          alt={alt}
          className={`vehicle-slideshow-img ${imgClassName}`.trim()}
        />
      </div>
    );
  }

  return (
    <div className={`vehicle-slideshow ${className}`.trim()}>
      <img
        key={index}
        src={displaySrc}
        alt={alt}
        className={`vehicle-slideshow-img ${imgClassName}`.trim()}
        onError={handleError}
        loading="lazy"
      />
      {hasMultiple && (
        <div className="vehicle-slideshow-dots" aria-hidden>
          {effective.map((_, i) => (
            <button
              key={i}
              type="button"
              className={`vehicle-slideshow-dot ${i === index ? "vehicle-slideshow-dot--active" : ""}`}
              onClick={(e) => {
                e.stopPropagation();
                goTo(i);
              }}
              aria-label={`Photo ${i + 1} of ${effective.length}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}

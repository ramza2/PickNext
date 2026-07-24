import { useState } from "react";

type ContentPosterSize = "xs" | "sm" | "md" | "lg";

const SIZE_CLASS: Record<ContentPosterSize, string> = {
  xs: "w-10 h-14 text-base",
  sm: "w-10 h-14 text-base",
  md: "w-16 h-24 text-xl",
  lg: "w-32 h-48 text-4xl",
};

export function ContentPoster({
  src,
  title,
  fallbackColor,
  size = "sm",
  className = "",
  loading = "lazy",
  roundedClassName = "rounded-lg",
}: {
  src: string | null | undefined;
  title: string;
  fallbackColor: string;
  size?: ContentPosterSize;
  className?: string;
  loading?: "lazy" | "eager";
  roundedClassName?: string;
}) {
  const [failed, setFailed] = useState(false);
  const showImage = Boolean(src) && !failed;
  const sizeClass = SIZE_CLASS[size];
  const alt = `${title} 포스터`;

  if (showImage && src) {
    return (
      <div
        className={`${sizeClass} ${roundedClassName} overflow-hidden flex-shrink-0 bg-muted ${className}`}
      >
        <img
          src={src}
          alt={alt}
          loading={loading}
          className="w-full h-full object-cover"
          onError={() => setFailed(true)}
        />
      </div>
    );
  }

  return (
    <div
      className={`${sizeClass} ${roundedClassName} flex items-center justify-center flex-shrink-0 text-white font-bold ${className}`}
      style={{ backgroundColor: fallbackColor }}
      role="img"
      aria-label={alt}
    >
      {title.charAt(0) || "?"}
    </div>
  );
}

export function formatReleaseYearMeta(
  releaseYear: number | null | undefined,
  extras: Array<string | null | undefined> = [],
): string | null {
  const parts: string[] = [];
  if (typeof releaseYear === "number" && Number.isFinite(releaseYear)) {
    parts.push(String(releaseYear));
  }
  for (const extra of extras) {
    if (extra) parts.push(extra);
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}

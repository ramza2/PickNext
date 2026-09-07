import { useRef } from "react";
import type { InputHTMLAttributes, Ref } from "react";
import { Search, X } from "lucide-react";

type ClearableSearchInputProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "value" | "onChange" | "type"
> & {
  value: string;
  onChange: (value: string) => void;
  /** Show leading search icon (default true). */
  showSearchIcon?: boolean;
  clearAriaLabel?: string;
  inputRef?: Ref<HTMLInputElement>;
};

export function ClearableSearchInput({
  value,
  onChange,
  showSearchIcon = true,
  clearAriaLabel = "검색어 지우기",
  className = "",
  inputRef,
  disabled,
  ...rest
}: ClearableSearchInputProps) {
  const localRef = useRef<HTMLInputElement | null>(null);

  const setRefs = (node: HTMLInputElement | null) => {
    localRef.current = node;
    if (typeof inputRef === "function") {
      inputRef(node);
    } else if (inputRef && "current" in inputRef) {
      (inputRef as { current: HTMLInputElement | null }).current = node;
    }
  };

  const hasValue = value.length > 0;
  const paddingLeft = showSearchIcon ? "pl-9" : "pl-3";
  const paddingRight = hasValue ? "pr-9" : "pr-3";

  return (
    <div className="relative w-full">
      {showSearchIcon ? (
        <Search
          size={16}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none"
          aria-hidden
        />
      ) : null}
      <input
        {...rest}
        ref={setRefs}
        type="search"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className={[
          "w-full border border-border rounded-xl py-2.5 text-sm bg-card",
          paddingLeft,
          paddingRight,
          className,
        ]
          .filter(Boolean)
          .join(" ")}
      />
      {hasValue && !disabled ? (
        <button
          type="button"
          aria-label={clearAriaLabel}
          className="absolute right-1.5 top-1/2 -translate-y-1/2 min-w-9 min-h-9 inline-flex items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
          onClick={() => {
            onChange("");
            window.requestAnimationFrame(() => {
              localRef.current?.focus();
            });
          }}
        >
          <X size={16} />
        </button>
      ) : null}
    </div>
  );
}

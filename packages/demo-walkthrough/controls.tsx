import type { ButtonHTMLAttributes, ReactNode, SVGProps } from "react";
type ButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "onClick"> & {
  onPress?: () => void;
  isDisabled?: boolean;
  isIconOnly?: boolean;
  size?: string;
  variant?: string;
};
export function Button({
  onPress,
  isDisabled,
  isIconOnly,
  size,
  variant,
  children,
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      type="button"
      disabled={isDisabled}
      onClick={onPress}
      className={`dw-button ${isIconOnly ? "dw-icon" : ""} ${className}`}
      data-variant={variant || "primary"}
      data-size={size}
    >
      {children}
    </button>
  );
}
type SliderProps = {
  "aria-label": string;
  minValue: number;
  maxValue: number;
  step: number;
  value: number;
  isDisabled?: boolean;
  onChange: (value: number) => void;
  children?: ReactNode;
};
export function Slider(p: SliderProps) {
  return (
    <input
      className="slider dw-slider"
      aria-label={p["aria-label"]}
      type="range"
      min={p.minValue}
      max={p.maxValue}
      step={p.step}
      value={p.value}
      disabled={p.isDisabled}
      onChange={(e) => p.onChange(Number(e.target.value))}
    />
  );
}
Slider.Track = ({ children }: { children?: ReactNode }) => <>{children}</>;
Slider.Fill = () => null;
Slider.Thumb = () => null;
function Icon({ children, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {children}
    </svg>
  );
}
export const Play = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="m8 4 12 8-12 8Z" />
  </Icon>
);
export const Pause = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M8 4v16M16 4v16" />
  </Icon>
);
export const ForwardStep = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="m4 4 12 8-12 8ZM20 4v16" />
  </Icon>
);
export const ArrowRotateLeft = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M3 4v6h6M3 10a9 9 0 1 1 2 9" />
  </Icon>
);
export const Text = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M10 9a4 4 0 1 0 0 6M21 9a4 4 0 1 0 0 6" />
  </Icon>
);

export const Plus = (p: SVGProps<SVGSVGElement>) => <Icon {...p}><path d="M12 5v14M5 12h14" /></Icon>;
export const Record = (p: SVGProps<SVGSVGElement>) => <Icon {...p}><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3" fill="currentColor"/></Icon>;
export const Layers = (p: SVGProps<SVGSVGElement>) => <Icon {...p}><path d="m12 3 10 5-10 5L2 8Zm-10 9 10 5 10-5M2 17l10 5 10-5"/></Icon>;
export const Library = (p: SVGProps<SVGSVGElement>) => <Icon {...p}><path d="M4 4v16M9 4v16m5-15 5 14"/></Icon>;
export const TimelineIcon = (p: SVGProps<SVGSVGElement>) => <Icon {...p}><path d="M3 12h18M6 8v8m6-6v4m6-6v8"/></Icon>;
export const MapIcon = (p: SVGProps<SVGSVGElement>) => <Icon {...p}><rect x="9" y="2" width="6" height="5" rx="1"/><rect x="2" y="17" width="6" height="5" rx="1"/><rect x="16" y="17" width="6" height="5" rx="1"/><path d="M12 7v5M5 17v-5h14v5"/></Icon>;

export const Stop = (p: SVGProps<SVGSVGElement>) => <Icon {...p}><rect x="6" y="6" width="12" height="12" rx="1" fill="currentColor" /></Icon>;

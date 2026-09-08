import type { ButtonHTMLAttributes } from "react";

type ButtonVariant = "primary" | "secondary";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

/**
 * Minimal, unstyled-but-accessible primitive (implementation plan
 * resolution 3 -- no design-system convention exists in this repo yet).
 * Native <button>, always keyboard-operable with a visible focus ring by
 * default (accessibility-standards SKILL.md).
 */
export function Button({ variant = "primary", className, ...props }: ButtonProps) {
  const base =
    "btn " +
    (variant === "primary" ? "btn-primary" : "btn-secondary") +
    (className ? ` ${className}` : "");
  return <button className={base} {...props} />;
}

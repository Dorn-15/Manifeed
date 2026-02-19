import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

import { cx } from "../../lib/cx";
import styles from "./Field.module.css";

type FieldProps = {
  label: string;
  htmlFor: string;
  children: ReactNode;
  className?: string;
};

type TextInputProps = InputHTMLAttributes<HTMLInputElement>;
type SelectInputProps = SelectHTMLAttributes<HTMLSelectElement>;

export function Field({ label, htmlFor, children, className }: FieldProps) {
  return (
    <label htmlFor={htmlFor} className={cx(styles.field, className)}>
      <span className={styles.label}>{label}</span>
      {children}
    </label>
  );
}

export function TextInput({ className, ...rest }: TextInputProps) {
  return <input className={cx(styles.control, className)} {...rest} />;
}

export function SelectInput({ className, ...rest }: SelectInputProps) {
  return <select className={cx(styles.control, className)} {...rest} />;
}

import styles from "./EnabledToggle.module.css";

type EnabledToggleProps = {
  enabled: boolean;
  ariaLabel: string;
  onChange: (nextEnabled: boolean) => void | Promise<void>;
  disabled?: boolean;
  loading?: boolean;
};

export function EnabledToggle({
  enabled,
  ariaLabel,
  onChange,
  disabled = false,
  loading = false,
}: EnabledToggleProps) {
  const blocked = disabled || loading;

  const handleClick = () => {
    if (blocked) {
      return;
    }

    void onChange(!enabled);
  };

  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label={ariaLabel}
      aria-busy={loading || undefined}
      disabled={blocked}
      className={`${styles.toggle} ${enabled ? styles.enabled : styles.disabled}`}
      onClick={handleClick}
    >
        <span className={styles.thumb} />
    </button>
  );
}

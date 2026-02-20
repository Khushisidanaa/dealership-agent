import "./StepIndicator.css";

interface Step<T extends string = string> {
  key: T;
  label: string;
}

interface StepIndicatorProps<T extends string = string> {
  steps: Step<T>[];
  current: string;
  completedPhases?: Set<T>;
  onStepClick?: (key: T) => void;
}

export function StepIndicator<T extends string = string>({
  steps,
  current,
  completedPhases,
  onStepClick,
}: StepIndicatorProps<T>) {
  const currentIdx = steps.findIndex((s) => s.key === current);

  return (
    <div className="steps">
      {steps.map((step, i) => {
        const isDone = completedPhases?.has(step.key) ?? i < currentIdx;
        const isActive = i === currentIdx;
        const isClickable = onStepClick && (isDone || isActive);
        const cls = [
          "step",
          isDone ? "step--done" : isActive ? "step--active" : "",
          isClickable ? "step--clickable" : "",
        ]
          .filter(Boolean)
          .join(" ");

        return (
          <div
            key={step.key}
            className={cls}
            onClick={() => isClickable && onStepClick?.(step.key)}
            role={isClickable ? "button" : undefined}
            tabIndex={isClickable ? 0 : undefined}
            onKeyDown={(e) => {
              if (isClickable && (e.key === "Enter" || e.key === " ")) {
                e.preventDefault();
                onStepClick?.(step.key);
              }
            }}
          >
            <div className="step-dot">
              {isDone ? (
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              ) : (
                <span>{i + 1}</span>
              )}
            </div>
            <span className="step-label">{step.label}</span>
            {i < steps.length - 1 && <div className="step-line" />}
          </div>
        );
      })}
    </div>
  );
}

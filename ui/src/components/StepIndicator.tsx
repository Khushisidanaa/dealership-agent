import "./StepIndicator.css";

interface Step {
  key: string;
  label: string;
}

interface StepIndicatorProps {
  steps: Step[];
  current: string;
}

export function StepIndicator({ steps, current }: StepIndicatorProps) {
  const currentIdx = steps.findIndex((s) => s.key === current);

  return (
    <div className="steps">
      {steps.map((step, i) => {
        const isDone = i < currentIdx;
        const isActive = i === currentIdx;
        const cls = isDone ? "step--done" : isActive ? "step--active" : "";
        return (
          <div key={step.key} className={`step ${cls}`}>
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

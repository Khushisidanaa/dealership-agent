import { useState } from "react";
import { api } from "../api/client";
import type { VehicleResult } from "../types";
import "./TestDriveModal.css";

type Phase = "form" | "calling" | "result";

interface CallResult {
  booking_id: string;
  status: string;
  confirmed: boolean;
  scheduled_date: string | null;
  scheduled_time: string | null;
  dealer_notes: string | null;
  vehicle_title: string;
  dealer_name: string;
}

interface TestDriveModalProps {
  sessionId: string;
  vehicle: VehicleResult;
  onClose: () => void;
  onBooked: (res: {
    booking_id: string;
    vehicle_id: string;
    vehicle_title: string;
    dealer_name: string;
    scheduled_date: string;
    scheduled_time: string;
    status: string;
  }) => void;
}

function formatDate(raw: string | null): string {
  if (!raw) return "TBD";
  try {
    return new Date(raw + "T00:00:00").toLocaleDateString("en-US", {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
  } catch {
    return raw;
  }
}

function formatTime(raw: string | null): string {
  if (!raw) return "TBD";
  if (raw.includes(":") && raw.length <= 5) {
    const [h, m] = raw.split(":").map(Number);
    const ampm = h >= 12 ? "PM" : "AM";
    const h12 = h % 12 || 12;
    return `${h12}:${String(m).padStart(2, "0")} ${ampm}`;
  }
  return raw;
}

export function TestDriveModal({
  sessionId,
  vehicle,
  onClose,
  onBooked,
}: TestDriveModalProps) {
  const [phase, setPhase] = useState<Phase>("form");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [callResult, setCallResult] = useState<CallResult | null>(null);

  const handleCall = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!date.trim() || !time.trim() || !name.trim()) {
      setError("Please fill in date, time, and your name.");
      return;
    }

    setPhase("calling");

    try {
      const result = await api.testDrive.call(sessionId, {
        vehicle_id: vehicle.vehicle_id,
        preferred_date: date.trim(),
        preferred_time: time.trim(),
        user_name: name.trim(),
      });

      setCallResult(result);
      setPhase("result");

      onBooked({
        booking_id: result.booking_id,
        vehicle_id: vehicle.vehicle_id,
        vehicle_title: result.vehicle_title || vehicle.title,
        dealer_name: result.dealer_name || vehicle.dealer_name,
        scheduled_date: result.scheduled_date || date.trim(),
        scheduled_time: result.scheduled_time || time.trim(),
        status: result.status,
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setPhase("form");
    }
  };

  const isConfirmed = callResult?.confirmed === true;
  const isFailed = callResult?.status === "call_failed";

  return (
    <div className="testdrive-overlay" onClick={onClose}>
      <div className="testdrive-modal" onClick={(e) => e.stopPropagation()}>
        <div className="testdrive-header">
          <h2>
            {phase === "form" && "Schedule Test Drive"}
            {phase === "calling" && "Calling Dealer..."}
            {phase === "result" &&
              (isConfirmed ? "Test Drive Confirmed" : "Call Complete")}
          </h2>
          {phase !== "calling" && (
            <button type="button" className="testdrive-close" onClick={onClose}>
              x
            </button>
          )}
        </div>

        <p className="testdrive-vehicle">{vehicle.title}</p>
        <p className="testdrive-dealer">{vehicle.dealer_name}</p>

        {phase === "form" && (
          <form className="testdrive-form" onSubmit={handleCall}>
            <label>
              <span>Preferred Date</span>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                required
              />
            </label>
            <label>
              <span>Preferred Time</span>
              <input
                type="time"
                value={time}
                onChange={(e) => setTime(e.target.value)}
                required
              />
            </label>
            <label>
              <span>Your Name</span>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                required
              />
            </label>
            {error && <div className="testdrive-error">{error}</div>}
            <div className="testdrive-actions">
              <button
                type="button"
                className="testdrive-cancel"
                onClick={onClose}
              >
                Cancel
              </button>
              <button type="submit" className="testdrive-call-btn">
                Call to Schedule
              </button>
            </div>
          </form>
        )}

        {phase === "calling" && (
          <div className="testdrive-calling">
            <div className="testdrive-calling-animation">
              <div className="testdrive-ring" />
              <div className="testdrive-ring testdrive-ring--delay" />
              <div className="testdrive-phone-icon">
                <svg
                  width="28"
                  height="28"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z" />
                </svg>
              </div>
            </div>
            <p className="testdrive-calling-text">
              Calling <strong>{vehicle.dealer_name}</strong>
            </p>
            <p className="testdrive-calling-sub">
              AI agent is scheduling your test drive for{" "}
              <strong>{formatDate(date)}</strong> at{" "}
              <strong>{formatTime(time)}</strong>
            </p>
            <p className="testdrive-calling-note">
              This usually takes 30 - 90 seconds
            </p>
          </div>
        )}

        {phase === "result" && callResult && (
          <div className="testdrive-result">
            <div
              className={`testdrive-status-badge ${isConfirmed ? "testdrive-status--confirmed" : isFailed ? "testdrive-status--failed" : "testdrive-status--declined"}`}
            >
              {isConfirmed
                ? "Confirmed"
                : isFailed
                  ? "Could Not Reach"
                  : "Not Confirmed"}
            </div>

            {isConfirmed && (
              <div className="testdrive-result-details">
                <div className="testdrive-result-row">
                  <span className="testdrive-result-label">Date</span>
                  <span className="testdrive-result-value">
                    {formatDate(callResult.scheduled_date)}
                  </span>
                </div>
                <div className="testdrive-result-row">
                  <span className="testdrive-result-label">Time</span>
                  <span className="testdrive-result-value">
                    {formatTime(callResult.scheduled_time)}
                  </span>
                </div>
                <div className="testdrive-result-row">
                  <span className="testdrive-result-label">Dealer</span>
                  <span className="testdrive-result-value">
                    {callResult.dealer_name}
                  </span>
                </div>
              </div>
            )}

            {callResult.dealer_notes && (
              <div className="testdrive-result-notes">
                <span className="testdrive-result-label">Dealer Notes</span>
                <p>{callResult.dealer_notes}</p>
              </div>
            )}

            <div className="testdrive-actions">
              <button
                type="button"
                className="testdrive-done-btn"
                onClick={onClose}
              >
                Done
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

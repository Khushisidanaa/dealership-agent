import { useState } from "react";
import { api } from "../api/client";
import type { VehicleResult } from "../types";
import "./TestDriveModal.css";

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

export function TestDriveModal({
  sessionId,
  vehicle,
  onClose,
  onBooked,
}: TestDriveModalProps) {
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!date.trim() || !time.trim() || !name.trim() || !phone.trim()) {
      setError("Please fill in date, time, name, and phone.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await api.testDrive.book(sessionId, {
        vehicle_id: vehicle.vehicle_id,
        preferred_date: date.trim(),
        preferred_time: time.trim(),
        user_name: name.trim(),
        user_phone: phone.trim(),
        user_email: email.trim() || undefined,
        confirm: true,
      });
      onBooked({
        booking_id: res.booking_id,
        vehicle_id: vehicle.vehicle_id,
        vehicle_title: vehicle.title,
        dealer_name: res.dealer_name || vehicle.dealer_name,
        scheduled_date: res.scheduled_date,
        scheduled_time: res.scheduled_time,
        status: res.status,
      });
      setSuccess(true);
      setTimeout(() => onClose(), 1500);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="testdrive-overlay" onClick={onClose}>
      <div className="testdrive-modal" onClick={(e) => e.stopPropagation()}>
        <div className="testdrive-header">
          <h2>Schedule test drive</h2>
          <button type="button" className="testdrive-close" onClick={onClose}>×</button>
        </div>
        <p className="testdrive-vehicle">{vehicle.title}</p>
        <p className="testdrive-dealer">{vehicle.dealer_name}</p>

        {success ? (
          <div className="testdrive-success">
            Request sent. The dealer will confirm your test drive.
          </div>
        ) : (
          <form className="testdrive-form" onSubmit={handleSubmit}>
            <label>
              <span>Date</span>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                required
              />
            </label>
            <label>
              <span>Time</span>
              <input
                type="time"
                value={time}
                onChange={(e) => setTime(e.target.value)}
                required
              />
            </label>
            <label>
              <span>Name</span>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                required
              />
            </label>
            <label>
              <span>Phone</span>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="Phone number"
                required
              />
            </label>
            <label>
              <span>Email (optional)</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email"
              />
            </label>
            {error && <div className="testdrive-error">{error}</div>}
            <div className="testdrive-actions">
              <button type="button" className="testdrive-cancel" onClick={onClose}>
                Cancel
              </button>
              <button type="submit" className="testdrive-submit" disabled={submitting}>
                {submitting ? "Sending…" : "Request test drive"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

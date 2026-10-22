export type QEntry = {
  id: number; appointment_id: number; patient_id: number; patient_name: string; doctor_id: number; session_label: string | null;
  token_number: number | null; token_label: string | null; appointment_type: string; presence: string; status: string;
  flagged: boolean; flag_source: string | null; flag_reason: string | null; acknowledged: boolean; alert_state: "none" | "normal" | "amber" | "red";
  checkin_change: string | null; check_in_ts: string | null; late_arrival: boolean; fast_tracked: boolean; waiting_seconds: number | null;
  chief_complaint: string | null; priority: string | null; priority_rationale: string | null; decided_by: string | null;
  red_flags: string[]; rule_based: boolean; audit_notes: string[];
};
export type DoctorBlock = {
  doctor: { id: number; name: string; specialty: string; room?: string }; mode: "token" | "nurse"; now_serving: string | null; with_doctor: QEntry | null; next: QEntry | null;
  needs_attention: QEntry[]; present_waiting: QEntry[]; booked_not_arrived: QEntry[]; expected_today_flagged: QEntry[];
  still_to_come: number; done_count: number; total: number;
};
export type QueueResp = {
  date: string; session: string;
  assigned_doctor?: { id: number; name: string; specialty: string; room: string } | null;
  doctors: DoctorBlock[];
};

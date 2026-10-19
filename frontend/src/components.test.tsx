import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { QuestionInput } from "./patient/IntakeWizard";
import { EmergencyScreen, RoutineOutcome } from "./patient/Outcomes";
import { I18nProvider, LANGS, translate } from "./shared/i18n";
import { DemoBanner, SafetyBanner } from "./shared/ui";
import { MicButton } from "./shared/voice";

function wrap(ui: React.ReactNode, lang = "en") {
  localStorage.setItem("lifeline.lang", lang);
  return render(<MemoryRouter><I18nProvider>{ui}</I18nProvider></MemoryRouter>);
}

describe("i18n", () => {
  it("has the same keys in every language file", () => {
    const en = Object.keys(LANGS.en).sort();
    for (const [code, dict] of Object.entries(LANGS)) expect(Object.keys(dict).sort(), code).toEqual(en);
  });
  it("translates and interpolates, falling back to English", () => {
    expect(translate("ta", "home.hello", { name: "Asha" })).toContain("Asha");
    expect(translate("xx", "auth.login")).toBe("Log in");
  });
});

describe("banners", () => {
  it("shows both safety banners", () => {
    wrap(<><DemoBanner /><SafetyBanner /></>);
    expect(screen.getByText(/synthetic data/)).toBeInTheDocument();
    expect(screen.getByText(/does not diagnose or prescribe/)).toBeInTheDocument();
  });
});

describe("safety screen question", () => {
  it("puts a big 'None of these' button first and submits it directly", () => {
    const onSubmit = vi.fn();
    wrap(<QuestionInput busy={false} onSubmit={onSubmit}
      q={{ key: "safety_screen", kind: "multi", question: "", source: "fixed", options: ["none", "chest_pain", "trouble_breathing", "fainting", "severe_bleeding", "sudden_weakness", "confusion", "seizure"] }} />);
    const buttons = screen.getAllByRole("button");
    expect(buttons[0]).toHaveTextContent("None of these");
    fireEvent.click(buttons[0]);
    expect(onSubmit).toHaveBeenCalledWith(["none"]);
  });
  it("renders the fixed question in Tamil", () => {
    wrap(<QuestionInput busy={false} onSubmit={() => undefined} q={{ key: "complaint", kind: "text", question: "", source: "fixed", options: [] }} />, "ta");
    expect(screen.getByText("உங்களுக்கு என்ன தொந்தரவு?")).toBeInTheDocument();
  });
});

describe("voice", () => {
  it("hides the mic button when speech recognition is unsupported", () => {
    const { container } = wrap(<MicButton onText={() => undefined} />);
    expect(container.querySelector(".mic")).toBeNull();
  });
});

describe("outcomes", () => {
  it("emergency screen shows numbers and ER details, never a booking or doctor list", () => {
    wrap(<EmergencyScreen numbers={["112", "108"]} hospital={{ id: 1, name: "Demo Hospital", address: "1 Street", area: "A", er_phone: "044-1", walk_in_window_text: "" }} />);
    expect(screen.getByText("Please go to the Emergency department now.")).toBeInTheDocument();
    expect(screen.getByText(/112/)).toBeInTheDocument();
    expect(screen.getByText("No booking has been made.")).toBeInTheDocument();
    expect(screen.queryByText(/Choose this doctor/)).toBeNull();
  });
  it("routine outcome shows the token and an approximate estimate", () => {
    wrap(<RoutineOutcome appt={{ id: 1, type: "booked", status: "booked", date: "2026-10-19", token_label: "M-07", est_call_from: "2026-10-19T10:00:00",
      est_call_to: "2026-10-19T10:30:00", doctor: { id: 1, name: "Dr. Demo", specialty: "General Medicine" },
      hospital: { id: 1, name: "Demo Hospital", address: "1 Street", area: "A", er_phone: "", walk_in_window_text: "" },
      session: { id: 1, label: "morning", window_start: "09:00", window_end: "12:00" }, state: "booked", intake_id: 1 }} />);
    expect(screen.getByTestId("token")).toHaveTextContent("M-07");
    expect(screen.getByText("approximate")).toBeInTheDocument();
    expect(screen.getByText(/arrive about 20 minutes/)).toBeInTheDocument();
  });
});

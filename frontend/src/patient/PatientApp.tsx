import { Route, Routes } from "react-router-dom";
import { useI18n } from "../shared/i18n";
import { Layout } from "../shared/Layout";
import BookingFlow from "./BookingFlow";
import Home from "./Home";
import MyAppointments from "./MyAppointments";
import MyRecords from "./MyRecords";
import Privacy from "./Privacy";
import Profile from "./Profile";
import SymptomFlow from "./SymptomFlow";

export default function PatientApp() {
  const { t } = useI18n();
  const nav = [
    { to: "/patient", label: t("nav.home") },
    { to: "/patient/appointments", label: t("nav.appointments") },
    { to: "/patient/records", label: t("nav.records") },
    { to: "/patient/privacy", label: t("nav.privacy") },
    { to: "/patient/profile", label: t("nav.profile") },
  ];
  return (
    <Layout nav={nav}>
      <Routes>
        <Route index element={<Home />} />
        <Route path="book" element={<BookingFlow />} />
        <Route path="symptoms" element={<SymptomFlow />} />
        <Route path="appointments" element={<MyAppointments />} />
        <Route path="records" element={<MyRecords />} />
        <Route path="privacy" element={<Privacy />} />
        <Route path="profile" element={<Profile />} />
      </Routes>
    </Layout>
  );
}

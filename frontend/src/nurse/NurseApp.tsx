import { Route, Routes } from "react-router-dom";
import { Layout } from "../shared/Layout";
import ActionLog from "./ActionLog";
import CheckInDesk from "./CheckInDesk";
import Dashboard from "./Dashboard";
import WalkIn from "./WalkIn";

export default function NurseApp() {
  const nav = [
    { to: "/staff/nurse", label: "Dashboard" }, { to: "/staff/nurse/checkin", label: "Check-in desk" },
    { to: "/staff/nurse/walkin", label: "Walk-in" }, { to: "/staff/nurse/log", label: "Action log" },
  ];
  return (
    <Layout nav={nav} wide>
      <Routes>
        <Route index element={<Dashboard />} />
        <Route path="checkin" element={<CheckInDesk />} />
        <Route path="walkin" element={<WalkIn />} />
        <Route path="log" element={<ActionLog />} />
      </Routes>
    </Layout>
  );
}

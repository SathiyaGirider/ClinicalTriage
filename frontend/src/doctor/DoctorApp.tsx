import { Route, Routes } from "react-router-dom";
import { Layout } from "../shared/Layout";
import Search from "./Search";
import Today from "./Today";
import Workspace from "./Workspace";

export default function DoctorApp() {
  return (
    <Layout nav={[{ to: "/staff/doctor", label: "Today" }, { to: "/staff/doctor/search", label: "My patients" }]} wide>
      <Routes>
        <Route index element={<Today />} />
        <Route path="patient/:patientId" element={<Workspace />} />
        <Route path="search" element={<Search />} />
      </Routes>
    </Layout>
  );
}

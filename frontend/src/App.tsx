import { Navigate, Route, Routes } from "react-router-dom";
import Login from "./auth/Login";
import Register from "./auth/Register";
import DoctorApp from "./doctor/DoctorApp";
import NurseApp from "./nurse/NurseApp";
import PatientApp from "./patient/PatientApp";
import { homeFor, useAuth } from "./shared/auth";
import { RequireRole } from "./shared/guards";
import { Loading } from "./shared/ui";

function Root() {
  const { me, loading } = useAuth();
  if (loading) return <Loading />;
  return <Navigate to={me ? homeFor(me.role) : "/login"} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Root />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/patient/*" element={<RequireRole role="patient"><PatientApp /></RequireRole>} />
      <Route path="/staff/nurse/*" element={<RequireRole role="nurse"><NurseApp /></RequireRole>} />
      <Route path="/staff/doctor/*" element={<RequireRole role="doctor"><DoctorApp /></RequireRole>} />
      <Route path="*" element={<Root />} />
    </Routes>
  );
}

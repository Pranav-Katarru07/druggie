import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import PatientsProvider from "./data/PatientsProvider";
import AppLayout from "./layout/AppLayout";
import BrowsePage from "./pages/BrowsePage";
import ReviewPage from "./pages/ReviewPage";

export default function App() {
  return (
    <PatientsProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<Navigate to="/review" replace />} />
            <Route path="review" element={<ReviewPage />} />
            <Route path="browse" element={<BrowsePage />} />
            <Route path="browse/:patientId" element={<BrowsePage />} />
            <Route path="*" element={<Navigate to="/review" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </PatientsProvider>
  );
}

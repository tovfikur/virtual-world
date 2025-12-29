import { useEffect } from "react";
import useAuthStore from "../stores/authStore";

export default function MainLayout({ children }) {
  return (
    <div className="pt-14">
      {" "}
      {/* Add top padding to avoid content under navbar */}
      {children}
    </div>
  );
}

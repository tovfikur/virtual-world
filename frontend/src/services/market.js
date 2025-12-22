import api from "./api";

export const marketAPI = {
  getStatus: () => api.get("/market/status"),
  setStatus: (data) => api.post("/market/status", data),
};

export default marketAPI;

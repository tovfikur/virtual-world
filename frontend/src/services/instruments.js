import api from "./api";

export const instrumentsAPI = {
  list: () => api.get("/instruments"),
  create: (data) => api.post("/instruments", data),
  update: (id, data) => api.patch(`/instruments/${id}`, data),
  remove: (id) => api.delete(`/instruments/${id}`),
};

export default instrumentsAPI;

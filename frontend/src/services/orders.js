import api from "./api";

export const ordersAPI = {
  placeOrder: (data) => api.post("/orders", data),
  listOrders: (params) => api.get("/orders", { params }),
  cancelOrder: (orderId) => api.delete(`/orders/${orderId}`),
};

export default ordersAPI;

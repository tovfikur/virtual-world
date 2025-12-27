import { useEffect, useState } from "react";
import { adminAPI } from "../services/api";
import { toast } from "react-hot-toast";
import useAuthStore from "../stores/authStore";

function AdminAnalyticsPage() {
  const { user } = useAuthStore();
  const [loading, setLoading] = useState(true);
  const [revenueDays, setRevenueDays] = useState(30);
  const [userDays, setUserDays] = useState(30);
  const [revenue, setRevenue] = useState(null);
  const [userAnalytics, setUserAnalytics] = useState(null);

  useEffect(() => {
    if (user?.role !== "admin") {
      toast.error("Admin access required");
      return;
    }
    loadData();
  }, [user, revenueDays, userDays]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [revRes, userRes] = await Promise.all([
        adminAPI.getRevenueAnalytics(revenueDays),
        adminAPI.getUserAnalytics(userDays),
      ]);
      setRevenue(revRes.data || null);
      setUserAnalytics(userRes.data || null);
    } catch (error) {
      console.error(error);
      toast.error("Failed to load analytics");
    } finally {
      setLoading(false);
    }
  };

  const exportCsv = (rows, headers, filename) => {
    if (!rows?.length) {
      toast.error("No data to export");
      return;
    }
    const headerLine = headers.map((h) => h.label).join(",");
    const lines = rows.map((row) =>
      headers
        .map((h) => {
          const val = row[h.key];
          return JSON.stringify(val ?? "");
        })
        .join(",")
    );
    const csv = [headerLine, ...lines].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleExportRevenue = () => {
    exportCsv(
      revenue?.daily_data || [],
      [
        { key: "date", label: "date" },
        { key: "revenue", label: "revenue" },
        { key: "transactions", label: "transactions" },
      ],
      `revenue-${revenueDays}d.csv`
    );
  };

  const handleExportUsers = () => {
    exportCsv(
      userAnalytics?.daily_data || [],
      [
        { key: "date", label: "date" },
        { key: "active_users", label: "active_users" },
        { key: "new_users", label: "new_users" },
      ],
      `users-${userDays}d.csv`
    );
  };

  if (user?.role !== "admin") {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-400 mb-4">
            Access Denied
          </h1>
          <p className="text-gray-400">
            You need admin privileges to access this page.
          </p>
        </div>
      </div>
    );
  }

  const revenueMax = Math.max(
    ...(revenue?.daily_data?.map((d) => d.revenue || 0) || [1])
  );
  const userMax = Math.max(
    ...(userAnalytics?.daily_data?.map(
      (d) => d.active_users || d.new_users || 0
    ) || [1])
  );

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <div className="bg-gray-800 border-b border-gray-700 p-6">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-3xl font-bold mb-2">Analytics & Reporting</h1>
          <p className="text-gray-400">Revenue and user engagement trends</p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6 space-y-8">
        <div className="flex items-center justify-between">
          <div className="flex gap-2">
            {[7, 30, 90].map((d) => (
              <button
                key={`rev-${d}`}
                className={`px-4 py-2 rounded font-semibold ${
                  revenueDays === d
                    ? "bg-blue-600"
                    : "bg-gray-700 hover:bg-gray-600"
                }`}
                onClick={() => setRevenueDays(d)}
              >
                Revenue {d}d
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            {[7, 30, 90].map((d) => (
              <button
                key={`user-${d}`}
                className={`px-4 py-2 rounded font-semibold ${
                  userDays === d
                    ? "bg-green-600"
                    : "bg-gray-700 hover:bg-gray-600"
                }`}
                onClick={() => setUserDays(d)}
              >
                Users {d}d
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
          </div>
        ) : (
          <div className="space-y-8">
            {/* Revenue Panel */}
            <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-xl font-bold">Revenue</h2>
                  <p className="text-gray-400 text-sm">
                    Last {revenueDays} days
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    className="bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded font-semibold"
                    onClick={loadData}
                  >
                    Refresh
                  </button>
                  <button
                    className="bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded font-semibold"
                    onClick={handleExportRevenue}
                  >
                    Export CSV
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div className="bg-gray-750 rounded p-4 border border-gray-700">
                  <p className="text-gray-400 text-sm">Total Revenue</p>
                  <p className="text-3xl font-bold text-green-400">
                    {revenue?.total_revenue?.toLocaleString() || 0} BDT
                  </p>
                </div>
                <div className="bg-gray-750 rounded p-4 border border-gray-700">
                  <p className="text-gray-400 text-sm">Avg Daily</p>
                  <p className="text-3xl font-bold text-blue-400">
                    {revenue?.average_daily_revenue?.toLocaleString?.() ||
                      Math.round(
                        (revenue?.total_revenue || 0) / (revenueDays || 1)
                      )}{" "}
                    BDT
                  </p>
                </div>
                <div className="bg-gray-750 rounded p-4 border border-gray-700">
                  <p className="text-gray-400 text-sm">Transactions</p>
                  <p className="text-3xl font-bold text-yellow-400">
                    {revenue?.transactions_count?.toLocaleString?.() ||
                      revenue?.total_transactions?.toLocaleString?.() ||
                      0}
                  </p>
                </div>
              </div>
              <div className="flex items-end space-x-2 h-56">
                {(revenue?.daily_data || []).slice(-30).map((day, idx) => {
                  const height = revenueMax
                    ? ((day.revenue || 0) / revenueMax) * 100
                    : 0;
                  return (
                    <div
                      key={idx}
                      className="flex-1 flex flex-col items-center"
                    >
                      <div
                        className="w-full bg-blue-600 rounded-t hover:bg-blue-500 transition-colors cursor-pointer"
                        style={{ height: `${height}%` }}
                        title={`${day.date}: ${day.revenue} BDT`}
                      ></div>
                      <span className="text-[10px] text-gray-500 mt-1">
                        {new Date(day.date).getDate()}
                      </span>
                    </div>
                  );
                })}
                {(revenue?.daily_data?.length || 0) === 0 && (
                  <div className="text-gray-400 text-sm">No revenue data</div>
                )}
              </div>
            </div>

            {/* User Analytics Panel */}
            <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-xl font-bold">User Analytics</h2>
                  <p className="text-gray-400 text-sm">Last {userDays} days</p>
                </div>
                <div className="flex gap-2">
                  <button
                    className="bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded font-semibold"
                    onClick={loadData}
                  >
                    Refresh
                  </button>
                  <button
                    className="bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded font-semibold"
                    onClick={handleExportUsers}
                  >
                    Export CSV
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div className="bg-gray-750 rounded p-4 border border-gray-700">
                  <p className="text-gray-400 text-sm">Active Today</p>
                  <p className="text-3xl font-bold text-green-400">
                    {userAnalytics?.active_users_today?.toLocaleString?.() || 0}
                  </p>
                </div>
                <div className="bg-gray-750 rounded p-4 border border-gray-700">
                  <p className="text-gray-400 text-sm">New Users (period)</p>
                  <p className="text-3xl font-bold text-blue-400">
                    {userAnalytics?.new_users_total?.toLocaleString?.() ||
                      userAnalytics?.new_users?.toLocaleString?.() ||
                      0}
                  </p>
                </div>
                <div className="bg-gray-750 rounded p-4 border border-gray-700">
                  <p className="text-gray-400 text-sm">Peak DAU</p>
                  <p className="text-3xl font-bold text-yellow-400">
                    {userAnalytics?.peak_dau?.toLocaleString?.() || 0}
                  </p>
                </div>
              </div>
              <div className="flex items-end space-x-2 h-56">
                {(userAnalytics?.daily_data || [])
                  .slice(-30)
                  .map((day, idx) => {
                    const dayValue = day.active_users ?? day.new_users ?? 0;
                    const height = userMax ? (dayValue / userMax) * 100 : 0;
                    return (
                      <div
                        key={idx}
                        className="flex-1 flex flex-col items-center"
                      >
                        <div
                          className="w-full bg-green-600 rounded-t hover:bg-green-500 transition-colors cursor-pointer"
                          style={{ height: `${height}%` }}
                          title={`${day.date}: ${dayValue} users`}
                        ></div>
                        <span className="text-[10px] text-gray-500 mt-1">
                          {new Date(day.date).getDate()}
                        </span>
                      </div>
                    );
                  })}
                {(userAnalytics?.daily_data?.length || 0) === 0 && (
                  <div className="text-gray-400 text-sm">No user data</div>
                )}
              </div>

              {userAnalytics?.daily_data &&
                userAnalytics.daily_data.length > 0 && (
                  <div className="mt-6 overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="text-left text-gray-400">
                          <th className="px-3 py-2">Date</th>
                          <th className="px-3 py-2">Active Users</th>
                          <th className="px-3 py-2">New Users</th>
                        </tr>
                      </thead>
                      <tbody>
                        {userAnalytics.daily_data.slice(-30).map((day) => (
                          <tr
                            key={day.date}
                            className="border-t border-gray-700"
                          >
                            <td className="px-3 py-2">{day.date}</td>
                            <td className="px-3 py-2">
                              {day.active_users ?? "-"}
                            </td>
                            <td className="px-3 py-2">
                              {day.new_users ?? "-"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default AdminAnalyticsPage;

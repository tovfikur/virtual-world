import { useEffect, useState } from "react";
import { adminAPI } from "../services/api";
import useAuthStore from "../stores/authStore";
import { toast } from "react-hot-toast";

function AdminMaintenancePage() {
  const { user } = useAuthStore();
  const [loading, setLoading] = useState(false);
  const [migrations, setMigrations] = useState([]);
  const [backupNote, setBackupNote] = useState("manual");
  const [restoreId, setRestoreId] = useState("");
  const [reindexScope, setReindexScope] = useState("database");

  useEffect(() => {
    if (user?.role !== "admin") {
      toast.error("Admin access required");
      return;
    }
    loadMigrations();
  }, [user]);

  const loadMigrations = async () => {
    try {
      const res = await adminAPI.migrationsHistory();
      setMigrations(res.data?.history || []);
    } catch (error) {
      console.error(error);
    }
  };

  const runOp = async (fn, successMsg) => {
    setLoading(true);
    try {
      await fn();
      toast.success(successMsg);
      loadMigrations();
    } catch (error) {
      console.error(error);
      toast.error("Operation failed");
    } finally {
      setLoading(false);
    }
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

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <div className="bg-gray-800 border-b border-gray-700 p-6">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-3xl font-bold mb-2">Maintenance & Operations</h1>
          <p className="text-gray-400">
            Database maintenance, backups, and migrations
          </p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6 space-y-8">
        {/* Database Maintenance */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-xl font-bold mb-4">Database Maintenance</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <button
              className="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded font-semibold disabled:opacity-50"
              disabled={loading}
              onClick={() => {
                if (!window.confirm("Run VACUUM on database?")) return;
                runOp(() => adminAPI.dbVacuum("database"), "VACUUM completed");
              }}
            >
              VACUUM
            </button>
            <button
              className="bg-indigo-600 hover:bg-indigo-700 px-6 py-3 rounded font-semibold disabled:opacity-50"
              disabled={loading}
              onClick={() => {
                if (!window.confirm("Run ANALYZE on database?")) return;
                runOp(
                  () => adminAPI.dbAnalyze("database"),
                  "ANALYZE completed"
                );
              }}
            >
              ANALYZE
            </button>
            <button
              className="bg-purple-600 hover:bg-purple-700 px-6 py-3 rounded font-semibold disabled:opacity-50"
              disabled={loading}
              onClick={() => {
                if (!window.confirm(`Queue REINDEX (scope: ${reindexScope})?`))
                  return;
                runOp(
                  () => adminAPI.dbReindex({ type: reindexScope }),
                  "REINDEX queued"
                );
              }}
            >
              REINDEX
            </button>
          </div>
          <div className="mt-4">
            <label className="text-sm text-gray-400 mr-3">Reindex Scope</label>
            <select
              className="bg-gray-700 text-white px-4 py-2 rounded border border-gray-600"
              value={reindexScope}
              onChange={(e) => setReindexScope(e.target.value)}
            >
              <option value="database">Database</option>
              <option value="tables">Tables</option>
              <option value="indexes">Indexes</option>
            </select>
          </div>
        </div>

        {/* Backups */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-xl font-bold mb-4">Backups</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-center">
            <div className="flex items-center gap-3">
              <input
                type="text"
                placeholder="Backup note"
                className="bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 flex-1"
                value={backupNote}
                onChange={(e) => setBackupNote(e.target.value)}
              />
              <button
                className="bg-green-600 hover:bg-green-700 px-6 py-3 rounded font-semibold disabled:opacity-50"
                disabled={loading}
                onClick={() => {
                  if (!window.confirm("Create backup now?")) return;
                  runOp(() => adminAPI.dbBackup(backupNote), "Backup started");
                }}
              >
                Create Backup
              </button>
            </div>
            <div className="flex items-center gap-3">
              <input
                type="text"
                placeholder="Backup ID to restore"
                className="bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 flex-1"
                value={restoreId}
                onChange={(e) => setRestoreId(e.target.value)}
              />
              <button
                className="bg-yellow-600 hover:bg-yellow-700 px-6 py-3 rounded font-semibold disabled:opacity-50"
                disabled={loading || !restoreId}
                onClick={() => {
                  if (!window.confirm("Restore backup and restart services?"))
                    return;
                  runOp(
                    () => adminAPI.dbRestore(restoreId),
                    "Restore requested"
                  );
                }}
              >
                Restore Backup
              </button>
            </div>
          </div>
          <p className="text-xs text-gray-400 mt-2">
            Restores may restart services and cause downtime. Confirm before
            proceeding.
          </p>
        </div>

        {/* Migrations */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-xl font-bold mb-4">Migrations</h2>
          <div className="flex flex-wrap gap-3 mb-4">
            <button
              className="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded font-semibold disabled:opacity-50"
              disabled={loading}
              onClick={() =>
                runOp(adminAPI.migrationsRunPending, "Ran pending migrations")
              }
            >
              Run Pending
            </button>
            <button
              className="bg-red-600 hover:bg-red-700 px-6 py-3 rounded font-semibold disabled:opacity-50"
              disabled={loading}
              onClick={() => {
                if (!window.confirm("Rollback last migration?")) return;
                runOp(
                  adminAPI.migrationsRollbackLast,
                  "Rolled back last migration"
                );
              }}
            >
              Rollback Last
            </button>
            <button
              className="bg-gray-700 hover:bg-gray-600 px-6 py-3 rounded font-semibold"
              onClick={loadMigrations}
            >
              Refresh History
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400">
                  <th className="px-3 py-2">Version</th>
                  <th className="px-3 py-2">Name</th>
                  <th className="px-3 py-2">Applied At</th>
                  <th className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {migrations.map((m) => (
                  <tr key={m.version} className="border-t border-gray-700">
                    <td className="px-3 py-2 font-mono">{m.version}</td>
                    <td className="px-3 py-2">{m.name}</td>
                    <td className="px-3 py-2">
                      {m.applied_at
                        ? new Date(m.applied_at).toLocaleString()
                        : "-"}
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={`px-2 py-1 rounded text-xs ${
                          m.status === "applied"
                            ? "bg-green-700 text-green-200"
                            : m.status === "pending"
                            ? "bg-yellow-700 text-yellow-200"
                            : "bg-red-700 text-red-200"
                        }`}
                      >
                        {m.status || "unknown"}
                      </span>
                    </td>
                  </tr>
                ))}
                {migrations.length === 0 && (
                  <tr>
                    <td className="px-3 py-2 text-gray-400" colSpan={4}>
                      No migration history available
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AdminMaintenancePage;

import { useEffect, useState } from "react";
import { tradingAPI, authAPI } from "../services/api";
import useAuthStore from "../stores/authStore";
import toast from "react-hot-toast";

const initialCompanyForm = { name: "", total_shares: 1000, initial_price: 1 };
const initialTxForm = { company_id: "", shares: 0, fee_percent: 0, fee_fixed_shares: 0 };

function TradingPage() {
  const [companies, setCompanies] = useState([]);
  const [loading, setLoading] = useState(false);
  const [batchLoading, setBatchLoading] = useState(false);
  const [companyForm, setCompanyForm] = useState(initialCompanyForm);
  const [txForm, setTxForm] = useState(initialTxForm);
  const [batchResult, setBatchResult] = useState(null);
  const { user, updateUser } = useAuthStore();
  const isAdmin = user?.role === "admin";

  const loadCompanies = async () => {
    try {
      setLoading(true);
      const res = await tradingAPI.listCompanies();
      setCompanies(res.data || []);
    } catch (e) {
      console.error(e);
      toast.error("Failed to load companies");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCompanies();
  }, []);

  const handleCreateCompany = async (e) => {
    e.preventDefault();
    try {
      await tradingAPI.createCompany({
        name: companyForm.name,
        total_shares: Number(companyForm.total_shares),
        initial_price: Number(companyForm.initial_price),
      });
      toast.success("Company created");
      setCompanyForm(initialCompanyForm);
      loadCompanies();
    } catch (err) {
      console.error(err);
      toast.error(err.response?.data?.detail || "Failed to create company");
    }
  };

  const refreshUserProfile = async () => {
    try {
      const res = await authAPI.getMe();
      updateUser(res.data);
    } catch (e) {
      console.error("Failed to refresh user profile", e);
    }
  };

  const handleCreateTransaction = async (e) => {
    e.preventDefault();
    if (!txForm.company_id) {
      toast.error("Select a company");
      return;
    }
    if (!txForm.shares || txForm.shares === 0) {
      toast.error("Shares must be non-zero");
      return;
    }
    try {
      await tradingAPI.createTransaction({
        company_id: txForm.company_id,
        shares: Number(txForm.shares),
        fee_percent: Number(txForm.fee_percent || 0),
        fee_fixed_shares: Number(txForm.fee_fixed_shares || 0),
      });
      toast.success("Transaction queued");
      await refreshUserProfile();
      loadCompanies();
      setTxForm({ ...initialTxForm, company_id: txForm.company_id });
    } catch (err) {
      console.error(err);
      if (err.response?.status === 402) {
        const detail = err.response?.data?.detail;
        const message = detail?.message || "Insufficient balance. Complete payment to continue.";
        toast.error(message);
        if (detail?.payment_url) {
          window.open(detail.payment_url, "_blank", "noopener,noreferrer");
        }
      } else {
        toast.error(err.response?.data?.detail || "Failed to queue transaction");
      }
    }
  };

  const handleRunBatch = async () => {
    try {
      setBatchLoading(true);
      const res = await tradingAPI.runBatch();
      setBatchResult(res.data);
      toast.success(`Processed ${res.data.processed} transactions`);
      loadCompanies();
    } catch (err) {
      console.error(err);
      toast.error(err.response?.data?.detail || "Batch failed");
    } finally {
      setBatchLoading(false);
    }
  };

  const handleDeleteCompany = async (companyId, name) => {
    if (!window.confirm(`Delete ${name}? This is only allowed if no outside holders exist.`)) {
      return;
    }
    try {
      await tradingAPI.deleteCompany(companyId);
      toast.success("Company deleted");
      loadCompanies();
    } catch (err) {
      console.error(err);
      toast.error(err.response?.data?.detail || "Delete failed");
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Trading Lab (Phase 1)</h1>
          <p className="text-sm text-gray-400">
            Sandbox panel to experiment with batch trading. Prices update every time you click "Run Batch".
          </p>
          <div className="mt-2">
            <a
              href="/exchange"
              className="inline-block px-3 py-1.5 rounded bg-indigo-700 hover:bg-indigo-600 text-white text-sm font-medium"
            >
              Go to Exchange (Phase 2)
            </a>
          </div>
        </div>

        <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <div>
            <p className="text-xs uppercase text-gray-400 tracking-wide">Available Balance</p>
            <p className="text-2xl font-semibold text-green-400">{user?.balance_bdt ?? 0} BDT</p>
          </div>
          <div className="text-sm text-gray-300">
            Buy orders debit immediately; sells credit instantly. If balance is low, the dummy gateway link will open to top up.
          </div>
        </div>

        <div className={`grid grid-cols-1 ${isAdmin ? "md:grid-cols-2" : ""} gap-6`}>
          {isAdmin && (
            <form onSubmit={handleCreateCompany} className="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">Create Company</h2>
                <button
                  type="submit"
                  className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 rounded text-sm font-medium"
                >
                  Create
                </button>
              </div>
              <label className="block text-sm">
                Name
                <input
                  className="mt-1 w-full rounded bg-gray-900 border border-gray-700 px-2 py-1"
                  value={companyForm.name}
                  onChange={(e) => setCompanyForm({ ...companyForm, name: e.target.value })}
                  required
                  maxLength={128}
                />
              </label>
              <label className="block text-sm">
                Total Shares
                <input
                  type="number"
                  className="mt-1 w-full rounded bg-gray-900 border border-gray-700 px-2 py-1"
                  value={companyForm.total_shares}
                  onChange={(e) => setCompanyForm({ ...companyForm, total_shares: e.target.value })}
                  min={1}
                />
              </label>
              <label className="block text-sm">
                Initial Price
                <input
                  type="number"
                  step="0.00000001"
                  className="mt-1 w-full rounded bg-gray-900 border border-gray-700 px-2 py-1"
                  value={companyForm.initial_price}
                  onChange={(e) => setCompanyForm({ ...companyForm, initial_price: e.target.value })}
                  min={0}
                />
              </label>
            </form>
          )}

          <form onSubmit={handleCreateTransaction} className="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Queue Transaction</h2>
              <button
                type="submit"
                className="px-3 py-1.5 bg-green-600 hover:bg-green-700 rounded text-sm font-medium"
              >
                Queue
              </button>
            </div>
            <label className="block text-sm">
              Company
              <select
                className="mt-1 w-full rounded bg-gray-900 border border-gray-700 px-2 py-1"
                value={txForm.company_id}
                onChange={(e) => setTxForm({ ...txForm, company_id: e.target.value })}
                required
              >
                <option value="">Select company</option>
                {companies.map((c) => (
                  <option key={c.company_id} value={c.company_id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              Shares (+buy / -sell)
              <input
                type="number"
                className="mt-1 w-full rounded bg-gray-900 border border-gray-700 px-2 py-1"
                value={txForm.shares}
                onChange={(e) => setTxForm({ ...txForm, shares: Number(e.target.value) })}
                required
              />
            </label>
            <label className="block text-sm">
              Fee % (0-1 range)
              <input
                type="number"
                step="0.0001"
                className="mt-1 w-full rounded bg-gray-900 border border-gray-700 px-2 py-1"
                value={txForm.fee_percent}
                onChange={(e) => setTxForm({ ...txForm, fee_percent: e.target.value })}
                min={0}
              />
            </label>
            <label className="block text-sm">
              Fee Fixed (shares)
              <input
                type="number"
                step="0.00000001"
                className="mt-1 w-full rounded bg-gray-900 border border-gray-700 px-2 py-1"
                value={txForm.fee_fixed_shares}
                onChange={(e) => setTxForm({ ...txForm, fee_fixed_shares: e.target.value })}
                min={0}
              />
            </label>
          </form>
        </div>

        <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Companies</h2>
            <button
              onClick={handleRunBatch}
              disabled={batchLoading}
              className="px-3 py-1.5 bg-purple-600 hover:bg-purple-700 rounded text-sm font-medium disabled:opacity-50"
            >
              {batchLoading ? "Running..." : "Run Batch Now"}
            </button>
          </div>
          {loading ? (
            <div className="text-gray-400 text-sm">Loading companies...</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-400 border-b border-gray-700">
                    <th className="py-2 pr-3">Name</th>
                    <th className="py-2 pr-3">Price</th>
                    <th className="py-2 pr-3">Sold</th>
                    <th className="py-2 pr-3">Total</th>
                    {isAdmin && <th className="py-2 pr-3 text-right">Actions</th>}
                  </tr>
                </thead>
                <tbody>
                  {companies.length === 0 && (
                    <tr>
                      <td className="py-3 text-gray-500" colSpan={4}>
                        No companies yet.
                      </td>
                    </tr>
                  )}
                    {companies.map((c) => (
                      <tr key={c.company_id} className="border-b border-gray-800">
                        <td className="py-2 pr-3 font-semibold">{c.name}</td>
                        <td className="py-2 pr-3">{Number(c.share_price).toFixed(4)}</td>
                        <td className="py-2 pr-3">{c.sold_shares}</td>
                        <td className="py-2 pr-3">{c.total_shares}</td>
                        {isAdmin && (
                          <td className="py-2 pr-3 text-right">
                            <button
                              type="button"
                              onClick={() => handleDeleteCompany(c.company_id, c.name)}
                              className="px-2 py-1 text-xs rounded bg-red-600 hover:bg-red-700"
                            >
                              Delete
                            </button>
                          </td>
                        )}
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}

          {batchResult && (
            <div className="mt-3 bg-gray-900 border border-gray-700 rounded p-3 text-sm text-gray-300 space-y-1">
              <div className="flex justify-between">
                <span>Processed transactions:</span>
                <span className="font-semibold">{batchResult.processed}</span>
              </div>
              <div className="flex justify-between">
                <span>Total Net BS:</span>
                <span className="font-semibold">{Number(batchResult.total_net_bs).toFixed(4)}</span>
              </div>
              <div>
                <p className="text-xs text-gray-400">Companies Updated:</p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-1">
                  {batchResult.companies_updated.map((c) => (
                    <div key={c.company_id} className="bg-gray-950 border border-gray-800 rounded p-2">
                      <div className="font-semibold">{c.name}</div>
                      <div className="text-xs text-gray-400">
                        Price: {Number(c.share_price).toFixed(4)} | Sold: {c.sold_shares}/{c.total_shares}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default TradingPage;

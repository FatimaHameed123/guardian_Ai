import { useCallback, useEffect, useState } from "react";
import {
  apiAddCase,
  apiDeleteCase,
  apiGetCaseDetails,
  apiGetCases,
  apiSaveCaseDetails,
  apiUpdateCase,
} from "../api";

const STATUSES = ["Open", "Closed", "Under Investigation"];
const LA_AREAS = [
  "Hollywood", "Central", "Newton", "Pacific", "Rampart", "77Th Street",
  "Van Nuys", "Wilshire", "Southwest", "Southeast", "Olympic", "Mission",
];

export default function Reports({ user }) {
  const [cases, setCases] = useState([]);
  const [selected, setSelected] = useState(null);
  const [details, setDetails] = useState({ full_story: "", suspect_info: "", evidence_notes: "" });
  const [form, setForm] = useState({
    case_title: "",
    crime_type: "",
    area: user?.area === "All" ? "Hollywood" : user?.area || "Hollywood",
    investigator_name: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const canManage = ["Admin", "SHO", "Inspector"].includes(user?.role);
  const isAdmin = user?.role === "Admin";

  const loadCases = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiGetCases();
      if (res.status === "ok") setCases(res.cases || []);
      else setError(res.message || "Could not load cases");
    } catch {
      setError("Backend unreachable. Start run_backend.py and log in as Admin/SHO/Inspector.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (canManage) loadCases();
    else setLoading(false);
  }, [canManage, loadCases]);

  const openDetails = async (c) => {
    setSelected(c);
    const res = await apiGetCaseDetails(c.case_id);
    if (res.status === "ok") {
      setDetails({
        full_story: res.full_story || "",
        suspect_info: res.suspect_info || "",
        evidence_notes: res.evidence_notes || "",
      });
    } else {
      setDetails({ full_story: "", suspect_info: "", evidence_notes: "" });
    }
  };

  const addCase = async () => {
    const res = await apiAddCase(form);
    if (res.status === "success") {
      setForm({ case_title: "", crime_type: "", area: form.area, investigator_name: "" });
      loadCases();
    } else setError(res.message || "Add failed");
  };

  const updateStatus = async (c, status) => {
    await apiUpdateCase(c.case_id, { status, investigator_name: c.investigator_name });
    loadCases();
  };

  const removeCase = async (id) => {
    if (!window.confirm("Delete this case and its encrypted details?")) return;
    await apiDeleteCase(id);
    setSelected(null);
    loadCases();
  };

  const saveDetails = async () => {
    if (!selected) return;
    const res = await apiSaveCaseDetails(selected.case_id, details);
    if (res.status !== "success") setError(res.message || "Save failed");
  };

  if (!canManage) {
    return (
      <div className="rounded-xl border border-slate-200 dark:border-border bg-white dark:bg-panel p-8 text-center">
        <p className="text-sm text-slate-600 dark:text-slate-400">
          Case management requires <b>Admin</b>, <b>SHO</b>, or <b>Inspector</b> role.
        </p>
        <p className="text-xs text-slate-400 mt-2">You are signed in as {user?.role}.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-slate-200 dark:border-border bg-white dark:bg-panel p-4 text-xs text-slate-500">
        Cases are stored in <b className="text-slate-700 dark:text-slate-300">CriminalInvestigation_Secured.db</b> (SQLite, project folder).
        Sensitive details use AES encryption.
      </div>

      {error && (
        <p className="text-sm text-red-500 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-2">{error}</p>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 rounded-xl border border-slate-200 dark:border-border bg-white dark:bg-panel overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-200 dark:border-border flex justify-between items-center">
            <h3 className="text-sm font-medium">Criminal cases ({cases.length})</h3>
            <button type="button" onClick={loadCases} className="text-xs text-accent">Refresh</button>
          </div>
          {loading ? (
            <p className="p-6 text-sm text-slate-400">Loading…</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-slate-400 border-b border-slate-200 dark:border-border">
                  <tr>
                    <th className="p-3">ID</th>
                    <th className="p-3">Title</th>
                    <th className="p-3">Type</th>
                    <th className="p-3">Area</th>
                    <th className="p-3">Status</th>
                    <th className="p-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {cases.map((c) => (
                    <tr
                      key={c.case_id}
                      className={`border-b border-slate-100 dark:border-border/50 hover:bg-slate-50 dark:hover:bg-white/5 ${
                        selected?.case_id === c.case_id ? "bg-slate-50 dark:bg-white/5" : ""
                      }`}
                    >
                      <td className="p-3">{c.case_id}</td>
                      <td className="p-3 font-medium">{c.case_title}</td>
                      <td className="p-3">{c.crime_type}</td>
                      <td className="p-3">{c.area}</td>
                      <td className="p-3">
                        <select
                          className="text-xs rounded border dark:border-border dark:bg-surface px-2 py-1"
                          value={c.status}
                          onChange={(e) => updateStatus(c, e.target.value)}
                        >
                          {STATUSES.map((s) => (
                            <option key={s} value={s}>{s}</option>
                          ))}
                        </select>
                      </td>
                      <td className="p-3 space-x-2">
                        <button type="button" className="text-xs text-accent" onClick={() => openDetails(c)}>
                          Details
                        </button>
                        {isAdmin && (
                          <button type="button" className="text-xs text-red-500" onClick={() => removeCase(c.case_id)}>
                            Delete
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {cases.length === 0 && (
                <p className="p-6 text-sm text-slate-400 text-center">No cases yet. Add one on the right.</p>
              )}
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 dark:border-border bg-white dark:bg-panel p-4">
            <h3 className="text-sm font-medium mb-3">Add case</h3>
            <div className="space-y-2">
              <input
                placeholder="Case title"
                className="w-full px-3 py-2 text-sm rounded-lg border dark:border-border dark:bg-surface"
                value={form.case_title}
                onChange={(e) => setForm({ ...form, case_title: e.target.value })}
              />
              <input
                placeholder="Crime type"
                className="w-full px-3 py-2 text-sm rounded-lg border dark:border-border dark:bg-surface"
                value={form.crime_type}
                onChange={(e) => setForm({ ...form, crime_type: e.target.value })}
              />
              <select
                className="w-full px-3 py-2 text-sm rounded-lg border dark:border-border dark:bg-surface"
                value={form.area}
                onChange={(e) => setForm({ ...form, area: e.target.value })}
                disabled={user?.role !== "Admin" && user?.area !== "All"}
              >
                {(user?.role === "Admin" ? LA_AREAS : [user?.area]).map((a) => (
                  <option key={a} value={a}>{a}</option>
                ))}
              </select>
              <input
                placeholder="Investigator name"
                className="w-full px-3 py-2 text-sm rounded-lg border dark:border-border dark:bg-surface"
                value={form.investigator_name}
                onChange={(e) => setForm({ ...form, investigator_name: e.target.value })}
              />
              <button
                type="button"
                onClick={addCase}
                className="w-full py-2 rounded-lg bg-slate-900 dark:bg-accent text-white text-sm"
              >
                Create case
              </button>
            </div>
          </div>

          {selected && (
            <div className="rounded-xl border border-slate-200 dark:border-border bg-white dark:bg-panel p-4">
              <h3 className="text-sm font-medium mb-1">Case #{selected.case_id} — encrypted details</h3>
              <p className="text-xs text-slate-400 mb-3">{selected.case_title}</p>
              <textarea
                placeholder="Full story"
                rows={3}
                className="w-full mb-2 px-3 py-2 text-sm rounded-lg border dark:border-border dark:bg-surface"
                value={details.full_story}
                onChange={(e) => setDetails({ ...details, full_story: e.target.value })}
              />
              <textarea
                placeholder="Suspect info"
                rows={2}
                className="w-full mb-2 px-3 py-2 text-sm rounded-lg border dark:border-border dark:bg-surface"
                value={details.suspect_info}
                onChange={(e) => setDetails({ ...details, suspect_info: e.target.value })}
              />
              <textarea
                placeholder="Evidence notes"
                rows={2}
                className="w-full mb-2 px-3 py-2 text-sm rounded-lg border dark:border-border dark:bg-surface"
                value={details.evidence_notes}
                onChange={(e) => setDetails({ ...details, evidence_notes: e.target.value })}
              />
              <button
                type="button"
                onClick={saveDetails}
                className="w-full py-2 rounded-lg border border-slate-200 dark:border-border text-sm"
              >
                Save encrypted details
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

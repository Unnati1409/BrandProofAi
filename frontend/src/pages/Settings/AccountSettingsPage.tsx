import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useWorkspace } from '../../context/WorkspaceContext';
import {
  Button,
  Input,
  PageHeader,
  Checkbox,
  Badge,
} from '../../components/ui';
import {
  Shield,
  Sparkles,
  AlertTriangle,
  CheckCircle2,
  Calendar,
  Building,
  User,
} from 'lucide-react';

export const AccountSettingsPage: React.FC = () => {
  const { user } = useAuth();
  const { activeWorkspace, updateWorkspaceSettings, isAdmin } = useWorkspace();

  // Workspace settings state
  const [workspaceName, setWorkspaceName] = useState(activeWorkspace?.name || '');
  const [retentionDays, setRetentionDays] = useState(activeWorkspace?.retention_days || 90);
  const [isSavingWs, setIsSavingWs] = useState(false);
  const [wsMessage, setWsMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // External AI Disclosure state
  const [disclosureAcknowledged, setDisclosureAcknowledged] = useState(false);
  const [isTogglingAi, setIsTogglingAi] = useState(false);
  const [aiMessage, setAiMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const handleSaveWorkspaceSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAdmin) return;

    setIsSavingWs(true);
    setWsMessage(null);

    try {
      await updateWorkspaceSettings({
        name: workspaceName.trim(),
        retention_days: Number(retentionDays),
      });
      setWsMessage({ type: 'success', text: 'Workspace settings saved successfully.' });
    } catch (err: any) {
      setWsMessage({ type: 'error', text: err.message || 'Failed to update workspace settings.' });
    } finally {
      setIsSavingWs(false);
    }
  };

  const handleToggleAi = async () => {
    if (!isAdmin) return;
    if (!activeWorkspace?.ai_enabled && !disclosureAcknowledged) {
      setAiMessage({
        type: 'error',
        text: 'You must review and check the External AI Disclosure acknowledgment before enabling Gemini processing.',
      });
      return;
    }

    setIsTogglingAi(true);
    setAiMessage(null);

    try {
      const willEnable = !activeWorkspace?.ai_enabled;
      await updateWorkspaceSettings({
        ai_enabled: willEnable,
        ai_disclosure_acknowledged: willEnable ? true : undefined,
      });

      setAiMessage({
        type: 'success',
        text: willEnable
          ? 'Google Gemini advisory checks have been activated for this workspace.'
          : 'Google Gemini processing has been disabled. The platform will operate in 100% deterministic rule mode.',
      });
    } catch (err: any) {
      setAiMessage({ type: 'error', text: err.message || 'Failed to update AI processing status.' });
    } finally {
      setIsTogglingAi(false);
    }
  };

  return (
    <div className="space-y-8 max-w-4xl">
      <PageHeader
        title="Settings & Governance"
        description="Configure profile information, workspace retention policy, and external AI disclosure controls."
      />

      {/* 1. User Profile Section */}
      <section className="bg-white border border-surface-200 rounded-lg shadow-subtle overflow-hidden">
        <div className="px-5 py-3 border-b border-surface-200 bg-surface-50 flex items-center gap-2">
          <User className="w-4 h-4 text-surface-600" />
          <h2 className="text-xs font-semibold text-surface-700 uppercase tracking-wider">
            Your Profile
          </h2>
        </div>

        <div className="p-5 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-surface-600 block mb-1">
                Full Name
              </label>
              <div className="text-sm font-medium text-surface-900 bg-surface-50 px-3 py-2 rounded border border-surface-200">
                {user?.full_name}
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-surface-600 block mb-1">
                Work Email
              </label>
              <div className="text-sm font-mono text-surface-900 bg-surface-50 px-3 py-2 rounded border border-surface-200">
                {user?.email}
              </div>
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-surface-600 block mb-1">
              User ID
            </label>
            <div className="text-2xs font-mono text-surface-500 bg-surface-50 px-3 py-1.5 rounded border border-surface-200 inline-block">
              {user?.id}
            </div>
          </div>
        </div>
      </section>

      {/* 2. Workspace Configuration Section */}
      <section className="bg-white border border-surface-200 rounded-lg shadow-subtle overflow-hidden">
        <div className="px-5 py-3 border-b border-surface-200 bg-surface-50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Building className="w-4 h-4 text-surface-600" />
            <h2 className="text-xs font-semibold text-surface-700 uppercase tracking-wider">
              Workspace Configuration
            </h2>
          </div>
          {!isAdmin && (
            <span className="text-2xs text-surface-500 italic">
              Admin role required to modify workspace configuration
            </span>
          )}
        </div>

        <form onSubmit={handleSaveWorkspaceSettings} className="p-5 space-y-4">
          {wsMessage && (
            <div
              className={`p-3 rounded text-xs flex items-center gap-2 ${
                wsMessage.type === 'success'
                  ? 'bg-emerald-50 border border-emerald-200 text-emerald-800'
                  : 'bg-red-50 border border-red-200 text-red-800'
              }`}
            >
              {wsMessage.type === 'success' ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
              )}
              <span>{wsMessage.text}</span>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="Workspace Name"
              value={workspaceName}
              onChange={(e) => setWorkspaceName(e.target.value)}
              disabled={!isAdmin}
              required
            />

            <div>
              <label className="text-xs font-semibold text-surface-700 select-none block mb-1.5">
                Workspace Slug
              </label>
              <div className="h-8.5 px-3 flex items-center text-sm font-mono bg-surface-100 border border-surface-300 rounded text-surface-600">
                /{activeWorkspace?.slug}
              </div>
            </div>
          </div>

          <div className="max-w-xs">
            <Input
              label="Audit & Content Retention Period (Days)"
              type="number"
              min={1}
              max={3650}
              value={retentionDays}
              onChange={(e) => setRetentionDays(Number(e.target.value))}
              disabled={!isAdmin}
              helperText="Days before archived content and audit logs undergo scheduled cleanup (1 - 3650)."
              required
            />
          </div>

          {isAdmin && (
            <div className="pt-2">
              <Button
                type="submit"
                variant="primary"
                size="sm"
                isLoading={isSavingWs}
              >
                Save Workspace Settings
              </Button>
            </div>
          )}
        </form>
      </section>

      {/* 3. External AI Disclosure & Controls (Google Gemini) */}
      <section className="bg-white border border-surface-200 rounded-lg shadow-subtle overflow-hidden">
        <div className="px-5 py-3 border-b border-surface-200 bg-surface-50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-surface-700" />
            <h2 className="text-xs font-semibold text-surface-700 uppercase tracking-wider">
              Google Gemini External AI Disclosure & Controls
            </h2>
          </div>
          {activeWorkspace?.ai_enabled ? (
            <Badge variant="success" size="sm">
              Active
            </Badge>
          ) : (
            <Badge variant="neutral" size="sm">
              Disabled
            </Badge>
          )}
        </div>

        <div className="p-5 space-y-5">
          {aiMessage && (
            <div
              className={`p-3 rounded text-xs flex items-center gap-2 ${
                aiMessage.type === 'success'
                  ? 'bg-emerald-50 border border-emerald-200 text-emerald-800'
                  : 'bg-red-50 border border-red-200 text-red-800'
              }`}
            >
              {aiMessage.type === 'success' ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
              )}
              <span>{aiMessage.text}</span>
            </div>
          )}

          {/* Core Principles & Fallback Transparency Box */}
          <div className="p-4 rounded-lg bg-surface-50 border border-surface-200 space-y-3 text-xs text-surface-700">
            <div className="font-semibold text-surface-900 flex items-center gap-1.5">
              <Shield className="w-4 h-4 text-surface-700" />
              Pre-Publication External AI Governance Principles
            </div>

            <ul className="space-y-2 text-surface-600 list-disc list-inside">
              <li>
                <strong className="text-surface-800">Approved Sources Only:</strong> Verification queries evaluate strictly against confirmed workspace brand guidelines and approved facts. External search or general model hallucinations are disabled.
              </li>
              <li>
                <strong className="text-surface-800">Data Privacy:</strong> Content sent to Google Gemini is ephemeral and encrypted in transit. Content is <em>never used to train</em> Google foundation models.
              </li>
              <li>
                <strong className="text-surface-800">Strict Human Decision-Making:</strong> The AI has zero approval authority in the data model. All AI findings are labelled <code>AI-assisted (Advisory)</code> and require human sign-off.
              </li>
              <li>
                <strong className="text-surface-800">Deterministic Fallback:</strong> If disabled, the system executes 100% deterministic checks (banned terms, exact spelling, required wording, expired facts, and WCAG contrast). Only advisory semantic claim and tone checks are bypassed.
              </li>
            </ul>

            {activeWorkspace?.ai_enabled_at && (
              <div className="pt-2 border-t border-surface-200 text-2xs text-surface-500 font-mono flex items-center gap-1.5">
                <Calendar className="w-3 h-3" />
                Activated on: {new Date(activeWorkspace.ai_enabled_at).toLocaleString()}
              </div>
            )}
          </div>

          {/* Admin Opt-in & Acknowledgment */}
          {isAdmin ? (
            <div className="space-y-4 pt-2">
              {!activeWorkspace?.ai_enabled && (
                <div className="p-3 rounded border border-surface-200 bg-white">
                  <div className="flex items-start gap-2.5">
                    <Checkbox
                      checked={disclosureAcknowledged}
                      onChange={(e) => setDisclosureAcknowledged(e.target.checked)}
                      className="mt-0.5"
                      id="disclosure-ack"
                    />
                    <label
                      htmlFor="disclosure-ack"
                      className="text-xs text-surface-800 font-medium cursor-pointer"
                    >
                      I have reviewed the Google Gemini External AI Disclosure on behalf of {activeWorkspace?.name}. I understand what data is transmitted, confirm that human approval remains mandatory, and authorize advisory AI evaluation.
                    </label>
                  </div>
                </div>
              )}

              <div className="flex items-center justify-between p-3 rounded-lg border border-surface-200 bg-surface-50">
                <div>
                  <div className="text-xs font-bold text-surface-900">
                    Google Gemini Pipeline Processing
                  </div>
                  <div className="text-2xs text-surface-500">
                    {activeWorkspace?.ai_enabled
                      ? 'Advisory claim checking and tone analysis are active.'
                      : 'Disabled. Workspace is operating in deterministic-only mode.'}
                  </div>
                </div>

                <Button
                  variant={activeWorkspace?.ai_enabled ? 'destructive' : 'primary'}
                  size="sm"
                  onClick={handleToggleAi}
                  isLoading={isTogglingAi}
                >
                  {activeWorkspace?.ai_enabled ? 'Disable Gemini AI' : 'Enable Gemini AI'}
                </Button>
              </div>
            </div>
          ) : (
            <div className="text-xs text-surface-500 italic p-3 rounded bg-surface-50 border border-surface-200">
              Only workspace Administrators can modify External AI processing status.
            </div>
          )}
        </div>
      </section>
    </div>
  );
};
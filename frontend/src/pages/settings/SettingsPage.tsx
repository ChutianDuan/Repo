import { PageTitle } from "../../components/common/PageTitle";
import { SectionCard } from "../../components/common/SectionCard";

interface SettingsPageProps {
  apiBaseUrl: string;
  userId: string;
  topK: number;
  ragEnabled: boolean;
  streamingEnabled: boolean;
  chunkSize: string;
  chunkOverlap: string;
  modelName: string;
  onApiBaseUrlChange: (value: string) => void;
  onUserIdChange: (value: string) => void;
  onTopKChange: (value: number) => void;
  onRagEnabledChange: (value: boolean) => void;
  onStreamingEnabledChange: (value: boolean) => void;
  onChunkSizeChange: (value: string) => void;
  onChunkOverlapChange: (value: string) => void;
  onModelNameChange: (value: string) => void;
}

export function SettingsPage({
  apiBaseUrl,
  userId,
  topK,
  ragEnabled,
  streamingEnabled,
  chunkSize,
  chunkOverlap,
  modelName,
  onApiBaseUrlChange,
  onUserIdChange,
  onTopKChange,
  onRagEnabledChange,
  onStreamingEnabledChange,
  onChunkSizeChange,
  onChunkOverlapChange,
  onModelNameChange,
}: SettingsPageProps) {
  return (
    <div className="settings-page page-stack">
      <PageTitle
        eyebrow="Configuration"
        title="Settings"
        description="集中配置网关地址、检索参数、chunk 策略和模型显示名称。"
      />

      <SectionCard title="Connection" description="留空 API Base URL 时走 Vite 代理 `/health` 和 `/v1`。">
        <div className="settings-grid">
          <label className="field">
            <span>Gateway Base URL</span>
            <input
              value={apiBaseUrl}
              onChange={(event) => onApiBaseUrlChange(event.target.value)}
              placeholder="http://server-ip:8080"
            />
          </label>
          <label className="field">
            <span>Current User ID</span>
            <input value={userId} onChange={(event) => onUserIdChange(event.target.value)} />
          </label>
          <label className="field">
            <span>Model Name</span>
            <input value={modelName} onChange={(event) => onModelNameChange(event.target.value)} />
          </label>
        </div>
      </SectionCard>

      <SectionCard title="Retrieval" description="这些配置会影响前端提交参数；后端持久配置接口接入后可改成保存动作。">
        <div className="settings-grid">
          <label className="field">
            <span>top_k</span>
            <input
              type="number"
              min={1}
              max={20}
              value={topK}
              onChange={(event) => onTopKChange(Number(event.target.value))}
            />
          </label>
          <label className="field">
            <span>chunk_size</span>
            <input value={chunkSize} onChange={(event) => onChunkSizeChange(event.target.value)} />
          </label>
          <label className="field">
            <span>overlap</span>
            <input value={chunkOverlap} onChange={(event) => onChunkOverlapChange(event.target.value)} />
          </label>
        </div>
        <div className="settings-toggles">
          <label className="toggle-control">
            <input
              type="checkbox"
              checked={ragEnabled}
              onChange={(event) => onRagEnabledChange(event.target.checked)}
            />
            <span>RAG retrieval enabled</span>
          </label>
          <label className="toggle-control">
            <input
              type="checkbox"
              checked={streamingEnabled}
              onChange={(event) => onStreamingEnabledChange(event.target.checked)}
            />
            <span>Streaming enabled</span>
          </label>
        </div>
      </SectionCard>
    </div>
  );
}

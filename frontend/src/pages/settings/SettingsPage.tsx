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
        eyebrow="项目配置"
        title="配置"
        description="保持默认即可使用；需要时再调整连接地址、检索数量和流式输出。"
      />

      <SectionCard title="连接" description="网关地址、用户和模型显示名称。">
        <div className="settings-grid">
          <label className="field">
            <span>网关地址</span>
            <input
              value={apiBaseUrl}
              onChange={(event) => onApiBaseUrlChange(event.target.value)}
              placeholder="http://server-ip:8080"
            />
          </label>
          <label className="field">
            <span>当前用户 ID</span>
            <input value={userId} onChange={(event) => onUserIdChange(event.target.value)} />
          </label>
          <label className="field">
            <span>模型名称</span>
            <input value={modelName} onChange={(event) => onModelNameChange(event.target.value)} />
          </label>
        </div>
      </SectionCard>

      <SectionCard title="检索" description="这些参数会随下一次提问提交。">
        <div className="settings-grid">
          <label className="field">
            <span>引用数</span>
            <input
              type="number"
              min={1}
              max={20}
              value={topK}
              onChange={(event) => onTopKChange(Number(event.target.value))}
            />
          </label>
          <label className="field">
            <span>切片大小</span>
            <input value={chunkSize} onChange={(event) => onChunkSizeChange(event.target.value)} />
          </label>
          <label className="field">
            <span>重叠</span>
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
            <span>使用知识库检索</span>
          </label>
          <label className="toggle-control">
            <input
              type="checkbox"
              checked={streamingEnabled}
              onChange={(event) => onStreamingEnabledChange(event.target.checked)}
            />
            <span>流式回答</span>
          </label>
        </div>
      </SectionCard>
    </div>
  );
}

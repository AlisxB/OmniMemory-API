'use client';
import { useState } from 'react';
import useSWR from 'swr';
import { fetchApi } from '@/lib/api';
import GlassCard from '@/components/GlassCard';

export default function WebhooksPage() {
  const [tenantId, setTenantId] = useState('');
  
  const { data: tenantsData } = useSWR('/admin/tenants', fetchApi);
  const tenants = tenantsData?.tenants || [];

  const { data: webhooks, error, isLoading } = useSWR(
    tenantId ? `/tenants/${tenantId}/webhooks` : null, 
    fetchApi
  );

  return (
    <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Gerenciador de Webhooks</h1>
          <p className="text-white/60 mt-1">Configure N8N/Integrações via Webhooks.</p>
        </div>
        <button className="bg-omni-neon text-black font-semibold px-6 py-2 rounded-full hover:shadow-[0_0_20px_rgba(0,245,255,0.4)] transition-all">
          + Novo Webhook
        </button>
      </header>

      <GlassCard>
        <div className="flex justify-between items-center mb-6">
          <select 
            value={tenantId}
            onChange={(e) => setTenantId(e.target.value)}
            className="w-80 bg-white/5 border border-white/10 rounded-lg py-2 pl-4 pr-10 text-white appearance-none focus:outline-none focus:ring-2 focus:ring-omni-neon/50 focus:border-omni-neon transition-all"
          >
            <option value="" className="bg-black">Selecione o Tenant para ver Webhooks</option>
            {tenants.map((t: any) => (
              <option key={t.tenant_id} value={t.tenant_id} className="bg-black">{t.name}</option>
            ))}
          </select>
        </div>

        {tenantId && isLoading && <div className="text-omni-neon animate-pulse text-sm">Validando DNS...</div>}
        {error && <div className="text-omni-accent">Erro: {error.message}</div>}

        {!isLoading && webhooks && (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-white/10 text-white/50 text-sm uppercase tracking-wider">
                  <th className="pb-4 pt-2 font-medium">URL de Callback / Trigger</th>
                  <th className="pb-4 pt-2 font-medium">Status</th>
                  <th className="pb-4 pt-2 font-medium">Segredo de Segurança</th>
                  <th className="pb-4 pt-2 font-medium text-right">Ações</th>
                </tr>
              </thead>
              <tbody>
                {webhooks.webhooks?.map((wh: any) => (
                  <tr key={wh.id} className="border-b border-white/5 hover:bg-white/[0.02] transition-colors group">
                    <td className="py-4">
                      <div className="font-medium text-white group-hover:text-omni-neon truncate max-w-[300px]">{wh.url}</div>
                      <div className="text-xs text-omni-purple mt-1 flex gap-1">
                        {wh.events.map((e: string) => <span key={e} className="border border-omni-purple/30 bg-omni-purple/10 px-1 rounded">{e}</span>)}
                      </div>
                    </td>
                    <td className="py-4">
                      {wh.is_active ? 
                        <span className="text-omni-success bg-omni-success/10 px-2 py-1 rounded text-xs border border-omni-success/20 animate-pulse">Escutando</span> : 
                        <span className="text-omni-accent bg-omni-accent/10 px-2 py-1 rounded text-xs border border-omni-accent/20">Desativado</span>
                      }
                    </td>
                    <td className="py-4 text-white/50 text-sm font-mono truncate max-w-[200px]">
                      {wh.secret.substring(0, 10)}********************
                    </td>
                    <td className="py-4 text-right">
                      <button className="text-xs border border-omni-accent/50 text-omni-accent rounded px-3 py-1 hover:bg-omni-accent hover:text-black transition-colors">Remover</button>
                    </td>
                  </tr>
                ))}
                {webhooks.webhooks?.length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-8 text-center text-white/40">Nenhuma rota (n8n) conectada.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </GlassCard>
    </div>
  );
}

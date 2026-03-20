'use client';
import { useState } from 'react';
import useSWR from 'swr';
import { fetchApi } from '@/lib/api';
import { 
  Search, BrainCircuit, User, Database, 
  Sparkles, Layers, ArrowRight, History,
  Info, Cpu
} from 'lucide-react';

export default function MemoryExplorerPage() {
  const [tenantId, setTenantId] = useState('');
  const [userId, setUserId] = useState('');
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [feedback, setFeedback] = useState<{message: string, type: 'success' | 'error'} | null>(null);

  // Busca lista de tenants para o select
  const { data: tenantsData } = useSWR('/admin/api/tenants', fetchApi);
  const tenants = tenantsData?.data || [];

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tenantId || !userId || !query) return;
    
    setIsSearching(true);
    setFeedback(null);
    try {
      const qs = new URLSearchParams({
        tenant_id: tenantId,
        query: query,
        limit: '10'
      });
      const res = await fetchApi(`/v1/context/search?${qs.toString()}`);
      
      const memories = res.data?.memories?.map((m: any) => ({ ...m, type: 'memory', display: m.value })) || [];
      const messages = res.data?.messages?.map((m: any) => ({ ...m, type: 'message', display: m.content })) || [];
      
      setSearchResults([...memories, ...messages]);
      setFeedback({ message: 'Sonda neural concluída com sucesso.', type: 'success' });
    } catch (err: any) {
      console.error(err);
      setFeedback({ message: 'Erro na busca semântica: ' + err.message, type: 'error' });
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="container-fluid p-0 animate-in fade-in duration-700 pb-5">
      
      {/* HEADER */}
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h1 className="dash-title mb-0">EXPLORADOR DE MEMÓRIA</h1>
          <div className="dash-subtitle mt-1">Busca Semântica & Auditoria de Vetores (RAG).</div>
        </div>
        <div className="glass-panel py-1 px-3 d-flex align-items-center gap-2" style={{height: 40, border: '1px solid rgba(179, 0, 255, 0.3) !important'}}>
          <Cpu className="text-omni-purple animate-pulse" size={16} />
          <span className="text-omni-label m-0" style={{color: '#b300ff', fontSize: '0.6rem'}}>Neural Active</span>
        </div>
      </div>

      {feedback && (
        <div className={`alert ${feedback.type === 'success' ? 'alert-success bg-success bg-opacity-10 border-success' : 'alert-danger bg-danger bg-opacity-10 border-danger'} text-white mb-4 animate-in slide-in-from-top duration-300`} style={{fontSize: '0.8rem', borderRadius: '8px'}}>
          {feedback.message}
        </div>
      )}

      <div className="row">
        {/* PAINEL DE PARÂMETROS */}
        <div className="col-lg-4">
          <div className="glass-panel mb-4">
            <h6 className="fw-semibold text-white mb-4 text-uppercase" style={{fontSize: '0.8rem', letterSpacing: '0.05em'}}>Parâmetros de Busca</h6>
            
            <form onSubmit={handleSearch}>
              <div className="mb-3">
                <label className="kpi-label mb-1">Tenant (Base)</label>
                <select 
                  value={tenantId}
                  onChange={(e) => setTenantId(e.target.value)}
                  className="form-control bg-transparent border-white-10 text-white py-2"
                  style={{borderRadius: '8px', appearance: 'none'}}
                >
                  <option value="" className="bg-black">Selecione o Cliente</option>
                  {tenants.map((t: any) => (
                    <option key={t.id} value={t.id} className="bg-black">{t.name}</option>
                  ))}
                </select>
              </div>

              <div className="mb-3">
                <label className="kpi-label mb-1">ID do Usuário (External)</label>
                <input 
                  type="text" 
                  value={userId}
                  onChange={(e) => setUserId(e.target.value)}
                  placeholder="Ex: 558599..."
                  className="form-control bg-transparent border-white-10 text-white py-2 font-mono"
                  style={{borderRadius: '8px', fontSize: '0.85rem'}}
                />
              </div>

              <div className="mb-4">
                <label className="kpi-label mb-1">Busca Neural (Pergunta)</label>
                <textarea 
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  rows={4}
                  placeholder="O que o bot sabe sobre..."
                  className="form-control bg-transparent border-white-10 text-white py-2"
                  style={{borderRadius: '8px', fontSize: '0.85rem', resize: 'none'}}
                />
              </div>

              <button 
                type="submit" 
                disabled={isSearching || !tenantId || !userId || !query}
                className="btn w-100 py-2 font-bold"
                style={{backgroundColor: '#00f0ff', color: '#000', borderRadius: '8px', border: 'none'}}
              >
                {isSearching ? 'PROCESSANDO...' : 'SONDAR REDE NEURAL'}
              </button>
            </form>
          </div>

          <div className="glass-panel py-3 px-3 d-flex gap-3 opacity-75">
            <Info size={16} className="text-omni-neon mt-1" />
            <p className="mb-0" style={{fontSize: '0.7rem', color: 'rgba(255,255,255,0.5)', lineHeight: 1.4}}>
              A busca utiliza **Embeddings de Vetores** para encontrar memórias por similaridade semântica.
            </p>
          </div>
        </div>

        {/* RESULTADOS */}
        <div className="col-lg-8">
          <div className="glass-panel h-100 min-h-[500px]">
            <div className="d-flex justify-content-between align-items-center mb-4">
              <h6 className="fw-semibold text-white mb-0 text-uppercase" style={{fontSize: '0.85rem', letterSpacing: '0.05em'}}>Mapeamento de Fatos Detectados</h6>
              <div className="text-white-50 font-mono" style={{fontSize: '0.7rem'}}>Resultados: {searchResults.length}</div>
            </div>

            {searchResults.length === 0 && !isSearching && (
              <div className="d-flex flex-column align-items-center justify-content-center py-5 opacity-25">
                <BrainCircuit size={48} className="mb-3" />
                <div className="text-center">
                  <h6 className="mb-1">Vácuo de Memória</h6>
                  <p className="small mb-0">Preencha os filtros para sondar o contexto.</p>
                </div>
              </div>
            )}

            {isSearching && (
              <div className="row g-3">
                {[1,2,4].map(i => (
                  <div key={i} className="col-md-6 col-xl-4">
                    <div className="glass-panel border-white-5 animate-pulse" style={{height: '140px', background: 'rgba(255,255,255,0.03) !important'}}></div>
                  </div>
                ))}
              </div>
            )}

            <div className="row g-3">
              {searchResults.map((mem: any, i: number) => (
                <div key={i} className="col-md-6 col-xl-4">
                  <div className="glass-panel p-3 border-white-10 h-100 d-flex flex-column justify-content-between position-relative" style={{background: 'rgba(255,255,255,0.02) !important'}}>
                    <div className="position-absolute top-0 end-0 p-2">
                       <span className="badge border border-omni-purple border-opacity-20 text-omni-purple" style={{fontSize: '0.6rem', background: 'rgba(179,0,255,0.05)'}}>
                         SEMANTIC MATCH
                       </span>
                    </div>
                    
                    <div className="mb-3">
                      <div className="kpi-label mb-2" style={{fontSize: '0.6rem', color: mem.type === 'memory' ? '#b300ff' : '#00f0ff'}}>
                        {mem.type === 'memory' ? 'Fato Neural (Memória)' : 'Mensagem Histórica'}
                      </div>
                      <p className="text-white-50 mb-0" style={{fontSize: '0.75rem', lineHeight: 1.5}}>{mem.display}</p>
                    </div>

                    <div className="pt-2 border-top border-white-5 d-flex justify-content-between align-items-center">
                      <code style={{fontSize: '0.6rem', color: 'rgba(255,255,255,0.2)'}}>
                        {mem.type === 'memory' ? `KEY:${mem.key.slice(0,8)}` : `ROLE:${mem.role}`}
                      </code>
                      <ArrowRight size={10} className="text-white-50" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

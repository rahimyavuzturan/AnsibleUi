import { useQuery } from '@tanstack/react-query';
import { getHealth } from '../lib/api';

/**
 * Uygulama kabugu.
 *
 * Faz 0 iskeleti: yalnizca API baglantisini dogrular.
 * Gercek yonlendirme ve duzen WP-40 ile gelecek.
 */
export function App() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
  });

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-950 text-slate-100">
      <h1 className="text-3xl font-semibold tracking-tight">AnsibleUI</h1>
      <p className="text-slate-400">Ansible deposu icin gorsel otomasyon platformu</p>
      <div className="rounded-md border border-slate-800 px-4 py-2 text-sm">
        {isLoading && <span className="text-slate-400">API kontrol ediliyor...</span>}
        {isError && <span className="text-red-400">API'ye ulasilamadi</span>}
        {data && <span className="text-emerald-400">API baglantisi hazir (v{data.version})</span>}
      </div>
    </main>
  );
}

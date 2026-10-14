// UI strings. English is primary; `ja` is a partial table ready for localization (falls back to English).

const en = {
  title: 'XENO ZIRAN SIMULATOR',
  subtitle: 'Operational-shape simulation · interactive runtime (local server)',
  subtitle_native: 'Operational-shape simulation · interactive runtime (on this device)',
  footer: 'Explore possible transitions under intervention.',
  research_results: 'Research Results',
  footer_static: 'This public deployment presents experimental results; it does not make real-world predictive claims.',
  run: 'Run', pause: 'Pause', step: 'Step', reset: 'Reset', speed: 'speed', rewind: 'rewind', checkpoint: 'checkpoint',
  save: 'Save', load: 'Load', export: 'Export', scenario: 'scenario',
  run_pause: 'Run or pause the simulation', reset_hint: 'Rebuild the scenario from its seed',
  step_counter: 'current step', sim_rate: 'simulation steps per second', render_rate: 'rendering frames per second',
  ws_rate: 'WebSocket delta frames per second and bandwidth', connections: 'live connections',
  view_network: 'Network', view_shape: 'Shape Space', view_address: 'Address Space', view_map: 'World Map',
  view_globe: '3D Globe', view_timeline: 'Timeline', view_compare: 'Compare', view_practice: 'Philosophical Practice',
  view_reduction: 'Runtime Reduction', view_reason: 'Reason Non-Redundancy', view_phases: 'Phase Timeline',
  view_primitives: 'Primitive Inspector',
  view_res_matrix: 'Resolution Matrix', view_res_hidden: 'Hidden Difference', view_res_penetration: 'Scale Penetration',
  view_res_structure: 'Reasoning Structure Inspector', view_res_disconnection: 'Disconnection Study',
  view_res_compression: 'Long-Run Compression', view_overview: 'Overview',
  view_hpo: 'Heterogeneous Philosophical Operations',
  view_laboratory: '3D Laboratory',
};

type Key = keyof typeof en;

const ja: Partial<Record<Key, string>> = {
  subtitle: '操作的形態シミュレーション · 対話型ランタイム（ローカルサーバ）',
  subtitle_native: '操作的形態シミュレーション · 対話型ランタイム（この端末上）',
  footer: '介入のもとで可能な遷移を探索してください。',
  research_results: '研究結果',
  footer_static: 'この公開版は実験結果を示すもので、現実世界についての予測的主張を行うものではありません。',
  run: '実行', pause: '一時停止', step: '1ステップ', reset: 'リセット',
  view_network: 'ネットワーク', view_shape: '形態空間', view_address: 'アドレス空間', view_map: '世界地図',
  view_globe: '3D地球儀', view_timeline: 'タイムライン', view_compare: '比較', view_practice: '哲学的実践',
};

const tables: Record<string, Partial<Record<Key, string>>> = { en, ja };
let lang = new URLSearchParams(location.search).get('lang') ?? 'en';

export function setLang(l: string) { lang = l; }
export function t(k: Key): string { return tables[lang]?.[k] ?? en[k]; }

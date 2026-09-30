// UI strings. English is primary; `ja` is a partial table ready for localization (falls back to English).

const en = {
  title: 'Xeno / Ziran Philosophical Runtime',
  subtitle: 'Operational Shape Simulation Platform',
  footer: 'Not a prediction. Explore possible transitions.',
  run: 'Run', pause: 'Pause', step: 'Step', reset: 'Reset', speed: 'speed', rewind: 'rewind', checkpoint: 'checkpoint',
  save: 'Save', load: 'Load', export: 'Export', scenario: 'scenario',
  run_pause: 'Run or pause the simulation', reset_hint: 'Rebuild the scenario from its seed',
  step_counter: 'current step', sim_rate: 'simulation steps per second', render_rate: 'rendering frames per second',
  ws_rate: 'WebSocket delta frames per second and bandwidth', connections: 'live connections',
  view_network: 'Network', view_shape: 'Shape Space', view_address: 'Address Space', view_map: 'World Map',
  view_globe: '3D Globe', view_timeline: 'Timeline', view_compare: 'Compare', view_practice: 'Philosophical Practice',
  view_reduction: 'Runtime Reduction', view_reason: 'Reason Non-Redundancy', view_phases: 'Phase Timeline',
  view_primitives: 'Primitive Inspector',
};

type Key = keyof typeof en;

const ja: Partial<Record<Key, string>> = {
  subtitle: '操作的形態シミュレーション・プラットフォーム',
  footer: '予測ではありません。可能な遷移を探索してください。',
  run: '実行', pause: '一時停止', step: '1ステップ', reset: 'リセット',
  view_network: 'ネットワーク', view_shape: '形態空間', view_address: 'アドレス空間', view_map: '世界地図',
  view_globe: '3D地球儀', view_timeline: 'タイムライン', view_compare: '比較', view_practice: '哲学的実践',
};

const tables: Record<string, Partial<Record<Key, string>>> = { en, ja };
let lang = new URLSearchParams(location.search).get('lang') ?? 'en';

export function setLang(l: string) { lang = l; }
export function t(k: Key): string { return tables[lang]?.[k] ?? en[k]; }

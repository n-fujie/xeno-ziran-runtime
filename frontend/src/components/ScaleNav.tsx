import { useSim } from '../store/sim';
import { SCALE_NAMES } from '../views/GraphView';

export default function ScaleNav({ hoverAddress }: { hoverAddress?: string | null }) {
  const scale = useSim((s) => s.scale);
  const requestScale = useSim((s) => s.requestScale);
  const info = useSim((s) => s.info);
  const counts = info?.clusters_per_level ?? [];
  return (
    <div className="scalenav">
      {SCALE_NAMES.map((name, i) => (
        <span key={name} className="scale-step">
          {i > 0 && <span className="arrow">→</span>}
          <button className={i === scale ? 'on' : ''} onClick={() => requestScale(i)}
            title={i < 4 ? `${counts[i] ?? '?'} clusters` : i === 4 ? 'configurations in viewport' : 'configurations + all relations'}>
            {name}
          </button>
        </span>
      ))}
      {hoverAddress && <span className="mono dim addr">address {hoverAddress}</span>}
    </div>
  );
}

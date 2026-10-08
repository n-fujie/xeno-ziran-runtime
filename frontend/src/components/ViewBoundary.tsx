// Contains a failure of one view (for example a lazily loaded chunk that cannot be fetched after a redeploy) so the
// header, navigation and the other views keep working.
import { Component, type ReactNode } from 'react';

// `view` resets a failure when another view opens, without remounting the children on every view change.
export default class ViewBoundary extends Component<{ view: string; children: ReactNode }, { error: string | null }> {
  state = { error: null as string | null };

  static getDerivedStateFromError(e: unknown) {
    return { error: String(e) };
  }

  componentDidUpdate(prev: { view: string }) {
    if (prev.view !== this.props.view && this.state.error) this.setState({ error: null });
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="panel-view" role="alert">
        <p className="warn">This view could not be loaded.</p>
        <p className="small dim mono">{this.state.error}</p>
        <button onClick={() => location.reload()}>Reload</button>
      </div>
    );
  }
}
